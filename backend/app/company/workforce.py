"""Dynamic workforce composer: capabilities -> reusable worker roster.

No hardcoded permanent agents beyond the existing 12 registered workers.
Composition derives from intent + enabled capabilities + company context.
"""
from __future__ import annotations

from typing import Any

# capability -> (worker role label, agent name)
WORKER_MAP: dict[str, tuple[str, str]] = {
    "website_analysis": ("Research Worker", "knowledge"),
    "knowledge": ("Research Worker", "knowledge"),
    "lead_discovery": ("Sales Worker", "sales_crm"),
    "lead_enrichment": ("Sales Worker", "sales_crm"),
    "qualification": ("Sales Worker", "sales_crm"),
    "scoring": ("Sales Worker", "sales_crm"),
    "crm": ("CRM Worker", "sales_crm"),
    "email": ("Communication Worker", "communication"),
    "messaging": ("Communication Worker", "communication"),
    "calendar": ("Communication Worker", "calendar"),
    "followup": ("Sales Worker", "sales_crm"),
    "proposal": ("Product Worker", "sales_crm"),
    "customer_onboarding": ("Project Manager Worker", "project_ops"),
    "project_management": ("Project Manager Worker", "project_ops"),
    "support": ("Support Worker", "customer_support"),
    "analytics": ("Analytics Worker", "analytics"),
    "reporting": ("Analytics Worker", "analytics"),
    "finance": ("Finance Worker", "finance"),
    "hr": ("HR Worker", "hr"),
    "marketing": ("Marketing Worker", "marketing"),
}

# intent -> capabilities the outcome needs (generic, composable)
INTENT_WORKFORCE: dict[str, list[str]] = {
    "hiring": ["hr"],
    "concierge": ["lead_discovery", "crm", "analytics"],
    "partner_acquisition": ["lead_discovery", "crm", "email", "followup",
                            "analytics"],
    "creator_campaign": ["lead_discovery", "email", "analytics"],
    "software_build": ["project_management", "knowledge", "analytics"],
    "lead_generation": ["lead_discovery", "lead_enrichment", "qualification",
                        "scoring", "crm", "analytics"],
    "campaign": ["lead_discovery", "crm", "email", "followup", "analytics"],
    "lead_outreach": ["crm", "email", "followup"],
    "customer_onboarding": ["crm", "project_management", "knowledge"],
    "schedule_meeting": ["calendar"],
    "website_analysis": ["website_analysis", "knowledge", "analytics"],
    "invoice_followup": ["finance", "email"],
    "weekly_review": ["analytics"],
    "onboard_client": ["crm", "project_management", "calendar", "email"],
    "integration_request": ["email"],
}


def compose(intent: str, enabled: list[str],
            context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return {manager, team[], missing[]} for an intent."""
    needed = INTENT_WORKFORCE.get(intent, ["knowledge", "analytics"])
    team: list[dict[str, Any]] = []
    seen: set[str] = set()
    for cap in needed:
        role, agent = WORKER_MAP.get(cap, ("General Worker", "knowledge"))
        key = (role, agent)
        if key in seen:
            continue
        seen.add(key)
        team.append({"role": role, "agent": agent, "capability": cap,
                     "available": cap in enabled})
    missing = [c for c in needed if c not in enabled]
    return {"manager": "AI Company Manager", "intent": intent, "team": team,
            "missing_capabilities": missing,
            "business": (context or {}).get("business_name", "")}
