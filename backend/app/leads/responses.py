"""Inbound response tracking + classification (Phase 10)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.audit.service import record
from app.leads.normalize import norm_email
from app.models.orm import CrmActivity, InboundMessage, Lead, LeadStatus

KEYWORDS = {
    "OPT_OUT": ("unsubscribe", "opt out", "stop", "remove me"),
    "REQUEST_FOR_MEETING": ("meeting", "call", "schedule", "demo"),
    "REQUEST_FOR_PRICING": ("price", "pricing", "quote", "cost"),
    "NOT_INTERESTED": ("not interested", "no thanks", "pass"),
    "INTERESTED": ("interested", "yes", "sounds good", "let's talk", "lets talk"),
    "OBJECTION": ("too expensive", "budget", "concern"),
    "QUESTION": ("?", "how", "what", "when"),
}


def classify(body: str) -> str:
    low = (body or "").lower()
    for label, kws in KEYWORDS.items():
        if any(k in low for k in kws):
            return label
    if "spam" in low:
        return "SPAM"
    return "NEEDS_HUMAN"


def ingest(db: Session, *, company_id: str, channel: str,
           from_address: str, body: str, actor: str = "webhook") -> dict:
    em = norm_email(from_address)
    lead = None
    if em:
        lead = db.query(Lead).filter(
            Lead.company_id == company_id, Lead.normalized_email == em).first()
    label = classify(body)
    msg = InboundMessage(company_id=company_id, lead_id=lead.id if lead else None,
                         channel=channel, from_address=from_address[:255],
                         body=body[:8000], classification=label)
    db.add(msg)
    db.flush()
    if lead:
        from datetime import UTC, datetime
        lead.last_response_at = datetime.now(UTC)
        if label == "INTERESTED" or label == "REQUEST_FOR_MEETING":
            lead.status = LeadStatus.MEETING if label == "REQUEST_FOR_MEETING" else LeadStatus.RESPONDED
        elif label == "OPT_OUT":
            lead.opted_out = True
            lead.status = LeadStatus.LOST
        elif label == "NOT_INTERESTED":
            lead.status = LeadStatus.LOST
        db.add(CrmActivity(company_id=company_id, lead_id=lead.id, kind="inbound",
                           subject=f"{channel} {label}", body=body[:2000],
                           meta={"message_id": msg.id}, created_by=actor))
    record(db, company_id=company_id, actor=actor, action="inbound.received",
           target_type="inbound_message", target_id=msg.id,
           details={"classification": label, "lead_id": lead.id if lead else None})
    db.flush()
    return {"ok": True, "classification": label,
            "lead_id": lead.id if lead else None, "message_id": msg.id}
