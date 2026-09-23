"""Company Brain: persistent typed memory + assembled company context.

Memory types: FACT | DECISION | GOAL | ASSUMPTION | USER_PREFERENCE |
EXTERNAL_INFORMATION | AI_RECOMMENDATION | EXECUTION_RESULT.
AI-generated content is NEVER stored as FACT (stored as AI_RECOMMENDATION
until a human confirms it).
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.audit.service import record
from app.models.orm import BusinessMemory

MEMORY_TYPES = {"FACT", "DECISION", "GOAL", "ASSUMPTION", "USER_PREFERENCE",
                "EXTERNAL_INFORMATION", "AI_RECOMMENDATION", "EXECUTION_RESULT"}

# legacy lowercase kinds accepted for backward compat
LEGACY_KINDS = {"fact", "preference", "goal_context", "pattern"}


def remember(db: Session, *, company_id: str, kind: str, key: str,
             value: str, actor: str = "system") -> BusinessMemory:
    ku = kind.strip().upper()
    if ku not in MEMORY_TYPES and kind not in LEGACY_KINDS:
        raise ValueError(f"kind must be one of {sorted(MEMORY_TYPES)}")
    if any(s in key.lower() for s in ("secret", "token", "password", "api_key")):
        raise ValueError("secrets must never be stored as memory")
    row = BusinessMemory(company_id=company_id, kind=ku if ku in MEMORY_TYPES else kind,
                         key=key[:200], value=value[:4000])
    db.add(row)
    db.flush()
    record(db, company_id=company_id, actor=actor, action="brain.remembered",
           target_type="memory", target_id=row.id, details={"kind": row.kind})
    return row


def recall(db: Session, *, company_id: str, kinds: list[str] | None = None,
           limit: int = 30) -> list[dict[str, Any]]:
    q = db.query(BusinessMemory).filter(BusinessMemory.company_id == company_id)
    if kinds:
        q = q.filter(BusinessMemory.kind.in_(kinds))
    rows = q.order_by(BusinessMemory.updated_at.desc()).limit(limit).all()
    return [{"id": r.id, "kind": r.kind, "key": r.key, "value": r.value} for r in rows]


def load_company_context(db: Session, *, company_id: str) -> dict[str, Any]:
    """Assemble the Company Brain snapshot for planning."""
    from app.analytics.metrics import funnel, operations, pipeline
    from app.intel.service import get_or_create_profile

    bp = get_or_create_profile(db, company_id=company_id)
    mem = {m["kind"]: [] for m in recall(db, company_id=company_id, limit=50)}
    for m in recall(db, company_id=company_id, limit=50):
        mem.setdefault(m["kind"], []).append(f"{m['key']}: {m['value']}"[:300])
    try:
        metrics = {"funnel": funnel(db, company_id=company_id),
                   "pipeline": pipeline(db, company_id=company_id),
                   "operations": operations(db, company_id=company_id)}
    except Exception:
        metrics = {}
    return {
        "business_name": bp.business_name, "industry": bp.industry,
        "description": (bp.description or "")[:1000],
        "products_services": bp.products_services or [],
        "target_customer": bp.target_customer, "geography": bp.geography,
        "icp": bp.icp or {}, "goals": bp.business_goals or [],
        "segments": bp.customer_segments or [],
        "memory": {k: v[:10] for k, v in mem.items()},
        "metrics": metrics,
    }
