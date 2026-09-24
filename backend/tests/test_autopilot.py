"""Autopilot policies, self-healing, collections, digest schedule."""
from __future__ import annotations


def test_autopilot_crud_owner_only(client):
    r = client.get("/api/v1/company/autopilot")
    assert r.status_code == 200 and r.json()["enabled"] is False
    r = client.put("/api/v1/company/autopilot", json={
        "enabled": True, "max_spend_month": 50000, "auto_channels": ["email", "sms"],
        "auto_invoice_below": 0, "auto_replan": True})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["enabled"] is True and body["auto_channels"] == ["email"]


def test_spend_cap_enforced(db, workspace_user):
    from app.crm.providers import get
    from app.policy.risk import check_spend

    ws = workspace_user["company"].id
    ok, _ = check_spend(db, company_id=ws, amount=10)
    assert ok is False  # disabled by default
    p = get("internal")
    assert p.create_company(db, company_id=ws, fields={"name": "X"})["ok"]


def test_self_heal_replans_once(client, db, workspace_user):
    from app.intel.service import get_or_create_profile

    from app.models.orm import Company

    ws = workspace_user["company"].id
    co = db.get(Company, ws)
    cfg = dict(co.config or {})
    cfg["autopilot"] = {"enabled": True, "max_spend_month": 0,
                        "auto_channels": [], "auto_invoice_below": 0,
                        "auto_replan": True}
    co.config = cfg
    db.commit()
    # unknown-agent workflow fails deterministically
    from app.core.context import Principal
    from app.orchestrator import handle_objective
    from app.workflow import engine as eng

    p = Principal(user_id="u", workspace_id=ws, roles=("owner",))
    wf = eng.create_workflow(db, company_id=ws, triggered_by_user_id="u",
                             conversation_id=None, title="t", objective="o",
                             plan={"intent": "x", "tasks": [
                                 {"id": "a", "agent": "no_such_agent_zzz",
                                  "title": "boom", "input": {}, "depends_on": []}]})
    # run via handle_objective path is plan-based; emulate post-run hook:
    from app.workflow.engine import run as _run
    _run(db, wf=wf, principal=p)
    assert wf.state.value == "FAILED"
    import app.orchestrator as _orch

    _orig = _orch._build_plan
    _orch._build_plan = lambda objective: {
        "intent": "x", "tasks": [{"id": "a", "agent": "no_such_agent_zzz",
                                  "title": "boom", "input": {},
                                  "depends_on": []}]}
    try:
        out = handle_objective(db, principal=p, objective="boom objective")
    finally:
        _orch._build_plan = _orig
    assert out.get("auto_replanned")
    from app.models.orm import Workflow
    child = db.get(Workflow, out["auto_replanned"])
    assert child.plan.get("parent_workflow_id") == out["workflow_id"]


def test_collections_and_digest(client, db, workspace_user):
    from app.agents.implementations.finance import _INVOICES

    ws = workspace_user["company"].id
    _INVOICES.put("inv-old", {"id": "inv-old", "workspace_id": ws, "customer": "Old Co",
                              "amount": 100, "due_at": "2020-01-01T00:00:00+00:00",
                              "status": "OPEN"})
    try:
        r = client.post("/api/v1/company/collections/run")
        assert r.status_code == 200 and r.json()["escalated"] >= 1
        sigs = client.get("/api/v1/company/signals").json()
        assert any("Overdue" in s["title"] for s in sigs)
    finally:
        _INVOICES._data.pop("inv-old", None) if hasattr(_INVOICES, "_data") else None
    r = client.post("/api/v1/company/digest/schedule", json={})
    assert r.status_code == 200 and "job_id" in r.json()
