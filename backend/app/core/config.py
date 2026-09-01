"""Centralized application settings.

Maps to PRD §15 (secrets) and §27 (LLM must not see raw credentials):
only configuration is loaded here, never model-side.
"""
import re
from functools import lru_cache
from typing import Annotated, Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "multi-agent-ai-company-os"
    app_env: str = "dev"
    app_secret_key: str = "change-me"
    app_log_level: str = "INFO"

    database_url: str = "postgresql+psycopg2://os:os@localhost:5432/os"
    vector_backend: str = "pgvector"

    redis_url: str = ""
    # MAICOS now uses Postgres for the job queue + scheduled jobs.
    # This field is kept for backward compatibility with old config
    # files; it is unused. See `workflow_jobs` and `scheduled_jobs`.
    # DEFAULT FALSE in production — the in-process worker has been
    # observed to crash the deploy on Railway (uvicorn process 1
    # exited with code 1, deploy marked Removed). Toggle back to true
    # via the WORKER_ENABLED env var once the underlying crash is
    # diagnosed via the deploy logs.
    worker_enabled: bool = False
    worker_id: str = "maicos-worker"
    # When true, the lifespan skips starting the in-process worker
    # entirely. Useful for diagnostic deploys where the user wants
    # to confirm the web process is up before turning the worker
    # back on. Set WORKER_SKIP=true to enable.
    worker_skip: bool = False
    # Hard upper bound on how long the lifespan waits for the
    # startup DB connectivity check. A broken DNS or unreachable
    # host must not hold up uvicorn beyond this many seconds.
    db_startup_timeout: float = 10.0

    llm_provider: str = "openrouter"
    llm_default_model: str = "minimax/minimax-m3:free"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    # OpenRouter (https://openrouter.ai). Set OPENROUTER_API_KEY in your
    # environment or paste it from the UI. Never commit the key.
    openrouter_api_key: str = ""
    openrouter_default_model: str = "minimax/minimax-m3:free"

    document_storage_dir: str = "./var/documents"
    # Comma-separated list. Wildcards ("*") are accepted in dev only.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["*"]
    )
    # Optional regex for Vercel preview URLs (*.vercel.app) etc.
    # Empty by default; supply via CORS_ORIGIN_REGEX if you use previews.
    cors_origin_regex: str = ""

    # --- Supabase ---
    # When set, the backend verifies Supabase-issued JWTs (RS256) and
    # provisions MAICOS users on first sight. MAICOS HS256 tokens keep
    # working — the verifier auto-detects by inspecting the JWT header.
    supabase_url: str = ""
    supabase_anon_key: str = ""

    default_autonomy_level: int = 2
    approval_policy_json: str = "{}"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, v: Any) -> Any:
        if isinstance(v, str) and v.strip():
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @model_validator(mode="after")
    def _reject_unresolved_placeholders(self) -> "Settings":
        """Catch config values that still contain template placeholders.

        The .env.example file uses <PASSWORD>, <REGION>, <PROJECT_REF>
        as illustrative placeholders. If a user copy-pastes one of
        those lines into Railway Variables without filling them in, the
        app would otherwise start, log a useless
        'could not translate host name "<REGION>"' error, and 502.
        Fail fast at startup instead.
        """
        placeholders = re.findall(r"<[A-Z_]+>", self.database_url)
        for ph in placeholders:
            raise ValueError(
                f"DATABASE_URL still contains an unresolved placeholder "
                f"{ph!r}. Replace it with the actual value (see the .env.example "
                f"file for the format)."
            )
        return self

    def approval_policy(self) -> dict[str, Any]:
        import json

        try:
            return json.loads(self.approval_policy_json)
        except Exception:  # noqa: BLE001
            return {}


@lru_cache
def get_settings() -> Settings:
    return Settings()

