"""DB-backed chunk store + semantic retrieval with safe fallback (Phase 3)."""
from __future__ import annotations

import hashlib
import math
from typing import Any

from sqlalchemy.orm import Session

from app.models.orm import DocumentChunk
from app.rag.embeddings import default_provider_name
from app.rag.embeddings import get as get_embedder


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _cosine(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    dot = sum(x * y for x, y in zip(a[:n], b[:n]))
    na = math.sqrt(sum(x * x for x in a[:n])) or 1.0
    nb = math.sqrt(sum(y * y for y in b[:n])) or 1.0
    return dot / (na * nb)


def chunk_text(text: str, size: int = 400, overlap: int = 50) -> list[str]:
    words = text.split()
    if not words:
        return []
    step = max(1, size - overlap)
    return [" ".join(words[i:i + size]) for i in range(0, len(words), step)]


def ingest_chunks(db: Session, *, company_id: str, document_id: str,
                  source: str, source_url: str | None, text: str,
                  access_roles: list[str]) -> dict[str, Any]:
    chunks = chunk_text(text)
    added, skipped = 0, 0
    # Try embeddings; on NOT_CONFIGURED store chunks without vectors
    vecs: list | None = None
    emb_model = ""
    emb_status = "NOT_CONFIGURED"
    try:
        provider = get_embedder(default_provider_name())
        if default_provider_name() == "test":
            # production must never accidentally use test vectors
            import os
            if os.environ.get("APP_ENV", "dev") == "production":
                provider = get_embedder("openai")
        res = provider.embed(chunks[:96])
        if res.get("ok"):
            vecs = res["vectors"]
            emb_model = str(res.get("model", ""))
            emb_status = "OK"
        else:
            emb_status = str(res.get("status", "NOT_CONFIGURED"))
    except Exception:
        emb_status = "PROVIDER_ERROR"
    for i, ch in enumerate(chunks):
        h = _hash(ch)
        exists = db.query(DocumentChunk).filter(
            DocumentChunk.company_id == company_id,
            DocumentChunk.content_hash == h).first()
        if exists:
            skipped += 1
            continue
        db.add(DocumentChunk(
            company_id=company_id, document_id=document_id, source=source,
            source_url=source_url, chunk_index=i, text=ch[:20000],
            content_hash=h,
            embedding=list(vecs[i]) if vecs and i < len(vecs) else None,
            embedding_model=emb_model, access_roles=access_roles or []))
        added += 1
    db.flush()
    # Also feed legacy in-memory index for backward compat
    try:
        from app.rag.index import get_index
        get_index().add(workspace_id=company_id, document_id=document_id,
                        document_name=source, text=text,
                        access_roles=access_roles or [])
    except Exception:
        pass
    return {"added": added, "skipped": skipped, "embedding_status": emb_status,
            "model": emb_model}


def semantic_search(db: Session, *, company_id: str, query: str,
                    roles: list[str], top_k: int = 5) -> dict[str, Any]:
    """Try vector search; fall back to token-overlap with explicit status."""
    from app.core.context import Principal
    from app.rag.index import get_index

    # embed query
    try:
        provider = get_embedder(default_provider_name())
        res = provider.embed([query])
    except Exception as exc:
        res = {"ok": False, "status": "PROVIDER_ERROR", "error": str(exc)[:300]}
    if not res.get("ok"):
        # Fallback: legacy lexical search, honestly labeled
        principal = Principal(user_id="search", workspace_id=company_id, roles=roles)
        results = get_index().search(principal=principal, query=query, top_k=top_k)
        return {"ok": True, "mode": "lexical_fallback",
                "embedding_status": res.get("status", "NOT_CONFIGURED"),
                "results": results}
    qvec = res["vectors"][0]
    rows = db.query(DocumentChunk).filter(
        DocumentChunk.company_id == company_id).limit(500).all()
    scored = []
    role_set = set(roles or [])
    for r in rows:
        if r.access_roles and not (role_set & set(r.access_roles)):
            continue
        if not r.embedding:
            continue
        scored.append((_cosine(qvec, list(r.embedding)), r))
    scored.sort(key=lambda x: x[0], reverse=True)
    return {"ok": True, "mode": "semantic", "embedding_status": "OK",
            "results": [{"document_id": r.document_id, "chunk_id": r.id,
                         "snippet": r.text[:400], "score": round(float(s), 3),
                         "source": r.source, "source_url": r.source_url}
                        for s, r in scored[:top_k]]}
