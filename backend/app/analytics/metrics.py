"""Metrics computed from DB. Clearly separates actual vs AI interpretation."""
from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.orm import Approval, ApprovalStatus, FollowUp, Lead, LeadStatus, Opportunity, Workflow


def funnel(db: Session, *, company_id: str) -> dict:
    rows = db.query(Lead.status, func.count(Lead.id)).filter(
        Lead.company_id == company_id).group_by(Lead.status).all()
    by_status = {s.value: c for s, c in rows}
    total = sum(by_status.values())
    contacted = sum(by_status.get(k, 0) for k in
                    ("CONTACTED", "RESPONDED", "MEETING", "PROPOSAL", "WON"))
    responded = sum(by_status.get(k, 0) for k in ("RESPONDED", "MEETING", "PROPOSAL", "WON"))
    meetings = sum(by_status.get(k, 0) for k in ("MEETING", "PROPOSAL", "WON"))
    won = by_status.get("WON", 0)
    return {
        "type": "actual",
        "leads_total": total,
        "by_status": by_status,
        "contacted": contacted,
        "responded": responded,
        "meetings": meetings,
        "won": won,
        "response_rate": round(responded / contacted, 3) if contacted else 0.0,
        "conversion_rate": round(won / total, 3) if total else 0.0,
    }


def pipeline(db: Session, *, company_id: str) -> dict:
    rows = db.query(Opportunity.stage, func.count(Opportunity.id),
                    func.coalesce(func.sum(Opportunity.amount), 0)).filter(
        Opportunity.company_id == company_id).group_by(Opportunity.stage).all()
    stages = {s: {"count": c, "value": int(v)} for s, c, v in rows}
    return {"type": "actual", "stages": stages,
            "total_value": sum(v["value"] for v in stages.values())}


def operations(db: Session, *, company_id: str) -> dict:
    wf_total = db.query(Workflow).filter(Workflow.company_id == company_id).count()
    pending_appr = db.query(Approval).filter(
        Approval.company_id == company_id,
        Approval.status == ApprovalStatus.PENDING).count()
    fu_due = db.query(FollowUp).filter(
        FollowUp.company_id == company_id, FollowUp.status == "scheduled").count()
    stuck = db.query(Lead).filter(
        Lead.company_id == company_id,
        Lead.status == LeadStatus.QUALIFIED).count()
    return {"type": "actual", "workflows": wf_total,
            "approvals_pending": pending_appr, "followups_scheduled": fu_due,
            "qualified_not_contacted": stuck}


def weekly_report(db: Session, *, company_id: str) -> dict:
    return {"type": "actual", "funnel": funnel(db, company_id=company_id),
            "pipeline": pipeline(db, company_id=company_id),
            "operations": operations(db, company_id=company_id),
            "note": "All numbers are actual DB counts. AI interpretation must be labeled separately."}
