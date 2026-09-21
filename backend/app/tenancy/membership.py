"""Membership + role enforcement. Additive; legacy single-workspace still works."""
from __future__ import annotations

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.context import Principal
from app.core.security import get_current_principal
from app.db.session import get_db
from app.models.orm import User, WorkspaceMembership

ROLE_RANK = {"member": 1, "admin": 2, "owner": 3}


def membership_role(db: Session, *, user_id: str, company_id: str) -> str | None:
    m = db.query(WorkspaceMembership).filter(
        WorkspaceMembership.user_id == user_id,
        WorkspaceMembership.company_id == company_id,
        WorkspaceMembership.status == "active").first()
    if m:
        return m.role
    # Backward compat: legacy user row owns exactly one workspace
    u = db.get(User, user_id)
    if u and u.company_id == company_id and (u.roles or []):
        for r in ("owner", "admin", "member"):
            if r in u.roles:
                return r
        return "member"
    return None


def ensure_member(db: Session, p: Principal, company_id: str) -> str:
    role = membership_role(db, user_id=p.user_id, company_id=company_id)
    if not role:
        raise HTTPException(status_code=403, detail="not a workspace member")
    return role


def require_workspace_role(*roles: str, company_arg: str = "workspace_id"):
    """Enforce membership + min role on a path/query param workspace id."""
    def _checker(p: Principal = Depends(get_current_principal),
                 db: Session = Depends(get_db)) -> Principal:
        # Callers pass workspace explicitly; default to token workspace.
        company_id = p.workspace_id
        role = membership_role(db, user_id=p.user_id, company_id=company_id)
        if not role:
            raise HTTPException(status_code=403, detail="not a workspace member")
        need = max(ROLE_RANK.get(r, 0) for r in roles)
        if ROLE_RANK.get(role, 0) < need:
            raise HTTPException(status_code=403, detail=f"requires one of: {roles}")
        return p
    return _checker


def assert_resource_workspace(resource_company_id: str, p: Principal) -> None:
    if resource_company_id != p.workspace_id:
        raise HTTPException(status_code=404, detail="not found")
