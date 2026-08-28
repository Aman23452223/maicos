"""Scheduled and event-triggered workflow routes (PRD §13, FR-14)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.context import Principal
from app.core.security import get_current_principal
from app.db.session import get_db
from app.orchestrator import schedule as schedule_workflow
from app.orchestrator import trigger_event

router = APIRouter(tags=["automation"])


@router.post("/workflows/schedule")
def schedule_endpoint(
    objective: str,
    run_at: str,
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Schedule a workflow to run at a specific time (ISO-8601)."""
    try:
        return schedule_workflow(
            db, principal=p, objective=objective, run_at_iso=run_at
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"bad run_at: {e}") from e


@router.post("/webhooks/{event}")
def ingest_event(
    event: str,
    request: Request,
    payload: dict[str, Any] | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Ingest an external event and enqueue a workflow.

    Authentication for production should be a per-workspace signing
    secret in the `X-MAICOS-Signature` header. The MVP accepts any
    payload and resolves the workspace from the body.
    """
    body = payload or {}
    workspace_id = body.get("workspace_id") or request.headers.get("X-MAICOS-Workspace")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="workspace_id required")
    data = {k: v for k, v in body.items() if k != "workspace_id"}
    return trigger_event(db, workspace_id=workspace_id, event=event, data=data)
