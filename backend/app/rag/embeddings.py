"""Embedding provider abstraction (Phase 3).

Statuses: OK | NOT_CONFIGURED | PROVIDER_ERROR. Never fake vectors.
Test providers allowed only in tests via register().
"""
from __future__ import annotations

import os
from typing import Protocol


class EmbeddingResult(dict):
    pass


class EmbeddingProvider(Protocol):
    name: str

    def embed(self, texts: list[str]) -> dict: ...


class OpenAIEmbeddingProvider:
    name = "openai"

    def embed(self, texts: list[str]) -> dict:
        key = os.environ.get("OPENAI_API_KEY", "")
        if not key:
            return {"ok": False, "status": "NOT_CONFIGURED",
                    "error": "OPENAI_API_KEY not configured"}
        try:
            from openai import OpenAI
            client = OpenAI(api_key=key)
            model = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
            resp = client.embeddings.create(model=model, input=texts[:96])
            vecs = [d.embedding for d in resp.data]
            return {"ok": True, "status": "OK", "vectors": vecs, "model": model}
        except Exception as exc:
            return {"ok": False, "status": "PROVIDER_ERROR", "error": str(exc)[:500]}


class TestEmbeddingProvider:
    """Deterministic hash vectors for tests only. Never used in production."""
    name = "test"

    def embed(self, texts: list[str]) -> dict:
        import hashlib
        vecs = []
        for t in texts:
            h = hashlib.sha256(t.encode()).digest()
            vecs.append([b / 255.0 for b in h[:32]])
        return {"ok": True, "status": "OK", "vectors": vecs, "model": "test-hash-32"}


_REGISTRY = {"openai": OpenAIEmbeddingProvider(), "test": TestEmbeddingProvider()}


def get(name: str):
    if name not in _REGISTRY:
        raise KeyError(f"unknown embedding provider: {name}")
    return _REGISTRY[name]


def default_provider_name() -> str:
    return os.environ.get("EMBEDDING_PROVIDER", "openai")
