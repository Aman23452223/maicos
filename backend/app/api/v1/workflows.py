"""Workflow / AI Manager routes (FR-03..FR-12)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.context import Principal
from app.core.security import get_current_principal
from app.db.session import get_db
from app.models.orm import (
    Conversation,
    TaskState,
    Workflow,
    WorkflowState,
)
from app.orchestrator import handle_objective
from app.schemas import CommandIn, TaskOut, TaskPatchIn, WorkflowOut
from app.workflow.engine import run as run_workflow

router = APIRouter(tags=["workflow"])


@router.post("/commands", response_model=WorkflowOut)
def submit_command(
    payload: CommandIn,
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> WorkflowOut:
    from app.core.ratelimit import check as _rl_check

    allowed, retry_after = _rl_check(f"cmd:{p.workspace_id}")
    if not allowed:
        raise HTTPException(status_code=429,
                            detail=f"rate limit: retry in {retry_after}s")
    conv_id = payload.conversation_id
    if not conv_id:
        conv = Conversation(company_id=p.workspace_id, user_id=p.user_id)
        db.add(conv)
        db.flush()
        conv_id = conv.id
    result = handle_objective(
        db, principal=p, objective=payload.objective, conversation_id=conv_id,
        plan_review=bool(payload.plan_review),
    )
    wf = db.get(Workflow, result["workflow_id"])
    if not wf:
        raise HTTPException(status_code=500, detail="workflow not persisted")
    return WorkflowOut(
        id=wf.id,
        title=wf.title,
        objective=wf.objective,
        state=wf.state.value,
        plan=wf.plan or {},
        created_at=wf.created_at,
        updated_at=wf.updated_at,
    )


@router.get("/conversations")
def list_conversations(
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = (
        db.query(Conversation)
        .filter(Conversation.company_id == p.workspace_id)
        .order_by(Conversation.created_at.desc())
        .limit(50)
        .all()
    )
    out: list[dict] = []
    for c in rows:
        wf_count = (
            db.query(Workflow).filter(Workflow.conversation_id == c.id).count()
        )
        out.append(
            {
                "id": c.id,
                "title": c.title,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "workflow_count": wf_count,
            }
        )
    return out


@router.get("/workflows", response_model=list[WorkflowOut])
def list_workflows(
    state: str | None = None,
    limit: int = 50,
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> list[WorkflowOut]:
    q = db.query(Workflow).filter(Workflow.company_id == p.workspace_id)
    if state:
        try:
            q = q.filter(Workflow.state == WorkflowState(state.upper()))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be 1..200")
    rows = q.order_by(Workflow.updated_at.desc()).limit(limit).all()
    return [
        WorkflowOut(
            id=w.id,
            title=w.title,
            objective=w.objective,
            state=w.state.value,
            plan=w.plan or {},
            created_at=w.created_at,
            updated_at=w.updated_at,
        )
        for w in rows
    ]


@router.get("/workflows/{workflow_id}", response_model=WorkflowOut)
def get_workflow(
    workflow_id: str,
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> WorkflowOut:
    wf = db.get(Workflow, workflow_id)
    if not wf or wf.company_id != p.workspace_id:
        raise HTTPException(status_code=404, detail="workflow not found")
    return WorkflowOut(
        id=wf.id,
        title=wf.title,
        objective=wf.objective,
        state=wf.state.value,
        plan=wf.plan or {},
        created_at=wf.created_at,
        updated_at=wf.updated_at,
    )


@router.get("/workflows/{workflow_id}/tasks", response_model=list[TaskOut])
def list_tasks(
    workflow_id: str,
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> list[TaskOut]:
    wf = db.get(Workflow, workflow_id)
    if not wf or wf.company_id != p.workspace_id:
        raise HTTPException(status_code=404, detail="workflow not found")
    return [
        TaskOut(
            id=t.id,
            agent_name=t.agent_name,
            title=t.title,
            description=t.description,
            state=t.state.value,
            depends_on=t.depends_on or [],
            output=t.output or {},
            error=t.error,
        )
        for t in wf.tasks
    ]


@router.patch("/workflows/{workflow_id}/tasks/{task_id}", response_model=TaskOut)
def patch_task(
    workflow_id: str,
    task_id: str,
    payload: TaskPatchIn,
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> TaskOut:
    """Edit a pending task's plan (title/description/input) before it runs.

    Allowed only while the task hasn't executed (PENDING) and the workflow
    isn't actively running to completion — i.e. the plan-review window.
    """
    from app.models.orm import Task

    wf = db.get(Workflow, workflow_id)
    if not wf or wf.company_id != p.workspace_id:
        raise HTTPException(status_code=404, detail="workflow not found")
    if wf.state not in {WorkflowState.WAITING_APPROVAL, WorkflowState.PLANNED,
                        WorkflowState.PARTIAL}:
        raise HTTPException(status_code=409,
                            detail=f"cannot edit tasks in {wf.state.value}")
    t = db.get(Task, task_id)
    if not t or t.workflow_id != wf.id:
        raise HTTPException(status_code=404, detail="task not found")
    if t.state != TaskState.PENDING:
        raise HTTPException(status_code=409,
                            detail=f"task already {t.state.value}, cannot edit")
    if payload.title is not None:
        t.title = payload.title[:255]
    if payload.description is not None:
        t.description = payload.description[:2000]
    if payload.input is not None:
        # Preserve engine bookkeeping keys.
        merged = dict(payload.input)
        merged["_plan_id"] = (t.input or {}).get("_plan_id", "")
        merged["_workspace"] = (t.input or {}).get("_workspace", {})
        t.input = merged
    db.commit()
    db.refresh(t)
    return TaskOut(
        id=t.id, agent_name=t.agent_name, title=t.title,
        description=t.description, state=t.state.value,
        depends_on=t.depends_on or [], output=t.output or {}, error=t.error,
    )


@router.post("/workflows/{workflow_id}/replan", response_model=WorkflowOut)
def replan(
    workflow_id: str,
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> WorkflowOut:
    """Safe replan: builds a FRESH workflow from failure context.

    The failed workflow is never mutated; the new plan references it via
    plan.parent_workflow_id. Only failed/partial workflows can replan.
    """
    from app.orchestrator import handle_objective

    wf = db.get(Workflow, workflow_id)
    if not wf or wf.company_id != p.workspace_id:
        raise HTTPException(status_code=404, detail="workflow not found")
    if wf.state not in {WorkflowState.FAILED, WorkflowState.PARTIAL}:
        raise HTTPException(status_code=409,
                            detail=f"only FAILED/PARTIAL workflows replan (is {wf.state.value})")
    failed = [f"{t.agent_name}:{t.title} ({t.error or 'no detail'})"
              for t in wf.tasks if t.state == TaskState.FAILED]
    objective = (f"{wf.objective}\n[Replan context: previous attempt had "
                 f"{len(failed)} failed task(s): {'; '.join(failed[:5])}. "
                 f"Prefer alternative capabilities and split risky steps.]")
    result = handle_objective(db, principal=p, objective=objective,
                              conversation_id=wf.conversation_id)
    child = db.get(Workflow, result["workflow_id"])
    plan = dict(child.plan or {})
    plan["parent_workflow_id"] = wf.id
    child.plan = plan
    db.commit()
    return get_workflow(result["workflow_id"], p, db)


@router.get("/workflows/{workflow_id}/runs")
def list_runs(
    workflow_id: str,
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Live execution steps per task (Instinct-style progress: what the
    worker is doing right now). Steps come from persisted agent run logs."""
    from app.models.orm import AgentRun, Task

    wf = db.get(Workflow, workflow_id)
    if not wf or wf.company_id != p.workspace_id:
        raise HTTPException(status_code=404, detail="workflow not found")
    task_ids = [t.id for t in wf.tasks]
    if not task_ids:
        return []
    rows = db.query(AgentRun).filter(AgentRun.task_id.in_(task_ids)).order_by(
        AgentRun.started_at.asc()).all()
    return [{
        "task_id": r.task_id, "agent": r.agent_name,
        "steps": r.steps or [], "tool_calls": r.tool_calls or [],
        "output_keys": sorted((r.output or {}).keys()),
        "error": r.error,
        "finished": bool(r.finished_at),
    } for r in rows]


@router.post("/workflows/{workflow_id}/resume", response_model=WorkflowOut)
def resume(
    workflow_id: str,
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> WorkflowOut:
    wf = db.get(Workflow, workflow_id)
    if not wf or wf.company_id != p.workspace_id:
        raise HTTPException(status_code=404, detail="workflow not found")
    if wf.state not in {WorkflowState.WAITING_APPROVAL, WorkflowState.RUNNING, WorkflowState.PARTIAL}:
        raise HTTPException(status_code=409, detail=f"cannot resume from {wf.state.value}")
    # A pending plan review must be approved first — resume must not bypass it.
    from app.models.orm import Approval, ApprovalStatus

    plan_pending = (
        db.query(Approval)
        .filter(Approval.workflow_id == wf.id, Approval.action == "plan_review",
                Approval.status == ApprovalStatus.PENDING)
        .count()
    )
    if plan_pending:
        raise HTTPException(status_code=409, detail="approve the plan in Approvals first")
    # Tasks still in WAITING_APPROVAL remain paused until the approval
    # center decides; tasks that became eligible after approvals are
    # picked up by the engine.
    pending_approval = [
        t for t in wf.tasks if t.state == TaskState.WAITING_APPROVAL
    ]
    if pending_approval:
        return get_workflow(workflow_id, p, db)
    run_workflow(db, wf=wf, principal=p)
    db.commit()
    return get_workflow(workflow_id, p, db)

