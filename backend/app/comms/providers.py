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
        # SMTP fallback if configured (Gmail App Password supported).
        if os.environ.get("SMTP_HOST"):
            try:
                import smtplib
                from email.message import EmailMessage
                msg = EmailMessage()
                msg["From"] = os.environ.get("SMTP_FROM", "maicos@localhost")
                msg["To"] = to
                msg["Subject"] = subject
                msg.set_content(body)
                host = os.environ["SMTP_HOST"]
                port = int(os.environ.get("SMTP_PORT",
                                          "587" if "gmail" in host else "25"))
                user = os.environ.get("SMTP_USER") or os.environ.get("SMTP_FROM")
                password = (os.environ.get("SMTP_PASSWORD")
                            or os.environ.get("SMTP_APP_PASSWORD", "").replace(" ", ""))
                if "gmail" in host:
                    with smtplib.SMTP(host, port, timeout=15) as s:
                        s.starttls()
                        if user and password:
                            s.login(user, password)
                        s.send_message(msg)
                else:
                    with smtplib.SMTP(host, port, timeout=15) as s:
                        if user and password:
                            s.starttls()
                            s.login(user, password)
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
        if channel == "whatsapp":
            token = os.environ.get("WHATSAPP_TOKEN", "")
            phone_id = os.environ.get("WHATSAPP_PHONE_ID", "")
            if not token or not phone_id:
                return _not_configured(
                    "whatsapp", "WHATSAPP_TOKEN/WHATSAPP_PHONE_ID not configured. "
                                "Message not sent.")
            try:
                import httpx
                r = httpx.post(
                    f"https://graph.facebook.com/v19.0/{phone_id}/messages",
                    headers={"Authorization": f"Bearer {token}",
                             "Content-Type": "application/json"},
                    json={"messaging_product": "whatsapp", "to": to,
                          "type": "text", "text": {"body": body[:4000]}},
                    timeout=20.0)
            except Exception as exc:
                return {"ok": False, "status": "FAILED",
                        "error": f"whatsapp request failed: {exc}"[:300]}
            if r.status_code in (401, 403):
                return {"ok": False, "status": "INVALID_CONFIGURATION",
                        "error": "whatsapp token rejected (401/403)"}
            try:
                data = r.json()
            except Exception:
                return {"ok": False, "status": "PROVIDER_ERROR",
                        "error": "whatsapp returned non-JSON"}
            msgs = data.get("messages") or []
            if r.status_code == 200 and msgs:
                return {"ok": True, "status": "SENT", "provider": "whatsapp",
                        "external_id": str(msgs[0].get("id", ""))}
            return {"ok": False, "status": "FAILED",
                    "error": str(data.get("error", data))[:500]}
        return _not_configured(
            channel, f"{channel} provider not configured. Message not sent.")


EMAIL = EmailProvider()
MESSAGING = MessagingProvider()
