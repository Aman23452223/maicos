"""Orchestrator - bridges the AI Manager and the workflow engine."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.agents.implementations.ai_manager import build_plan
from app.audit.service import record
from app.core.context import Principal
from app.queue.jobs import Job, enqueue, new_job_id, redis_enabled
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


def handle_objective(
    db: Session,
    *,
    principal: Principal,
    objective: str,
    conversation_id: str | None = None,
    enqueue_async: bool = False,
) -> dict[str, Any]:
    plan = _build_plan(objective)
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
        enqueue(
            Job(
                id=new_job_id(),
                workflow_id=wf.id,
                workspace_id=principal.workspace_id,
                trigger="on_demand",
                payload={"workflow_id": wf.id},
            )
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
    """Register a scheduled workflow to run at a future time (PRD FR-14)."""
    from datetime import datetime

    from apscheduler.triggers.date import DateTrigger

    from app.scheduler import get_scheduler

    run_at = datetime.fromisoformat(run_at_iso)
    job_id = new_job_id()
    payload = {
        "objective": objective,
        "workspace_id": principal.workspace_id,
    }

    def _fire() -> None:
        enqueue(
            Job(
                id=job_id,
                workflow_id="",
                workspace_id=principal.workspace_id,
                trigger="scheduled",
                payload=payload,
            )
        )

    if not redis_enabled():
        record(
            db,
            company_id=principal.workspace_id,
            actor=principal.user_id,
            action="workflow.scheduled.skipped",
            target_type="workflow",
            target_id=job_id,
            details={"reason": "redis_disabled", "run_at": run_at_iso, "objective": objective[:200]},
        )
        db.commit()
        return {
            "job_id": job_id,
            "run_at": run_at_iso,
            "scheduled": False,
            "reason": "redis_disabled",
        }

    get_scheduler().add_job(
        _fire, trigger=DateTrigger(run_date=run_at), id=job_id, replace_existing=True
    )
    record(
        db,
        company_id=principal.workspace_id,
        actor=principal.user_id,
        action="workflow.scheduled",
        target_type="workflow",
        target_id=job_id,
        details={"run_at": run_at_iso, "objective": objective[:200]},
    )
    db.commit()
    return {"job_id": job_id, "run_at": run_at_iso, "scheduled": True}


def trigger_event(
    db: Session,
    *,
    workspace_id: str,
    event: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Ingest an external event and enqueue a workflow (PRD FR-14).

    When Redis is not configured, the event is recorded in the audit log
    but the workflow is not started (the worker would need Redis to
    consume the job). The HTTP response still returns 200 with a
    `queued` flag so the caller knows the side-effect did not happen.
    """
    payload = {"event": event, "workspace_id": workspace_id, **(data or {})}
    queued = enqueue(
        Job(
            id=new_job_id(),
            workflow_id="",
            workspace_id=workspace_id,
            trigger="event",
            payload=payload,
        )
    )
    record(
        db,
        company_id=workspace_id,
        actor="webhook",
        action="workflow.event",
        target_type="event",
        target_id=event,
        details={**(data or {}), "queued": queued},
    )
    db.commit()
    return {"queued": queued, "event": event}
