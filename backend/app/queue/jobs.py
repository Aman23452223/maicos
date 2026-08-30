"""Postgres-backed workflow job queue (replaces Redis LIST).

This module replaces the previous Redis-based queue. Workers claim
rows with `SELECT ... FOR UPDATE SKIP LOCKED`, run the job, and mark
the row COMPLETED / FAILED.

Two wake-up mechanisms are supported:

- `LISTEN maicos_jobs` — receives a `pg_notify` after every INSERT
  (see migration `8f055dc11b82_pg_notify_trigger_for_workflow_jobs`).
- Polling fallback — a short `SELECT ... FOR UPDATE SKIP LOCKED` loop
  with a sleep, used when the LISTEN connection is not established.

Both paths share the same claim helper.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.orm import JobStatus, WorkflowJob

log = get_logger("queue")


@dataclass
class Job:
    id: str
    workflow_id: str
    workspace_id: str
    trigger: str
    payload: dict[str, Any]


def _row_to_job(row: WorkflowJob) -> Job:
    return Job(
        id=row.id,
        workflow_id=row.workflow_id or "",
        workspace_id=row.company_id,
        trigger=row.trigger,
        payload=dict(row.payload or {}),
    )


def new_job_id() -> str:
    return str(uuid.uuid4())


def enqueue(
    db: Session,
    *,
    company_id: str,
    trigger: str,
    payload: dict[str, Any],
    workflow_id: str | None = None,
    scheduled_job_id: str | None = None,
) -> Job:
    """Insert a job row. The pg_notify trigger wakes the worker.

    Returns the persisted `Job` dataclass (id assigned by DB).
    """
    job_id = new_job_id()
    row = WorkflowJob(
        id=job_id,
        company_id=company_id,
        trigger=trigger,
        payload=payload,
        status=JobStatus.PENDING,
        workflow_id=workflow_id,
        scheduled_job_id=scheduled_job_id,
    )
    db.add(row)
    db.flush()  # populate defaults + indexes, but do not commit yet
    return _row_to_job(row)


def enqueue_job(
    db: Session,
    *,
    company_id: str,
    trigger: str,
    payload: dict[str, Any],
    workflow_id: str | None = None,
) -> Job:
    """Public alias kept for backward compatibility with callers that
    previously imported `enqueue(Job(...))`."""
    return enqueue(
        db,
        company_id=company_id,
        trigger=trigger,
        payload=payload,
        workflow_id=workflow_id,
    )


def dequeue(db: Session, *, claimed_by: str, claim_for_seconds: int = 60) -> Job | None:
    """Claim the next PENDING job using SKIP LOCKED.

    Returns `None` if no job is currently available. The caller is
    responsible for `mark_completed` or `mark_failed` on the returned
    job.
    """
    sql = text(
        """
        WITH next_job AS (
            SELECT id
            FROM workflow_jobs
            WHERE status = 'PENDING'
            ORDER BY created_at
            FOR UPDATE SKIP LOCKED
            LIMIT 1
        )
        UPDATE workflow_jobs wj
        SET status = 'CLAIMED',
            claimed_by = :claimed_by,
            claimed_at = now(),
            attempts = wj.attempts + 1
        FROM next_job
        WHERE wj.id = next_job.id
        RETURNING wj.id, wj.workflow_id, wj.company_id, wj.trigger, wj.payload
        """
    )
    result = db.execute(
        sql, {"claimed_by": claimed_by, "claim_for_seconds": claim_for_seconds}
    ).first()
    if not result:
        return None
    return Job(
        id=result.id,
        workflow_id=result.workflow_id or "",
        workspace_id=result.company_id,
        trigger=result.trigger,
        payload=dict(result.payload or {}),
    )


def mark_completed(db: Session, job_id: str) -> None:
    db.execute(
        text(
            "UPDATE workflow_jobs SET status = 'COMPLETED', finished_at = now() "
            "WHERE id = :id"
        ),
        {"id": job_id},
    )


def mark_failed(db: Session, job_id: str, error: str, *, dead: bool = False) -> None:
    status = "DEAD" if dead else "FAILED"
    db.execute(
        text(
            "UPDATE workflow_jobs SET status = :status, last_error = :err, "
            "finished_at = now() WHERE id = :id"
        ),
        {"id": job_id, "err": error, "status": status},
    )


def queue_stats(db: Session) -> dict[str, int]:
    """Return counts per status (for /v1/queue/stats endpoint)."""
    rows = db.execute(
        text("SELECT status, count(*) FROM workflow_jobs GROUP BY status")
    ).all()
    return {row[0]: int(row[1]) for row in rows}