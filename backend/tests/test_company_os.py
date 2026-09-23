"""Company OS: brain, manager, workforce, blueprint, software, checkup."""
from __future__ import annotations


def test_memory_types_and_secret_rejection(db, workspace_user):
    from app.company.brain import recall, remember

    ws = workspace_user["company"].id
    remember(db, company_id=ws, kind="FACT", key="hours", value="9-9")
    remember(db, company_id=ws, kind="AI_RECOMMENDATION", key="idea", value="try X")
    kinds = {m["kind"] for m in recall(db, company_id=ws)}
    assert {"FACT", "AI_RECOMMENDATION"} <= kinds
    try:
        remember(db, company_id=ws, kind="FACT", key="api_token", value="x")
        raise SystemExit("should have raised")
    except ValueError:
        pass
    try:
        remember(db, company_id=ws, kind="NOPE", key="k", value="v")
        raise SystemExit("should have raised")
    except ValueError:
        pass


def test_manager_run_and_investigate(client):
    r = client.post("/api/v1/company/run",
                    json={"objective": "Find restaurants in Nagpur", "plan_review": True})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["state"] == "WAITING_APPROVAL"
    assert body["workforce"]["manager"] == "AI Company Manager"
    assert body["company"]
    r = client.post("/api/v1/company/investigate",
                    json={"question": "Revenue dropped this month."})
    assert r.status_code == 200 and r.json()["type"] == "analysis"
    assert r.json()["candidate_causes"]


def test_workforce_compose_generic():
    from app.company.workforce import compose

    roster = compose("campaign", ["crm", "email"])
    roles = {t["role"] for t in roster["team"]}
    assert "Communication Worker" in roles
    assert set(roster["missing_capabilities"]) == {"lead_discovery", "followup", "analytics"}
    assert all(t["available"] == (t["capability"] in ("crm", "email"))
               for t in roster["team"])
    # no industry names anywhere in roster
    blob = str(roster).lower()
    assert "zomato" not in blob and "restaurant" not in blob


def test_blueprint_flow(client):
    r = client.post("/api/v1/company/blueprint",
                    json={"idea": "AI-powered clothing rental marketplace"})
    assert r.status_code == 200, r.text
    bp = r.json()
    assert bp["sections"]["mvp_scope"]["status"] == "recommendation"
    r = client.post("/api/v1/company/blueprint/apply", json={"blueprint": bp})
    assert r.status_code == 200 and r.json()["ok"] is True
    goals = client.get("/api/v1/business/goals").json()
    assert len(goals) >= 3


def test_software_honest_without_tokens(monkeypatch):
    import os

    from app.company import software

    for k in ("GITHUB_TOKEN", "VERCEL_TOKEN"):
        monkeypatch.delenv(k, raising=False)
        os.environ.pop(k, None)
    assert software.analyze_repo("a/b")["status"] == "NOT_CONFIGURED"
    assert software.plan_as_pr("a/b", title="t", plan_markdown="x",
                               head="")["status"] == "FAILED"
    assert software.deployment_status("nope", "")["status"] == "NOT_ENABLED"
    assert software.smoke_test("http://127.0.0.1:9/nope")["status"] == "PROVIDER_ERROR"


def test_checkup_signals_persist(client, db, workspace_user):
    from app.leads.providers import Prospect
    from app.leads.service import import_prospects
    from app.models.orm import Lead, LeadStatus

    ws = workspace_user["company"].id
    out = import_prospects(db, company_id=ws, prospects=[
        Prospect(company_name="Stale Co", email="s@stale.test")])
    lead = db.get(Lead, out["ids"][0])
    lead.status = LeadStatus.QUALIFIED
    db.commit()
    r = client.post("/api/v1/company/checkup")
    assert r.status_code == 200, r.text
    sigs = client.get("/api/v1/company/signals").json()
    assert any("never contacted" in s["title"] or "qualified" in s["title"].lower()
               for s in sigs)
    # rerun dedups
    n = len(client.get("/api/v1/company/signals").json())
    client.post("/api/v1/company/checkup")
    assert len(client.get("/api/v1/company/signals").json()) == n


def test_decisions_initiatives_events_projects(client):
    assert client.post("/api/v1/company/decisions",
                       json={"title": "Use Postgres-first", "context": "ops"}).status_code == 200
    assert len(client.get("/api/v1/company/decisions").json()) == 1
    r = client.post("/api/v1/company/initiatives", json={"title": "Launch MVP"})
    assert r.status_code == 200
    assert len(client.get("/api/v1/company/initiatives").json()) == 1
    assert isinstance(client.get("/api/v1/company/events").json(), list)
    assert isinstance(client.get("/api/v1/company/projects").json(), list)


def test_autonomy_and_usage(client):
    auto = client.get("/api/v1/company/autonomy").json()
    assert auto["levels"]["5"] == "Human approval required"
    assert auto["actions"]["deploy_production"] == 5
    usage = client.get("/api/v1/usage").json()
    assert usage["type"] == "estimate" and "tool_calls" in usage


def test_company_context_and_workforce_api(client):
    ctx = client.get("/api/v1/company/context").json()
    assert "metrics" in ctx and "memory" in ctx
    wf = client.get("/api/v1/company/workforce?intent=lead_generation").json()
    assert wf["manager"] == "AI Company Manager" and wf["team"]
