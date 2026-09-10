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


@router.post("/workspaces", response_model=WorkspaceOut)
def create_workspace(payload: WorkspaceCreate, db: Session = Depends(get_db)) -> WorkspaceOut:
    company = Company(name=payload.name)
    db.add(company)
    db.flush()
    record(
        db,
        company_id=company.id,
        actor="system",
        action="workspace.created",
        target_type="workspace",
        target_id=company.id,
        details={"name": payload.name},
    )
    db.commit()
    db.refresh(company)
    return WorkspaceOut(id=company.id, name=company.name, autonomy_level=company.autonomy_level)


@router.post("/workspaces/{workspace_id}/users", response_model=UserOut)
def create_user(
    workspace_id: str,
    payload: UserCreate,
    db: Session = Depends(get_db),
    _: Principal = Depends(require_role("admin", "owner")),
) -> UserOut:
    user = User(
        company_id=workspace_id,
        email=payload.email,
        name=payload.name,
        password_hash=hash_password(payload.password),
        roles=payload.roles,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserOut(id=user.id, email=user.email, name=user.name, roles=user.roles)


@router.post("/auth/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
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

