"""Minimal smoke app for Railway deploy verification.

Replaces app.main for diagnostic deploys. Exposes only:
  GET /          - 200 OK
  GET /health    - 200 {"status": "ok", "version": "smoke"}
  GET /api/v1/diag - 200 with env dump

This isolates whether the Railway 502 is caused by the build
image, the env vars, or something specific to app/main.py.
If this comes up on Railway, the issue is in the main app.
If this also fails, the issue is in the build/env.
"""from fastapi import FastAPI

app = FastAPI(title="MAICOS Smoke Test")


@app.get("/")
def root() -> dict:
    return {"service": "maicos-smoke", "status": "ok"}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": "smoke"}


@app.get("/api/v1/diag")
def diag() -> dict:
    import os

    return {
        "service": "maicos-smoke",
        "version": "smoke",
        "database_url_set": bool(os.environ.get("DATABASE_URL")),
        "supabase_url_set": bool(os.environ.get("SUPABASE_URL")),
        "port": os.environ.get("PORT", "unset"),
        "app_env": os.environ.get("APP_ENV", "unset"),
        "cors_origins": os.environ.get("CORS_ORIGINS", "unset"),
    }
