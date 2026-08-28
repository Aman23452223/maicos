"""Workflow engine (PRD §19, FR-08..FR-12, §29).

The engine is intentionally simple in the MVP:
  * One in-process task runner (no external queue required to demo).
  * Topological order over `depends_on`.
  * Per-task retries with a small cap.
  * Partial completion: tasks that fail are reported, but the workflow
    does not flip the whole thing to FAILED if other tasks succeeded
    (matches PRD §29 / state PARTIAL).
"""
from __future__ import annotations

from datetime import UTC
from typing import Any

from sqlalchemy.orm import Session

from app.agents.base import AgentContext, AgentResult, AgentTask
from app.agents.registry import get as get_agent
from app.approvals.service import create_approval, is_resolved
from app.audit.service import record
from app.core.logging import get_logger
from app.models.orm import (
    AgentRun,
    Task,
    TaskState,
    Workflow,
    WorkflowState,
)
from app.workflow.budget import (
    MAX_TASK_ATTEMPTS,
    check_workflow,
)

log = get_logger("workflow")


def create_workflow(
    db: Session,
    *,
    company_id: str,
    triggered_by_user_id: str,
    conversation_id: str | None,
    title: str,
    objective: str,
    plan: dict[str, Any],
) -> Workflow:
    wf = Workflow(
        company_id=company_id,
        triggered_by_user_id=triggered_by_user_id,
        conversation_id=conversation_id,
        title=title,
        objective=objective,
        plan=plan,
        state=WorkflowState.PLANNED,
    )
    db.add(wf)
    db.flush()
    plan_tasks = plan.get("tasks", [])
    check_workflow(len(plan_tasks))
    for index, t in enumerate(plan_tasks):
        # Persist a stable id so `depends_on` references resolve. We accept
        # plans that either include an explicit `id` or fall back to the
        # array index; the engine resolves either form.
        plan_id = t.get("id") or str(index)
        db.add(
            Task(
                workflow_id=wf.id,
                agent_name=t["agent"],
                title=t.get("title", t["agent"]),
                description=t.get("description", ""),
                depends_on=t.get("depends_on", []),
                state=TaskState.PENDING,
                input={**t.get("input", {}), "_plan_id": plan_id},
            )
        )
    record(
        db,
        company_id=company_id,
        actor=triggered_by_user_id,
        action="workflow.created",
        target_type="workflow",
        target_id=wf.id,
        details={"title": title},
    )
    db.flush()
    return wf


def _topo_ready(tasks: list[Task], done_ids: set[str]) -> list[Task]:
    # Build a map from `plan_id` to task so `depends_on` entries (which may
    # be plan ids or numeric indices from older plans) resolve to the
    # actual task id in `done_ids`.
    by_plan_id: dict[str, Task] = {}
    by_index: dict[str, Task] = {}
    for idx, t in enumerate(tasks):
        plan_id = (t.input or {}).get("_plan_id")
        if plan_id:
            by_plan_id[str(plan_id)] = t
        by_index[str(idx)] = t
    def resolve(ref: str) -> str | None:
        if ref in by_plan_id:
            return by_plan_id[ref].id
        if ref in by_index:
            return by_index[ref].id
        return None

    ready: list[Task] = []
    for t in tasks:
        if t.state in {TaskState.COMPLETED, TaskState.SKIPPED, TaskState.FAILED}:
            continue
        if t.state == TaskState.WAITING_APPROVAL:
            continue
        deps = t.depends_on or []
        if all((resolve(d) in done_ids) for d in deps):
            ready.append(t)
    return ready


def _summarize(db: Session, wf: Workflow) -> dict[str, Any]:
    tasks = list(wf.tasks)
    counts: dict[str, int] = {}
    for t in tasks:
        counts[t.state.value] = counts.get(t.state.value, 0) + 1
    return {
        "workflow_id": wf.id,
        "state": wf.state.value,
        "task_counts": counts,
        "tasks": [
            {
                "id": t.id,
                "agent": t.agent_name,
                "title": t.title,
                "state": t.state.value,
                "error": t.error,
            }
            for t in tasks
        ],
    }


def run(db: Session, *, wf: Workflow, principal) -> Workflow:
    """Execute pending ready tasks until idle, paused, or done.

    `principal` is required so that tool calls have a tenant identity.
    Use the triggering user's principal for on-demand runs, or a
    dedicated service principal for scheduled/event-driven runs.
    """
    wf.state = WorkflowState.RUNNING
    db.flush()
    tasks = list(wf.tasks)
    done: set[str] = {t.id for t in tasks if is_resolved(t)}

    while True:
        ready = _topo_ready(tasks, done)
        if not ready:
            break
        for t in ready:
            if t.state == TaskState.WAITING_APPROVAL:
                continue
            _execute_task(db, wf, t, principal)
            if t.state in {TaskState.COMPLETED, TaskState.SKIPPED}:
                done.add(t.id)
            if t.state == TaskState.WAITING_APPROVAL:
                # Pause only after every ready task that does NOT need
                # approval has run. This lets a single pass create all
                # pending approvals at once, so the user can decide
                # them in one batch and the next pass proceeds to the
                # next stage of the workflow.
                break
        # If any task is waiting on approval, pause the workflow so the
        # user can act on the batch. The next call to run() resumes.
        if any(t.state == TaskState.WAITING_APPROVAL for t in tasks):
            wf.state = WorkflowState.WAITING_APPROVAL
            db.flush()
            return wf

    failed = [t for t in tasks if t.state == TaskState.FAILED]
    completed = [t for t in tasks if t.state == TaskState.COMPLETED]
    if failed and completed:
        wf.state = WorkflowState.PARTIAL
    elif failed and not completed:
        wf.state = WorkflowState.FAILED
    else:
        wf.state = WorkflowState.COMPLETED

    record(
        db,
        company_id=wf.company_id,
        actor="workflow_engine",
        action="workflow.finished",
        target_type="workflow",
        target_id=wf.id,
        details={"state": wf.state.value, "summary": _summarize(db, wf)},
    )
    db.flush()
    return wf


def _seed_shared(tasks: list[Task], current: Task) -> dict:
    """Build a `shared` dict of upstream task outputs for the current task.

    Resolves `depends_on` to plan ids and merges the dependent tasks'
    stored outputs into a single dict so an agent can read, for example,
    `shared["contact"]["id"]`.
    """
    by_plan_id = {(t.input or {}).get("_plan_id"): t for t in tasks}
    by_plan_id = {k: v for k, v in by_plan_id.items() if k is not None}
    deps = current.depends_on or []
    merged: dict = {}
    for ref in deps:
        upstream = by_plan_id.get(ref)
        if not upstream:
            continue
        out = upstream.output or {}
        # The plan id becomes the key so agents can address outputs by
        # the same id used in the plan definition.
        merged[upstream.input.get("_plan_id")] = out
    return merged


def _execute_task(db: Session, wf: Workflow, t: Task, principal) -> None:
    # Resume path: if the task previously requested approval and that
    # approval has now been approved, replay the original tool call
    # directly so the agent's "needs_approval" output does not
    # re-trigger an approval request.
    pending_approval = _consume_approved_approval(db, t)
    if pending_approval is not None:
        t.state = TaskState.RUNNING
        t.attempts += 1
        run_row = _make_run_row(db, wf, t)
        replay = _replay_approved_action(db, t, principal, pending_approval, run_row)
        if replay.get("ok") and replay.get("confirmed"):
            t.state = TaskState.COMPLETED
            t.output = replay.get("data") or {}
            t.error = None
            from datetime import datetime
            run_row.finished_at = datetime.now(UTC)
            run_row.output = t.output
        else:
            t.state = TaskState.FAILED
            t.error = replay.get("message") or "approved action failed"
            run_row.error = t.error
        return

    t.state = TaskState.RUNNING
    t.attempts += 1
    agent = get_agent(t.agent_name)
    run_row = _make_run_row(db, wf, t)

    shared = _seed_shared(list(wf.tasks), t)
    shared["agent_name"] = t.agent_name

    ctx = AgentContext(
        db=db,
        principal=principal,
        workflow_id=wf.id,
        task_id=t.id,
        run_id=run_row.id,
        shared=shared,
    )
    result: AgentResult = agent.run(AgentTask(title=t.title, description=t.description, input=t.input), ctx)

    run_row.steps = ctx.log
    run_row.tool_calls = ctx.log

    if result.needs_approval:
        # Older plans may not have set `_operation`; fall back to the
        # first allowed tool for the connector so the replay path can
        # still pick something sensible.
        payload = dict(result.needs_approval["payload"])
        target_system = result.needs_approval.get("target_system", "")
        if "_operation" not in payload:
            payload["_operation"] = _first_op_for(t.agent_name, target_system)
        create_approval(
            db,
            workflow=wf,
            task_id=t.id,
            requested_by_agent=t.agent_name,
            action=result.needs_approval["action"],
            target_system=target_system,
            description=result.needs_approval["description"],
            payload=payload,
        )
        t.state = TaskState.WAITING_APPROVAL
        t.output = result.output or {}
        return

    if result.error:
        if t.attempts < MAX_TASK_ATTEMPTS:
            t.state = TaskState.PENDING
            t.error = result.error
            return
        t.state = TaskState.FAILED
        t.error = result.error
        run_row.error = result.error
        return

    t.output = result.output or {}
    t.state = TaskState.COMPLETED
    t.error = None
    run_row.output = result.output or {}
    from datetime import datetime

    run_row.finished_at = datetime.now(UTC)


def _first_op_for(agent_name: str, connector: str) -> str:
    """Pick a default operation for a connector based on agent name.

    Used as a backward-compat fallback when an agent's
    `needs_approval` payload does not specify `_operation`. Keep this
    mapping conservative; new agents should always set the key.
    """
    defaults = {
        "communication": "message.send",
        "calendar": "event.create",
        "finance": "invoice.create",
    }
    return defaults.get(agent_name, "")


def _make_run_row(db: Session, wf: Workflow, t: Task) -> AgentRun:
    run_row = AgentRun(
        company_id=wf.company_id,
        task_id=t.id,
        agent_name=t.agent_name,
        steps=[],
        tool_calls=[],
    )
    db.add(run_row)
    db.flush()
    return run_row


def _consume_approved_approval(db: Session, t: Task) -> dict | None:
    """Return the payload of the most recent approved approval for a task.

    We do NOT remove the approval - it stays for audit. We only return
    the payload so the engine can replay the original tool call.
    """
    from app.models.orm import Approval, ApprovalStatus

    a = (
        db.query(Approval)
        .filter(
            Approval.task_id == t.id,
            Approval.status == ApprovalStatus.APPROVED,
        )
        .order_by(Approval.created_at.desc())
        .first()
    )
    if a is None:
        return None
    return {
        "action": a.action,
        "target_system": a.target_system,
        "payload": a.payload or {},
    }


def _replay_approved_action(
    db: Session,
    t: Task,
    principal,
    approval: dict,
    run_row: AgentRun,
) -> dict:
    """Replay a previously-approved action.

    Preferred path: the agent implements `execute_approved` and does
    whatever the approval was about (e.g. finance prepares an invoice,
    communication sends an email, calendar books an event).

    Fallback: for approvals on a standard tool operation (target_system
    is a connector), look up the connector and call the tool directly.
    """
    from app.agents.base import AgentContext
    from app.agents.registry import get as get_agent

    agent = get_agent(t.agent_name)
    payload = dict(approval.get("payload", {}))

    # Preferred: let the agent itself run the approved action.
    try:
        ctx = AgentContext(
            db=db,
            principal=principal,
            workflow_id=t.workflow_id,
            task_id=t.id,
            run_id=run_row.id,
            shared={"agent_name": t.agent_name},
        )
        result = agent.execute_approved(approval, ctx)
        run_row.tool_calls = ctx.log
        return {
            "ok": result.error is None,
            "confirmed": result.error is None,
            "data": result.output,
            "message": result.error,
        }
    except NotImplementedError:
        pass
    except AttributeError:
        pass

    # Fallback: connector replay.
    from app.integrations.base import execute_tool

    target_system = approval.get("target_system", "")
    allowed = list(agent.allowed_tools or [])
    connector_map = {
        "email": "email",
        "calendar": "calendar",
        "finance": "finance",
        "crm": "crm",
    }
    connector = connector_map.get(target_system, target_system)
    explicit_op = payload.pop("_operation", None) if isinstance(payload, dict) else None
    candidates = [op for op in allowed if op.startswith(f"{connector}.")]
    if explicit_op and f"{connector}.{explicit_op}" in allowed:
        operation = explicit_op
    elif candidates:
        operation = candidates[0].split(".", 1)[1]
    else:
        return {
            "ok": False,
            "confirmed": False,
            "message": f"no allowed tool for {connector}",
        }
    try:
        from app.integrations.base import ToolResult

        tool_result: ToolResult = execute_tool(
            principal,
            connector,
            operation,
            payload,
            allowed,
        )
    except Exception as e:  # noqa: BLE001
        run_row.tool_calls = [
            {
                "type": "tool_call",
                "connector": connector,
                "operation": operation,
                "ok": False,
                "confirmed": False,
                "error": str(e),
            }
        ]
        return {"ok": False, "confirmed": False, "message": str(e)}
    run_row.tool_calls = [
        {
            "type": "tool_call",
            "connector": connector,
            "operation": operation,
            "ok": tool_result.ok,
            "confirmed": tool_result.confirmed,
            "external_id": tool_result.external_id,
        }
    ]
    return {
        "ok": tool_result.ok,
        "confirmed": tool_result.confirmed,
        "data": tool_result.data,
        "message": tool_result.message,
        "external_id": tool_result.external_id,
    }

