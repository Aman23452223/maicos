"""Outbound voice calls via Twilio (real). No creds -> NOT_CONFIGURED."""
from __future__ import annotations

import os


def _auth() -> tuple[str, str, str]:
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    from_ = os.environ.get("TWILIO_FROM_NUMBER", "")
    return sid, token, from_


def initiate_call(*, to: str, message: str) -> dict:
    """Start a call that speaks `message` (TwiML Say). Approval enforced upstream."""
    sid, token, from_ = _auth()
    if not (sid and token and from_):
        return {"ok": False, "status": "NOT_CONFIGURED",
                "error": "TWILIO_ACCOUNT_SID/AUTH_TOKEN/FROM_NUMBER not configured"}
    if not to:
        return {"ok": False, "status": "FAILED", "error": "recipient required"}
    twiml = f"<Response><Say>{message[:1000]}</Say></Response>"
    try:
        import httpx
        r = httpx.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls.json",
            auth=(sid, token),
            data={"To": to, "From": from_, "Twiml": twiml}, timeout=20.0)
    except Exception as exc:
        return {"ok": False, "status": "PROVIDER_ERROR", "error": str(exc)[:300]}
    if r.status_code in (401, 403):
        return {"ok": False, "status": "INVALID_CONFIGURATION",
                "error": "Twilio credentials rejected"}
    try:
        data = r.json()
    except Exception:
        return {"ok": False, "status": "PROVIDER_ERROR",
                "error": "Twilio returned non-JSON"}
    if r.status_code not in (200, 201) or "sid" not in data:
        return {"ok": False, "status": "PROVIDER_ERROR",
                "error": str(data)[:300]}
    return {"ok": True, "status": "INITIATED", "provider": "twilio",
            "external_id": data["sid"], "to": to}


def call_status(call_sid: str) -> dict:
    sid, token, _ = _auth()
    if not (sid and token):
        return {"ok": False, "status": "NOT_CONFIGURED",
                "error": "TWILIO credentials not configured"}
    try:
        import httpx
        r = httpx.get(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls/{call_sid}.json",
            auth=(sid, token), timeout=15.0)
        data = r.json()
    except Exception as exc:
        return {"ok": False, "status": "PROVIDER_ERROR", "error": str(exc)[:300]}
    return {"ok": True, "status": "OK",
            "call_status": data.get("status"), "duration": data.get("duration")}
