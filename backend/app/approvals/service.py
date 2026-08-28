"""Approval center (PRD §14, §20, FR-09)."""
from __future__ import annotations

from datetime import UTC
from typing import Any

from sqlalchemy.orm import Session

from app.audit.service import record
from app.core.config import get_settings
from app.models.orm import Approval, ApprovalStatus, TaskState, Workflow, WorkflowState

_POLICY_LEVELS = {
    "automatic": 0,
    "approval": 1,
    "required": 2,
    "admin": 2,
}

# Actions that always require approval by default per PRD §14,
# even if the policy file does not list them explicitly.
_ALWAYS_REQUIRED = {
    "send_external_communication",
    "create_financial_document",
    "execute_payment",
    "delete_critical_data",
    "change_security_settings",
}


def requires_approval(action: str) -> bool:
    """Return True if a given action requires human approval.

    Per PRD §14, external communication, financial actions, payments,
    critical data deletion and security changes are approval-gated by
    default. The configured policy can only make this stricter (e.g.
    "admin") or relax automatic actions - it cannot silently downgrade
    a required action without an explicit override.
    """
    if action in _ALWAYS_REQUIRED:
        return True
    settings = get_settings()
    policy = settings.approval_policy()
    rule = policy.get(action)
    if rule is None:
        return False
    level = _POLICY_LEVELS.get(str(rule).lower(), 0)
    return level >= 1


def create_approval(
    db: Session,
    *,
    workflow: Workflow,
    task_id: str | None,
    requested_by_agent: str,
    action: str,
    target_system: str,
    description: str,
    payload: dict[str, Any],
) -> Approval:
    approval = Approval(
        company_id=workflow.company_id,
        workflow_id=workflow.id,
        task_id=task_id,
        action=action,
        target_system=target_system,
        description=description,
        payload=payload,
        status=ApprovalStatus.PENDING,
        requested_by_agent=requested_by_agent,
    )
    db.add(approval)
    workflow.state = WorkflowState.WAITING_APPROVAL
    record(
        db,
        company_id=workflow.company_id,
        actor=requested_by_agent,
        action="approval.requested",
        target_type="approval",
        target_id="pending",
        details={"action": action, "target_system": target_system},
    )
    db.flush()
    return approval


def decide(
    db: Session,
    *,
    approval: Approval,
    decision: str,
    decided_by_user_id: str,
    note: str | None = None,
) -> Approval:
    from datetime import datetime

    from app.models.orm import Task

    d = decision.upper()
    if d not in {"APPROVE", "REJECT"}:
        raise ValueError("decision must be APPROVE or REJECT")
    approval.status = ApprovalStatus.APPROVED if d == "APPROVE" else ApprovalStatus.REJECTED
    approval.decided_by_user_id = decided_by_user_id
    approval.decision_note = note
    approval.decided_at = datetime.now(UTC)

    # Move the associated task back into the runnable queue so the
    # workflow engine picks it up on the next pass. On rejection, the
    # task is marked FAILED (the engine skips failed tasks and may
    # still reach a PARTIAL state).
    if approval.task_id:
        task = db.get(Task, approval.task_id)
        if task is not None:
            if d == "APPROVE":
                task.state = TaskState.PENDING
            else:
                task.state = TaskState.FAILED
                task.error = "approval rejected"

    wf = db.get(Workflow, approval.workflow_id)
    if wf and wf.state == WorkflowState.WAITING_APPROVAL:
        wf.state = WorkflowState.RUNNING
    record(
        db,
        company_id=approval.company_id,
        actor=decided_by_user_id,
        action=f"approval.{d.lower()}d",
        target_type="approval",
        target_id=approval.id,
        details={"note": note} if note else {},
    )
    db.flush()
    return approval


def is_resolved(task) -> bool:
    return task.state in {TaskState.COMPLETED, TaskState.SKIPPED}

