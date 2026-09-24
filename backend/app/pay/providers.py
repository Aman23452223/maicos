"""Payment providers: manual + Razorpay/Stripe skeletons (no fake success)."""
from __future__ import annotations

import os
import uuid

from sqlalchemy.orm import Session

from app.audit.service import record
from app.models.orm import PaymentRequest


def _not_configured(provider: str, detail: str) -> dict:
    return {"ok": False, "status": "NOT_CONFIGURED", "provider": provider, "error": detail}


def create_request(db: Session, *, company_id: str, amount: int,
                   currency: str = "INR", provider: str = "manual",
                   opportunity_id: str | None = None, actor: str = "user") -> dict:
    provider = (provider or "manual").lower()
    if provider == "manual":
        pr = PaymentRequest(company_id=company_id, opportunity_id=opportunity_id,
                            provider="manual", amount=int(amount), currency=currency,
                            status="pending", provider_ref=str(uuid.uuid4()))
        db.add(pr)
        db.flush()
        record(db, company_id=company_id, actor=actor, action="payment.requested",
               target_type="payment", target_id=pr.id,
               details={"amount": amount, "currency": currency})
        return {"ok": True, "status": "PENDING", "id": pr.id}
    if provider == "stripe":
        if not os.environ.get("STRIPE_KEY"):
            return _not_configured(provider, "STRIPE_KEY not configured")
        return {"ok": False, "status": "PROVIDER_ERROR",
                "error": "Stripe adapter: use Razorpay for INR or request Stripe wiring"}
    return {"ok": False, "status": "PROVIDER_ERROR", "error": f"unknown provider {provider}"}


def create_razorpay_link(*, amount_paise: int, description: str,
                         customer: dict | None = None) -> dict:
    """Create a real Razorpay payment link (no charge until customer pays)."""
    key_id = os.environ.get("RAZORPAY_KEY_ID", "")
    secret = os.environ.get("RAZORPAY_KEY_SECRET", "")
    if not (key_id and secret):
        return _not_configured("razorpay", "RAZORPAY_KEY_ID/RAZORPAY_KEY_SECRET not configured")
    if not amount_paise or amount_paise <= 0:
        return {"ok": False, "status": "FAILED", "error": "amount required"}
    try:
        import httpx
        r = httpx.post("https://api.razorpay.com/v1/payment_links",
                       auth=(key_id, secret),
                       json={"amount": int(amount_paise), "currency": "INR",
                             "description": description[:255] or "Payment",
                             "customer": {k: v for k, v in (customer or {}).items() if v}},
                       timeout=20.0)
    except Exception as exc:
        return {"ok": False, "status": "PROVIDER_ERROR", "error": str(exc)[:300]}
    if r.status_code == 401:
        return {"ok": False, "status": "INVALID_CONFIGURATION",
                "error": "Razorpay credentials rejected"}
    try:
        data = r.json()
    except Exception:
        return {"ok": False, "status": "PROVIDER_ERROR",
                "error": "Razorpay returned non-JSON"}
    if r.status_code not in (200, 201) or "id" not in data:
        return {"ok": False, "status": "PROVIDER_ERROR",
                "error": str(data.get("error", data))[:300]}
    return {"ok": True, "status": "LINK_CREATED", "provider": "razorpay",
            "external_id": data["id"], "short_url": data.get("short_url", "")}


def razorpay_link_status(link_id: str) -> dict:
    key_id = os.environ.get("RAZORPAY_KEY_ID", "")
    secret = os.environ.get("RAZORPAY_KEY_SECRET", "")
    if not (key_id and secret):
        return _not_configured("razorpay", "RAZORPAY_KEY_ID/RAZORPAY_KEY_SECRET not configured")
    try:
        import httpx
        r = httpx.get(f"https://api.razorpay.com/v1/payment_links/{link_id}",
                      auth=(key_id, secret), timeout=15.0)
        data = r.json()
    except Exception as exc:
        return {"ok": False, "status": "PROVIDER_ERROR", "error": str(exc)[:300]}
    return {"ok": True, "status": "OK", "link_status": data.get("status"),
            "amount_paid": data.get("amount_paid", 0)}


def webhook(db: Session, *, company_id: str, provider: str,
            provider_ref: str, status: str) -> dict:
    pr = db.query(PaymentRequest).filter(
        PaymentRequest.company_id == company_id,
        PaymentRequest.provider_ref == provider_ref).first()
    if not pr:
        return {"ok": False, "status": "VERIFICATION_FAILED", "error": "unknown reference"}
    pr.status = status
    db.flush()
    record(db, company_id=company_id, actor=f"{provider}_webhook",
           action="payment.updated", target_type="payment", target_id=pr.id,
           details={"status": status})
    try:
        from app.company.events import emit

        emit(db, company_id=company_id,
             type="payment.received" if status in ("paid", "captured", "succeeded")
             else "payment.failed",
             payload={"payment_id": pr.id, "status": status})
    except Exception:
        pass
    return {"ok": True, "status": "OK", "id": pr.id}
