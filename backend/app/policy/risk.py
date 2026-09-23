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
