"""Consolidated CRM report must reflect real records only.

Regression cover:
- `ceo_brief` without a caller summary previously returned the hardcoded
  "Sales up 12%. Two invoices overdue. One project blocked." Now it
  composes strictly from this workspace's DB/store records, and says
  plainly when an area is empty.
- `schedule_sequence` (and the sales batch path) previously returned bare
  counts. Reports now carry actual lead names, priorities, due dates and
  created follow-up IDs.
- Nothing missing/failed is ever marked successful.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta


def _ctx(db, ws):
    from app.agents.base import AgentContext
    from app.core.context import Principal
    return AgentContext(db=db, principal=Principal(user_id="u", workspace_id=ws, roles=("owner",)),
                        workflow_id="w", task_id="t", run_id="r",
                        shared={"agent_name": "analytics"})


def _brief(db, ws, action_input=None):
    from app.agents.base import AgentTask
    from app.agents.implementations.analytics import AnalyticsAgent
    return AnalyticsAgent().run(
        AgentTask(title="CEO brief", description="brief",
                  input={"action": "ceo_brief", **(action_input or {})}),
        _ctx(db, ws))


def test_ceo_brief_empty_workspace_claims_nothing(db, workspace_user):
    ws = workspace_user["company"].id
    res = _brief(db, ws)
    assert res.error is None, res.error
    out = res.output
    assert out.get("source") == "actual"
    text = (out.get("summary") or "")
    assert "12%" not in text and "Two invoices" not in text and "blocked" not in text
    assert "No leads" in text
    assert out.get("needs_attention") == []


def test_ceo_brief_reports_real_numbers_and_names(db, workspace_user):
    from app.models.orm import Company, Lead, LeadStatus, Opportunity

    ws = workspace_user["company"].id
    other = Company(name="Other Co")
    db.add(other)
    db.flush()
    db.add(Lead(company_id=ws, company_name="Acme", status=LeadStatus.QUALIFIED, score=80))
    db.add(Lead(company_id=ws, company_name="Beta", status=LeadStatus.CONTACTED, score=50))
    db.add(Opportunity(company_id=ws, title="Acme deal", amount=5000, stage="proposal"))
    db.add(Lead(company_id=other.id, company_name="Foreign", status=LeadStatus.QUALIFIED,
                score=90))
    db.commit()

    from app.agents.implementations.finance import _INVOICES
    past = (datetime.now(UTC) - timedelta(days=3)).isoformat()
    _INVOICES.put("inv-rep-1", {"id": "inv-rep-1", "workspace_id": ws,
                                "customer": "Globex", "amount": 199.0,
                                "due_at": past, "status": "OPEN"})
    _INVOICES.put("inv-rep-foreign", {"id": "inv-rep-foreign",
                                      "workspace_id": other.id,
                                      "customer": "ForeignCo", "amount": 999.0,
                                      "due_at": past, "status": "OPEN"})
    try:
        res = _brief(db, ws)
        assert res.error is None, res.error
        out = res.output
        text = out.get("summary") or ""
        assert "12%" not in text, text
        assert "2 leads" in text, text
        assert "5000" in text, text
        assert "Globex" in text, text
        assert "Foreign" not in text and "ForeignCo" not in text, text
        kinds = {n.get("kind") for n in out.get("needs_attention") or []}
        assert "overdue_invoices" in kinds and "stuck_leads" in kinds, kinds
        assert out["metrics"]["overdue_invoices"] == 1
    finally:
        for key in ("inv-rep-1", "inv-rep-foreign"):
            try:
                _INVOICES.delete(key)
            except Exception:
                pass


def test_ceo_brief_explicit_summary_kept(db, workspace_user):
    ws = workspace_user["company"].id
    res = _brief(db, ws, {"summary": "Board-approved Q3 note."})
    assert res.error is None, res.error
    assert res.output.get("summary") == "Board-approved Q3 note."
    assert res.output.get("source") == "caller"


def test_schedule_sequence_returns_names_dates_ids(db, workspace_user):
    from app.models.orm import FollowUp, Lead, LeadStatus
    from app.scheduling.followups import schedule_sequence

    ws = workspace_user["company"].id
    lead = Lead(company_id=ws, company_name="Acme", status=LeadStatus.QUALIFIED,
                score=85)
    db.add(lead)
    db.commit()
    out = schedule_sequence(db, company_id=ws, lead_id=lead.id)
    assert out.get("ok") is True
    assert out.get("lead_name") == "Acme"
    assert out.get("priority") == "high"
    assert "score" in (out.get("priority_rule") or "")
    assert out.get("created") == 4
    ids = out.get("created_followup_ids") or []
    assert len(ids) == 4
    rows = db.query(FollowUp).filter(FollowUp.lead_id == lead.id).all()
    assert {r.id for r in rows} == set(ids)
    dues = [f.get("due_at") for f in out.get("followups") or []]
    assert len(dues) == 4 and all(d for d in dues)
    assert dues == sorted(dues)
    # Idempotent rerun creates nothing new.
    again = schedule_sequence(db, company_id=ws, lead_id=lead.id)
    assert again.get("created") == 0
    assert db.query(FollowUp).filter(FollowUp.lead_id == lead.id).count() == 4


def test_sales_batch_reports_per_lead_entries(db, workspace_user):
    from app.agents.base import AgentTask
    from app.agents.implementations.sales_crm import SalesCRMAgent
    from app.models.orm import Lead, LeadStatus

    ws = workspace_user["company"].id
    db.add(Lead(company_id=ws, company_name="High Co", status=LeadStatus.QUALIFIED,
                score=90))
    db.add(Lead(company_id=ws, company_name="Low Co", status=LeadStatus.CONTACTED,
                score=10))
    db.commit()
    res = SalesCRMAgent().run(
        AgentTask(title="x", description="schedule them all",
                  input={"action": "schedule_followups"}),
        _ctx(db, ws))
    assert res.error is None, res.error
    out = res.output
    assert out.get("sequences_created") == 8
    by_name = {e["lead_name"]: e for e in out.get("leads") or []}
    assert set(by_name) == {"High Co", "Low Co"}
    assert by_name["High Co"]["priority"] == "high"
    assert by_name["Low Co"]["priority"] == "normal"
    for entry in by_name.values():
        assert len(entry["created_followup_ids"]) == 4
        assert len(entry["due_dates"]) == 4
