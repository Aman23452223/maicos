"""Provider-independent LLM gateway (PRD §15).

Agents do not import vendor SDKs directly. They call this gateway so the
provider and model can be swapped via configuration.

Supported providers (set LLM_PROVIDER):
  * openai       - OpenAI Chat Completions
  * anthropic    - Anthropic Messages
  * openrouter   - OpenAI-compatible, free models (e.g. MiniMax-M3 free)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.core.config import get_settings


@dataclass
class LLMRequest:
    system: str
    user: str
    model: str | None = None
    temperature: float = 0.2
    json_mode: bool = False


@dataclass
class LLMResponse:
    text: str
    model: str
    raw: dict | None = None


class LLMClient(Protocol):
    def complete(self, req: LLMRequest) -> LLMResponse: ...


class OpenAIClient:
    def __init__(self, default_model: str, base_url: str | None = None) -> None:
        self.default_model = default_model
        self.base_url = base_url
        self._client = None

    def _sdk(self):
        if self._client is None:
            from openai import OpenAI  # type: ignore

            s = get_settings()
            self._client = OpenAI(
                api_key=s.openai_api_key,
                base_url=self.base_url,
            )
        return self._client

    def complete(self, req: LLMRequest) -> LLMResponse:
        client = self._sdk()
        model = req.model or self.default_model
        kwargs: dict = {
            "model": model,
            "temperature": req.temperature,
            "messages": [
                {"role": "system", "content": req.system},
                {"role": "user", "content": req.user},
            ],
        }
        if req.json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        r = client.chat.completions.create(**kwargs)
        return LLMResponse(text=r.choices[0].message.content or "", model=model, raw=r.model_dump())


class OpenRouterClient(OpenAIClient):
    """OpenAI-compatible client pointed at OpenRouter.

    Free models (e.g. `minimax/minimax-m3:free`) are routed through
    OpenRouter; the model id includes the provider prefix.
    """

    OPENROUTER_BASE = "https://openrouter.ai/api/v1"

    def __init__(self, default_model: str) -> None:
        super().__init__(default_model, base_url=self.OPENROUTER_BASE)

    def _sdk(self):  # type: ignore[override]
        if self._client is None:
            from openai import OpenAI  # type: ignore

            from app.core.secrets import get_secret

            token = get_secret("OPENROUTER_API_KEY")
            if not token:
                raise RuntimeError(
                    "OPENROUTER_API_KEY not set. Paste it via the UI (Settings) "
                    "or set it as an env var / secret. Never commit it."
                )
            self._client = OpenAI(
                api_key=token,
                base_url=self.OPENROUTER_BASE,
                default_headers={
                    # OpenRouter recommends identifying the app; values are
                    # public info, no secrets.
                    "HTTP-Referer": "https://maicos.local",
                    "X-Title": "MAICOS",
                },
            )
        return self._client


class AnthropicClient:
    def __init__(self, default_model: str) -> None:
        self.default_model = default_model
        self._client = None

    def _sdk(self):
        if self._client is None:
            import anthropic  # type: ignore

            s = get_settings()
            self._client = anthropic.Anthropic(api_key=s.anthropic_api_key)
        return self._client

    def complete(self, req: LLMRequest) -> LLMResponse:
        client = self._sdk()
        model = req.model or self.default_model
        r = client.messages.create(
            model=model,
            max_tokens=2048,
            temperature=req.temperature,
            system=req.system,
            messages=[{"role": "user", "content": req.user}],
        )
        text = ""
        for block in r.content:
            if getattr(block, "type", None) == "text":
                text += block.text
        return LLMResponse(text=text, model=model, raw=None)


def get_llm() -> LLMClient:
    s = get_settings()
    provider = s.llm_provider.lower()
    if provider == "openrouter":
        return OpenRouterClient(s.llm_default_model)
    if provider == "openai":
        return OpenAIClient(s.llm_default_model)
    if provider == "anthropic":
        return AnthropicClient(s.llm_default_model)
    # Fallback so the system boots without config.
    return OpenAIClient(s.llm_default_model)

