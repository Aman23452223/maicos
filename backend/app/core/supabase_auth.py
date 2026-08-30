"""Supabase Auth integration (PRD §18).

When `SUPABASE_URL` and `SUPABASE_ANON_KEY` are set, the backend
verifies Supabase-issued JWTs from the `Authorization: Bearer <jwt>`
header. The `sub` claim is the Supabase `auth.users.id` (UUID). We
look up the MAICOS `User` by `supabase_user_id` and provision one on
first sight (lazy, transactionally-safe).

When Supabase is not configured, the original MAICOS JWT (HS256,
signed with `APP_SECRET_KEY`) keeps working — the two paths are
mutually exclusive per request.
"""
from __future__ import annotations

import json
import urllib.request
import uuid
from typing import Any

from fastapi import HTTPException
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.orm import Company, User

log = get_logger("supabase_auth")

_JWKS_CACHE: dict[str, Any] | None = None
_JWKS_CACHE_TS: float = 0.0
_JWKS_TTL_SECONDS = 600


def supabase_enabled() -> bool:
    s = get_settings()
    return bool(s.supabase_url and s.supabase_anon_key)


def _jwks() -> dict[str, Any]:
    global _JWKS_CACHE, _JWKS_CACHE_TS
    import time

    if _JWKS_CACHE is not None and (time.time() - _JWKS_CACHE_TS) < _JWKS_TTL_SECONDS:
        return _JWKS_CACHE
    s = get_settings()
    jwks_url = f"{s.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    with urllib.request.urlopen(jwks_url, timeout=5) as resp:
        _JWKS_CACHE = json.loads(resp.read().decode("utf-8"))
        _JWKS_CACHE_TS = time.time()
    return _JWKS_CACHE


def _verify_supabase_jwt(token: str) -> dict[str, Any]:
    """Verify a Supabase-issued JWT against the project's JWKS.

    Returns the decoded claims on success. Raises 401 on any failure.
    """
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"bad token header: {e}") from e
    kid = header.get("kid")
    if not kid:
        raise HTTPException(status_code=401, detail="missing kid in token")
    keys = _jwks().get("keys", [])
    key = next((k for k in keys if k.get("kid") == kid), None)
    if key is None:
        raise HTTPException(status_code=401, detail="unknown key id")
    try:
        return jwt.decode(
            token,
            key,
            algorithms=[key.get("alg", "RS256") or "RS256"],
            audience="authenticated",
        )
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"invalid supabase jwt: {e}") from e


def _get_or_create_user(db: Session, *, claims: dict[str, Any]) -> User:
    """Find or lazily create the MAICOS user for a Supabase principal.

    The Supabase `sub` claim is the canonical identity. We:

      1. look up `User.supabase_user_id == sub`; if found, return it
      2. otherwise look up `User.email == email` (claimed by Supabase);
         if found, attach the supabase_user_id and return it
      3. otherwise provision a new user + workspace (the user becomes
         the workspace owner with the full role set)
    """
    sub = claims.get("sub")
    email = claims.get("email")
    if not sub or not email:
        raise HTTPException(status_code=401, detail="supabase token missing sub/email")

    user = db.query(User).filter(User.supabase_user_id == sub).first()
    if user:
        return user

    user = db.query(User).filter(User.email == email).first()
    if user:
        user.supabase_user_id = sub
        db.flush()
        return user

    company = Company(name=email.split("@", 1)[1] if "@" in email else email)
    db.add(company)
    db.flush()
    user = User(
        id=str(uuid.uuid4()),
        company_id=company.id,
        email=email,
        name=claims.get("user_metadata", {}).get("name") or email.split("@", 1)[0],
        supabase_user_id=sub,
        roles=["admin", "owner"],
        is_active=True,
    )
    db.add(user)
    db.flush()
    log.info("supabase.user_provisioned", user_id=user.id, company_id=company.id)
    return user


def authenticate(db: Session, *, authorization: str | None) -> User:
    """Authenticate an incoming request.

    - If `Authorization: Bearer ...` looks like a Supabase JWT and
      `SUPABASE_URL` is set, verify against Supabase JWKS and provision.
    - Otherwise fall through to MAICOS HS256 verification.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.split(" ", 1)[1].strip()

    if supabase_enabled():
        # Cheap check: Supabase JWTs are 3 segments (JWE-style not used
        # for auth tokens). MAICOS tokens are signed with HS256. Try
        # Supabase first if the token has a 'kid' header.
        try:
            header = jwt.get_unverified_header(token)
        except JWTError:
            header = {}
        if header.get("kid"):
            claims = _verify_supabase_jwt(token)
            return _get_or_create_user(db, claims=claims)

    # Fall back to MAICOS JWT
    s = get_settings()
    try:
        payload = jwt.decode(token, s.app_secret_key, algorithms=["HS256"])
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"invalid token: {e}") from e
    user = db.get(User, payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="user inactive")
    return user
