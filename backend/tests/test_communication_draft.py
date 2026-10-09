"""Welcome-email draft output must be real, persisted, and never sent.

Regression cover for the Pipeline Inspector gap: clicking the completed
"Draft welcome email" task showed no subject/body. The backend chain
(agent -> email.message.draft -> task.output -> listTasks) is asserted
here; the Inspector renders whatever `output` the API returns.

- Draft saves the REAL to/subject/body from the task input (no faking).
- Output survives a fresh session + API read (what a page refresh does).
- Drafting never sends: outbox holds DRAFT, never SENT, for the workspace.
"""
from __future__ import annotations


SUBJECT = "Welcome to Sharma Traders, ABC!"
BODY = "Hi Aman,\n\nWelcome aboard ABC Traders. Your account manager will call you tomorrow.\n\nTeam Sharma"


def _ctx(db, ws):
    import uuid
    from app.agents.base import AgentContext
    from app.core.context import Principal
    # Unique ids per call: tool calls are idempotent on
    # workflow_id:task_id:connector.operation, so fixed ids would collide
    # with other tests using the shared file stores.
    tag = uuid.uuid4().hex[:8]
    return AgentContext(db=db, principal=Principal(user_id="u", workspace_id=ws, roles=("owner",)),
                        workflow_id=f"w-{tag}", task_id=f"t-{tag}", run_id=f"r-{tag}",
                        shared={"agent_name": "communication"})


def _draft_plan():
    return {"intent": "x", "tasks": [
        {"id": "mail", "agent": "communication", "title": "Draft welcome email",
         "input": {"action": "draft", "to": "aman@abc.test",
                   "subject": SUBJECT, "body": BODY},
         "depends_on": []},
    ]}


def test_draft_saves_real_subject_body(db, workspace_user):
    from app.core.context import Principal
    from app.models.orm import TaskState
    from app.workflow import engine as eng

    ws = workspace_user["company"].id
    p = Principal(user_id="u", workspace_id=ws, roles=("owner",))
    wf = eng.create_workflow(db, company_id=ws, triggered_by_user_id="u",
                             conversation_id=None, title="t", objective="o",
                             plan=_draft_plan())
    wf = eng.run(db, wf=wf, principal=p)
    assert wf.state.value == "COMPLETED", wf.state
    t = list(wf.tasks)[0]
    assert t.state == TaskState.COMPLETED, (t.state, t.error)
    draft = (t.output or {}).get("draft") or {}
    assert draft.get("status") == "DRAFT"
    assert draft.get("to") == "aman@abc.test"
    assert draft.get("subject") == SUBJECT
    assert draft.get("body") == BODY


def test_draft_output_persists_across_api_read(db, workspace_user, client):
    """Fresh session + API read (== browser refresh) still returns output."""
    from app.core.context import Principal
    from app.workflow import engine as eng

    ws = workspace_user["company"].id
    p = Principal(user_id="client-user", workspace_id=ws, roles=("owner",))
    wf = eng.create_workflow(db, company_id=ws, triggered_by_user_id="u",
                             conversation_id=None, title="t", objective="o",
                             plan=_draft_plan())
    eng.run(db, wf=wf, principal=p)
    db.commit()
    db.expire_all()

    # New HTTP request = new DB session, like a page refresh.
    r = client.get(f"/api/v1/workflows/{wf.id}/tasks")
    assert r.status_code == 200, r.text
    tasks = r.json()
    assert len(tasks) == 1
    draft = (tasks[0].get("output") or {}).get("draft") or {}
    assert draft.get("subject") == SUBJECT
    assert draft.get("body") == BODY


def _seed_sharma(db, ws):
    """Mirror the reported workspace: profile + CRM record + vault doc."""
    from app.models.orm import BusinessProfile, Lead
    db.add(BusinessProfile(
        company_id=ws, business_name="Sharma Traders",
        industry="FMCG distribution",
        products_services=["Atta", "Mustard oil", "Sugar", "Rice"],
        target_customer="kirana stores and food businesses"))
    db.add(Lead(company_id=ws, company_name="Aarav Electrical Works",
                email="contact@aarav.test", score=80))
    db.commit()
    from app.rag.index import get_index
    get_index().add(
        workspace_id=ws, document_id="cat-1", document_name="Sharma Catalogue",
        text=("Sharma Traders wholesale price list. Atta 50kg bag Rs 1980. "
              "Mustard oil 15kg tin Rs 2450. Sugar Rs 42 per kg. "
              "We supply kirana stores across the region with weekly delivery."),
        access_roles=[])


def test_welcome_draft_resolves_crm_email_and_full_body(db, workspace_user):
    from app.agents.base import AgentTask
    from app.agents.implementations.communication import CommunicationAgent

    ws = workspace_user["company"].id
    _seed_sharma(db, ws)
    res = CommunicationAgent().run(
        AgentTask(title="Draft welcome email", description="welcome ABC",
                  input={"action": "draft", "customer": "Aarav Electrical Works"}),
        _ctx(db, ws))
    assert res.error is None, res.error
    draft = (res.output or {}).get("draft") or {}
    assert draft.get("status") == "DRAFT"
    # Real recipient from the CRM record — never "list", never invented.
    assert draft.get("to") == "contact@aarav.test"
    assert draft.get("subject") == "Welcome to Sharma Traders, Aarav Electrical Works"
    body = draft.get("body") or ""
    assert len(body) > 200, body
    assert "Aarav Electrical Works" in body
    assert "Sharma Traders" in body
    assert "Atta" in body  # knowledge-base offerings present
    assert body.strip() != "Hi,"
    assert (res.output or {}).get("purpose") == "welcome"


def test_billing_request_draft_lists_upstream_missing_fields(db, workspace_user):
    from app.agents.base import AgentContext, AgentTask
    from app.agents.implementations.communication import CommunicationAgent
    from app.core.context import Principal

    ws = workspace_user["company"].id
    _seed_sharma(db, ws)
    ctx = AgentContext(
        db=db, principal=Principal(user_id="u", workspace_id=ws, roles=("owner",)),
        workflow_id="w-b", task_id="t-b", run_id="r-b",
        shared={"agent_name": "communication",
                "gap": {"missing": ["GST number", "billing address"]}})
    res = CommunicationAgent().run(
        AgentTask(title="Request missing billing details",
                  description="ask for pending billing info",
                  input={"action": "draft", "customer": "Aarav Electrical Works"}),
        ctx)
    assert res.error is None, res.error
    assert (res.output or {}).get("purpose") == "billing_request"
    draft = (res.output or {}).get("draft") or {}
    assert draft.get("to") == "contact@aarav.test"
    assert "Billing" in (draft.get("subject") or "")
    body = draft.get("body") or ""
    # Exact upstream-missing fields appear; nothing else invented.
    assert "GST number" in body and "billing address" in body
    assert len(body) > 200


def test_missing_crm_email_reported_not_invented(db, workspace_user):
    from app.agents.base import AgentTask
    from app.agents.implementations.communication import CommunicationAgent
    from app.models.orm import Lead

    ws = workspace_user["company"].id
    db.add(Lead(company_id=ws, company_name="NoMail Traders", email=None))
    db.commit()
    res = CommunicationAgent().run(
        AgentTask(title="Draft welcome email", description="welcome",
                  input={"action": "draft", "customer": "NoMail Traders"}),
        _ctx(db, ws))
    assert res.error is None, res.error
    draft = (res.output or {}).get("draft") or {}
    assert draft.get("to") in ("", None)
    assert "list" not in (draft.get("to") or "")
    missing = (res.output or {}).get("missing") or []
    assert any("recipient" in m for m in missing), missing
    # No address hallucinated anywhere in the saved fields.
    assert "@" not in (draft.get("to") or "")


def test_welcome_draft_end_to_end_saved_output(db, workspace_user, client):
    """Engine run -> commit -> fresh API read returns the real draft."""
    from app.core.context import Principal
    from app.models.orm import TaskState
    from app.workflow import engine as eng

    ws = workspace_user["company"].id
    _seed_sharma(db, ws)
    p = Principal(user_id="u", workspace_id=ws, roles=("owner",))
    wf = eng.create_workflow(
        db, company_id=ws, triggered_by_user_id="u", conversation_id=None,
        title="t", objective="o",
        plan={"intent": "x", "tasks": [
            {"id": "mail", "agent": "communication",
             "title": "Draft welcome email for Aarav",
             "input": {"action": "draft", "customer": "Aarav Electrical Works"},
             "depends_on": []}]})
    eng.run(db, wf=wf, principal=p)
    db.commit()
    db.expire_all()

    r = client.get(f"/api/v1/workflows/{wf.id}/tasks")
    assert r.status_code == 200, r.text
    t = r.json()[0]
    assert t["state"] == TaskState.COMPLETED.value
    draft = (t.get("output") or {}).get("draft") or {}
    assert draft.get("to") == "contact@aarav.test"
    assert "Aarav Electrical Works" in (draft.get("subject") or "")
    assert len(draft.get("body") or "") > 200
    from app.core.context import Principal
    from app.workflow import engine as eng

    ws = workspace_user["company"].id
    p = Principal(user_id="u", workspace_id=ws, roles=("owner",))
    wf = eng.create_workflow(db, company_id=ws, triggered_by_user_id="u",
                             conversation_id=None, title="t", objective="o",
                             plan=_draft_plan())
    eng.run(db, wf=wf, principal=p)

    from app.integrations.connectors.email import _OUTBOX
    mine = [m for m in _OUTBOX.all() if m.get("workspace_id") == ws]
    assert mine, "draft must be persisted in the outbox"
    assert all(m.get("status") == "DRAFT" for m in mine)
    assert not any(m.get("status") == "SENT" for m in mine)


def test_approved_send_output_carries_real_subject_body(db, workspace_user):
    """Lock the output mapping the Inspector's sent-view relies on.

    Runs `execute_approved` directly (no SMTP configured, so delivery is
    file-outbox only — nothing leaves the machine).
    """
    from app.agents.implementations.communication import CommunicationAgent

    ws = workspace_user["company"].id
    res = CommunicationAgent().execute_approved(
        {"action": "send_external_communication",
         "payload": {"channel": "email", "to": "aman@abc.test",
                     "subject": SUBJECT, "body": BODY}},
        _ctx(db, ws))
    assert res.error is None, res.error
    sent = (res.output or {}).get("sent") or {}
    assert sent.get("status") == "SENT"
    assert sent.get("to") == "aman@abc.test"
    assert sent.get("subject") == SUBJECT
    assert sent.get("body") == BODY
    assert (res.output or {}).get("channel") == "email"


def test_draft_never_sends(db, workspace_user):
    from app.core.context import Principal
    from app.workflow import engine as eng

    ws = workspace_user["company"].id
    p = Principal(user_id="u", workspace_id=ws, roles=("owner",))
    wf = eng.create_workflow(db, company_id=ws, triggered_by_user_id="u",
                             conversation_id=None, title="t", objective="o",
                             plan=_draft_plan())
    eng.run(db, wf=wf, principal=p)

    from app.integrations.connectors.email import _OUTBOX
    mine = [m for m in _OUTBOX.all() if m.get("workspace_id") == ws]
    assert mine, "draft must be persisted in the outbox"
    assert all(m.get("status") == "DRAFT" for m in mine)
    assert not any(m.get("status") == "SENT" for m in mine)


def test_customer_resolved_from_title_via_crm_match(db, workspace_user):
    """Customer name lives only in the task title; CRM verifies the match."""
    from app.agents.base import AgentTask
    from app.agents.implementations.communication import CommunicationAgent

    ws = workspace_user["company"].id
    _seed_sharma(db, ws)
    res = CommunicationAgent().run(
        AgentTask(title="Draft welcome email for Aarav Electrical Works",
                  description="onboard them",
                  input={"action": "draft"}),
        _ctx(db, ws))
    assert res.error is None, res.error
    draft = (res.output or {}).get("draft") or {}
    assert draft.get("to") == "contact@aarav.test"
    assert "Sharma Traders" in (draft.get("subject") or "")


def test_placeholder_body_regenerated_not_kept(db, workspace_user):
    """Templated bodies ({{name}}, [Your Name]) are regenerated, not saved."""
    from app.agents.base import AgentTask
    from app.agents.implementations.communication import CommunicationAgent

    ws = workspace_user["company"].id
    _seed_sharma(db, ws)
    res = CommunicationAgent().run(
        AgentTask(title="Draft welcome email", description="welcome",
                  input={"action": "draft", "customer": "Aarav Electrical Works",
                         "subject": "Welcome!",
                         "body": "Dear {{recipient_name}},\n\nWelcome to us, "
                                 "your friends in business. Call {{sender}} anytime. "
                                 "We do all the good things for valued people like you."}),
        _ctx(db, ws))
    assert res.error is None, res.error
    body = ((res.output or {}).get("draft") or {}).get("body") or ""
    assert "{{" not in body and "}}" not in body
    assert "Aarav Electrical Works" in body and "Sharma Traders" in body


def test_bracket_slot_body_regenerated_not_kept(db, workspace_user):
    """Bodies with [Contact First Name]-style slots are regenerated."""
    from app.agents.base import AgentTask
    from app.agents.implementations.communication import CommunicationAgent

    ws = workspace_user["company"].id
    _seed_sharma(db, ws)
    stub = ("Hi [Contact First Name],\n\nWelcome aboard! We are glad to have "
            "you with us and will support your journey with timely service "
            "and clear communication throughout the onboarding process.\n\n"
            "If you have questions, reply to this email or reach us at "
            "[Company Phone / Support Address] for quick help.\n\n"
            "Warm regards,\n[Sender Name]\n[Title]\n[Company Name]")
    res = CommunicationAgent().run(
        AgentTask(title="Draft welcome email", description="welcome",
                  input={"action": "draft", "customer": "Aarav Electrical Works",
                         "subject": "Welcome!", "body": stub}),
        _ctx(db, ws))
    assert res.error is None, res.error
    body = ((res.output or {}).get("draft") or {}).get("body") or ""
    assert "[" not in body and "]" not in body, body
    assert "Aarav Electrical Works" in body and "Sharma Traders" in body


def test_wrong_direction_subject_regenerated(db, workspace_user):
    """A welcome subject naming the customer as the destination is rebuilt."""
    from app.agents.base import AgentTask
    from app.agents.implementations.communication import CommunicationAgent

    ws = workspace_user["company"].id
    _seed_sharma(db, ws)
    res = CommunicationAgent().run(
        AgentTask(title="Draft welcome email", description="welcome",
                  input={"action": "draft", "customer": "Aarav Electrical Works",
                         "subject": "Welcome to Aarav Electrical Works"}),
        _ctx(db, ws))
    assert res.error is None, res.error
    subject = ((res.output or {}).get("draft") or {}).get("subject") or ""
    assert "Sharma Traders" in subject, subject
