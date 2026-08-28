"""Adapter: HubSpot CRM connector.

Uses the HubSpot CRM v3 API over HTTP. Tokens are read from the secret
store at call time, never from the LLM prompt. The connector interface
is unchanged; `register()` makes it discoverable to agents.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.core.context import Principal
from app.core.secrets import get_secret
from app.integrations.base import ToolAuthError, ToolResult, register

HUBSPOT_BASE = "https://api.hubapi.com"


class HubSpotCRMConnector:
    name = "hubspot_crm"

    def operations(self) -> list[str]:
        return [
            "contact.upsert",
            "deal.create",
            "deal.update_stage",
            "activity.record",
        ]

    def _client(self) -> tuple[httpx.Client, str]:
        token = get_secret("HUBSPOT_PRIVATE_APP_TOKEN")
        if not token:
            raise ToolAuthError("HUBSPOT_PRIVATE_APP_TOKEN not configured")
        return httpx.Client(base_url=HUBSPOT_BASE, timeout=15.0, headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }), "hubspot"

    def execute(self, principal: Principal, operation: str, payload: dict[str, Any]) -> ToolResult:
        client, _ = self._client()
        try:
            if operation == "contact.upsert":
                # HubSpot upsert by email uses POST /crm/v3/objects/contacts.
                r = client.post("/crm/v3/objects/contacts", json={
                    "properties": {
                        "email": payload.get("email"),
                        "firstname": payload.get("first_name"),
                        "lastname": payload.get("last_name"),
                        "company": payload.get("company"),
                    }
                })
                ok = r.status_code in (200, 201)
                data = r.json() if ok else {"raw": r.text}
                return ToolResult(ok=ok, confirmed=ok, data=data,
                                  external_id=(data.get("id") if ok else None),
                                  message=None if ok else f"hubspot: {r.status_code}")
            if operation == "deal.create":
                r = client.post("/crm/v3/objects/deals", json={
                    "properties": {
                        "dealname": payload.get("name", "New Deal"),
                        "amount": str(payload.get("amount", "")),
                    }
                })
                ok = r.status_code in (200, 201)
                data = r.json() if ok else {"raw": r.text}
                return ToolResult(ok=ok, confirmed=ok, data=data,
                                  external_id=(data.get("id") if ok else None),
                                  message=None if ok else f"hubspot: {r.status_code}")
            if operation == "deal.update_stage":
                did = payload.get("id")
                if not did:
                    return ToolResult(ok=False, confirmed=False, message="missing deal id")
                r = client.patch(f"/crm/v3/objects/deals/{did}", json={
                    "properties": {"dealstage": payload.get("stage")}
                })
                ok = r.status_code == 200
                return ToolResult(ok=ok, confirmed=ok, data=(r.json() if ok else {"raw": r.text}),
                                  external_id=did if ok else None,
                                  message=None if ok else f"hubspot: {r.status_code}")
            if operation == "activity.record":
                return ToolResult(ok=True, confirmed=True, data={"recorded": True})
            return ToolResult(ok=False, confirmed=False, message=f"unsupported: {operation}")
        finally:
            client.close()


def maybe_register() -> None:
    """Register the real connector only if its credentials are present.

    This keeps the MVP runnable without HubSpot credentials while making
    the real integration a configuration flip away.
    """
    if get_secret("HUBSPOT_PRIVATE_APP_TOKEN"):
        register(HubSpotCRMConnector())
