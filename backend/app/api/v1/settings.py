"""Runtime LLM settings (paste your own provider keys via the UI)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.audit.service import record
from app.core.context import Principal
from app.core.secrets import get_secret, set_runtime_secret
from app.core.security import get_current_principal, require_role
from app.db.session import get_db
from app.llm.gateway import get_llm

router = APIRouter(tags=["settings"])


class SettingsOut(BaseModel):
    llm_provider: str
    llm_default_model: str
    openrouter_configured: bool
    openai_configured: bool
    anthropic_configured: bool


class SettingsUpdate(BaseModel):
    llm_provider: str | None = None
    llm_default_model: str | None = None
    openrouter_api_key: str | None = Field(default=None, min_length=10)
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None


@router.get("/settings", response_model=SettingsOut)
def read_settings(
    _: Principal = Depends(get_current_principal),
) -> SettingsOut:
    from app.core.config import get_settings

    s = get_settings()
    return SettingsOut(
        llm_provider=s.llm_provider,
        llm_default_model=s.llm_default_model,
        openrouter_configured=bool(get_secret("OPENROUTER_API_KEY")),
        openai_configured=bool(get_secret("OPENAI_API_KEY")),
        anthropic_configured=bool(get_secret("ANTHROPIC_API_KEY")),
    )


@router.post("/settings", response_model=SettingsOut)
def update_settings(
    payload: SettingsUpdate,
    p: Principal = Depends(require_role("admin", "owner")),
    db: Session = Depends(get_db),
) -> SettingsOut:
    if payload.llm_provider:
        if payload.llm_provider not in {"openrouter", "openai", "anthropic"}:
            raise HTTPException(status_code=400, detail="unsupported provider")
        os_environ_update = {"LLM_PROVIDER": payload.llm_provider}
        import os
        os.environ.update(os_environ_update)
    if payload.llm_default_model:
        import os
        os.environ["LLM_DEFAULT_MODEL"] = payload.llm_default_model
    if payload.openrouter_api_key:
        set_runtime_secret("OPENROUTER_API_KEY", payload.openrouter_api_key)
    if payload.openai_api_key:
        set_runtime_secret("OPENAI_API_KEY", payload.openai_api_key)
    if payload.anthropic_api_key:
        set_runtime_secret("ANTHROPIC_API_KEY", payload.anthropic_api_key)
    # Bust pydantic-settings cache so the new env takes effect.
    from app.core.config import get_settings
    get_settings.cache_clear()
    s = get_settings()
    record(
        db,
        company_id=p.workspace_id,
        actor=p.user_id,
        action="settings.updated",
        target_type="settings",
        target_id="llm",
        details={
            "provider": s.llm_provider,
            "keys_set": {
                "openrouter": bool(payload.openrouter_api_key),
                "openai": bool(payload.openai_api_key),
                "anthropic": bool(payload.anthropic_api_key),
            },
        },
    )
    db.commit()
    return read_settings(_=p)


@router.post("/settings/test")
def test_llm(
    p: Principal = Depends(get_current_principal),
) -> dict[str, Any]:
    """Ping the configured LLM to confirm credentials work."""
    try:
        client = get_llm()
        r = client.complete(_test_request())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"LLM test failed: {e}") from e
    return {"ok": True, "model": r.model, "sample": r.text[:120]}


def _test_request():
    from app.llm.gateway import LLMRequest

    return LLMRequest(
        system="You are a connectivity check. Reply with one short sentence.",
        user="ping",
        temperature=0,
    )
