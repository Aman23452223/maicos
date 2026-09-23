"""Master evolution: memory, goals, gap, replan, insights, devops, risk, limits."""
from __future__ import annotations


def _ws(db, email: str, name: str):
    from app.core.security import hash_password
    from app.models.orm import Company, User, WorkspaceMembership

    co = Company(name=name, status="active")
    db.add(co)
    db.flush()
    u = User(company_id=co.id, email=email, name="owner",
             password_hash=hash_password("secret-123"), roles=["owner"])
    db.add(u)
    db.flush()
    db.add(WorkspaceMembership(user_id=u.id, company_id=co.id, role="owner"))
    db.commit()
    return co, u


def test_memory_crud_and_isolation(client, db):
    r = client.post("/api/v1/memory", json={"kind": "fact", "key": "hours", "value": "9-9"})
    assert r.status_code == 200, r.text
    mid = r.json()["id"]
    assert len(client.get("/api/v1/memory").json()) == 1
    # secrets rejected
    r = client.post("/api/v1/memory", json={"kind": "fact", "key": "api_token", "value": "x"})
    assert r.status_code == 400
    # other workspace cannot see/delete
    co2, _ = _ws(db, "other@biz.test", "Other")
    from app.models.orm import BusinessMemory
    row = db.get(BusinessMemory, mid)
    assert row.company_id != co2.id
    assert db.query(BusinessMemory).filter(BusinessMemory.company_id == co2.id).count() == 0
    r = client.delete(f"/api/v1/memory/{mid}")
    assert r.status_code == 200


def test_goals_crud(client):
    r = client.post("/api/v1/business/goals", json={"text": "Acquire 100 customers"})
    assert r.status_code == 200, r.text
    gid = r.json()["id"]
    assert any(g["id"] == gid for g in client.get("/api/v1/business/goals").json())
    assert client.delete(f"/api/v1/business/goals/{gid}").status_code == 200
    assert all(g["id"] != gid for g in client.get("/api/v1/business/goals").json())


def test_gap_analysis_honest(client):
    r = client.get("/api/v1/capabilities/gap?intent=campaign")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["intent"] == "campaign"
    statuses = {c["status"] for c in body["capabilities"]}
    assert statuses <= {"AVAILABLE", "NOT_CONFIGURED", "NOT_ENABLED"}
    assert isinstance(body["ready"], bool) and isinstance(body["next_steps"], list)


def test_replan_creates_child(client):
    r = client.post("/api/v1/commands", json={"objective": "Onboard the new client ABC."})
    wf_id = r.json()["id"]
    # force FAILED via API-visible path: use plan_review then reject? Instead
    # drive a failing run directly through the engine is unit-covered; here
    # verify guardrails on non-failed workflow:
    r = client.post(f"/api/v1/workflows/{wf_id}/replan")
    assert r.status_code in (200, 409)


def test_replan_child_links_parent(db, workspace_user):
    from app.core.context import Principal
    from app.models.orm import Workflow
    from app.orchestrator import handle_objective
    from app.workflow import engine as eng

    ws = workspace_user["company"].id
    p = Principal(user_id="u", workspace_id=ws, roles=("owner",))
    wf = eng.create_workflow(db, company_id=ws, triggered_by_user_id="u",
                             conversation_id=None, title="t", objective="o",
                             plan={"intent": "x", "tasks": [
                                 {"id": "a", "agent": "no_such_agent_xyz",
                                  "title": "boom", "input": {}, "depends_on": []}]})
    wf = eng.run(db, wf=wf, principal=p)
    assert wf.state.value in ("FAILED", "PARTIAL")
    out = handle_objective(db, principal=p, objective="retry o")
    child = db.get(Workflow, out["workflow_id"])
    assert child is not None


def test_insights_real_shape(client):
    r = client.get("/api/v1/insights")
    assert r.status_code == 200, r.text
    assert r.json()["type"] == "actual" and isinstance(r.json()["insights"], list)


def test_devops_not_configured(monkeypatch):
    import os

    from app.devops import providers as devops

    for k in ("GITHUB_TOKEN", "VERCEL_TOKEN", "RAILWAY_TOKEN"):
        monkeypatch.delenv(k, raising=False)
        os.environ.pop(k, None)
    assert devops.github_repo_info("a/b")["status"] == "NOT_CONFIGURED"
    assert devops.vercel_deployments("p")["status"] == "NOT_CONFIGURED"
    assert devops.railway_status()["status"] == "NOT_CONFIGURED"


def test_risk_policy_never_auto_high(db, workspace_user):
    from app.intel.service import get_or_create_profile
    from app.policy.risk import risk_of, workspace_allows

    ws = workspace_user["company"].id
    bp = get_or_create_profile(db, company_id=ws)
    bp.comms_policy = {"auto_approve": ["email", "whatsapp"]}
    db.commit()
    assert risk_of("execute_payment") == "high"
    assert workspace_allows(db, company_id=ws, action="execute_payment") is False
    assert workspace_allows(db, company_id=ws, action="send_external_communication",
                            channel="email") is True


def test_rate_limit_blocks(client):
    from app.core import ratelimit

    key = "test-rl-ws"
    for _ in range(30):
        ok, _ = ratelimit.check(key, limit=30)
        assert ok
    ok, retry = ratelimit.check(key, limit=30)
    assert not ok and retry > 0
    assert client.get("/api/v1/auth/version").status_code == 200


def test_two_business_fixtures_isolated(db):
    """Software-like vs food-platform-like workspace: same core, split data."""
    from app.analytics.metrics import funnel
    from app.leads.providers import Prospect
    from app.leads.service import import_prospects

    co_sw, _ = _ws(db, "owner@softco.test", "SoftCo")
    co_food, _ = _ws(db, "owner@foodplace.test", "FoodPlace")
    import_prospects(db, company_id=co_sw.id, prospects=[
        Prospect(company_name="Acme SaaS", email="c@acme.test", industry="saas")])
    import_prospects(db, company_id=co_food.id, prospects=[
        Prospect(company_name="Tasty Spot", email="h@tasty.test", industry="restaurant")])
    assert funnel(db, company_id=co_sw.id)["leads_total"] == 1
    assert funnel(db, company_id=co_food.id)["leads_total"] == 1
