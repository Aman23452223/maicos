"""Queue observability routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import Principal
from app.core.security import require_role
from app.db.session import get_db
from app.queue import jobs as queue

router = APIRouter(prefix="/queue", tags=["queue"])


@router.get("/stats")
def stats(
    db: Session = Depends(get_db),
    _: Principal = Depends(require_role("admin", "owner")),
) -> dict[str, Any]:
    """Counts of workflow jobs per status."""
    return queue.queue_stats(db)