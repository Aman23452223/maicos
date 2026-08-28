"""Standardized tool / connector interface (PRD §21, §27).

Every connector implements the same surface. The tool layer is the
authorization boundary: the agent registry grants `allowed_tools`, and
the tool layer checks scopes and resolves secrets via the secret store
- never via the LLM prompt.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Protocol

from app.core.context import Principal


class ToolError(Exception):
    pass


class ToolAuthError(ToolError):
    pass


class ToolConflictError(ToolError):
    """Raised when an idempotency key has already been used with a
    different payload (PRD risk: integration failure / over-automation).
    """


@dataclass
class ToolResult:
    ok: bool
    data: dict[str, Any] | None = None
    confirmed: bool = False  # True only when the external system returned success
    message: str | None = None
    external_id: str | None = None


class Connector(Protocol):
    name: str

    def operations(self) -> list[str]: ...

    def execute(
        self,
        principal: Principal,
        operation: str,
        payload: dict[str, Any],
    ) -> ToolResult: ...


_REGISTRY: dict[str, Connector] = {}


def register(connector: Connector) -> None:
    _REGISTRY[connector.name] = connector


def get(connector_name: str) -> Connector:
    if connector_name not in _REGISTRY:
        raise ToolError(f"unknown connector: {connector_name}")
    return _REGISTRY[connector_name]


def list_connectors() -> list[dict[str, Any]]:
    return [
        {"name": c.name, "operations": c.operations()} for c in _REGISTRY.values()
    ]


_IDEMPOTENCY: dict[str, tuple[str, ToolResult]] = {}
_IDEMPOTENCY_LOCK = threading.Lock()


def _idempotency_lookup(key: str, payload_fingerprint: str) -> ToolResult | None:
    with _IDEMPOTENCY_LOCK:
        existing = _IDEMPOTENCY.get(key)
    if not existing:
        return None
    prior_fingerprint, prior_result = existing
    if prior_fingerprint != payload_fingerprint:
        raise ToolConflictError(
            f"idempotency key reused with different payload: {key}"
        )
    return prior_result


def _idempotency_store(key: str, payload_fingerprint: str, result: ToolResult) -> None:
    with _IDEMPOTENCY_LOCK:
        _IDEMPOTENCY[key] = (payload_fingerprint, result)


def execute_tool(
    principal: Principal,
    connector_name: str,
    operation: str,
    payload: dict[str, Any],
    allowed_tools: list[str],
    idempotency_key: str | None = None,
) -> ToolResult:
    """Authorize and execute a tool call (FR-06)."""
    token = f"{connector_name}.{operation}"
    if allowed_tools and "*" not in allowed_tools and token not in allowed_tools:
        raise ToolAuthError(f"tool not permitted for principal: {token}")
    connector = get(connector_name)
    if operation not in connector.operations():
        raise ToolError(f"operation not supported: {operation}")
    if idempotency_key:
        import hashlib
        import json

        fingerprint = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()
        cached = _idempotency_lookup(idempotency_key, fingerprint)
        if cached is not None:
            return cached
        result = connector.execute(principal, operation, payload)
        if result.ok and result.confirmed:
            _idempotency_store(idempotency_key, fingerprint, result)
        return result
    return connector.execute(principal, operation, payload)

