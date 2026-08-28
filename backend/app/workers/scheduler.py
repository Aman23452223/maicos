"""Worker process entry point.

Run with: `python -m app.workers.scheduler`

Consumes workflow jobs from the Redis queue and executes them. In
production this would be multiple replicas behind a leader election.
"""
from __future__ import annotations

import signal
import sys

from sqlalchemy.orm import Session

from app.core.context import Principal
from app.core.logging import configure_logging, get_logger
from app.db.session import SessionLocal
from app.models.orm import Workflow
from app.orchestrator import handle_objective
from app.queue.jobs import dequeue
from app.workflow.engine import run as run_workflow

log = get_logger("worker")
_stop: list[bool] = [False]


def _service_principal(db: Session, workspace_id: str) -> Principal:
    """Build a service principal for the given workspace.

    For MVP we use a synthetic principal that the audit log records as
    'system'. A future iteration can introduce dedicated service
    accounts and per-workspace role grants.
    """
    return Principal(
        user_id=f"system:{workspace_id}",
        workspace_id=workspace_id,
        roles=("admin", "owner", "system"),
    )


def _process_on_demand(db: Session, job_payload: dict) -> None:
    wf_id = job_payload.get("workflow_id")
    if not wf_id:
        log.warning("job.missing_workflow_id", payload=job_payload)
        return
    wf = db.get(Workflow, wf_id)
    if not wf:
        log.warning("job.workflow_not_found", workflow_id=wf_id)
        return
    run_workflow(db, wf=wf, principal=_service_principal(db, wf.company_id))
    db.commit()
    log.info("job.completed", workflow_id=wf_id, state=wf.state.value)


def _process_scheduled(db: Session, job_payload: dict) -> None:
    """Scheduled job: build a fresh workflow from the stored objective."""
    objective = job_payload.get("objective")
    workspace_id = job_payload.get("workspace_id")
    if not objective or not workspace_id:
        return
    principal = _service_principal(db, workspace_id)
    result = handle_objective(db, principal=principal, objective=objective)
    log.info("scheduled.executed", workflow_id=result["workflow_id"], state=result["state"])


def _process_event(db: Session, job_payload: dict) -> None:
    """Event-driven job: route the event to the matching workflow template."""
    event_name = job_payload.get("event", "")
    workspace_id = job_payload.get("workspace_id")
    if not event_name or not workspace_id:
        return
    objective_templates = {
        "lead.created": f"Follow up with new lead: {job_payload.get('lead_name', 'unknown')}",
        "invoice.overdue": f"Handle overdue invoice follow-ups and tell me what needs approval for {job_payload.get('customer', 'customer')}",
        "ticket.opened": f"Triage and respond to new support ticket: {job_payload.get('subject', '')}",
    }
    objective = objective_templates.get(event_name)
    if not objective:
        log.info("event.unhandled", event_name=event_name)
        return
    principal = _service_principal(db, workspace_id)
    handle_objective(db, principal=principal, objective=objective)
    log.info("event.processed", event_name=event_name)


_HANDLERS = {
    "on_demand": _process_on_demand,
    "scheduled": _process_scheduled,
    "event": _process_event,
}


def loop() -> None:
    log.info("worker.start", pid=__import__("os").getpid())
    while not _stop[0]:
        job = dequeue(timeout=5)
        if not job:
            continue
        handler = _HANDLERS.get(job.trigger)
        if not handler:
            log.warning("job.unknown_trigger", trigger=job.trigger)
            continue
        db = SessionLocal()
        try:
            handler(db, job.payload)
        except Exception:
            log.exception("job.failed", workflow_id=job.workflow_id)
        finally:
            db.close()
    log.info("worker.stop")


def _on_signal(_signo, _frame):
    _stop[0] = True


if __name__ == "__main__":
    configure_logging()
    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)
    try:
        loop()
    except KeyboardInterrupt:
        sys.exit(0)
