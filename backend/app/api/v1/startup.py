"""Startup Builder API (idea -> validation -> blueprint -> workspace)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.audit.service import record
from app.core.context import Principal
from app.core.security import get_current_principal
from app.db.session import get_db
from app.models.orm import StartupBlueprint, WorkforceRole

router = APIRouter(tags=["startup"])


class IdeaIn(BaseModel):
    idea: str


@router.post("/startup/idea")
def startup_idea(payload: IdeaIn, p: Principal = Depends(get_current_principal),
                 db: Session = Depends(get_db)):
    from app.company.startup import parse_idea

    _ = (db, p)
    try:
        return parse_idea(payload.idea)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/startup/validate")
def startup_validate(payload: IdeaIn,
                     p: Principal = Depends(get_current_principal),
                     db: Session = Depends(get_db)):
    from app.company.startup import validate_idea

    return validate_idea(db, company_id=p.workspace_id, idea=payload.idea)


class BlueprintSaveIn(BaseModel):
    idea: str
    sections: dict = {}


@router.post("/startup/blueprint")
def startup_blueprint_save(payload: BlueprintSaveIn,
                           p: Principal = Depends(get_current_principal),
                           db: Session = Depends(get_db)):
    row = StartupBlueprint(company_id=p.workspace_id, idea=payload.idea[:2000],
                           sections=payload.sections, status="draft")
    db.add(row)
    db.commit()
    return {"id": row.id, "status": row.status}


@router.get("/startup/blueprints")
def startup_blueprints(p: Principal = Depends(get_current_principal),
                       db: Session = Depends(get_db)):
    rows = db.query(StartupBlueprint).filter(
        StartupBlueprint.company_id == p.workspace_id).order_by(
        StartupBlueprint.created_at.desc()).limit(50).all()
    return [{"id": r.id, "idea": r.idea[:200], "status": r.status,
             "sections": len(r.sections or {})} for r in rows]


@router.post("/startup/blueprints/{bid}/approve")
def startup_blueprint_approve(bid: str,
                              p: Principal = Depends(get_current_principal),
                              db: Session = Depends(get_db)):
    row = db.get(StartupBlueprint, bid)
    if not row or row.company_id != p.workspace_id:
        raise HTTPException(status_code=404, detail="not found")
    row.status = "approved"
    record(db, company_id=p.workspace_id, actor=p.user_id,
           action="startup.approved", target_type="blueprint",
           target_id=row.id, details={})
    db.commit()
    return {"id": row.id, "status": row.status}


@router.post("/startup/blueprints/{bid}/apply")
def startup_blueprint_apply(bid: str,
                            p: Principal = Depends(get_current_principal),
                            db: Session = Depends(get_db)):
    from app.company.blueprint import apply_blueprint

    row = db.get(StartupBlueprint, bid)
    if not row or row.company_id != p.workspace_id:
        raise HTTPException(status_code=404, detail="not found")
    if row.status != "approved":
        raise HTTPException(status_code=409, detail="approve the blueprint first")
    out = apply_blueprint(db, company_id=p.workspace_id,
                          blueprint={"idea": row.idea, "sections": row.sections or {}},
                          actor=p.user_id)
    row.status = "applied"
    db.commit()
    return {**out, "blueprint_id": row.id}


class WorkspaceCreateIn(BaseModel):
    name: str
    blueprint_id: str | None = None


@router.post("/startup/create-workspace")
def startup_create_workspace(payload: WorkspaceCreateIn,
                             p: Principal = Depends(get_current_principal),
                             db: Session = Depends(get_db)):
    from app.company.startup import create_startup_workspace

    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="name required")
    if payload.blueprint_id:
        row = db.get(StartupBlueprint, payload.blueprint_id)
        if not row or row.company_id != p.workspace_id:
            raise HTTPException(status_code=404, detail="blueprint not found")
        if row.status != "applied":
            raise HTTPException(status_code=409,
                                detail="apply the approved blueprint first")
    try:
        return create_startup_workspace(db, user_id=p.user_id, name=payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/startup/status")
def startup_status(p: Principal = Depends(get_current_principal),
                   db: Session = Depends(get_db)):
    from app.company.startup import lifecycle_status

    return lifecycle_status(db, company_id=p.workspace_id)


class RoleIn(BaseModel):
    title: str
    kind: str = "ai"


@router.get("/startup/roles")
def startup_roles(p: Principal = Depends(get_current_principal),
                  db: Session = Depends(get_db)):
    rows = db.query(WorkforceRole).filter(
        WorkforceRole.company_id == p.workspace_id).all()
    return [{"id": r.id, "title": r.title, "kind": r.kind, "status": r.status}
            for r in rows]


@router.post("/startup/roles")
def startup_role_add(payload: RoleIn, p: Principal = Depends(get_current_principal),
                     db: Session = Depends(get_db)):
    if payload.kind not in ("ai", "human"):
        raise HTTPException(status_code=400, detail="kind must be ai|human")
    row = WorkforceRole(company_id=p.workspace_id, title=payload.title[:255],
                        kind=payload.kind)
    db.add(row)
    db.commit()
    return {"id": row.id}
