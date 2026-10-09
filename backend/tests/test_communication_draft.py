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
