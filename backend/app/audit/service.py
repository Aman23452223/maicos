"""Audit log service (PRD FR-11, §18)."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.orm import AuditLog


def record(
    db: Session,
    *,
    company_id: str,
    actor: str,
    action: str,
    target_type: str,
    target_id: str,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        company_id=company_id,
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details or {},
    )
    db.add(entry)
    db.flush()
    return entry

