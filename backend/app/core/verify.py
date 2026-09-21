"""Verify-before-completion helpers (Phase 17). No silent success."""
from __future__ import annotations

from sqlalchemy.orm import Session


def verify_crm_record(db: Session, *, company_id: str, kind: str, record_id: str) -> bool:
    from app.models.orm import CrmCompany, CrmContact, Lead, Opportunity
    m = {"company": CrmCompany, "contact": CrmContact, "lead": Lead,
         "opportunity": Opportunity}.get(kind)
    if not m:
        return False
    row = db.get(m, record_id)
    return bool(row and row.company_id == company_id)


def require_confirmed(result: dict, what: str) -> None:
    if not result.get("ok") or result.get("status") in (
            "NOT_CONFIGURED", "FAILED", None) and not result.get("confirmed", True):
        raise ValueError(f"{what} not verified: {result.get('error') or result}")
