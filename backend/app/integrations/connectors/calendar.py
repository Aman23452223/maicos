"""Calendar connector (file-backed local store).

Real events are persisted to `calendar.events.json` on disk and can
be observed externally. A real Google Calendar / Outlook adapter
should replace this when the corresponding credentials are
configured (see connectors/google_calendar.py).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.context import Principal
from app.integrations.base import ToolResult, register
from app.integrations.store import JsonStore, stores_root

_EVENTS = JsonStore[dict[str, Any]](stores_root() / "calendar.events.json")


class CalendarConnector:
    name = "calendar"

    def operations(self) -> list[str]:
        return ["event.create", "event.list", "availability.find", "event.delete"]

    def execute(self, principal: Principal, operation: str, payload: dict[str, Any]) -> ToolResult:
        if operation == "event.create":
            eid = str(uuid.uuid4())
            rec = {
                "id": eid,
                "workspace_id": principal.workspace_id,
                "status": "CONFIRMED",
                "title": payload.get("title", "Meeting"),
                "start": payload.get("start"),
                "end": payload.get("end"),
                "attendees": payload.get("attendees", []),
            }
            _EVENTS.put(eid, rec)
            return ToolResult(ok=True, confirmed=True, data=rec, external_id=eid,
                              message="persisted to calendar.events.json")
        if operation == "event.list":
            ws = payload.get("workspace_id", principal.workspace_id)
            events = [e for e in _EVENTS.all() if e.get("workspace_id") == ws]
            return ToolResult(ok=True, confirmed=True, data={"events": events, "count": len(events)})
        if operation == "availability.find":
            # Suggest the next business hour slot 1 day from now.
            suggestion = (datetime.now(UTC) + timedelta(days=1)).replace(
                hour=10, minute=0, second=0, microsecond=0
            ).isoformat()
            return ToolResult(ok=True, confirmed=True, data={"suggested": [suggestion]})
        if operation == "event.delete":
            eid_raw = payload.get("id")
            eid_lookup = eid_raw if isinstance(eid_raw, str) else None
            if not eid_lookup or not _EVENTS.get(eid_lookup):
                return ToolResult(ok=False, confirmed=False, message="event not found")
            _EVENTS.delete(eid_lookup)
            return ToolResult(ok=True, confirmed=True, data={"deleted": eid})
        return ToolResult(ok=False, confirmed=False, message=f"unsupported: {operation}")


register(CalendarConnector())
