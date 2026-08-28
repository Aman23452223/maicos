"""Lightweight, never-logged secret access.

Per PRD §18 / §27, the LLM must never receive raw credentials.
This module is the single boundary that resolves secrets for connectors.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from app.core.config import get_settings


@dataclass(frozen=True)
class ResolvedSecret:
    name: str
    value: str

    def redact(self) -> str:
        return f"{self.name}=***"


@lru_cache
def get_secret(name: str) -> str | None:
    """Resolve a secret from env or an external store.

    The MVP implementation reads from environment variables. A vault
    adapter (AWS Secrets Manager, HashiCorp Vault, etc.) can be swapped
    in here without changing any agent/tool code.
    """
    val = os.environ.get(name)
    if val:
        return val
    settings = get_settings()
    if name == "OPENAI_API_KEY":
        return settings.openai_api_key or None
    if name == "ANTHROPIC_API_KEY":
        return settings.anthropic_api_key or None
    if name == "OPENROUTER_API_KEY":
        return settings.openrouter_api_key or os.environ.get("OPENROUTER_API_KEY") or None
    return None


def set_runtime_secret(name: str, value: str) -> None:
    """Set a secret in-process (e.g. from the UI Settings page).

    This stores the secret in the current process's environment so all
    subsequent calls to `get_secret` see it. It is **never** persisted
    to disk or logs. Combined with the redacted model output, this lets
    users paste a key once and use the LLM without a redeploy.
    """
    os.environ[name] = value
    # Bust the cache so the next call re-reads the env.
    get_secret.cache_clear()

