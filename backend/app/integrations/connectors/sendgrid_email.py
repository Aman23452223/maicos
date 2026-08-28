"""Adapter: SendGrid email connector.

Uses the SendGrid v3 API. API key comes from the secret store, never
the LLM prompt. Per PRD §28, we only return SENT when the provider
returns 202.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.core.context import Principal
from app.core.secrets import get_secret
from app.integrations.base import ToolAuthError, ToolResult, register

SENDGRID_BASE = "https://api.sendgrid.com/v3"


class SendGridEmailConnector:
    name = "sendgrid_email"

    def operations(self) -> list[str]:
        return ["message.send"]

    def _client(self) -> httpx.Client:
        token = get_secret("SENDGRID_API_KEY")
        if not token:
            raise ToolAuthError("SENDGRID_API_KEY not configured")
        return httpx.Client(
            base_url=SENDGRID_BASE,
            timeout=15.0,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )

    def execute(self, principal: Principal, operation: str, payload: dict[str, Any]) -> ToolResult:
        if operation != "message.send":
            return ToolResult(ok=False, confirmed=False, message=f"unsupported: {operation}")
        sender = get_secret("SENDGRID_FROM_EMAIL")
        if not sender:
            return ToolResult(ok=False, confirmed=False, message="SENDGRID_FROM_EMAIL not configured")
        body = {
            "personalizations": [{"to": [{"email": payload.get("to")}]}],
            "from": {"email": sender},
            "subject": payload.get("subject", ""),
            "content": [{"type": "text/plain", "value": payload.get("body", "")}],
        }
        client = self._client()
        try:
            r = client.post("/mail/send", json=body)
            ok = r.status_code == 202  # SendGrid accepts async
            if not ok:
                return ToolResult(ok=False, confirmed=False,
                                  data={"raw": r.text}, message=f"sendgrid: {r.status_code}")
            return ToolResult(
                ok=True,
                confirmed=True,
                data={"to": payload.get("to"), "subject": payload.get("subject")},
                message="provider accepted",
            )
        finally:
            client.close()


def maybe_register() -> None:
    if get_secret("SENDGRID_API_KEY") and get_secret("SENDGRID_FROM_EMAIL"):
        register(SendGridEmailConnector())
