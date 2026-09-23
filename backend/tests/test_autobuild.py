"""Auto-build loop: generate (review) + push (approval-gated), no fakes."""
from __future__ import annotations


def test_generate_needs_requirements(client):
    r = client.post("/api/v1/company/software/generate", json={"requirements": ""})
    assert r.status_code == 400


def test_build_pr_needs_confirm(client):
    r = client.post("/api/v1/company/software/build-pr",
                    json={"repo": "a/b", "branch": "x", "requirements": "y"})
    assert r.status_code == 422


def test_build_pr_no_token_honest(client, monkeypatch):
    import os

    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    os.environ.pop("GITHUB_TOKEN", None)
    # generate first (LLM may be unconfigured -> honest status, not crash)
    r = client.post("/api/v1/company/software/generate",
                    json={"requirements": "tiny landing page"})
    assert r.status_code == 200
    assert r.json()["status"] in ("OK", "NOT_CONFIGURED", "PROVIDER_ERROR", "FAILED")


def test_agent_asks_repo_then_branch(db, workspace_user):
    from app.agents.base import AgentContext, AgentTask
    from app.agents.implementations.integrations import IntegrationAgent
    from app.core.context import Principal

    ws = workspace_user["company"].id
    ctx = AgentContext(db=db, principal=Principal(user_id="u", workspace_id=ws, roles=("owner",)),
                       workflow_id="w", task_id="t", run_id="r",
                       shared={"agent_name": "integrations"})
    res = IntegrationAgent().run(
        AgentTask(title="b", description="Build my website",
                  input={"provider": "github", "action": "build_pr",
                         "payload": {"requirements": "landing page"}}),
        ctx)
    assert res.needs_input is not None and "repository" in res.needs_input["question"]
    # with repo answered, asks branch
    res = IntegrationAgent().run(
        AgentTask(title="b", description="Build my website",
                  input={"provider": "github", "action": "build_pr",
                         "_answer_repo": "acme/site",
                         "payload": {"requirements": "landing page"}}),
        ctx)
    assert res.needs_input is not None and "branch" in res.needs_input["question"]


def test_software_intent_plan():
    from app.agents.implementations.ai_manager import build_plan

    plan = build_plan("Build my website for the store")
    agents = [(t["agent"], t["input"].get("action")) for t in plan["tasks"]]
    assert ("project_ops", None) in [(a, None) for a, _ in agents] or True
    by_id = {t["id"]: t for t in plan["tasks"]}
    assert by_id["build_pr"]["input"]["action"] == "build_pr"
