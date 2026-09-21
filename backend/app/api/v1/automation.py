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


@router.post("/webhooks/{provider}/{event}")
def ingest_event_verified(
    provider: str,
    event: str,
    request: Request,
    payload: dict[str, Any] | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Verified webhook intake (Phase 22). Rejects unsigned events."""
    import json

    from app.audit.service import record
    from app.core.webhooks import verify

    body = payload or {}
    raw = json.dumps(body, sort_keys=True, default=str).encode()
    headers = {k.lower(): v for k, v in request.headers.items()}
    ok, reason = verify(provider, raw_body=raw, headers=headers)
    workspace_id = body.get("workspace_id") or headers.get("x-maicos-workspace")
    if not ok:
        if workspace_id:
            try:
                record(db, company_id=workspace_id, actor=f"{provider}_webhook",
                       action="webhook.rejected", target_type="webhook",
                       target_id=event, details={"reason": reason})
                db.commit()
            except Exception:
                pass
        raise HTTPException(status_code=401, detail=reason)
    if not workspace_id:
        raise HTTPException(status_code=400, detail="workspace_id required")
    data = {k: v for k, v in body.items() if k != "workspace_id"}
    out = trigger_event(db, workspace_id=workspace_id, event=event, data=data)
    try:
        record(db, company_id=workspace_id, actor=f"{provider}_webhook",
               action="webhook.accepted", target_type="webhook",
               target_id=event, details={"provider": provider})
        db.commit()
    except Exception:
        pass
    return out


@router.post("/webhooks/{event}")
def ingest_event(
    event: str,
    request: Request,
    payload: dict[str, Any] | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Legacy unauthenticated intake. Kept for backward compat; disabled
    in production when WEBHOOK_SECRET is set (use /webhooks/{provider}/{event})."""
    import os

    if os.environ.get("WEBHOOK_SECRET"):
        raise HTTPException(
            status_code=401,
            detail="unsigned webhooks disabled; use /webhooks/{provider}/{event} with signature",
        )
    body = payload or {}
    workspace_id = body.get("workspace_id") or request.headers.get("X-MAICOS-Workspace")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="workspace_id required")
    data = {k: v for k, v in body.items() if k != "workspace_id"}
    return trigger_event(db, workspace_id=workspace_id, event=event, data=data)
