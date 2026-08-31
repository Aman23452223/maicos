"""In-process Postgres job worker.

This replaces the previous Redis BLPOP-based worker. The worker runs
inside the FastAPI process (started in `app.main.lifespan`) and:

  1. subscribes to the `maicos_jobs` Postgres NOTIFY channel (via
     psycopg2 — same driver the rest of the app uses, so DNS and
     auth match exactly)
  2. on every wake-up, calls `dequeue()` to atomically claim a row
  3. dispatches the job to a handler by `trigger` (on_demand, scheduled, event)
  4. marks the row COMPLETED / FAILED and continues

A polling fallback (every 5s) is used when the LISTEN connection
drops. The worker is a singleton per process; if you scale the API
horizontally, multiple workers will cooperatively claim jobs because
of `FOR UPDATE SKIP LOCKED`.

Run the worker in a separate process with:

    python -m app.workers.scheduler
"""
from __future__ import annotations

import asyncio
import os
import signal
import socket

from sqlalchemy import text

from app.core.config import get_settings
from app.core.context import Principal
from app.core.logging import configure_logging, get_logger
from app.db.session import SessionLocal
from app.models.orm import Workflow
from app.orchestrator import handle_objective
from app.queue import jobs as queue
from app.workflow.engine import run as run_workflow

log = get_logger("worker")

_worker_task: asyncio.Task | None = None
_stop_event: asyncio.Event | None = None
_worker_id: str = ""

ON_DEMAND = "on_demand"
SCHEDULED = "scheduled"
EVENT = "event"


def _service_principal(workspace_id: str) -> Principal:
    """Synthetic system principal used to dispatch background jobs.

    The audit log records the actor as 'system:<workspace_id>'. A
    future iteration can introduce dedicated service accounts and
    per-workspace role grants.
    """
    return Principal(
        user_id=f"system:{workspace_id}",
        workspace_id=workspace_id,
        roles=("admin", "owner", "system"),
    )


def _process_on_demand(db, payload: dict) -> None:
    wf_id = payload.get("workflow_id")
    if not wf_id:
        log.warning("job.missing_workflow_id", payload=payload)
        return
    wf = db.get(Workflow, wf_id)
    if not wf:
        log.warning("job.workflow_not_found", workflow_id=wf_id)
        return
    run_workflow(db, wf=wf, principal=_service_principal(wf.company_id))
    db.commit()
    log.info("job.completed", workflow_id=wf_id, state=wf.state.value)


def _process_scheduled(db, payload: dict) -> None:
    """Scheduled job: build a fresh workflow from the stored objective."""
    objective = payload.get("objective")
    workspace_id = payload.get("workspace_id")
    if not objective or not workspace_id:
        return
    principal = _service_principal(workspace_id)
    result = handle_objective(db, principal=principal, objective=objective)
    log.info("scheduled.executed", workflow_id=result["workflow_id"], state=result["state"])


def _process_event(db, payload: dict) -> None:
    """Event-driven job: route the event to the matching workflow template."""
    event_name = payload.get("event", "")
    workspace_id = payload.get("workspace_id")
    if not event_name or not workspace_id:
        return
    objective_templates = {
        "lead.created": f"Follow up with new lead: {payload.get('lead_name', 'unknown')}",
        "invoice.overdue": (
            f"Handle overdue invoice follow-ups and tell me what needs approval "
            f"for {payload.get('customer', 'customer')}"
        ),
        "ticket.opened": f"Triage and respond to new support ticket: {payload.get('subject', '')}",
    }
    objective = objective_templates.get(event_name)
    if not objective:
        log.info("event.unhandled", event_name=event_name)
        return
    principal = _service_principal(workspace_id)
    handle_objective(db, principal=principal, objective=objective)
    log.info("event.processed", event_name=event_name)


_HANDLERS = {
    ON_DEMAND: _process_on_demand,
    SCHEDULED: _process_scheduled,
    EVENT: _process_event,
}


def _drain_once(timeout: float = 0.0) -> int:
    """Claim and process every currently-pending job. Returns count processed."""
    processed = 0
    while True:
        db = SessionLocal()
        try:
            job = queue.dequeue(db, claimed_by=_worker_id)
            if job is None:
                return processed
            db.commit()  # commit the claim
        except Exception:
            db.rollback()
            log.exception("worker.claim_failed")
            return processed
        finally:
            db.close()

        # Run handler in a fresh session so its commits do not overlap
        # with the claim commit.
        handler = _HANDLERS.get(job.trigger)
        if not handler:
            log.warning("job.unknown_trigger", trigger=job.trigger)
            _mark_failed(job.id, f"unknown trigger: {job.trigger}")
            continue
        run_db = SessionLocal()
        try:
            handler(run_db, job.payload)
            queue.mark_completed(run_db, job.id)
            run_db.commit()
            processed += 1
            log.info("job.handled", id=job.id, trigger=job.trigger)
        except Exception as exc:
            run_db.rollback()
            log.exception("job.failed", id=job.id, trigger=job.trigger)
            # After 3 attempts, mark DEAD so we stop re-trying.
            if job.workflow_id is None:
                # Re-claim to read attempts
                attempts = _attempts_for(run_db, job.id)
            else:
                attempts = 1  # safe default; we can re-read if needed
            dead = (attempts or 0) >= 3
            _mark_failed(job.id, str(exc), dead=dead)
        finally:
            run_db.close()


def _attempts_for(db, job_id: str) -> int | None:
    row = db.execute(
        text("SELECT attempts FROM workflow_jobs WHERE id = :id"),
        {"id": job_id},
    ).first()
    return int(row[0]) if row else None


def _mark_failed(job_id: str, error: str, *, dead: bool = False) -> None:
    db = SessionLocal()
    try:
        queue.mark_failed(db, job_id, error, dead=dead)
        db.commit()
    except Exception:
        db.rollback()
        log.exception("worker.mark_failed_error", id=job_id)
    finally:
        db.close()


async def _listen_loop(stop: asyncio.Event) -> None:
    """LISTEN maicos_jobs loop.

    Implemented with psycopg2 (the same driver used by SQLAlchemy
    throughout the app) rather than asyncpg, so DNS resolution and
    auth settings match the rest of the stack. On any failure, the
    loop sleeps and retries — it never raises out.

    The polling fallback in `_poll_loop` runs in parallel, so a
    broken LISTEN does not stop job processing.
    """
    import psycopg2
    import psycopg2.extensions

    while not stop.is_set():
        conn = None
        try:
            dsn = _to_psycopg2_dsn(get_settings().database_url)
            conn = psycopg2.connect(dsn, connect_timeout=5)
            conn.set_isolation_level(
                psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT
            )
            cur = conn.cursor()
            cur.execute("LISTEN maicos_jobs")
            cur.close()
            log.info("worker.listening", channel="maicos_jobs")
            # Run the blocking select/poll in a thread so the asyncio
            # event loop is never starved. The thread exits when `stop`
            # is set.
            await asyncio.to_thread(_psycopg2_listen_thread, conn, stop)
        except Exception as exc:  # noqa: BLE001 - reconnect on any error
            log.warning(
                "worker.listen_failed",
                error=str(exc),
                fallback="polling",
            )
            try:
                await asyncio.wait_for(stop.wait(), timeout=5.0)
            except TimeoutError:
                pass
        else:
            return
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception as exc:  # noqa: BLE001
                    log.warning("worker.listen_close_failed", error=str(exc))


def _to_psycopg2_dsn(url: str) -> str:
    """Convert a SQLAlchemy-style URL to a libpq DSN for psycopg2."""
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql://", 1)
    if url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql+psycopg://", "postgresql://", 1)
    if url.startswith("postgresql://"):
        return url
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


def _psycopg2_listen_thread(conn, stop: asyncio.Event) -> None:
    """Blocking loop: select on the libpq socket, drain jobs on each NOTIFY.

    Runs in a thread (via asyncio.to_thread). The thread checks the
    asyncio.Event between waits and exits within ~1 second after the
    event is set.
    """
    import select

    while not stop.is_set():
        if select.select([conn], [], [], 1.0) != ([], [], []):
            conn.poll()
            while conn.notifies:
                conn.notifies.pop(0)
                # Run the job claim/dispatch inline. This is the
                # same synchronous helper used by the polling loop.
                try:
                    _drain_once()
                except Exception:
                    import logging

                    logging.getLogger("worker").exception(
                        "worker.drain_failed",
                    )


async def _poll_loop(stop: asyncio.Event) -> None:
    """Polling fallback. Used alongside the LISTEN loop in production."""
    while not stop.is_set():
        try:
            await asyncio.to_thread(_drain_once)
        except Exception:
            log.exception("worker.poll_failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=5.0)
        except TimeoutError:
            continue


async def start_worker() -> None:
    """Start the worker. Idempotent — calling twice is a no-op."""
    global _worker_task, _stop_event, _worker_id
    if _worker_task is not None:
        return
    s = get_settings()
    _worker_id = s.worker_id or f"{socket.gethostname()}:{os.getpid()}"
    _stop_event = asyncio.Event()

    async def _guarded(coro):
        try:
            await coro
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - never let worker kill uvicorn
            log.error("worker.task_crashed", error=str(exc))

    listen_task = asyncio.create_task(
        _guarded(_listen_loop(_stop_event)), name="worker-listen"
    )
    poll_task = asyncio.create_task(
        _guarded(_poll_loop(_stop_event)), name="worker-poll"
    )
    _worker_task = asyncio.gather(listen_task, poll_task, return_exceptions=True)
    log.info("worker.start", id=_worker_id)


async def stop_worker() -> None:
    global _worker_task, _stop_event
    if _stop_event is not None:
        _stop_event.set()
    if _worker_task is not None:
        try:
            await asyncio.wait_for(_worker_task, timeout=5.0)
        except TimeoutError:
            _worker_task.cancel()
    _worker_task = None
    _stop_event = None
    log.info("worker.stop")


def main() -> None:
    """Standalone entry point: `python -m app.workers.scheduler`."""
    configure_logging()
    log.info("worker.cli_start", id=_worker_id)

    async def _run() -> None:
        await start_worker()

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda: _stop_event and _stop_event.set())
            except NotImplementedError:
                # Windows / non-Unix
                pass
        if _worker_task is not None:
            await _worker_task
        await stop_worker()

    asyncio.run(_run())


if __name__ == "__main__":
    main()