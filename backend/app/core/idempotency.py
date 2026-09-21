"""DB-backed idempotency (Phase 18). Survives restarts."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.orm import IdempotencyKey


def _fp(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def check_or_claim(db: Session, *, company_id: str, key: str,
                   payload: dict) -> dict | None:
    """Return cached result if same key+payload seen, else None (caller executes)."""
    fp = _fp(payload)
    row = db.query(IdempotencyKey).filter(
        IdempotencyKey.company_id == company_id, IdempotencyKey.key == key).first()
    if not row:
        return None
    if row.fingerprint != fp:
        raise ValueError(f"idempotency key reused with different payload: {key}")
    return dict(row.result or {})


def store(db: Session, *, company_id: str, key: str,
          payload: dict, result: dict) -> None:
    fp = _fp(payload)
    row = db.query(IdempotencyKey).filter(
        IdempotencyKey.company_id == company_id, IdempotencyKey.key == key).first()
    if row:
        row.fingerprint = fp
        row.result = result
    else:
        db.add(IdempotencyKey(company_id=company_id, key=key,
                              fingerprint=fp, result=result))
    db.flush()


def execute_once(db: Session, *, company_id: str, key: str, payload: dict,
                 fn: Any) -> dict[str, Any]:
    cached = check_or_claim(db, company_id=company_id, key=key, payload=payload)
    if cached is not None:
        return {**cached, "deduplicated": True}
    result = fn()
    if isinstance(result, dict) and result.get("ok"):
        store(db, company_id=company_id, key=key, payload=payload, result=result)
    return result
