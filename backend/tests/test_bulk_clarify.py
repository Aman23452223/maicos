"""Bulk send + clarification roundtrip (no real credentials)."""
from __future__ import annotations


def _ctx(db, ws):
    from app.agents.base import AgentContext
    from app.core.context import Principal
    return AgentContext(db=db, principal=Principal(user_id="u", workspace_id=ws, roles=("owner",)),
                        workflow_id="w", task_id="t", run_id="r",
                        shared={"agent_name": "communication"})


def test_bulk_intent_routing():
    from app.agents.implementations.ai_manager import build_plan, classify

    assert classify("send email to all clients Diwali offer") in ("direct_send", "bulk_send")
    plan = build_plan("send email to all clients Diwali offer")
    assert plan["tasks"][0]["input"]["action"] == "bulk_send"


def test_bulk_asks_when_no_recipients(db, workspace_user):
    from app.agents.base import AgentTask
    from app.agents.implementations.communication import CommunicationAgent

    ws = workspace_user["company"].id
    res = CommunicationAgent().run(
        AgentTask(title="x", description="send email to all",
                  input={"action": "bulk_send", "channel": "email",
                         "bulk_query": "send email to all", "body": "hi"}),
        _ctx(db, ws))
    assert res.needs_input is not None and "Kaunse" in res.needs_input["question"]
    assert res.needs_approval is None


def test_bulk_named_resolution_and_approval(db, workspace_user):
    from app.agents.base import AgentTask
    from app.agents.implementations.communication import CommunicationAgent
    from app.leads.providers import Prospect
    from app.leads.service import import_prospects

    ws = workspace_user["company"].id
    import_prospects(db, company_id=ws, prospects=[
        Prospect(company_name="Aman Foods", email="aman@x.test"),
        Prospect(company_name="Neha Sweets", email="neha@x.test")])
    res = CommunicationAgent().run(
        AgentTask(title="x", description='send email to "Aman Foods"',
                  input={"action": "bulk_send", "channel": "email",
                         "bulk_query": 'send email to "Aman Foods"',
                         "subject": "Offer", "body": "Hi {{name}}"}),
        _ctx(db, ws))
    # approval gate (default policy) with preview
    assert res.needs_approval is not None
    assert "1 contacts" in res.needs_approval["description"]


def test_input_roundtrip_via_engine(db, workspace_user):
    """Agent asks -> approval -> answer -> rerun -> done."""
    from app.agents.base import AgentContext, AgentResult, AgentTask
    from app.agents.registry import register
    from app.core.context import Principal
    from app.models.orm import Approval, ApprovalStatus, Workflow
    from app.workflow import engine as eng

    class Asker:
        name = "asker_tmp"
        allowed_tools = []

        def run(self, task, ctx):
            if ctx.task_id and task.input.get("_answer"):
                return AgentResult(output={"got": task.input["_answer"]})
            return AgentResult(needs_input={"question": "Which city?", "field": "_answer"})

    register(Asker())
    ws = workspace_user["company"].id
    p = Principal(user_id="u", workspace_id=ws, roles=("owner",))
    wf = eng.create_workflow(db, company_id=ws, triggered_by_user_id="u",
                             conversation_id=None, title="t", objective="o",
                             plan={"intent": "x", "tasks": [
                                 {"id": "a", "agent": "asker_tmp",
                                  "title": "ask", "input": {}, "depends_on": []}]})
    wf = eng.run(db, wf=wf, principal=p)
    assert wf.state.value == "WAITING_APPROVAL"
    ap = db.query(Approval).filter(
        Approval.workflow_id == wf.id,
        Approval.status == ApprovalStatus.PENDING).first()
    assert ap.action == "input_required"
    # user answers
    from app.approvals.service import decide
    decide(db, approval=ap, decision="APPROVE", decided_by_user_id="u", note="Nagpur")
    wf = eng.run(db, wf=wf, principal=p)
    assert wf.state.value == "COMPLETED"
    t = list(wf.tasks)[0]
    assert t.output.get("got") == "Nagpur"


def test_csv_import_endpoint(client):
    r = client.post(
        "/api/v1/leads/import-csv?list_name=diwali",
        files={"file": ("c.csv", "company_name,email\nA,a@x.test\nB,b@x.test\n", "text/csv")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] == 2 and body["source"] == "list:diwali"
    leads = client.get("/api/v1/leads").json()
    assert len(leads) >= 2
