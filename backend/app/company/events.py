"""Internal company event bus (generic, workspace-scoped)."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.orm import CompanyEvent

ALLOWED_TYPES = {
    "lead.created", "lead.qualified", "lead.converted", "customer.created",
    "payment.received", "payment.failed", "meeting.booked", "meeting.cancelled",
    "deployment.failed", "deployment.succeeded", "task.failed",
    "workflow.completed", "goal.created", "goal.progress_changed",
    "budget.threshold_reached", "integration.failed", "integration.disconnected",
    "startup.created", "project.created", "campaign.started", "campaign.completed",
    "partner.onboarded",
}


def emit(db: Session, *, company_id: str, type: str,
         payload: dict[str, Any] | None = None) -> CompanyEvent | None:
    if type not in ALLOWED_TYPES:
        return None
    row = CompanyEvent(company_id=company_id, type=type, payload=payload or {})
    db.add(row)
    db.flush()
    return row
