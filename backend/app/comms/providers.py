"""Email + messaging providers. Real sends only; no fake WhatsApp."""
from __future__ import annotations

import os
import uuid


def _not_configured(provider: str, detail: str) -> dict:
    return {"ok": False, "status": "NOT_CONFIGURED", "provider": provider, "error": detail}


class EmailProvider:
    name = "email"

    def draft(self, *, to: str, subject: str, body: str) -> dict:
        return {"ok": True, "status": "DRAFT",
                "draft": {"to": to, "subject": subject, "body": body}}

    def send(self, *, to: str, subject: str, body: str,
             idempotency_key: str = "") -> dict:
        # Prefer SendGrid if configured
        if os.environ.get("SENDGRID_API_KEY"):
            try:
                from app.integrations.connectors.sendgrid_email import SendGridEmailConnector
                from app.core.context import Principal
                conn = SendGridEmailConnector()
                p = Principal(user_id="system", workspace_id="system", roles=[])
                res = conn.execute(p, "message.send",
                                   {"to": to, "subject": subject, "body": body})
                if res.ok and res.confirmed:
                    return {"ok": True, "status": "SENT", "provider": "sendgrid",
                            "external_id": res.external_id}
                return {"ok": False, "status": "FAILED",
                        "error": res.message or "sendgrid rejected"}
            except Exception as exc:
                return {"ok": False, "status": "FAILED", "error": str(exc)[:500]}
        # SMTP fallback if configured
        if os.environ.get("SMTP_HOST"):
            try:
                import smtplib
                from email.message import EmailMessage
                msg = EmailMessage()
                msg["From"] = os.environ.get("SMTP_FROM", "maicos@localhost")
                msg["To"] = to
                msg["Subject"] = subject
                msg.set_content(body)
                with smtplib.SMTP(os.environ["SMTP_HOST"],
                                  int(os.environ.get("SMTP_PORT", "25")),
                                  timeout=15) as s:
                    s.send_message(msg)
                return {"ok": True, "status": "SENT", "provider": "smtp",
                        "external_id": str(uuid.uuid4())}
            except Exception as exc:
                return {"ok": False, "status": "FAILED", "error": str(exc)[:500]}
        # No provider: persist a draft, never claim SENT
        return _not_configured(
            "email", "no email provider configured (SENDGRID_API_KEY or SMTP_HOST). "
                     "Draft prepared but not sent.")


class MessagingProvider:
    name = "messaging"

    def send(self, *, to: str, body: str, channel: str = "whatsapp") -> dict:
        if channel == "whatsapp" and os.environ.get("WHATSAPP_TOKEN"):
            return {"ok": False, "status": "FAILED",
                    "error": "whatsapp provider skeleton only; wire Meta/Twilio API here"}
        return _not_configured(
            channel, f"{channel} provider not configured. Message not sent.")


EMAIL = EmailProvider()
MESSAGING = MessagingProvider()
