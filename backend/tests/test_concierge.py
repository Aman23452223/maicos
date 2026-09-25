"""Concierge tasks + live run steps (Instinct-style progress, honest)."""
from __future__ import annotations


def test_concierge_intent():
    from app.agents.implementations.ai_manager import build_plan, classify

    assert classify("book a hotel in Goa for next weekend") == "concierge"
    assert classify("order vegetarian pizza at my address") == "concierge"
    plan = build_plan("book a hotel in Goa")
    assert plan["intent"] == "concierge"
    assert [t["agent"] for t in plan["tasks"]] == [
        "sales_crm", "sales_crm", "communication"]
    # no fake booking/success claims anywhere
    blob = str(plan).lower()
    assert "booking confirmed" not in blob and "order placed" not in blob
    assert "payment successful" not in blob


def test_runs_endpoint_shows_steps(client):
    r = client.post("/api/v1/commands", json={"objective": "Onboard the new client ABC."})
    wf_id = r.json()["id"]
    runs = client.get(f"/api/v1/workflows/{wf_id}/runs").json()
    assert isinstance(runs, list) and len(runs) > 0
    assert all("steps" in x and "task_id" in x for x in runs)
    # cross-workspace blocked
    assert client.get("/api/v1/workflows/nope/runs").status_code == 404
