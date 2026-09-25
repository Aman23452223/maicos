"""Self-gap analysis: required vs available capabilities (honest statuses)."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.capabilities.registry import CAPABILITIES, enabled_for
from app.integrations.catalog import verify as verify_provider

# intent -> capabilities it needs
INTENT_CAPABILITIES: dict[str, list[str]] = {
    "hiring": ["hr"],
    "concierge": ["lead_discovery", "crm"],
    "partner_acquisition": ["lead_discovery", "crm", "email"],
    "creator_campaign": ["lead_discovery", "email"],
    "software_build": ["project_management", "knowledge"],
    "lead_generation": ["lead_discovery", "crm", "analytics"],
    "lead_outreach": ["crm", "email", "followup"],
    "campaign": ["lead_discovery", "crm", "email", "followup", "analytics"],
    "direct_send": ["email"],
    "bulk_send": ["email", "crm"],
    "schedule_meeting": ["calendar"],
    "website_analysis": ["website_analysis", "knowledge"],
    "customer_onboarding": ["crm", "project_management"],
    "invoice_followup": ["finance", "email"],
    "weekly_review": ["analytics"],
    "integration_request": ["email"],
}

# capability -> provider that must verify (if any)
CAPABILITY_PROVIDERS: dict[str, str] = {
    "lead_discovery": "search_tavily",
    "email": "email_sendgrid",
    "messaging": "whatsapp",
    "calendar": "google_calendar",
    "crm": "crm_hubspot",
}


def analyze(db: Session, *, company_id: str, intent: str) -> dict[str, Any]:
    needed = INTENT_CAPABILITIES.get(intent, ["knowledge"])
    enabled = enabled_for(db, company_id=company_id)
    caps: list[dict[str, Any]] = []
    blockers: list[str] = []
    for cap in needed:
        if cap not in CAPABILITIES:
            continue
        if cap not in enabled:
            caps.append({"capability": cap, "status": "NOT_ENABLED",
                         "detail": "not enabled for this workspace plan"})
            blockers.append(f"{cap}: NOT_ENABLED")
            continue
        provider = CAPABILITY_PROVIDERS.get(cap)
        if provider:
            v = verify_provider(provider)
            if not v.get("ok"):
                caps.append({"capability": cap, "status": "NOT_CONFIGURED",
                             "detail": v.get("error", "")})
                blockers.append(f"{cap}: NOT_CONFIGURED ({provider})")
                continue
        caps.append({"capability": cap, "status": "AVAILABLE", "detail": ""})
    # email has an internal fallback (SMTP/file outbox): refine
    for c in caps:
        if c["capability"] == "email" and c["status"] == "NOT_CONFIGURED":
            import os
            if os.environ.get("SMTP_HOST"):
                c["status"] = "AVAILABLE"
                c["detail"] = "via SMTP fallback"
                blockers[:] = [b for b in blockers if not b.startswith("email:")]
    return {
        "intent": intent,
        "capabilities": caps,
        "blockers": blockers,
        "ready": not blockers,
        "next_steps": ([f"Configure {b.split('(')[-1].rstrip(')') or b} in Integrations"
                        for b in blockers] if blockers
                       else ["All required capabilities available — dispatch the command."]),
    }
