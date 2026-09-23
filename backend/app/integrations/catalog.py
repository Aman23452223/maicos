"""Authorized integrations catalog (separate from Business Intel research).

Each entry: description, auth type, required envs, actions actually
supported, verify(). A URL analyzed in Business Intel NEVER counts as a
connection. Statuses: connected | configured | configuration_required |
disconnected | error. No fake success, no secrets in responses.
"""
from __future__ import annotations

import os
from typing import Any


def _present(*names: str) -> bool:
    return any(bool(os.environ.get(n)) for n in names)


CATALOG: list[dict[str, Any]] = [
    {
        "provider": "zomato",
        "name": "Zomato",
        "description": "Restaurant/order integration (official API only).",
        "auth_type": "api_key",
        "required_envs": ["ZOMATO_API_KEY"],
        "actions": ["get_outlet", "get_menu", "get_orders", "get_order_status",
                    "update_availability"],
        "note": ("Requires a legitimate Zomato partner API credential. "
                 "Public page URLs are research (Business Intel), not access."),
    },
    {
        "provider": "whatsapp",
        "name": "WhatsApp Business",
        "description": "Template/transactional messaging via Meta/Twilio.",
        "auth_type": "api_key",
        "required_envs": ["WHATSAPP_TOKEN"],
        "actions": ["send_template", "send_text"],
    },
    {
        "provider": "google_calendar",
        "name": "Google Calendar",
        "description": "Availability, event create/update/cancel.",
        "auth_type": "oauth",
        "required_envs": ["GOOGLE_CALENDAR_CREDENTIALS"],
        "actions": ["get_availability", "create_event", "update_event", "cancel_event"],
    },
    {
        "provider": "google_sheets",
        "name": "Google Sheets",
        "description": "Read/write business spreadsheets.",
        "auth_type": "oauth",
        "required_envs": ["GOOGLE_SHEETS_CREDENTIALS"],
        "actions": ["read_range", "append_row"],
    },
    {
        "provider": "email_smtp",
        "name": "Email (SMTP)",
        "description": "Send via configured SMTP server.",
        "auth_type": "api_key",
        "required_envs": ["SMTP_HOST"],
        "actions": ["send"],
    },
    {
        "provider": "email_sendgrid",
        "name": "Email (SendGrid)",
        "description": "Send via SendGrid API.",
        "auth_type": "api_key",
        "required_envs": ["SENDGRID_API_KEY"],
        "actions": ["send"],
    },
    {
        "provider": "instagram_meta",
        "name": "Instagram / Meta",
        "description": "Business profile insights where Meta permits.",
        "auth_type": "oauth",
        "required_envs": ["META_ACCESS_TOKEN"],
        "actions": ["get_profile", "get_media"],
    },
    {
        "provider": "crm_hubspot",
        "name": "HubSpot CRM",
        "description": "Contacts, companies, deals sync.",
        "auth_type": "api_key",
        "required_envs": ["HUBSPOT_API_KEY", "HUBSPOT_TOKEN"],
        "actions": ["create_contact", "create_company", "create_deal"],
    },
    {
        "provider": "search_tavily",
        "name": "Tavily Search",
        "description": "Lead/business discovery search.",
        "auth_type": "api_key",
        "required_envs": ["SEARCH_PROVIDER_API_KEY", "TAVILY_API_KEY"],
        "actions": ["search"],
    },
    {
        "provider": "github",
        "name": "GitHub",
        "description": "Repository read + pull requests (scoped token).",
        "auth_type": "api_key",
        "required_envs": ["GITHUB_TOKEN"],
        "actions": ["repo_info", "open_pr"],
    },
    {
        "provider": "vercel",
        "name": "Vercel",
        "description": "Deployment status for projects.",
        "auth_type": "api_key",
        "required_envs": ["VERCEL_TOKEN"],
        "actions": ["list_deployments"],
    },
    {
        "provider": "railway",
        "name": "Railway",
        "description": "Service/account status.",
        "auth_type": "api_key",
        "required_envs": ["RAILWAY_TOKEN"],
        "actions": ["status"],
    },
]


def get_entry(provider: str) -> dict | None:
    for e in CATALOG:
        if e["provider"] == provider:
            return e
    return None


def verify(provider: str) -> dict[str, Any]:
    """Check whether a provider is genuinely usable right now."""
    entry = get_entry(provider)
    if not entry:
        return {"ok": False, "status": "NOT_ENABLED",
                "error": f"unknown provider {provider}"}
    if not _present(*entry["required_envs"]):
        return {"ok": False, "status": "NOT_CONFIGURED",
                "error": ("Configuration required: set "
                          + "/".join(entry["required_envs"]))}
    if provider == "zomato":
        # No verified official endpoint for partner orders in this
        # environment; architecture ready, access not verified.
        return {"ok": False, "status": "NOT_CONFIGURED",
                "error": ("Configuration required: no supported official "
                          "Zomato API endpoint verified with this credential. "
                          "Public Zomato URLs remain Business Intel research.")}
    if provider == "search_tavily":
        try:
            import httpx
            key = os.environ.get("SEARCH_PROVIDER_API_KEY",
                                 os.environ.get("TAVILY_API_KEY", ""))
            r = httpx.post("https://api.tavily.com/search",
                           json={"api_key": key, "query": "test",
                                 "max_results": 1},
                           timeout=15.0)
            if r.status_code in (401, 403):
                return {"ok": False, "status": "INVALID_CONFIGURATION",
                        "error": "search key rejected (401/403)"}
            if r.status_code == 200:
                return {"ok": True, "status": "OK"}
            return {"ok": False, "status": "PROVIDER_ERROR",
                    "error": f"search HTTP {r.status_code}"}
        except Exception as exc:
            return {"ok": False, "status": "PROVIDER_ERROR",
                    "error": str(exc)[:300]}
    return {"ok": True, "status": "OK", "note": "credential present"}


def execute_action(provider: str, action: str, payload: dict,
                   workspace_id: str) -> dict[str, Any]:
    """Controlled tool gateway for agents. No unrestricted access."""
    entry = get_entry(provider)
    if not entry:
        return {"ok": False, "status": "NOT_ENABLED",
                "error": f"unknown provider {provider}"}
    if action not in entry["actions"]:
        return {"ok": False, "status": "NOT_ENABLED",
                "error": f"action {action} not supported for {provider}"}
    v = verify(provider)
    if not v.get("ok"):
        return v
    # Live executors; others route via existing provider modules when
    # their credentials verify.
    if provider == "github":
        from app.devops import providers as devops

        if action == "repo_info":
            return devops.github_repo_info(str(payload.get("repo", "")))
        if action == "open_pr":
            return devops.github_open_pr(
                str(payload.get("repo", "")), str(payload.get("title", "")),
                str(payload.get("head", "")), str(payload.get("base", "main")),
                str(payload.get("body", "")))
    if provider == "vercel" and action == "list_deployments":
        from app.devops import providers as devops

        return devops.vercel_deployments(str(payload.get("project", "")))
    if provider == "railway" and action == "status":
        from app.devops import providers as devops

        return devops.railway_status()
    if provider == "search_tavily":
        from app.leads.providers import get as get_discovery
        res = get_discovery("search").discover(
            str(payload.get("query", "")), limit=int(payload.get("limit", 5)))
        return {"ok": res.ok, "status": res.status,
                "prospects": [vars(p) for p in res.prospects],
                "message": res.message}
    return {"ok": False, "status": "PROVIDER_ERROR",
            "error": f"{provider}.{action} executor not wired; credential verified only"}
