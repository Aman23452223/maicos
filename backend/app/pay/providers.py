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
    if provider in ("razorpay", "stripe"):
        key = os.environ.get("RAZORPAY_KEY" if provider == "razorpay" else "STRIPE_KEY", "")
        if not key:
            return _not_configured(provider, f"{provider} credentials not configured")
        return {"ok": False, "status": "PROVIDER_ERROR",
                "error": f"{provider} adapter skeleton: wire SDK + webhook here"}
    return {"ok": False, "status": "PROVIDER_ERROR", "error": f"unknown provider {provider}"}


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
    return {"ok": True, "status": "OK", "id": pr.id}
