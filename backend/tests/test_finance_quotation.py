"""Finance draft quotations (no fabrication, ever).

Regression cover for the onboarding failure
`unknown finance action: create_financial_document`:

- `prepare_quotation` builds a labour-labelled DRAFT via the proposals
  architecture (kind=quotation, status=draft).
- Missing quantities/specs/prices land in `unresolved_fields` — never invented.
- No customer AND no items -> NEEDS_INPUT (no guessing).
- Catalogue prices come only from the workspace knowledge vault, marked
  illustrative with source. No invoice, no payment, no external send.
- Tenant isolation enforced on lead lookup.
- The planner catalog must not advertise `create_financial_document`
  (an approval-action name, not a runnable agent action).
- The engine maps unknown finance actions to SKIPPED (visible, honest).
"""
from __future__ import annotations


def _ctx(db, ws):
    from app.agents.base import AgentContext
    from app.core.context import Principal
    return AgentContext(db=db, principal=Principal(user_id="u", workspace_id=ws, roles=("owner",)),
                        workflow_id="w", task_id="t", run_id="r",
                        shared={"agent_name": "finance"})


def _run(db, ws, action_input):
    from app.agents.base import AgentTask
    from app.agents.implementations.finance import FinanceAgent
    return FinanceAgent().run(
        AgentTask(title="Prepare draft quotation", description="quote",
                  input={"action": "prepare_quotation", **action_input}),
        _ctx(db, ws))


def _drafts(db, ws):
    from app.models.orm import ProposalDocument
    return db.query(ProposalDocument).filter(
        ProposalDocument.company_id == ws,
        ProposalDocument.kind == "quotation").all()


def _invoices_for(ws):
    from app.agents.implementations.finance import _invoices_for as f
    return f(ws)


def test_prepare_quotation_draft_with_unresolved(db, workspace_user):
    ws = workspace_user["company"].id
    res = _run(db, ws, {"customer": "ABC Traders",
                        "items": [{"product": "Atta 50kg bag"},
                                  {"product": "Mustard oil", "quantity": 20, "unit": "L"}]})
    assert res.error is None, res.error
    assert res.needs_input is None and res.needs_approval is None
    out = res.output
    assert out["status"] == "draft"
    assert out["sent"] is False and out["invoiced"] is False
    assert out["payment_recorded"] is False
    # Nothing invented: qty/spec/price of item 0 + spec/price of item 1.
    unf = out["unresolved_fields"]
    assert any("quantity" in u for u in unf), unf
    assert any("spec" in u for u in unf), unf
    assert any("unit_price" in u for u in unf), unf
    assert out["indicative_total"] is None  # cannot total with TBDs
    docs = _drafts(db, ws)
    assert len(docs) == 1
    assert docs[0].status == "draft"
    assert "DRAFT — NOT A FINAL QUOTATION" in docs[0].content
    assert "No invoice issued" in docs[0].content


def test_prepare_quotation_needs_input_when_empty(db, workspace_user):
    ws = workspace_user["company"].id
    res = _run(db, ws, {})
    assert res.error is None
    assert res.needs_input is not None
    assert res.needs_input["field"] == "_answer"
    assert "bina iske" in res.needs_input["question"] or "Quotation" in res.needs_input["question"]
    assert _drafts(db, ws) == []  # guessed nothing


def test_prepare_quotation_uses_catalogue_price(db, workspace_user):
    from app.rag.index import get_index

    ws = workspace_user["company"].id
    get_index().add(workspace_id=ws, document_id="cat-1",
                    document_name="Sharma Catalogue",
                    text=("Sharma Traders price list. Mustard oil 15kg tin "
                          "Rs 2450 only. Atta 50kg bag Rs 1980. Sugar Rs 42 per kg."),
                    access_roles=[])
    res = _run(db, ws, {"customer": "ABC Traders",
                        "items": [{"product": "Mustard oil 15kg tin", "quantity": 2}]})
    assert res.error is None, res.error
    out = res.output
    assert not any("unit_price" in u for u in out["unresolved_fields"]), out["unresolved_fields"]
    docs = _drafts(db, ws)
    assert len(docs) == 1
    assert "Rs 2450" in docs[0].content
    assert "illustrative" in docs[0].content
    assert "Sharma Catalogue" in docs[0].content
    # 2 x 2450 = 4900 indicative (both qty+price present on every line).
    assert out["indicative_total"] == 4900.0


def test_prepare_quotation_tenant_isolation(db, workspace_user):
    from app.models.orm import Company, Lead

    ws = workspace_user["company"].id
    other = Company(name="Other Co")
    db.add(other)
    db.flush()
    foreign = Lead(company_id=other.id, company_name="Foreign Ltd")
    db.add(foreign)
    db.commit()
    res = _run(db, ws, {"lead_id": foreign.id, "items": [{"product": "Atta"}]})
    assert res.error == "lead not found"
    assert _drafts(db, ws) == []
    assert _drafts(db, other.id) == []


def test_prepare_quotation_creates_no_invoice_or_payment(db, workspace_user):
    ws = workspace_user["company"].id
    before = list(_invoices_for(ws))
    res = _run(db, ws, {"customer": "ABC Traders",
                        "items": [{"product": "Atta", "quantity": 10}]})
    assert res.error is None, res.error
    after = _invoices_for(ws)
    assert [i["id"] for i in after] == [i["id"] for i in before]


def test_planner_catalog_lists_prepare_quotation_not_approval_action():
    from app.agents.llm_planner import _PLAN_SCHEMA_HINT
    assert "prepare_quotation" in _PLAN_SCHEMA_HINT
    # `create_financial_document` is an approval-action name handled only in
    # execute_approved(); advertising it as a runnable action caused the
    # onboarding SKIPPED failure.
    assert "create_financial_document" not in _PLAN_SCHEMA_HINT


def test_unknown_finance_action_skipped_by_engine(db, workspace_user):
    from app.agents.base import AgentTask  # noqa: F401 (shape check)
    from app.core.context import Principal
    from app.models.orm import TaskState
    from app.workflow import engine as eng

    ws = workspace_user["company"].id
    p = Principal(user_id="u", workspace_id=ws, roles=("owner",))
    wf = eng.create_workflow(db, company_id=ws, triggered_by_user_id="u",
                             conversation_id=None, title="t", objective="o",
                             plan={"intent": "x", "tasks": [
                                 {"id": "q", "agent": "finance",
                                  "title": "Prepare draft quotation",
                                  "input": {"action": "create_financial_document"},
                                  "depends_on": []}]})
    wf = eng.run(db, wf=wf, principal=p)
    t = list(wf.tasks)[0]
    assert t.state == TaskState.SKIPPED, (t.state, t.error)
    assert "unknown finance action" in (t.error or "")
