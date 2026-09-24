"""7 workload items: staff tasks, digest, voice, razorpay, inbox, pipeline."""
from __future__ import annotations


def test_staff_tasks_flow(client):
    team = client.get("/api/v1/company/team").json()
    assert len(team) >= 1
    me = team[0]["id"]
    r = client.post("/api/v1/company/tasks", json={"title": "Call Sharma", "assignee_user_id": me})
    assert r.status_code == 200, r.text
    tid = r.json()["id"]
    mine = client.get("/api/v1/company/tasks/mine").json()
    assert any(t["id"] == tid for t in mine)
    assert client.post(f"/api/v1/company/tasks/{tid}/state",
                       json={"state": "COMPLETED"}).status_code == 200
    # cross-workspace teammate rejected
    r = client.post("/api/v1/company/tasks", json={"title": "x", "assignee_user_id": "nope"})
    assert r.status_code == 404


def test_digest_intent_and_send(client):
    from app.agents.implementations.ai_manager import build_plan, classify

    assert classify("send the morning digest") == "morning_digest"
    assert build_plan("subah ki report bhejo")["tasks"][0]["input"]["action"] == "send_digest"
    r = client.post("/api/v1/commands", json={"objective": "Send the morning business digest."})
    assert r.status_code == 200


def test_voice_razorpay_honest(monkeypatch):
    import os

    from app.voice import providers as voice
    from app.pay import providers as pay

    for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER",
              "RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET"):
        monkeypatch.delenv(k, raising=False)
        os.environ.pop(k, None)
    assert voice.initiate_call(to="+919999999999", message="hi")["status"] == "NOT_CONFIGURED"
    assert voice.call_status("x")["status"] == "NOT_CONFIGURED"
    assert pay.create_razorpay_link(amount_paise=100, description="t")["status"] == "NOT_CONFIGURED"
    assert pay.razorpay_link_status("x")["status"] == "NOT_CONFIGURED"


def test_inbox_and_reply_policy(client, db, workspace_user):
    from app.leads.providers import Prospect
    from app.leads.responses import ingest
    from app.leads.service import import_prospects

    ws = workspace_user["company"].id
    out = import_prospects(db, company_id=ws, prospects=[
        Prospect(company_name="Inbox Co", email="i@inbox.test")])
    ingest(db, company_id=ws, channel="email", from_address="i@inbox.test",
           body="What are your prices?")
    db.commit()
    threads = client.get("/api/v1/inbox").json()
    assert len(threads) == 1 and threads[0]["messages"][0]["body"].startswith("What are")
    # no auto-send by default -> 409 with guidance
    r = client.post("/api/v1/inbox/reply",
                    json={"lead_id": out["ids"][0], "to": "", "body": "Hi!"})
    assert r.status_code == 409


def test_pipeline_move(client):
    r = client.post("/api/v1/opportunities", json={"title": "Deal A", "amount": 50000})
    oid = r.json()["id"]
    assert len(client.get("/api/v1/opportunities").json()) >= 1
    r = client.patch(f"/api/v1/opportunities/{oid}", json={"stage": "meeting"})
    assert r.json()["stage"] == "meeting"
    assert client.patch(f"/api/v1/opportunities/{oid}", json={"status": "bogus"}).status_code == 400
