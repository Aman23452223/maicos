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


def test_ceo_brief_singular_lead_grammar(db, workspace_user):
    from app.models.orm import Lead

    ws = workspace_user["company"].id
    db.add(Lead(company_id=ws, company_name="Solo"))
    db.commit()
    res = _brief(db, ws)
    assert res.error is None, res.error
    assert "1 lead in CRM" in (res.output.get("summary") or "")


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
    assert again.get("already_scheduled") == 4
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
    rerun = SalesCRMAgent().run(
        AgentTask(title="x", description="schedule again",
                  input={"action": "schedule_followups"}),
        _ctx(db, ws))
    rerun_leads = {e["lead_name"]: e for e in
                   (rerun.output or {}).get("leads") or []}
    assert rerun_leads["High Co"]["created"] == 0
    assert rerun_leads["High Co"]["already_scheduled"] == 4


def test_batch_reports_population_considered_vs_skipped(db, workspace_user):
    """Every record is accounted for: scored vs settled-skipped."""
    from app.agents.base import AgentTask
    from app.agents.implementations.sales_crm import SalesCRMAgent
    from app.models.orm import Lead, LeadStatus

    ws = workspace_user["company"].id
    db.add(Lead(company_id=ws, company_name="Fresh", status=LeadStatus.NEW))
    db.add(Lead(company_id=ws, company_name="Old", status=LeadStatus.DISQUALIFIED,
                score=5))
    db.commit()
    out = SalesCRMAgent().run(
        AgentTask(title="x", description="qualify batch",
                  input={"action": "qualify_batch"}),
        _ctx(db, ws)).output
    assert out.get("considered") == 1, out
    # Fresh was scored in this run and settled DISQUALIFIED too.
    assert out.get("skipped_settled", {}).get("DISQUALIFIED") == 2, out
    assert out.get("scored") == 1


def test_clients_report_reconciles_with_records(db, workspace_user, client):
    from app.models.orm import FollowUp, Lead, LeadStatus
    from datetime import UTC, datetime

    ws = workspace_user["company"].id
    a = Lead(company_id=ws, company_name="Acme", email="a@acme.test",
             status=LeadStatus.QUALIFIED, score=85,
             notes="looking for atta supply")
    b = Lead(company_id=ws, company_name="Junk", status=LeadStatus.DISQUALIFIED,
             score=5)
    db.add_all([a, b])
    db.flush()
    db.add(FollowUp(company_id=ws, lead_id=a.id,
                    due_at=datetime.now(UTC), channel="email",
                    status="scheduled", attempt=0, idempotency_key="k-rep-1"))
    db.commit()

    r = client.get("/api/v1/reports/clients")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("type") == "actual"
    s = body["summary"]
    assert s["crm_records"] == 2
    assert s["scored"] == 2 and s["qualified"] == 1 and s["disqualified"] == 1
    assert s["new_unscored"] == 0
    assert s["followups_total"] == 1 and s["followups_scheduled"] == 1
    by_name = {c["name"]: c for c in body["clients"]}
    acme = by_name["Acme"]
    assert acme["decision"] == "in follow-up"
    assert acme["priority"] == "high" and acme["score"] == 85
    assert len(acme["followup_ids"]) == 1 and acme["next_due_at"]
    assert "atta" in (acme["requirements_note"] or "").lower()
    assert by_name["Junk"]["decision"] == "disqualified"
    assert "60" in by_name["Junk"]["reason"]


def test_followup_empty_is_explained_not_silent(db, workspace_user):
    """The reported bug: COMPLETED with sequences_created 0 and no reason.

    Root cause was NOT scheduling/persistence — ineligible leads (NEW /
    DISQUALIFIED) simply match nothing. The fix reports WHY per lead.
    """
    from app.agents.base import AgentTask
    from app.agents.implementations.sales_crm import SalesCRMAgent
    from app.models.orm import Lead, LeadStatus

    ws = workspace_user["company"].id
    db.add(Lead(company_id=ws, company_name="Fresh Co", status=LeadStatus.NEW,
                score=0))
    db.add(Lead(company_id=ws, company_name="Junk Co", status=LeadStatus.DISQUALIFIED,
                score=10))
    db.commit()

    ctx = _ctx(db, ws)
    res = SalesCRMAgent().run(
        AgentTask(title="x", description="schedule them all",
                  input={"action": "schedule_followups"}),
        ctx)
    assert res.error is None, res.error
    out = res.output
    assert out.get("sequences_created") == 0 and out.get("leads") == []
    assert "Qualif" in (out.get("reason") or ""), out
    assert out.get("lead_status_breakdown", {}).get("NEW") == 1
    assert out.get("lead_status_breakdown", {}).get("DISQUALIFIED") == 1
    by_name = {e["lead_name"]: e for e in out.get("ineligible_leads") or []}
    assert "not yet qualified" in by_name["Fresh Co"]["reason"]
    assert "disqualified" in by_name["Junk Co"]["reason"]


def test_discovered_prospects_not_counted_until_saved(db, workspace_user):
    """Discovery output and CRM counts stay separate until import persists."""
    from app.analytics.metrics import funnel
    from app.leads.providers import Prospect
    from app.leads.service import import_prospects
    from app.models.orm import Lead

    ws = workspace_user["company"].id
    # Discovered (e.g. Tavily) but never imported: not a CRM lead.
    ghosts = [Prospect(company_name="Ghost Co", website="https://ghost.test")]
    assert funnel(db, company_id=ws)["leads_total"] == 0
    assert db.query(Lead).filter(Lead.company_id == ws).count() == 0

    imp = import_prospects(db, company_id=ws, prospects=[
        Prospect(company_name="Real Co", email="r@real.test")], actor="user")
    db.commit()
    assert imp["created"] == 1
    assert funnel(db, company_id=ws)["leads_total"] == 1
    names = [l.company_name for l in
             db.query(Lead).filter(Lead.company_id == ws).all()]
    assert names == ["Real Co"] and "Ghost Co" not in names
    _ = ghosts


def _run_action(db, ws, action, action_input=None):
    from app.agents.base import AgentTask
    from app.agents.implementations.sales_crm import SalesCRMAgent
    from app.core.context import Principal
    from app.agents.base import AgentContext
    ctx = AgentContext(db=db, principal=Principal(user_id="u", workspace_id=ws,
                                                 roles=("owner",)),
                       workflow_id="w", task_id="t", run_id="r",
                       shared={"agent_name": "sales_crm"})
    return SalesCRMAgent().run(
        AgentTask(title="x", description="x",
                  input={"action": action, **(action_input or {})}), ctx)


def test_batch_scoring_reports_attained_statuses_not_inflated(db, workspace_user):
    """'qualified: N' previously counted scorings, not QUALIFIED outcomes."""
    from app.models.orm import Lead, LeadStatus

    ws = workspace_user["company"].id
    db.add(Lead(company_id=ws, company_name="Good Co", email="g@good.test",
                industry="", location="", notes="looking for supply",
                status=LeadStatus.NEW, score=0))
    db.add(Lead(company_id=ws, company_name="Junk Co", status=LeadStatus.NEW,
                score=0))
    db.commit()
    for action in ("qualify_batch", "qualify", "score"):
        out = _run_action(db, ws, action).output
        assert "qualified" not in out, (action, out)
        assert out.get("scored", 0) >= 1, (action, out)
        assert isinstance(out.get("became_qualified"), int)
        assert isinstance(out.get("leads"), list) and out["leads"], (action, out)
        for e in out["leads"]:
            assert {"lead_id", "lead_name", "score", "status"} <= set(e), e


def test_deduplicate_reports_without_merging(db, workspace_user):
    from app.models.orm import Lead, LeadStatus

    ws = workspace_user["company"].id
    db.add(Lead(company_id=ws, company_name="Acme", status=LeadStatus.NEW,
                score=0, domain="acme.test"))
    db.add(Lead(company_id=ws, company_name="Acme Inc", status=LeadStatus.NEW,
                score=0, domain="acme.test"))
    db.commit()
    before = db.query(Lead).filter(Lead.company_id == ws).count()
    out = _run_action(db, ws, "deduplicate").output
    after = db.query(Lead).filter(Lead.company_id == ws).count()
    assert after == before  # reported, never auto-merged
    groups = out.get("possible_duplicate_groups") or []
    assert any(g["count"] >= 2 for g in groups), groups
    assert out.get("scored", 0) >= 2
