"""Minimal smoke app for Railway deploy verification.

Replaces app.main for diagnostic deploys. Exposes only:
  GET /          - 200 OK
  GET /health    - 200 {"status": "ok", "version": "smoke"}
  GET /api/v1/diag - 200 with env dump

This isolates whether the Railway 502 is caused by the build
image, the env vars, or something specific to app/main.py.
If this comes up on Railway, the issue is in the main app.
If this also fails, the issue is in the build/env.
"""
import os

from fastapi import FastAPI

app = FastAPI(title="MAICOS Smoke Test")


@app.get("/")
def root() -> dict:
    return {"service": "maicos-smoke", "status": "ok"}


@app.get("/health")
def health() -> dict:
    # Write the .main-app-passed marker so the next deploy switches
    # to the real app. This is what tells the Dockerfile wrapper
    # that the runtime is healthy.
    try:
        with open("/app/.main-app-passed", "w") as f:
            f.write("ok")
    except OSError:
        # /app might not be writable in the running container, but
        # the side effect of writing the marker is only used by the
        # NEXT deploy's CMD, not by this one.
        pass
    return {"status": "ok", "version": "smoke"}


@app.get("/api/v1/diag")
def diag() -> dict:
    return {
        "service": "maicos-smoke",
        "version": "smoke",
        "database_url_set": bool(os.environ.get("DATABASE_URL")),
        "supabase_url_set": bool(os.environ.get("SUPABASE_URL")),
        "port": os.environ.get("PORT", "unset"),
        "app_env": os.environ.get("APP_ENV", "unset"),
        "cors_origins": os.environ.get("CORS_ORIGINS", "unset"),
    }
