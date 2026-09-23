"""Plan review/edit + meeting/campaign intents (no credentials)."""
from __future__ import annotations


def test_meeting_and_campaign_intents():
    from app.agents.implementations.ai_manager import (
        _parse_meeting_datetime,
        build_plan,
        classify,
    )

    assert classify("schedule meeting with Aman tomorrow 3pm") == "schedule_meeting"
    plan = build_plan("schedule meeting with Aman tomorrow 3pm")
    assert plan["tasks"][0]["agent"] == "calendar"
    assert plan["tasks"][0]["input"].get("start")

    plan = build_plan("schedule meeting with Neha")
    assert plan["tasks"][0]["input"].get("needs_date") is True

    assert classify("Diwali campaign chalana hai") == "campaign"
    plan = build_plan("Diwali campaign chalana hai for our store")
    agents = [t["agent"] for t in plan["tasks"]]
    assert agents == ["sales_crm", "sales_crm", "communication",
                      "communication", "sales_crm", "analytics"]

    assert _parse_meeting_datetime("meet monday 10am") is not None
    assert _parse_meeting_datetime("just meet sometime") is None


def test_plan_review_flow(client):
    r = client.post("/api/v1/commands", json={
        "objective": "Find restaurants in Nagpur", "plan_review": True})
    assert r.status_code == 200, r.text
    wf_id = r.json()["id"]
    assert r.json()["state"] == "WAITING_APPROVAL"
    # nothing executed yet
    tasks = client.get(f"/api/v1/workflows/{wf_id}/tasks").json()
    assert all(t["state"] == "PENDING" for t in tasks)
    # resume must refuse before plan approval
    r = client.post(f"/api/v1/workflows/{wf_id}/resume")
    assert r.status_code == 409
    # edit a task
    t0 = tasks[0]
    r = client.patch(f"/api/v1/workflows/{wf_id}/tasks/{t0['id']}",
                     json={"title": t0["title"] + " (edited)"})
    assert r.status_code == 200 and r.json()["title"].endswith("(edited)")
    # approve plan -> auto-runs
    ap = [a for a in client.get("/api/v1/approvals?status=PENDING").json()
          if a["action"] == "plan_review" and a["workflow_id"] == wf_id]
    assert len(ap) == 1
    r = client.post(f"/api/v1/approvals/{ap[0]['id']}/decision",
                    json={"decision": "APPROVE"})
    assert r.status_code == 200
    wf = client.get(f"/api/v1/workflows/{wf_id}").json()
    assert wf["state"] in ("COMPLETED", "PARTIAL", "FAILED", "WAITING_APPROVAL", "RUNNING")


def test_plan_reject_cancels(client):
    r = client.post("/api/v1/commands", json={
        "objective": "Find restaurants in Nagpur", "plan_review": True})
    wf_id = r.json()["id"]
    ap = [a for a in client.get("/api/v1/approvals?status=PENDING").json()
          if a["action"] == "plan_review" and a["workflow_id"] == wf_id][0]
    client.post(f"/api/v1/approvals/{ap['id']}/decision", json={"decision": "REJECT"})
    wf = client.get(f"/api/v1/workflows/{wf_id}").json()
    assert wf["state"] == "CANCELLED"


def test_patch_rejected_states(client):
    r = client.post("/api/v1/commands", json={"objective": "Onboard the new client ABC."})
    wf_id = r.json()["id"]
    tasks = client.get(f"/api/v1/workflows/{wf_id}/tasks").json()
    done = [t for t in tasks if t["state"] == "COMPLETED"]
    if done:
        r = client.patch(f"/api/v1/workflows/{wf_id}/tasks/{done[0]['id']}",
                         json={"title": "x"})
        assert r.status_code == 409
