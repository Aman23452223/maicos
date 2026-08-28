"""Permission-scoped retrieval over company documents (PRD §22).

The MVP store keeps an in-memory inverted index with token bags and
per-document role gates. Retrieval always intersects the result set
with the principal's roles. The same interface can be backed by
pgvector or a dedicated vector DB later.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from app.core.context import Principal


@dataclass
class Chunk:
    document_id: str
    document_name: str
    text: str
    tokens: set[str]
    access_roles: tuple[str, ...]


class KnowledgeIndex:
    def __init__(self) -> None:
        self._chunks: list[Chunk] = []
        self._by_workspace: dict[str, list[int]] = defaultdict(list)

    def add(
        self,
        *,
        workspace_id: str,
        document_id: str,
        document_name: str,
        text: str,
        access_roles: list[str],
        chunk_size: int = 400,
        chunk_overlap: int = 50,
    ) -> int:
        """Add a document, splitting into overlapping word-window chunks.

        Returns the number of chunks indexed.
        """
        words = text.split()
        if not words:
            return 0
        step = max(1, chunk_size - chunk_overlap)
        count = 0
        for start in range(0, len(words), step):
            window = words[start : start + chunk_size]
            if not window:
                break
            joined = " ".join(window)
            tokens = {t.lower() for t in re.findall(r"[A-Za-z0-9]+", joined) if len(t) > 2}
            if not tokens:
                continue
            chunk = Chunk(
                document_id=document_id,
                document_name=document_name,
                text=joined,
                tokens=tokens,
                access_roles=tuple(access_roles or []),
            )
            self._chunks.append(chunk)
            self._by_workspace[workspace_id].append(len(self._chunks) - 1)
            count += 1
        return count

    def search(
        self,
        *,
        principal: Principal,
        query: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        q_tokens = {t.lower() for t in re.findall(r"[A-Za-z0-9]+", query) if len(t) > 2}
        if not q_tokens:
            return []
        scored: list[tuple[float, Chunk]] = []
        roles = set(principal.roles)
        for idx in self._by_workspace.get(principal.workspace_id, []):
            chunk = self._chunks[idx]
            # Permission gate: empty role list = open to all in workspace.
            if chunk.access_roles and not (roles & set(chunk.access_roles)):
                continue
            overlap = len(q_tokens & chunk.tokens)
            if overlap == 0:
                continue
            # Length-normalized score to penalize very long chunks.
            score = overlap / (1 + 0.1 * (len(chunk.tokens) - overlap))
            scored.append((score, chunk))
        scored.sort(key=lambda s: s[0], reverse=True)
        return [
            {
                "document_id": c.document_id,
                "name": c.document_name,
                "snippet": c.text[:400],
                "score": round(score, 3),
            }
            for score, c in scored[:top_k]
        ]


_INDEX = KnowledgeIndex()


def get_index() -> KnowledgeIndex:
    return _INDEX
