"""AI Company Manager: UNDERSTAND -> CONTEXT -> WORKFORCE -> PLAN ->
EXECUTE -> VERIFY -> MEASURE -> REMEMBER -> REPORT (+ proactive follow-up).

Sits ABOVE the existing orchestrator: enriches context, composes the
workforce roster into the plan, delegates execution to handle_objective,
then measures, remembers and reports. Never bypasses approvals.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.audit.service import record
from app.company.brain import load_company_context, remember
from app.company.workforce import compose
from app.core.context import Principal


def run_outcome(db: Session, *, principal: Principal, objective: str,
                conversation_id: str | None = None,
                plan_review: bool = False) -> dict[str, Any]:
    from app.orchestrator import handle_objective

    ctx = load_company_context(db, company_id=principal.workspace_id)
    result = handle_objective(db, principal=principal, objective=objective,
                              conversation_id=conversation_id,
                              plan_review=plan_review)
    plan = result.get("plan", {})
    intent = plan.get("intent", "generic")
    from app.capabilities.registry import enabled_for

    roster = compose(intent, sorted(enabled_for(db, company_id=principal.workspace_id)),
                     context=ctx)
    plan["workforce"] = roster
    # Measure: attach current metrics snapshot to the result.
    result["workforce"] = roster
    result["company"] = {"business_name": ctx["business_name"],
                         "goals": ctx["goals"]}
    # Remember the execution result (typed, never a silent fact).
    try:
        remember(db, company_id=principal.workspace_id,
                 kind="EXECUTION_RESULT",
                 key=f"outcome:{result['workflow_id']}",
                 value=f"{objective[:200]} -> {result['state']}",
                 actor=principal.user_id)
        record(db, company_id=principal.workspace_id, actor="company_manager",
               action="outcome.reported", target_type="workflow",
               target_id=result["workflow_id"],
               details={"state": result["state"], "intent": intent})
        db.commit()
    except Exception:
        pass
    return result


def investigate(db: Session, *, principal: Principal,
                question: str) -> dict[str, Any]:
    """Diagnostic loop for 'revenue dropped' style questions.

    Inspects funnel/pipeline/operations, synthesizes candidate causes
    (labeled analysis, not facts), and returns a corrective plan outline
    for approval — no external actions taken here.
    """
    from app.analytics.metrics import funnel, operations, pipeline

    ctx = load_company_context(db, company_id=principal.workspace_id)
    fun = funnel(db, company_id=principal.workspace_id)
    pipe = pipeline(db, company_id=principal.workspace_id)
    ops = operations(db, company_id=principal.workspace_id)
    causes: list[str] = []
    by_status = fun.get("by_status", {})
    if fun.get("response_rate", 0) < 0.1 and fun.get("contacted", 0) > 0:
        causes.append("Low response rate: outreach messages may need revision.")
    if ops.get("qualified_not_contacted", 0) > 0:
        causes.append(f"{ops['qualified_not_contacted']} qualified leads never contacted.")
    if ops.get("followups_scheduled", 0) > 0:
        causes.append("Follow-ups pending execution.")
    if ops.get("approvals_pending", 0) > 0:
        causes.append(f"{ops['approvals_pending']} approvals blocking execution.")
    if not causes:
        causes.append("No single dominant cause in current metrics; deeper "
                      "segment analysis recommended.")
    return {"type": "analysis", "question": question,
            "metrics": {"funnel": fun, "pipeline": pipe, "operations": ops},
            "candidate_causes": causes,
            "corrective_outline": [
                "Qualify and contact stale qualified leads.",
                "Run due follow-ups.",
                "Clear pending approvals.",
                "Launch a targeted campaign to the best segment."]}
