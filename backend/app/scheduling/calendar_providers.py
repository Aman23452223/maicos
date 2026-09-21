"""Calendar providers: internal fallback + Google wiring (Phase 11)."""
from __future__ import annotations

import os
import uuid
from datetime import datetime


def _not_configured(detail: str) -> dict:
    return {"ok": False, "status": "NOT_CONFIGURED", "error": detail}


def availability_lookup(*, start_iso: str, end_iso: str) -> dict:
    """Real freebusy only if Google creds exist; else honest fallback state."""
    if os.environ.get("GOOGLE_CALENDAR_CREDENTIALS"):
        return {"ok": False, "status": "FAILED",
                "error": "google credentials present but calendar sync not yet implemented"}
    return _not_configured("no calendar provider configured; availability unknown")


def create_event(*, title: str, start_iso: str, attendees: list[str],
                 description: str = "") -> dict:
    if os.environ.get("GOOGLE_CALENDAR_CREDENTIALS"):
        try:
            from app.integrations.connectors.google_calendar import GoogleCalendarConnector
            from app.core.context import Principal
            conn = GoogleCalendarConnector()
            p = Principal(user_id="system", workspace_id="system", roles=[])
            res = conn.execute(p, "event.create",
                               {"title": title, "start": start_iso,
                                "attendees": attendees, "description": description})
            if res.ok and res.confirmed:
                try:
                    datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
                except Exception:
                    pass
                return {"ok": True, "status": "BOOKED", "provider": "google",
                        "external_id": res.external_id, "event": res.data}
            return {"ok": False, "status": "FAILED", "error": res.message}
        except Exception as exc:
            return {"ok": False, "status": "FAILED", "error": str(exc)[:500]}
    # Internal fallback: verified local record (not a real external booking)
    try:
        datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
    except Exception:
        return {"ok": False, "status": "FAILED", "error": "invalid start_iso"}
    eid = str(uuid.uuid4())
    return {"ok": True, "status": "BOOKED_INTERNAL",
            "provider": "internal", "external_id": eid,
            "event": {"id": eid, "title": title, "start": start_iso,
                      "attendees": attendees}}
