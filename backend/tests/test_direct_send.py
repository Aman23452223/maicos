"""One-shot send: intent routing, channel honesty, auto-approve policy."""
from __future__ import annotations


def test_direct_send_intent_and_parse():
    from app.agents.implementations.ai_manager import build_plan, classify

    assert classify("send email to boss@co.test about Diwali offer") == "direct_send"
    assert classify("whatsapp kar 9876543210 new offer aaya hai") == "direct_send"
    assert classify("story dal new offer ki") == "direct_send"
    assert classify("Show today's Zomato orders.") == "integration_request"

    plan = build_plan("send email to boss@co.test about Diwali offer")
    assert plan["intent"] == "direct_send"
    t = plan["tasks"][0]
    assert t["agent"] == "communication" and t["input"]["channel"] == "email"
    assert t["input"]["to"] == "boss@co.test"

    plan = build_plan("story dal new offer ki")
    assert plan["tasks"][0]["input"]["channel"] == "story"


def test_story_rejected_honestly(db, workspace_user):
    from app.agents.base import AgentContext, AgentTask
    from app.agents.implementations.communication import CommunicationAgent
    from app.core.context import Principal

    ws = workspace_user["company"].id
    ctx = AgentContext(db=db, principal=Principal(user_id="u", workspace_id=ws, roles=("owner",)),
                       workflow_id="w", task_id="t", run_id="r",
                       shared={"agent_name": "communication"})
    res = CommunicationAgent().run(
        AgentTask(title="x", description="",
                  input={"action": "send", "channel": "story", "to": "x",
                         "body": "hi"}), ctx)
    assert res.error and "story" in res.error.lower()


def test_missing_recipient_fails(db, workspace_user):
    from app.agents.base import AgentContext, AgentTask
    from app.agents.implementations.communication import CommunicationAgent
    from app.core.context import Principal

    ws = workspace_user["company"].id
    ctx = AgentContext(db=db, principal=Principal(user_id="u", workspace_id=ws, roles=("owner",)),
                       workflow_id="w", task_id="t", run_id="r",
                       shared={"agent_name": "communication"})
    res = CommunicationAgent().run(
        AgentTask(title="x", description="",
                  input={"action": "send", "channel": "email", "to": "",
                         "body": "hi"}), ctx)
    assert res.error and "recipient" in res.error.lower()


def test_whatsapp_not_configured_without_creds(db, workspace_user, monkeypatch):
    import os

    from app.agents.base import AgentContext, AgentTask
    from app.agents.implementations.communication import CommunicationAgent
    from app.core.context import Principal

    monkeypatch.delenv("WHATSAPP_TOKEN", raising=False)
    monkeypatch.delenv("WHATSAPP_PHONE_ID", raising=False)
    ws = workspace_user["company"].id
    # auto-approve whatsapp so it attempts delivery (no approval gate)
    from app.intel.service import get_or_create_profile
    bp = get_or_create_profile(db, company_id=ws)
    bp.comms_policy = {"auto_approve": ["whatsapp"]}
    db.commit()
    ctx = AgentContext(db=db, principal=Principal(user_id="u", workspace_id=ws, roles=("owner",)),
                       workflow_id="w", task_id="t", run_id="r",
                       shared={"agent_name": "communication"})
    res = CommunicationAgent().run(
        AgentTask(title="x", description="",
                  input={"action": "send", "channel": "whatsapp",
                         "to": "919876543210", "body": "hi"}), ctx)
    assert res.error and "not configured" in res.error.lower()


def test_auto_approve_skips_approval(db, workspace_user):
    from app.agents.base import AgentContext, AgentTask
    from app.agents.implementations.communication import CommunicationAgent
    from app.core.context import Principal

    ws = workspace_user["company"].id
    from app.intel.service import get_or_create_profile
    bp = get_or_create_profile(db, company_id=ws)
    bp.comms_policy = {"auto_approve": ["email"]}
    db.commit()
    ctx = AgentContext(db=db, principal=Principal(user_id="u", workspace_id=ws, roles=("owner",)),
                       workflow_id="w", task_id="t", run_id="r",
                       shared={"agent_name": "communication"})
    # No SMTP configured: legacy connector still outbox-SENTs (compat);
    # key assertion: no needs_approval gate.
    res = CommunicationAgent().run(
        AgentTask(title="x", description="",
                  input={"action": "send", "channel": "email",
                         "to": "a@b.test", "subject": "hi", "body": "hello"}), ctx)
    assert res.needs_approval is None


def test_approval_gate_by_default(db, workspace_user):
    from app.agents.base import AgentContext, AgentTask
    from app.agents.implementations.communication import CommunicationAgent
    from app.core.context import Principal

    ws = workspace_user["company"].id
    ctx = AgentContext(db=db, principal=Principal(user_id="u", workspace_id=ws, roles=("owner",)),
                       workflow_id="w", task_id="t", run_id="r",
                       shared={"agent_name": "communication"})
    res = CommunicationAgent().run(
        AgentTask(title="x", description="",
                  input={"action": "send", "channel": "email",
                         "to": "a@b.test", "subject": "hi", "body": "hello"}), ctx)
    assert res.needs_approval is not None
    assert res.needs_approval["target_system"] == "email"
