"""Minimal FastAPI app for Railway deploy smoke-test.

This replaces the full MAICOS backend temporarily, to confirm
that the Railway build pipeline can produce a running container.
It exposes only /health and /diag with no database, no worker,
no migrations.

If this comes up on Railway, the build/pipeline is healthy and
the failure is in the real code. Revert by restoring the real
backend/Dockerfile from git.
"""
from fastapi import FastAPI

app = FastAPI(title="MAICOS Smoke Test")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/")
def root() -> dict:
    return {"service": "maicos-smoke", "status": "ok"}