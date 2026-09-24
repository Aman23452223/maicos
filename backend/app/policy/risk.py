"""Risk levels + workspace autonomy overrides.

LOW: automatic. MEDIUM: policy-gated (default: approval unless workspace
opts the channel into auto_approve). HIGH: always approval.
Workspace overrides live in BusinessProfile.comms_policy / config and can
only relax LOW/MEDIUM — never HIGH (payments, destructive, contracts,
finance docs, publishing, production deploys).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

RISK_LEVELS: dict[str, str] = {
    # External sends default to approval (approvals/service keeps them in
    # _ALWAYS_REQUIRED); a workspace may explicitly auto-approve listed
    # channels via comms_policy (Sending Mode UI).
    "send_external_communication": "medium",
    "create_financial_document": "high",
    "execute_payment": "high",
    "delete_critical_data": "high",
    "change_security_settings": "high",
    "publish_content": "high",
    "deploy_production": "high",
    "crm_write": "medium",
    "calendar_write": "medium",
    "proposal_send": "high",
    "rag_read": "low",
    "analytics_read": "low",
    "lead_discover": "low",
}

# Medium-risk actions a workspace may auto-approve per channel/capability.
MEDIUM_AUTO_KEYS = {"email", "whatsapp", "calendar", "crm"}


def risk_of(action: str) -> str:
    return RISK_LEVELS.get(action, "medium")


DEFAULT_AUTOPILOT = {
    "enabled": False,
    "max_spend_month": 0,
    "auto_channels": [],
    "auto_invoice_below": 0,
    "auto_replan": False,
}


def autopilot(db: Session, *, company_id: str) -> dict:
    """Workspace autopilot policy (owner sets once, system obeys)."""
    try:
        from app.models.orm import Company

        co = db.get(Company, company_id)
        cfg = dict(DEFAULT_AUTOPILOT)
        if co and isinstance(co.config, dict):
            cfg.update(co.config.get("autopilot") or {})
        return cfg
    except Exception:
        return dict(DEFAULT_AUTOPILOT)


def spend_this_month(db: Session, *, company_id: str) -> int:
    """Sum of approved/collected payment amounts this calendar month."""
    from datetime import UTC, datetime

    from app.models.orm import PaymentRequest

    start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    rows = db.query(PaymentRequest).filter(
        PaymentRequest.company_id == company_id,
        PaymentRequest.created_at >= start).all()
    return sum(int(r.amount or 0) for r in rows)


def check_spend(db: Session, *, company_id: str, amount: int) -> tuple[bool, str]:
    """Enforce monthly spend cap. Returns (allowed, reason)."""
    pol = autopilot(db, company_id=company_id)
    if not pol.get("enabled"):
        return False, "autopilot disabled"
    cap = int(pol.get("max_spend_month") or 0)
    if cap <= 0:
        return False, "no spend cap configured"
    if spend_this_month(db, company_id=company_id) + int(amount or 0) > cap:
        return False, f"monthly cap {cap} would be exceeded"
    return True, "within cap"


def workspace_allows(db: Session, *, company_id: str, action: str,
                     channel: str = "") -> bool:
    """True if the workspace policy permits automatic execution."""
    if risk_of(action) == "high":
        return False
    try:
        from app.intel.service import get_or_create_profile

        bp = get_or_create_profile(db, company_id=company_id)
        policy = bp.comms_policy or {}
        auto = [str(a).lower() for a in (policy.get("auto_approve") or [])]
        if channel and channel.lower() in auto and channel.lower() in MEDIUM_AUTO_KEYS:
            return True
        if action in (policy.get("auto_actions") or []):
            return True
    except Exception:
        pass
    return False
