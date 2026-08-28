"""Adapter: Google Calendar connector.

OAuth2 access token from the secret store. We use the v3 Calendar API.
A real deployment should refresh tokens; the connector is intentionally
minimal so the swap point is obvious.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.core.context import Principal
from app.core.secrets import get_secret
from app.integrations.base import ToolAuthError, ToolResult, register

GCAL_BASE = "https://www.googleapis.com/calendar/v3"


class GoogleCalendarConnector:
    name = "google_calendar"

    def operations(self) -> list[str]:
        return ["event.create", "event.list", "availability.find"]

    def _client(self) -> httpx.Client:
        token = get_secret("GOOGLE_CALENDAR_ACCESS_TOKEN")
        if not token:
            raise ToolAuthError("GOOGLE_CALENDAR_ACCESS_TOKEN not configured")
        return httpx.Client(
            base_url=GCAL_BASE,
            timeout=15.0,
            headers={"Authorization": f"Bearer {token}"},
        )

    def execute(self, principal: Principal, operation: str, payload: dict[str, Any]) -> ToolResult:
        client = self._client()
        try:
            cal = get_secret("GOOGLE_CALENDAR_ID") or "primary"
            if operation == "event.create":
                r = client.post(f"/calendars/{cal}/events", json={
                    "summary": payload.get("title", "Meeting"),
                    "description": payload.get("description", ""),
                    "start": {"dateTime": payload.get("start")},
                    "end": {"dateTime": payload.get("end")},
                    "attendees": [{"email": e} for e in payload.get("attendees", [])],
                })
                ok = r.status_code in (200, 201)
                data = r.json() if ok else {"raw": r.text}
                return ToolResult(ok=ok, confirmed=ok, data=data,
                                  external_id=(data.get("id") if ok else None),
                                  message=None if ok else f"google: {r.status_code}")
            if operation == "event.list":
                r = client.get(f"/calendars/{cal}/events", params={"maxResults": 25})
                ok = r.status_code == 200
                return ToolResult(ok=ok, confirmed=ok,
                                  data=(r.json() if ok else {"raw": r.text}),
                                  message=None if ok else f"google: {r.status_code}")
            if operation == "availability.find":
                # Free/busy is a real Google API; for the MVP we just return
                # a placeholder slot. Replace with /freeBusy when wiring up.
                return ToolResult(ok=True, confirmed=True,
                                  data={"suggested": []},
                                  message="availability lookup not yet implemented")
            return ToolResult(ok=False, confirmed=False, message=f"unsupported: {operation}")
        finally:
            client.close()


def maybe_register() -> None:
    if get_secret("GOOGLE_CALENDAR_ACCESS_TOKEN"):
        register(GoogleCalendarConnector())
