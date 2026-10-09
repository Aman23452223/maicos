"""DB-backed follow-up engine. No duplicate follow-ups via idempotency keys."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.audit.service import record
from app.models.orm import CrmActivity, FollowUp, Lead, LeadStatus

DEFAULT_SEQUENCE_DAYS = [0, 2, 5, 10]

PRIORITY_RULE = "lead score >= 70 → high, >= 40 → medium, else normal"


def lead_priority(lead: Lead) -> str:
    """Deterministic priority from the lead's real score (rule documented
    in every output so it stays auditable, never a hidden judgment)."""
    try:
        score = int(lead.score or 0)
    except (TypeError, ValueError):
        score = 0
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "normal"


def schedule_sequence(db: Session, *, company_id: str, lead_id: str,
                      days: list[int] | None = None,
                      channel: str = "email", actor: str = "system") -> dict:
    lead = db.get(Lead, lead_id)
    if not lead or lead.company_id != company_id:
        return {"ok": False, "error": "lead not found"}
    days = days or DEFAULT_SEQUENCE_DAYS
    now = datetime.now(UTC)
    already = db.query(FollowUp).filter(
        FollowUp.company_id == company_id, FollowUp.lead_id == lead_id).count()
    created: list[dict[str, Any]] = []
    for i, d in enumerate(days):
        key = f"followup:{company_id}:{lead_id}:{i}:{d}"
        exists = db.query(FollowUp).filter(FollowUp.idempotency_key == key).first()
        if exists:
            continue
        fu = FollowUp(company_id=company_id, lead_id=lead_id,
                      due_at=now + timedelta(days=d), channel=channel,
                      status="scheduled", attempt=i, idempotency_key=key)
        db.add(fu)
        db.flush()
        created.append({"id": fu.id,
                        "due_at": fu.due_at.isoformat() if fu.due_at else None,
                        "channel": channel, "attempt": i})
    lead.follow_up_status = "scheduled"
    if not lead.next_follow_up_at:
        lead.next_follow_up_at = now + timedelta(days=days[0])
    db.flush()
    record(db, company_id=company_id, actor=actor, action="followup.scheduled",
           target_type="lead", target_id=lead_id, details={"created": len(created)})
    return {"ok": True, "created": len(created),
            "already_scheduled": already,
            "lead_id": lead_id, "lead_name": lead.company_name,
            "lead_status": lead.status.value
            if hasattr(lead.status, "value") else str(lead.status),
            "lead_score": int(lead.score or 0),
            "priority": lead_priority(lead), "priority_rule": PRIORITY_RULE,
            "created_followup_ids": [c["id"] for c in created],
            "followups": created}


def due_followups(db: Session, *, company_id: str, limit: int = 50) -> list[FollowUp]:
    now = datetime.now(UTC)
    return (
        db.query(FollowUp)
        .filter(FollowUp.company_id == company_id,
                FollowUp.status == "scheduled", FollowUp.due_at <= now)
        .order_by(FollowUp.due_at.asc()).limit(limit).all()
    )


def execute_due(db: Session, *, company_id: str, actor: str = "worker",
                send: Any | None = None) -> dict:
    """Execute due follow-ups. Stops on responded/won/lost/opt-out/meeting."""
    from app.comms.providers import EMAIL
    from app.leads.service import touch_contacted

    items = due_followups(db, company_id=company_id)
    sent, skipped = 0, 0
    for fu in items:
        lead = db.get(Lead, fu.lead_id)
        if not lead or lead.company_id != company_id:
            fu.status = "skipped"; continue
        if lead.opted_out or lead.status in (
            LeadStatus.RESPONDED, LeadStatus.MEETING,
            LeadStatus.WON, LeadStatus.LOST, LeadStatus.PROPOSAL,
        ) or lead.last_response_at:
            fu.status = "cancelled"
            fu.result = {"reason": "stop condition"}
            skipped += 1
            continue
        sender = send or EMAIL.send
        try:
            res = sender(to=lead.email or "", subject="Following up",
                         body=f"Hi {lead.company_name}, following up.",
                         idempotency_key=fu.idempotency_key)
        except Exception as exc:
            res = {"ok": False, "status": "FAILED", "error": str(exc)[:300]}
        if res.get("ok"):
            fu.status = "sent"
            fu.result = {"provider": res.get("provider"), "external_id": res.get("external_id")}
            touch_contacted(db, company_id=company_id, lead_id=lead.id)
            lead.next_follow_up_at = None
            sent += 1
        elif res.get("status") == "NOT_CONFIGURED":
            fu.status = "blocked"
            fu.result = {"reason": res.get("error")}
            skipped += 1
        else:
            fu.status = "failed"
            fu.result = {"error": res.get("error")}
            skipped += 1
        db.add(CrmActivity(company_id=company_id, lead_id=lead.id, kind="followup",
                           subject=f"followup {fu.status}", body="",
                           meta={"followup_id": fu.id, **fu.result}, created_by=actor))
    db.flush()
    return {"sent": sent, "skipped": skipped, "checked": len(items)}
