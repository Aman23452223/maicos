"""Workspace memory + business goals (generic, workspace-scoped)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.audit.service import record
from app.core.context import Principal
from app.core.security import get_current_principal
from app.db.session import get_db
from app.intel.service import get_or_create_profile
from app.models.orm import BusinessMemory

router = APIRouter(tags=["context"])

MEMORY_KINDS = {"fact", "preference", "goal_context", "pattern"}


class MemoryIn(BaseModel):
    kind: str = "fact"
    key: str = ""
    value: str = ""


class GoalIn(BaseModel):
    text: str
    status: str = "active"


@router.post("/memory")
def save_memory(payload: MemoryIn, p: Principal = Depends(get_current_principal),
                db: Session = Depends(get_db)):
    if payload.kind not in MEMORY_KINDS:
        raise HTTPException(status_code=400, detail=f"kind must be one of {sorted(MEMORY_KINDS)}")
    if "secret" in payload.key.lower() or "token" in payload.key.lower():
        raise HTTPException(status_code=400, detail="secrets must never be stored as memory")
    row = BusinessMemory(company_id=p.workspace_id, kind=payload.kind,
                         key=payload.key[:200], value=payload.value[:4000])
    db.add(row)
    db.flush()
    record(db, company_id=p.workspace_id, actor=p.user_id, action="memory.saved",
           target_type="memory", target_id=row.id, details={"kind": payload.kind})
    db.commit()
    return {"id": row.id}


@router.get("/memory")
def list_memory(kind: str | None = None, limit: int = 50,
                p: Principal = Depends(get_current_principal),
                db: Session = Depends(get_db)):
    q = db.query(BusinessMemory).filter(BusinessMemory.company_id == p.workspace_id)
    if kind:
        q = q.filter(BusinessMemory.kind == kind)
    rows = q.order_by(BusinessMemory.updated_at.desc()).limit(min(max(limit, 1), 200)).all()
    return [{"id": r.id, "kind": r.kind, "key": r.key, "value": r.value} for r in rows]


@router.delete("/memory/{memory_id}")
def delete_memory(memory_id: str, p: Principal = Depends(get_current_principal),
                  db: Session = Depends(get_db)):
    row = db.get(BusinessMemory, memory_id)
    if not row or row.company_id != p.workspace_id:
        raise HTTPException(status_code=404, detail="not found")
    db.delete(row)
    db.commit()
    return {"ok": True}


def _goals(bp) -> list[dict]:
    return list(bp.business_goals or [])


@router.get("/business/goals")
def list_goals(p: Principal = Depends(get_current_principal),
               db: Session = Depends(get_db)):
    return _goals(get_or_create_profile(db, company_id=p.workspace_id))


@router.post("/business/goals")
def add_goal(payload: GoalIn, p: Principal = Depends(get_current_principal),
             db: Session = Depends(get_db)):
    bp = get_or_create_profile(db, company_id=p.workspace_id)
    goals = _goals(bp)
    item = {"id": str(uuid.uuid4())[:8], "text": payload.text[:500],
            "status": payload.status}
    goals.append(item)
    bp.business_goals = goals
    record(db, company_id=p.workspace_id, actor=p.user_id, action="goal.added",
           target_type="goal", target_id=item["id"], details={"text": item["text"][:100]})
    db.commit()
    return item


@router.get("/capabilities/gap")
def capability_gap(intent: str, p: Principal = Depends(get_current_principal),
                   db: Session = Depends(get_db)):
    from app.capabilities.gap import analyze
    return analyze(db, company_id=p.workspace_id, intent=intent)


@router.delete("/business/goals/{goal_id}")
def delete_goal(goal_id: str, p: Principal = Depends(get_current_principal),
                db: Session = Depends(get_db)):
    bp = get_or_create_profile(db, company_id=p.workspace_id)
    goals = [g for g in _goals(bp) if g.get("id") != goal_id]
    if len(goals) == len(_goals(bp)):
        raise HTTPException(status_code=404, detail="not found")
    bp.business_goals = goals
    db.commit()
    return {"ok": True}
