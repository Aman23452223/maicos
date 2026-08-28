"""Authentication and RBAC (PRD FR-01, FR-02, §18)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import bcrypt
from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.context import Principal, set_principal
from app.db.session import get_db
from app.models.orm import User

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    # bcrypt has a 72-byte limit; truncate defensively to keep the helper
    # robust regardless of caller input.
    raw = password.encode("utf-8")[:72]
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    raw = password.encode("utf-8")[:72]
    try:
        return bcrypt.checkpw(raw, password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(*, sub: str, workspace_id: str, roles: list[str]) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": sub,
        "workspace_id": workspace_id,
        "roles": roles,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=8)).timestamp()),
    }
    return jwt.encode(payload, s.app_secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    s = get_settings()
    try:
        return jwt.decode(token, s.app_secret_key, algorithms=[ALGORITHM])
    except JWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"invalid token: {e}") from e


def get_current_principal(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Principal:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_token(token)
    user = db.get(User, payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="user inactive")
    principal = Principal(
        user_id=user.id,
        workspace_id=user.company_id,
        roles=tuple(user.roles or []),
    )
    set_principal(principal)
    return principal


def require_role(*roles: str):
    def _checker(p: Principal = Depends(get_current_principal)) -> Principal:
        if not any(r in p.roles for r in roles):
            raise HTTPException(status_code=403, detail=f"requires one of: {roles}")
        return p

    return _checker

