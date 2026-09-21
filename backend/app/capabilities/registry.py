"""Generic capabilities. No industry-specific entries."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.orm import BusinessProfile

CAPABILITIES = [
    "website_analysis", "knowledge", "lead_discovery", "lead_enrichment",
    "qualification", "scoring", "crm", "email", "messaging", "calendar",
    "followup", "proposal", "customer_onboarding", "project_management",
    "support", "analytics", "reporting", "finance", "hr", "marketing",
]

# Plan -> enabled capabilities (no billing, just entitlement mapping)
PLANS: dict[str, list[str]] = {
    "starter": ["website_analysis", "knowledge", "crm", "analytics", "reporting"],
    "growth": ["website_analysis", "knowledge", "lead_discovery", "lead_enrichment",
               "qualification", "scoring", "crm", "email", "followup", "proposal",
               "calendar", "analytics", "reporting"],
    "scale": list(CAPABILITIES),
}


def enabled_for(db: Session, *, company_id: str) -> set[str]:
    bp = db.query(BusinessProfile).filter(
        BusinessProfile.company_id == company_id).first()
    if bp and (bp.enabled_capabilities or []):
        return {c for c in bp.enabled_capabilities if c in CAPABILITIES}
    # Fall back to company plan mapping. Default is scale (all) for backward
    # compat: existing workspaces never explicitly disabled anything, so the
    # gate must not drop their tasks. Explicit config opts into gating.
    from app.models.orm import Company
    co = db.get(Company, company_id)
    raw_plan = ((co.plan or {}) if co and co.plan else {}).get("name")
    if not raw_plan:
        return set(PLANS["scale"])
    return set(PLANS.get(str(raw_plan).lower(), PLANS["scale"]))


def check(db: Session, *, company_id: str, capability: str) -> dict:
    if capability not in CAPABILITIES:
        return {"ok": False, "status": "NOT_ENABLED", "error": f"unknown capability {capability}"}
    if capability in enabled_for(db, company_id=company_id):
        return {"ok": True, "status": "OK"}
    return {"ok": False, "status": "NOT_ENABLED",
            "error": f"capability {capability} not enabled for this workspace plan"}
