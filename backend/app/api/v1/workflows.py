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
from app.schemas import CommandIn, TaskOut, WorkflowOut
from app.workflow.engine import run as run_workflow

router = APIRouter(tags=["workflow"])


@router.post("/commands", response_model=WorkflowOut)
def submit_command(
    payload: CommandIn,
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> WorkflowOut:
    conv_id = payload.conversation_id
    if not conv_id:
        conv = Conversation(company_id=p.workspace_id, user_id=p.user_id)
        db.add(conv)
        db.flush()
        conv_id = conv.id
    result = handle_objective(
        db, principal=p, objective=payload.objective, conversation_id=conv_id
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

