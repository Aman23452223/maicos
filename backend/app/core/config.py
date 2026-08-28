"""Centralized application settings.

Maps to PRD §15 (secrets) and §27 (LLM must not see raw credentials):
only configuration is loaded here, never model-side.
"""
from functools import lru_cache
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    redis_url: str = "redis://localhost:6379/0"

    llm_provider: str = "openrouter"
    llm_default_model: str = "minimax/minimax-m3:free"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    # OpenRouter (https://openrouter.ai). Set OPENROUTER_API_KEY in your
    # environment or paste it from the UI. Never commit the key.
    openrouter_api_key: str = ""
    openrouter_default_model: str = "minimax/minimax-m3:free"

    document_storage_dir: str = "./var/documents"
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    default_autonomy_level: int = 2
    approval_policy_json: str = "{}"

    def approval_policy(self) -> dict[str, Any]:
        import json

        try:
            return json.loads(self.approval_policy_json)
        except Exception:  # noqa: BLE001
            return {}


@lru_cache
def get_settings() -> Settings:
    return Settings()

