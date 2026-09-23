"""Modes: startup flow, hiring triage, partner/creator/software intents."""
from __future__ import annotations


def test_startup_idea_validate_blueprint_workspace(client):
    r = client.post("/api/v1/startup/idea", json={"idea": "food delivery in Nagpur"})
    assert r.status_code == 200, r.text
    assert r.json()["source"] == "USER_INPUT"
    r = client.post("/api/v1/startup/validate",
                    json={"idea": "food delivery in Nagpur"})
    assert r.status_code == 200
    assert "research_status" in r.json()
    # blueprint via company endpoint, then save/approve/apply/create workspace
    bp = client.post("/api/v1/company/blueprint",
                     json={"idea": "food delivery in Nagpur"}).json()
    saved = client.post("/api/v1/startup/blueprint",
                        json={"idea": "food delivery in Nagpur",
                              "sections": bp["sections"]}).json()
    assert saved["status"] == "draft"
    client.post(f"/api/v1/startup/blueprints/{saved['id']}/approve")
    applied = client.post(f"/api/v1/startup/blueprints/{saved['id']}/apply").json()
    assert applied["ok"] is True
    ws = client.post("/api/v1/startup/create-workspace",
                     json={"name": "FoodStart", "blueprint_id": saved["id"]}).json()
    assert ws["name"] == "FoodStart"
    # new workspace isolated + usable
    r = client.post("/api/v1/auth/switch", json={"workspace_id": ws["id"]})
    assert r.status_code == 200
    st = client.get("/api/v1/startup/status").json()
    assert st["total"] == len(st["stages"]) and st["readiness"] >= 0


def test_lifecycle_never_invented(client):
    st = client.get("/api/v1/startup/status").json()
    assert set(st["stages"]) >= {"idea", "validate", "build", "launch"}
    assert 0 <= st["readiness"] <= 100


def test_hiring_triage_asks(db, workspace_user):
    from app.agents.base import AgentContext, AgentTask
    from app.agents.implementations.hr import HRAgent
    from app.core.context import Principal

    ws = workspace_user["company"].id
    ctx = AgentContext(db=db, principal=Principal(user_id="u", workspace_id=ws, roles=("owner",)),
                       workflow_id="w", task_id="t", run_id="r",
                       shared={"agent_name": "hr"})
    res = HRAgent().run(
        AgentTask(title="x", description="Find three developers for my company",
                  input={"action": "triage_hiring",
                         "objective": "Find three developers for my company"}),
        ctx)
    assert res.needs_input is not None and "HUMAN" in res.needs_input["question"]
    # decisive human wording proceeds
    res = HRAgent().run(
        AgentTask(title="x", description="Hire a backend developer",
                  input={"action": "triage_hiring",
                         "objective": "Hire a backend developer"}),
        ctx)
    assert res.needs_approval is not None
    assert res.needs_approval["action"] == "hire_human"


def test_new_intents_route():
    from app.agents.implementations.ai_manager import build_plan, classify

    assert classify("We need 5 delivery partners") == "hiring"
    assert classify("Find influencer creators for launch") == "creator_campaign"
    assert classify("Build my website for the store") == "software_build"
    assert classify("Onboard partner restaurants") == "partner_acquisition"
    assert build_plan("Build my website")["tasks"][0]["agent"] == "project_ops"
    assert build_plan("Find creators")["tasks"][0]["input"]["action"] == "discover_creators"


def test_creator_no_key_honest(monkeypatch):
    import os

    from app.leads.creators import discover

    for k in ("SEARCH_PROVIDER_API_KEY", "TAVILY_API_KEY"):
        monkeypatch.delenv(k, raising=False)
        os.environ.pop(k, None)
    out = discover("food creators Nagpur")
    assert out["status"] == "DATA_UNAVAILABLE" and out["creators"] == []


def test_roles_and_events(client):
    r = client.post("/api/v1/startup/roles", json={"title": "Delivery Partner", "kind": "human"})
    assert r.status_code == 200
    roles = client.get("/api/v1/startup/roles").json()
    assert any(x["kind"] == "human" for x in roles)
    assert client.post("/api/v1/startup/roles", json={"title": "X", "kind": "robot"}).status_code == 400
    assert isinstance(client.get("/api/v1/company/events").json(), list)
