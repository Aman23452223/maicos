"""Workspace/tenant context (PRD §18 strict tenant isolation)."""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class Principal:
    user_id: str
    workspace_id: str
    roles: tuple[str, ...]
    autonomy_level: int = 2


_current: ContextVar[Principal | None] = ContextVar("current_principal", default=None)


def set_principal(p: Principal | None) -> None:
    _current.set(p)


def get_principal() -> Principal | None:
    return _current.get()


def require_principal() -> Principal:
    p = _current.get()
    if p is None:
        raise PermissionError("No authenticated principal in request context")
    return p

