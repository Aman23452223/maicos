"""Workspace and authentication routes (FR-01, FR-02)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.audit.service import record
from app.core.context import Principal
from app.core.security import (
    create_access_token,
    get_current_principal,
    hash_password,
    require_role,
    verify_password,
)
from app.db.session import get_db
from app.models.orm import Company, User
from app.schemas import (
    LoginIn,
    RegisterIn,
    TokenOut,
    UserCreate,
    UserOut,
    WorkspaceCreate,
    WorkspaceOut,
)

router = APIRouter(tags=["auth"])


@router.get("/auth/version")
def auth_version():
    return {"version": "2026-09-11-004", "has_register": True}


@router.post("/workspaces", response_model=WorkspaceOut)
def create_workspace(payload: WorkspaceCreate, db: Session = Depends(get_db),
                     p: Principal = Depends(get_current_principal)) -> WorkspaceOut:
    from app.models.orm import WorkspaceMembership

    # Any authenticated member can create; creator becomes OWNER of new workspace.
    company = Company(name=payload.name, status="active")
    db.add(company)
    db.flush()
    db.add(WorkspaceMembership(user_id=p.user_id, company_id=company.id,
                               role="owner", status="active"))
    record(
        db,
        company_id=company.id,
        actor=p.user_id,
        action="workspace.created",
        target_type="workspace",
        target_id=company.id,
        details={"name": payload.name},
    )
    db.commit()
    db.refresh(company)
    return WorkspaceOut(id=company.id, name=company.name, autonomy_level=company.autonomy_level)


@router.get("/workspaces")
def list_workspaces(p: Principal = Depends(get_current_principal),
                    db: Session = Depends(get_db)):
    from app.models.orm import Company, WorkspaceMembership
    rows = db.query(WorkspaceMembership).filter(
        WorkspaceMembership.user_id == p.user_id,
        WorkspaceMembership.status == "active").all()
    out = []
    for m in rows:
        co = db.get(Company, m.company_id)
        if co:
            out.append({"id": co.id, "name": co.name, "role": m.role,
                        "status": co.status, "current": co.id == p.workspace_id})
    # Backward compat: legacy primary workspace without membership row
    if not out:
        co = db.get(Company, p.workspace_id)
        if co:
            out.append({"id": co.id, "name": co.name, "role": "owner",
                        "status": co.status, "current": True})
    return out


@router.post("/auth/switch")
def switch_workspace(payload: dict, p: Principal = Depends(get_current_principal),
                     db: Session = Depends(get_db)):
    from app.schemas import TokenOut
    from app.tenancy.membership import membership_role as _role_for

    ws = str(payload.get("workspace_id", ""))
    role = _role_for(db, user_id=p.user_id, company_id=ws)
    if not role:
        raise HTTPException(status_code=403, detail="not a workspace member")
    token = create_access_token(sub=p.user_id, workspace_id=ws, roles=[role])
    return TokenOut(access_token=token)


@router.post("/workspaces/{workspace_id}/users", response_model=UserOut)
def create_user(
    workspace_id: str,
    payload: UserCreate,
    db: Session = Depends(get_db),
    p: Principal = Depends(require_role("admin", "owner")),
) -> UserOut:
    from app.models.orm import WorkspaceMembership

    # Strict tenant check: can only manage users in own workspace.
    if workspace_id != p.workspace_id:
        raise HTTPException(status_code=403, detail="cross-workspace user creation forbidden")
    user = User(
        company_id=workspace_id,
        email=payload.email,
        name=payload.name,
        password_hash=hash_password(payload.password),
        roles=payload.roles,
    )
    db.add(user)
    db.flush()
    role = (payload.roles or ["member"])[0] if payload.roles else "member"
    if role not in ("owner", "admin", "member"):
        role = "member"
    db.add(WorkspaceMembership(user_id=user.id, company_id=workspace_id,
                               role=role, status="active"))
    db.commit()
    db.refresh(user)
    return UserOut(id=user.id, email=user.email, name=user.name, roles=user.roles)


@router.post("/auth/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
    clean_email = str(payload.email).lower().strip()
    user = db.query(User).filter(User.email == clean_email).first()
    if not user:
        raise HTTPException(status_code=401, detail="invalid credentials")
    if not user.password_hash:
        user.password_hash = hash_password(payload.password)
        db.commit()
        db.refresh(user)
    elif not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = create_access_token(
        sub=user.id, workspace_id=user.company_id, roles=user.roles or []
    )
    return TokenOut(access_token=token)


@router.post("/auth/register", response_model=TokenOut)
def register(payload: RegisterIn, db: Session = Depends(get_db)) -> TokenOut:
    clean_email = str(payload.email).lower().strip()
    user = db.query(User).filter(User.email == clean_email).first()
    if user:
        # If user already exists (e.g. provisioned previously without a password)
        if not user.password_hash:
            user.password_hash = hash_password(payload.password)
            if payload.name and not user.name:
                user.name = payload.name
            db.commit()
            db.refresh(user)
        elif not verify_password(payload.password, user.password_hash):
            raise HTTPException(
                status_code=400,
                detail="Email already registered. Please sign in with your password.",
            )
        token = create_access_token(
            sub=user.id, workspace_id=user.company_id, roles=user.roles or []
        )
        return TokenOut(access_token=token)

    try:
        company_id = str(uuid.uuid4())
        company_name = (
            payload.company_name
            or (clean_email.split("@")[1] if "@" in clean_email else "Workspace")
        )
        company = Company(
            id=company_id,
            name=company_name,
            autonomy_level=2,
        )
        db.add(company)
        db.flush()

        user_id = str(uuid.uuid4())
        user = User(
            id=user_id,
            company_id=company_id,
            email=clean_email,
            name=payload.name or clean_email.split("@")[0],
            password_hash=hash_password(payload.password),
            roles=["admin", "owner"],
            is_active=True,
        )
        db.add(user)
        db.flush()
        from app.models.orm import WorkspaceMembership

        db.add(WorkspaceMembership(user_id=user_id, company_id=company_id,
                                  role="owner", status="active"))
        db.commit()
        db.refresh(user)

        token = create_access_token(
            sub=user.id, workspace_id=user.company_id, roles=user.roles or []
        )
        return TokenOut(access_token=token)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to create workspace: {e}"
        )


@router.get("/auth/me", response_model=UserOut)
def me(p: Principal = Depends(get_current_principal), db: Session = Depends(get_db)) -> UserOut:
    u = db.get(User, p.user_id)
    if not u:
        raise HTTPException(status_code=404, detail="user not found")
    return UserOut(id=u.id, email=u.email, name=u.name, roles=u.roles)

