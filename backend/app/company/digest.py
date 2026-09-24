"""Morning business digest: real numbers, auto-sent to the owner."""
from __future__ import annotations

from sqlalchemy.orm import Session


def build_digest(db: Session, *, company_id: str) -> str:
    from app.analytics.metrics import funnel, operations, pipeline
    from app.company.checkup import run_checkup

    fun = funnel(db, company_id=company_id)
    pipe = pipeline(db, company_id=company_id)
    ops = operations(db, company_id=company_id)
    try:
        check = run_checkup(db, company_id=company_id, actor="digest")
        signals = check.get("signals", [])
    except Exception:
        signals = []
    lines = ["Good morning! Your business digest:",
             f"- Leads: {fun.get('leads_total', 0)} total, "
             f"{fun.get('responded', 0)} responded, {fun.get('meetings', 0)} meetings, "
             f"{fun.get('won', 0)} won",
             f"- Pipeline value: {pipe.get('total_value', 0)}",
             f"- Follow-ups scheduled: {ops.get('followups_scheduled', 0)}",
             f"- Approvals waiting: {ops.get('approvals_pending', 0)}",
             f"- Qualified, not contacted: {ops.get('qualified_not_contacted', 0)}"]
    for s in signals[:5]:
        lines.append(f"- [{s.get('severity')}] {s.get('title')}")
    return "\n".join(lines)[:4000]


def send_to_owner(db: Session, *, company_id: str) -> dict:
    """Send digest to the workspace owner email (internal report, no approval)."""
    from app.comms.providers import EMAIL
    from app.models.orm import User

    owner = db.query(User).filter(
        User.company_id == company_id,
        User.is_active.is_(True)).first()
    # Prefer an owner-role user.
    for u in db.query(User).filter(User.company_id == company_id).all():
        if "owner" in (u.roles or []):
            owner = u
            break
    if not owner or not owner.email:
        return {"ok": False, "status": "FAILED", "error": "no owner email"}
    text = build_digest(db, company_id=company_id)
    return EMAIL.send(to=owner.email, subject="Morning business digest", body=text)
