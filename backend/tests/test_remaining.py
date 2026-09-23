"""Remaining items: OAuth, plans/billing, pgvector/RLS guards, vector modes."""
from __future__ import annotations


def test_oauth_needs_config(client, monkeypatch):
    import os

    for k in ("GOOGLE_OAUTH_CLIENT_ID", "META_APP_ID"):
        monkeypatch.delenv(k, raising=False)
        os.environ.pop(k, None)
    r = client.get("/api/v1/integrations/google/oauth/start")
    assert r.status_code == 422 and "NOT_CONFIGURED" in r.json()["detail"]
    r = client.get("/api/v1/integrations/meta/oauth/start")
    assert r.status_code == 422
    r = client.get("/api/v1/integrations/nope/oauth/start")
    assert r.status_code == 404


def test_plan_assign_and_billing(client):
    r = client.put("/api/v1/workspaces/xxx/plan", json={"name": "starter"})
    assert r.status_code == 403  # cross-workspace forbidden
    me = client.get("/api/v1/auth/me").json()
    _ = me
    # own workspace plan change
    ws = client.get("/api/v1/workspaces").json()[0]["id"]
    r = client.put(f"/api/v1/workspaces/{ws}/plan", json={"name": "starter"})
    assert r.status_code == 200, r.text
    assert r.json()["capabilities"] == ["analytics", "crm", "knowledge",
                                        "reporting", "website_analysis"]
    assert client.put(f"/api/v1/workspaces/{ws}/plan",
                      json={"name": "nope"}).status_code == 400
    ov = client.get("/api/v1/billing/overview").json()
    assert ov["plan"] == "starter" and "usage" in ov


def test_ensure_postgres_extras_noop_sqlite():
    from sqlalchemy import create_engine

    from app.db.ensure_schema import ensure_postgres_extras

    eng = create_engine("sqlite:///:memory:")
    assert ensure_postgres_extras(eng) == {"pgvector": [], "rls": []}
    eng.dispose()


def test_vector_modes_honest(db, workspace_user):
    from app.rag.vector_store import semantic_search

    ws = workspace_user["company"].id
    # no key -> lexical fallback
    import os
    old = os.environ.pop("OPENAI_API_KEY", None)
    try:
        out = semantic_search(db, company_id=ws, query="hello world", roles=[])
        assert out["mode"] == "lexical_fallback"
        assert out["embedding_status"] == "NOT_CONFIGURED"
    finally:
        if old:
            os.environ["OPENAI_API_KEY"] = old
    # test provider -> semantic (python scoring, sqlite has no pgvector)
    os.environ["EMBEDDING_PROVIDER"] = "test"
    try:
        from app.rag.vector_store import ingest_chunks
        res = ingest_chunks(db, company_id=ws, document_id="d1",
                            source="upload", source_url=None,
                            text="the quick brown fox jumps over",
                            access_roles=[])
        assert res["embedding_status"] == "OK"
        out = semantic_search(db, company_id=ws, query="quick fox", roles=[])
        assert out["mode"] == "semantic" and out["results"]
    finally:
        os.environ.pop("EMBEDDING_PROVIDER", None)
