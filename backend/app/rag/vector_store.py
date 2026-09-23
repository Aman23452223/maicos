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
    # Mirror 1536-dim vectors into the pgvector column (Postgres only).
    if vecs and emb_status == "OK":
        try:
            _mirror_pgvector(db, company_id, document_id)
        except Exception:
            pass
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


def _mirror_pgvector(db: Session, company_id: str, document_id: str) -> None:
    """Copy JSON embeddings into embedding_vector where dims fit (1536)."""
    from sqlalchemy import text as _text

    if db.bind is None or db.bind.dialect.name != "postgresql":
        return
    rows = db.query(DocumentChunk).filter(
        DocumentChunk.company_id == company_id,
        DocumentChunk.document_id == document_id).all()
    for r in rows:
        if not r.embedding or len(r.embedding) != 1536:
            continue
        vec = "[" + ",".join(str(float(x)) for x in r.embedding) + "]"
        db.execute(_text('UPDATE "document_chunks" SET "embedding_vector" = '
                         "(:v)::vector WHERE id = :i"),
                   {"v": vec, "i": r.id})
    db.flush()


def _pg_candidates(db: Session, *, company_id: str, qvec: list[float],
                   top_k: int) -> list | None:
    """pgvector <-> search. Returns rows or None when unavailable."""
    from sqlalchemy import text as _text

    if db.bind is None or db.bind.dialect.name != "postgresql":
        return None
    if len(qvec) != 1536:
        return None
    try:
        vec = "[" + ",".join(str(float(x)) for x in qvec) + "]"
        res = db.execute(
            _text('SELECT id FROM "document_chunks" WHERE company_id = :ws '
                  'AND embedding_vector IS NOT NULL '
                  'ORDER BY embedding_vector <-> (:v)::vector LIMIT :k'),
            {"ws": company_id, "v": vec, "k": top_k * 4}).fetchall()
        if not res:
            return []
        ids = [r[0] for r in res]
        return db.query(DocumentChunk).filter(DocumentChunk.id.in_(ids)).all()
    except Exception:
        return None


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
    # Prefer pgvector index when available (honestly reported below).
    pg_rows = _pg_candidates(db, company_id=company_id, qvec=qvec, top_k=top_k)
    if pg_rows:
        rows = pg_rows
        mode = "semantic_pgvector"
    else:
        rows = db.query(DocumentChunk).filter(
            DocumentChunk.company_id == company_id).limit(500).all()
        mode = "semantic"
    scored = []
    role_set = set(roles or [])
    for r in rows:
        if r.access_roles and not (role_set & set(r.access_roles)):
            continue
        if not r.embedding:
            continue
        scored.append((_cosine(qvec, list(r.embedding)), r))
    scored.sort(key=lambda x: x[0], reverse=True)
    return {"ok": True, "mode": mode, "embedding_status": "OK",
            "results": [{"document_id": r.document_id, "chunk_id": r.id,
                         "snippet": r.text[:400], "score": round(float(s), 3),
                         "source": r.source, "source_url": r.source_url}
                        for s, r in scored[:top_k]]}
