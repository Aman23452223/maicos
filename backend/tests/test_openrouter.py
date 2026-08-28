"""Live integration tests against OpenRouter.

These tests hit the real OpenRouter API. They are skipped unless
OPENROUTER_API_KEY is set in the environment, so CI without a secret
stays green while a developer can run them locally with a key.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.llm.gateway import LLMRequest, OpenRouterClient

pytestmark = pytest.mark.skipif(
    not os.environ.get("OPENROUTER_API_KEY")
    and not get_settings().openrouter_api_key,
    reason="OPENROUTER_API_KEY not configured",
)


def test_openrouter_minimax_m3_completes():
    client = OpenRouterClient("minimax/minimax-m3:free")
    r = client.complete(
        LLMRequest(
            system="You are a connectivity check. Reply with one short sentence.",
            user="ping",
            temperature=0,
        )
    )
    assert r.text
    assert r.model
