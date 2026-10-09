"""Upstream handoff into missing-information analysis (no hardcoded keys).

Regression cover for the onboarding failure where
`Identify missing customer/billing info` (analytics `summarize_context`)
failed with `no upstream context to summarize` while its CRM + Knowledge
Vault prerequisites had completed — and downstream tasks stayed PENDING.

Root cause: the agent read only `shared["context"]` (a plan-id
convention that holds for exactly one deterministic plan) instead of
this task's real `depends_on` outputs seeded by the engine. The PENDING
downstream tasks were the correct consequence (FAILED never unblocks
dependents), not a second bug.
"""
from __future__ import annotations


def _ctx(db, ws):
    from app.agents.base import AgentContext
    from app.core.context import Principal
    return AgentContext(db=db, principal=Principal(user_id="u", workspace_id=ws, roles=("owner",)),
                        workflow_id="w", task_id="t", run_id="r",
                        shared={"agent_name": "analytics"})


def test_summarize_reads_real_dependencies_not_hardcoded_key(db, workspace_user):
    from app.agents.base import AgentTask
    from app.agents.implementations.analytics import AnalyticsAgent

    ws = workspace_user["company"].id
    ctx = _ctx(db, ws)
    # Upstream outputs under ARBITRARY plan ids — no "context" key anywhere.
    ctx.shared.update({
        "crm_0": {"company": {"name": "ABC Traders"},
                  "contact": {"name": "Aman", "email": "aman@abc.test"}},
        "search": {"results": [{"snippet": "ABC Traders buys atta in bulk, GST registered"}]},
    })
    res = AnalyticsAgent().run(
        AgentTask(title="Identify missing customer/billing info", description="gap check",
                  input={"action": "summarize_context",
                         "required_fields": ["email", "billing address", "GST number"]}),
        ctx)
    assert res.error is None, res.error
    out = res.output
    assert "atta" in out["brief"]
    assert "email" in out["present"] and "aman@abc.test" in out["present"]["email"]
    assert out["missing"] == ["billing address", "GST number"]


def test_empty_upstream_is_honest_error(db, workspace_user):
    from app.agents.base import AgentTask
    from app.agents.implementations.analytics import AnalyticsAgent

    ws = workspace_user["company"].id
    res = AnalyticsAgent().run(
        AgentTask(title="Identify missing customer/billing info", description="gap check",
                  input={"action": "summarize_context"}),
        _ctx(db, ws))
    assert res.error is not None and "depends_on" in res.error
    assert res.output == {}


def test_meeting_prep_plan_still_works(db, workspace_user):
    """The one plan that relied on the old 'context' key keeps working."""
    from app.agents.base import AgentTask
    from app.agents.implementations.analytics import AnalyticsAgent

    ws = workspace_user["company"].id
    ctx = _ctx(db, ws)
    ctx.shared.update({"context": {"query": "Q3 review",
                                    "results": [{"snippet": "Discuss renewal terms"}]}})
    res = AnalyticsAgent().run(
        AgentTask(title="Prepare brief", description="Summarize context",
                  input={"action": "summarize_context"}),
        ctx)
    assert res.error is None, res.error
    assert "renewal" in res.output["brief"]
    assert res.output["sources"] == 1


def _unregister(*names):
    from app.agents import base as _registry
    for n in names:
        _registry._REGISTRY.pop(n, None)  # type: ignore[attr-defined]


def test_engine_crm_plus_knowledge_feed_gap_analysis(db, workspace_user):
    """CRM + Knowledge Vault outputs flow into the analysis task via engine."""
    from app.agents.base import AgentContext, AgentResult, AgentTask
    from app.agents.registry import register
    from app.core.context import Principal
    from app.models.orm import TaskState
    from app.workflow import engine as eng

    class CrmStubCtx:
        name = "crm_stub_ctx"
        description = "Test stub: emits a CRM record."
        allowed_tools = []

        def run(self, task, ctx):
            return AgentResult(output={
                "company": {"name": "ABC Traders"},
                "contact": {"name": "Aman", "email": "aman@abc.test"}})

    class KvStubCtx:
        name = "kv_stub_ctx"
        description = "Test stub: emits vault search results."
        allowed_tools = []

        def run(self, task, ctx):
            return AgentResult(output={
                "query": "ABC Traders billing",
                "results": [{"snippet": "ABC Traders pays on 30-day credit, no GST on file"}]})

    register(CrmStubCtx())
    register(KvStubCtx())
    try:
        ws = workspace_user["company"].id
        p = Principal(user_id="u", workspace_id=ws, roles=("owner",))
        wf = eng.create_workflow(
            db, company_id=ws, triggered_by_user_id="u", conversation_id=None,
            title="t", objective="o",
            plan={"intent": "x", "tasks": [
                {"id": "crm_0", "agent": "crm_stub_ctx", "title": "Retrieve CRM record",
                 "input": {}, "depends_on": []},
                {"id": "search", "agent": "kv_stub_ctx", "title": "Search Knowledge Vault",
                 "input": {}, "depends_on": []},
                {"id": "gap", "agent": "analytics",
                 "title": "Identify missing customer/billing info",
                 "input": {"action": "summarize_context",
                           "required_fields": ["email", "billing address", "GST number",
                                               "credit terms"]},
                 "depends_on": ["crm_0", "search"]},
            ]})
        wf = eng.run(db, wf=wf, principal=p)
        assert wf.state.value == "COMPLETED", wf.state
        gap = [t for t in wf.tasks if (t.input or {}).get("_plan_id") == "gap"][0]
        assert gap.state == TaskState.COMPLETED, (gap.state, gap.error)
        # "credit terms" as a phrase is absent from the evidence ("30-day
        # credit" is present but that is not the same claim) — honest miss.
        assert gap.output["missing"] == ["billing address", "GST number",
                                         "credit terms"], gap.output
        assert "email" in gap.output["present"]
    finally:
        _unregister("crm_stub_ctx", "kv_stub_ctx")


def test_failed_prerequisite_blocks_dependents(db, workspace_user):
    """PENDING downstream of a FAILED task is correct gating, not a bug."""
    from app.agents.base import AgentResult
    from app.agents.registry import register
    from app.core.context import Principal
    from app.models.orm import TaskState
    from app.workflow import engine as eng

    class Failer:
        name = "failer_ctx"
        description = "Test stub: always errors."
        allowed_tools = []

        def run(self, task, ctx):
            return AgentResult(error="boom")

    register(Failer())
    try:
        ws = workspace_user["company"].id
        p = Principal(user_id="u", workspace_id=ws, roles=("owner",))
        wf = eng.create_workflow(
            db, company_id=ws, triggered_by_user_id="u", conversation_id=None,
            title="t", objective="o",
            plan={"intent": "x", "tasks": [
                {"id": "bad", "agent": "failer_ctx", "title": "fails",
                 "input": {}, "depends_on": []},
                {"id": "later", "agent": "analytics",
                 "title": "must not run without prerequisite",
                 "input": {"action": "funnel"}, "depends_on": ["bad"]},
            ]})
        wf = eng.run(db, wf=wf, principal=p)
        states = {(t.input or {}).get("_plan_id"): t.state for t in wf.tasks}
        assert states["bad"] == TaskState.FAILED
        # Dependent never executed: no output, still PENDING.
        assert states["later"] == TaskState.PENDING
        later = [t for t in wf.tasks if (t.input or {}).get("_plan_id") == "later"][0]
        assert later.output in (None, {})
    finally:
        _unregister("failer_ctx")


def test_brief_synthesizes_lead_names_and_counts(db, workspace_user):
    """No snippets: brief still states recorded names and counts."""
    from app.agents.base import AgentTask
    from app.agents.implementations.analytics import AnalyticsAgent

    ws = workspace_user["company"].id
    ctx = _ctx(db, ws)
    ctx.shared.update({
        "sel": {"count": 2, "leads": [
            {"company_name": "Acme"}, {"company_name": "Beta"}]},
        "fol": {"sequences_created": 8},
    })
    res = AnalyticsAgent().run(
        AgentTask(title="Summarize", description="sum",
                  input={"action": "summarize_context"}),
        ctx)
    assert res.error is None, res.error
    brief = res.output.get("brief") or ""
    assert "Acme" in brief and "Beta" in brief, brief
    assert "sequences created: 8" in brief, brief
    text = res.output.get("report_text") or ""
    assert "Business results:" in text and "Acme" in text, text
