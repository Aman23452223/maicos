"""Proactive company checkup: metrics -> persistent signals + plans."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.orm import CompanySignal


def run_checkup(db: Session, *, company_id: str, actor: str = "system") -> dict:
    from app.analytics.metrics import funnel, operations, pipeline

    fun = funnel(db, company_id=company_id)
    pipe = pipeline(db, company_id=company_id)
    ops = operations(db, company_id=company_id)
    candidates: list[dict] = []
    if fun.get("response_rate", 0) < 0.1 and fun.get("contacted", 0) > 0:
        candidates.append({"kind": "issue", "severity": "high",
                           "title": "Low response rate",
                           "detail": f"Response rate {fun['response_rate']}."})
    n = ops.get("qualified_not_contacted", 0)
    if n:
        candidates.append({"kind": "issue", "severity": "medium",
                           "title": f"{n} qualified leads never contacted",
                           "detail": "Stalled pipeline."})
    if ops.get("followups_scheduled", 0):
        candidates.append({"kind": "opportunity", "severity": "medium",
                           "title": "Follow-ups ready to run",
                           "detail": f"{ops['followups_scheduled']} scheduled."})
    if ops.get("approvals_pending", 0):
        candidates.append({"kind": "issue", "severity": "medium",
                           "title": f"{ops['approvals_pending']} approvals waiting",
                           "detail": "Execution blocked on human review."})
    if pipe.get("total_value", 0) > 0:
        candidates.append({"kind": "opportunity", "severity": "low",
                           "title": f"Pipeline value {pipe['total_value']}",
                           "detail": "Open opportunities tracked."})
    created = 0
    for c in candidates:
        exists = db.query(CompanySignal).filter(
            CompanySignal.company_id == company_id,
            CompanySignal.kind == c["kind"], CompanySignal.title == c["title"],
            CompanySignal.status == "open").first()
        if exists:
            continue
        db.add(CompanySignal(company_id=company_id, kind=c["kind"],
                             severity=c["severity"], title=c["title"],
                             detail=c["detail"]))
        created += 1
    from app.audit.service import record
    record(db, company_id=company_id, actor=actor, action="company.checkup",
           target_type="company", target_id=company_id,
           details={"signals_created": created})
    db.commit()
    return {"type": "actual", "signals_created": created,
            "signals": candidates,
            "metrics": {"funnel": fun, "pipeline": pipe, "operations": ops}}
