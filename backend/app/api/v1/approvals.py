"""Approval center routes (FR-09, §14, §20)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.approvals.service import decide
from app.core.context import Principal
from app.core.security import get_current_principal
from app.db.session import get_db
from app.models.orm import Approval, ApprovalStatus
from app.schemas import ApprovalDecisionIn, ApprovalOut

router = APIRouter(tags=["approvals"])


@router.get("/approvals", response_model=list[ApprovalOut])
def list_approvals(
    status: str | None = None,
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> list[ApprovalOut]:
    q = db.query(Approval).filter(Approval.company_id == p.workspace_id)
    if status:
        try:
            q = q.filter(Approval.status == ApprovalStatus(status.upper()))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    return [
        ApprovalOut(
            id=a.id,
            workflow_id=a.workflow_id,
            task_id=a.task_id,
            action=a.action,
            target_system=a.target_system,
            description=a.description,
            payload=a.payload or {},
            status=a.status.value,
            requested_by_agent=a.requested_by_agent,
            created_at=a.created_at,
        )
        for a in q.order_by(Approval.created_at.desc()).all()
    ]


@router.post("/approvals/{approval_id}/decision", response_model=ApprovalOut)
def decide_approval(
    approval_id: str,
    payload: ApprovalDecisionIn,
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> ApprovalOut:
    a = db.get(Approval, approval_id)
    if not a or a.company_id != p.workspace_id:
        raise HTTPException(status_code=404, detail="approval not found")
    if a.status != ApprovalStatus.PENDING:
        raise HTTPException(status_code=409, detail=f"already {a.status.value}")
    decide(
        db,
        approval=a,
        decision=payload.decision,
        decided_by_user_id=p.user_id,
        note=payload.note,
    )
    if a.action == "plan_review" and payload.decision.upper() != "APPROVE":
        # Rejected plan never executes.
        from app.models.orm import Workflow as _Workflow0
        from app.models.orm import WorkflowState as _WS

        wf0 = db.get(_Workflow0, a.workflow_id)
        if wf0 is not None:
            wf0.state = _WS.CANCELLED
    db.commit()
    # Auto-resume: on APPROVE, if no other PENDING approvals remain for the
    # workflow, continue execution immediately (Phase 16). Safe because the
    # engine replays only the approved payload and checks confirmations.
    try:
        from app.models.orm import TaskState
        from app.models.orm import Workflow as _Workflow

        if payload.decision.upper() == "APPROVE":
            remaining = (
                db.query(Approval)
                .filter(
                    Approval.workflow_id == a.workflow_id,
                    Approval.status == ApprovalStatus.PENDING,
                )
                .count()
            )
            if remaining == 0:
                from app.models.orm import Task
                from app.workflow.engine import run as run_workflow

                wf = db.get(_Workflow, a.workflow_id)
                if wf is not None:
                    blocked = (
                        db.query(Task)
                        .filter(
                            Task.workflow_id == wf.id,
                            Task.state == TaskState.WAITING_APPROVAL,
                        )
                        .count()
                    )
                    # decide() already flipped the decided task to PENDING,
                    # so blocked==0 means safe to resume now.
                    if blocked == 0:
                        run_workflow(db, wf=wf, principal=p)
                        db.commit()
    except Exception:
        # Auto-resume is best-effort; manual POST /workflows/{id}/resume
        # always remains available.
        pass
    db.refresh(a)
    return ApprovalOut(
        id=a.id,
        workflow_id=a.workflow_id,
        task_id=a.task_id,
        action=a.action,
        target_system=a.target_system,
        description=a.description,
        payload=a.payload or {},
        status=a.status.value,
        requested_by_agent=a.requested_by_agent,
        created_at=a.created_at,
    )

