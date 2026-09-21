"""Won opportunity -> Customer -> project/tasks -> verify (generic)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.audit.service import record
from app.models.orm import Customer, Lead, Opportunity

DEFAULT_CHECKLIST = ["Confirm requirements", "Collect documents",
                     "Assign owner", "Schedule kickoff", "Verify completion"]


def onboard(db: Session, *, company_id: str, opportunity_id: str,
            actor: str = "user") -> dict:
    opp = db.get(Opportunity, opportunity_id)
    if not opp or opp.company_id != company_id:
        return {"ok": False, "status": "FAILED", "error": "opportunity not found"}
    if opp.status != "won":
        return {"ok": False, "status": "FAILED",
                "error": "opportunity must be WON before onboarding"}
    lead = db.get(Lead, opp.lead_id) if opp.lead_id else None
    cust = Customer(company_id=company_id, lead_id=opp.lead_id,
                    name=opp.title or (lead.company_name if lead else "Customer"),
                    email=lead.email if lead else None,
                    onboarding_state="in_progress",
                    checklist=list(DEFAULT_CHECKLIST))
    db.add(cust)
    db.flush()
    # Reuse project engine via orchestrator (no second task system)
    try:
        from app.core.context import Principal
        from app.orchestrator import handle_objective
        principal = Principal(user_id=actor, workspace_id=company_id, roles=["owner"])
        res = handle_objective(
            db, principal=principal,
            objective=f"Onboard customer {cust.name}: {', '.join(DEFAULT_CHECKLIST)}")
        workflow_id = res.get("workflow_id")
    except Exception as exc:
        workflow_id = None
        cust.extra = {"workflow_error": str(exc)[:300]}
    record(db, company_id=company_id, actor=actor, action="customer.onboarded",
           target_type="customer", target_id=cust.id,
           details={"workflow_id": workflow_id})
    db.flush()
    return {"ok": True, "status": "OK", "customer_id": cust.id,
            "workflow_id": workflow_id, "checklist": DEFAULT_CHECKLIST}
