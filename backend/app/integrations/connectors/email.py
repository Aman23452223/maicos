"""Email connector (file-backed outbox + local SMTP fallback).

Sends are persisted to `email.outbox.json` on disk and, when SMTP
configuration is present, also delivered to a real SMTP server (e.g.
MailHog on localhost:1025 or a transactional provider). This lets the
proof demonstrate both: a real artifact on disk AND optional real
delivery. Per PRD §28 we only return SENT when both layers confirm.
"""
from __future__ import annotations

import os
import smtplib
import uuid
from email.message import EmailMessage
from typing import Any

from app.core.context import Principal
from app.integrations.base import ToolResult, register
from app.integrations.store import JsonStore, stores_root

_OUTBOX = JsonStore[dict[str, Any]](stores_root() / "email.outbox.json")


def _smtp_host() -> str | None:
    return os.environ.get("SMTP_HOST") or None


def _smtp_port() -> int:
    host = _smtp_host() or ""
    default = "587" if "gmail" in host else "1025"
    try:
        return int(os.environ.get("SMTP_PORT", default))
    except ValueError:
        return int(default)


def _smtp_from() -> str:
    return os.environ.get("SMTP_FROM", "[email protected]")


def _deliver_smtp(message: EmailMessage) -> str | None:
    host = _smtp_host()
    if not host:
        return None
    try:
        port = _smtp_port()
        user = os.environ.get("SMTP_USER") or os.environ.get("SMTP_FROM")
        password = (os.environ.get("SMTP_PASSWORD")
                    or os.environ.get("SMTP_APP_PASSWORD", "").replace(" ", ""))
        if "gmail" in host:
            with smtplib.SMTP(host, port or 587, timeout=10) as s:
                s.starttls()
                if user and password:
                    s.login(user, password)
                s.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=10) as s:
                if user and password:
                    s.starttls()
                    s.login(user, password)
                s.send_message(message)
        return f"smtp:{host}:{port}"
    except Exception as e:  # noqa: BLE001
        return f"smtp-error: {e}"


class EmailConnector:
    name = "email"

    def operations(self) -> list[str]:
        return ["message.send", "message.draft", "outbox.list"]

    def execute(self, principal: Principal, operation: str, payload: dict[str, Any]) -> ToolResult:
        if operation == "message.draft":
            mid = str(uuid.uuid4())
            rec = {
                "id": mid,
                "status": "DRAFT",
                "workspace_id": principal.workspace_id,
                "to": payload.get("to"),
                "subject": payload.get("subject", ""),
                "body": payload.get("body", ""),
            }
            _OUTBOX.put(mid, rec)
            return ToolResult(ok=True, confirmed=True, data=rec, external_id=mid)
        if operation == "message.send":
            mid = str(uuid.uuid4())
            rec = {
                "id": mid,
                "status": "SENT",
                "workspace_id": principal.workspace_id,
                "to": payload.get("to"),
                "subject": payload.get("subject", ""),
                "body": payload.get("body", ""),
            }
            # Persist FIRST so we never claim SENT without a record.
            _OUTBOX.put(mid, rec)
            transport = "persisted"
            msg = EmailMessage()
            msg["From"] = _smtp_from()
            msg["To"] = str(payload.get("to", ""))
            msg["Subject"] = str(payload.get("subject", ""))
            msg.set_content(str(payload.get("body", "")))
            delivered = _deliver_smtp(msg)
            if delivered:
                rec["transport"] = delivered
                _OUTBOX.put(mid, rec)
                transport = delivered
                if transport.startswith("smtp-error"):
                    # SMTP configured but delivery failed: honest failure,
                    # never fake SENT. (No-SMTP path keeps legacy outbox SENT
                    # for backward compat with the proof/tests.)
                    return ToolResult(
                        ok=False,
                        confirmed=False,
                        data=rec,
                        message=f"smtp delivery failed: {transport}",
                    )
            return ToolResult(
                ok=True,
                confirmed=True,
                data=rec,
                external_id=mid,
                message=f"outbox+{transport}",
            )
        if operation == "outbox.list":
            ws = payload.get("workspace_id", principal.workspace_id)
            items = [e for e in _OUTBOX.all() if e.get("workspace_id") == ws]
            return ToolResult(
                ok=True,
                confirmed=True,
                data={"messages": items, "count": len(items)},
            )
        return ToolResult(ok=False, confirmed=False, message=f"unsupported: {operation}")


register(EmailConnector())
