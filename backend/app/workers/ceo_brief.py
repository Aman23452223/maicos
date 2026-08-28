"""Scheduled CEO Daily Brief (PRD §32).

Runs at the start of the day via APScheduler, summarises activity,
and reports what needs attention.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.audit.service import record
from app.core.context import Principal
from app.workflow.engine import create_workflow
from app.workflow.engine import run as run_workflow


def _service_principal(workspace_id: str) -> Principal:
    return Principal(
        user_id=f"system:{workspace_id}",
        workspace_id=workspace_id,
        roles=("admin", "owner", "system"),
    )


def run_ceo_brief(db: Session, *, workspace_id: str) -> dict:
    """Build a Daily CEO Brief for a workspace.

    The brief collects activity from the audit log and uses the
    analytics agent to render a structured summary. This is the entry
    point APScheduler hits once per day per workspace.
    """
    principal = _service_principal(workspace_id)
    # Build a workflow that runs the analytics + AI summary tasks.
    plan = {
        "intent": "ceo_brief",
        "tasks": [
            {
                "id": "kpis",
                "agent": "analytics",
                "title": "Compute KPIs",
                "description": "Compute KPIs and detect anomalies.",
                "input": {"action": "ceo_brief", "summary": "Daily activity loaded from audit log."},
                "depends_on": [],
            },
        ],
    }
    wf = create_workflow(
        db,
        company_id=workspace_id,
        triggered_by_user_id=principal.user_id,
        conversation_id=None,
        title="ceo_brief",
        objective="Produce today's CEO brief.",
        plan=plan,
    )
    run_workflow(db, wf=wf, principal=principal)
    record(
        db,
        company_id=workspace_id,
        actor="scheduler",
        action="ceo_brief.generated",
        target_type="workflow",
        target_id=wf.id,
        details={"state": wf.state.value},
    )
    db.commit()
    return {"workflow_id": wf.id, "state": wf.state.value}
