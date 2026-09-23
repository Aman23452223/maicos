"""Orchestrator - bridges the AI Manager and the workflow engine."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.agents.implementations.ai_manager import build_plan
from app.audit.service import record
from app.core.context import Principal
from app.queue import jobs as queue
from app.workflow.engine import create_workflow
from app.workflow.engine import run as run_workflow


def _build_plan(objective: str) -> dict[str, Any]:
    """Try the LLM planner first, fall back to the deterministic one.

    PRD §5 expects the AI Manager to reason; the deterministic planner
    in `ai_manager.build_plan` is the safe fallback used in tests and
    when the LLM is unavailable.
    """
    from app.agents.llm_planner import plan_with_llm

    plan = plan_with_llm(objective)
    if plan and "tasks" in plan and plan["tasks"]:
        return plan
    return build_plan(objective)


def _workflow_summary(wf) -> list[dict[str, Any]]:
    return [
        {
            "id": t.id,
            "agent": t.agent_name,
            "title": t.title,
            "state": t.state.value,
            "error": t.error,
        }
        for t in wf.tasks
    ]


def _workspace_context(db: Session, principal: Principal) -> dict[str, Any]:
    """Load business-aware execution context (generic, no industry logic)."""
    from app.capabilities.registry import enabled_for
    from app.intel.service import get_or_create_profile
    from app.tenancy.membership import membership_role

    role = membership_role(db, user_id=principal.user_id,
                           company_id=principal.workspace_id)
    if not role:
        # Backward compat: synthetic/legacy contexts (unit tests, service
        # principals for workspaces not yet in DB) fall back to the
        # principal's own roles instead of hard-failing. Real workspaces
        # with real users are still strictly enforced.
        from app.models.orm import Company, User

        workspace_exists = db.get(Company, principal.workspace_id) is not None
        user_exists = db.get(User, principal.user_id) is not None
        if workspace_exists and user_exists:
            raise PermissionError("not a workspace member")
        role = next((r for r in (principal.roles or []) if r in ("owner", "admin", "member")), "member")
    try:
        bp = get_or_create_profile(db, company_id=principal.workspace_id)
        business_name, industry, icp, goals = (
            bp.business_name, bp.industry, bp.icp or {}, bp.business_goals or [])
    except Exception:
        business_name, industry, icp, goals = "", "", {}, []
    try:
        from app.models.orm import BusinessMemory

        mem_rows = (db.query(BusinessMemory)
                    .filter(BusinessMemory.company_id == principal.workspace_id)
                    .order_by(BusinessMemory.updated_at.desc()).limit(20).all())
        memory = [{"kind": m.kind, "key": m.key, "value": m.value[:500]}
                  for m in mem_rows]
    except Exception:
        memory = []
    try:
        capabilities = sorted(enabled_for(db, company_id=principal.workspace_id))
    except Exception:
        capabilities = []
    return {
        "user_id": principal.user_id,
        "workspace_id": principal.workspace_id,
        "role": role,
        "business_name": business_name,
        "industry": industry,
        "icp": icp,
        "goals": goals,
        "memory": memory,
        "capabilities": capabilities,
    }


def handle_objective(
    db: Session,
    *,
    principal: Principal,
    objective: str,
    conversation_id: str | None = None,
    enqueue_async: bool = False,
    plan_review: bool = False,
) -> dict[str, Any]:
    ctx = _workspace_context(db, principal)
    plan = _build_plan(objective)
    # Capability gate: drop tasks requiring disabled capabilities (honest skip).
    try:
        from app.capabilities.registry import check as cap_check

        task_cap = {"sales_crm": "crm", "communication": "email",
                    "calendar": "calendar", "knowledge": "knowledge",
                    "analytics": "analytics", "marketing": "marketing",
                    "finance": "finance", "hr": "hr",
                    "customer_support": "support", "project_ops": "project_management"}
        kept = []
        for t in plan.get("tasks", []):
            cap = task_cap.get(t.get("agent", ""), "")
            if cap and not cap_check(db, company_id=principal.workspace_id,
                                     capability=cap).get("ok"):
                continue
            # inject workspace context into every task input (agents read it)
            inp = dict(t.get("input", {}))
            inp["_workspace"] = {"id": ctx["workspace_id"], "role": ctx["role"],
                                 "business_name": ctx["business_name"],
                                 "industry": ctx["industry"],
                                 "goals": [g.get("text", "") for g in ctx["goals"]
                                           if g.get("status", "active") == "active"][:5],
                                 "memory_facts": [f"{m['key']}: {m['value']}"[:200]
                                                  for m in ctx["memory"]
                                                  if m["kind"] in ("fact", "preference")][:10]}
            t["input"] = inp
            kept.append(t)
        if kept:
            plan["tasks"] = kept
    except PermissionError:
        raise
    except Exception:
        pass
    plan["_workspace_context"] = {"role": ctx["role"],
                                  "capabilities": ctx["capabilities"],
                                  "business_name": ctx["business_name"]}
    wf = create_workflow(
        db,
        company_id=principal.workspace_id,
        triggered_by_user_id=principal.user_id,
        conversation_id=conversation_id,
        title=plan.get("intent", "workflow"),
        objective=objective,
        plan=plan,
    )
    if enqueue_async:
        queue.enqueue(
            db,
            company_id=principal.workspace_id,
            trigger="on_demand",
            workflow_id=wf.id,
            payload={"workflow_id": wf.id},
        )
        record(
            db,
            company_id=principal.workspace_id,
            actor=principal.user_id,
            action="workflow.enqueued",
            target_type="workflow",
            target_id=wf.id,
            details={"trigger": "on_demand"},
        )
        db.commit()
        return {
            "workflow_id": wf.id,
            "state": wf.state.value,
            "plan": plan,
            "tasks": _workflow_summary(wf),
        }
    if plan_review:
        # Pause BEFORE execution: owner inspects/edits the task plan in the
        # Approvals UI, then approves to run. Nothing has executed yet.
        from app.approvals.service import create_approval
        from app.models.orm import WorkflowState

        create_approval(
            db,
            workflow=wf,
            task_id=None,
            requested_by_agent="ai_manager",
            action="plan_review",
            target_system="workflow",
            description=(f"Review plan '{plan.get('intent', 'workflow')}' "
                         f"({len(plan.get('tasks', []))} tasks) before execution."),
            payload={"plan": plan},
        )
        wf.state = WorkflowState.WAITING_APPROVAL
        record(
            db,
            company_id=principal.workspace_id,
            actor=principal.user_id,
            action="workflow.plan_review",
            target_type="workflow",
            target_id=wf.id,
            details={"intent": plan.get("intent")},
        )
        db.commit()
        return {
            "workflow_id": wf.id,
            "state": wf.state.value,
            "plan": plan,
            "tasks": _workflow_summary(wf),
        }
    run_workflow(db, wf=wf, principal=principal)
    record(
        db,
        company_id=principal.workspace_id,
        actor=principal.user_id,
        action="workflow.orchestrated",
        target_type="workflow",
        target_id=wf.id,
        details={"intent": plan.get("intent")},
    )
    try:
        from app.company.events import emit

        emit(db, company_id=principal.workspace_id, type="workflow.completed",
             payload={"workflow_id": wf.id, "state": wf.state.value,
                      "intent": plan.get("intent")})
    except Exception:
        pass
    db.commit()
    return {
        "workflow_id": wf.id,
        "state": wf.state.value,
        "plan": plan,
        "tasks": _workflow_summary(wf),
    }


def schedule(
    db: Session,
    *,
    principal: Principal,
    objective: str,
    run_at_iso: str,
) -> dict[str, Any]:
    """Register a scheduled workflow to run at a future time (PRD FR-14).

    The row is written to `scheduled_jobs`; pg_cron dispatches it into
    `workflow_jobs` at the due time. APScheduler is no longer used.
    """
    from datetime import datetime

    from app.models.orm import ScheduledJob

    run_at = datetime.fromisoformat(run_at_iso)
    row = ScheduledJob(
        company_id=principal.workspace_id,
        objective=objective,
        run_at=run_at,
        created_by_user_id=principal.user_id,
    )
    db.add(row)
    db.flush()
    record(
        db,
        company_id=principal.workspace_id,
        actor=principal.user_id,
        action="workflow.scheduled",
        target_type="workflow",
        target_id=row.id,
        details={"run_at": run_at_iso, "objective": objective[:200]},
    )
    db.commit()
    return {
        "job_id": row.id,
        "run_at": run_at_iso,
        "scheduled": True,
        "driver": "pg_cron",
    }


def trigger_event(
    db: Session,
    *,
    workspace_id: str,
    event: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Ingest an external event and enqueue a workflow (PRD FR-14).

    The job is written to the `workflow_jobs` table; the trigger from
    `pg_notify` wakes the worker. No Redis dependency.
    """
    payload = {"event": event, "workspace_id": workspace_id, **(data or {})}
    queue.enqueue(
        db,
        company_id=workspace_id,
        trigger="event",
        payload=payload,
    )
    record(
        db,
        company_id=workspace_id,
        actor="webhook",
        action="workflow.event",
        target_type="event",
        target_id=event,
        details=data or {},
    )
    db.commit()
    return {"queued": True, "event": event, "driver": "postgres_queue"}
