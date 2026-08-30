#!/bin/sh
# MAICOS backend startup script.
#
# Sequence:
#   1. Wait up to 30 seconds for DATABASE_URL to be populated (Railway
#      may inject service references slightly after the container starts).
#   2. Run Alembic migrations (idempotent — no-op once head is reached).
#   3. Start uvicorn.
#
# If DATABASE_URL never appears, the migrations step is skipped and
# uvicorn still starts. API requests will then return 500 until the
# variable is configured, but the service stays healthy enough for
# the platform to keep the container up.
set -e

echo "[start] pid=$$ waiting for DATABASE_URL..."
for i in $(seq 1 30); do
    if [ -n "${DATABASE_URL:-}" ]; then
        echo "[start] DATABASE_URL present after ${i}s"
        break
    fi
    sleep 1
done

if [ -n "${DATABASE_URL:-}" ]; then
    echo "[start] running alembic upgrade head"
    if ! alembic upgrade head; then
        echo "[start] alembic failed; starting uvicorn anyway"
    fi
else
    echo "[start] DATABASE_URL not set after 30s; skipping migrations"
fi

echo "[start] starting uvicorn on port ${PORT:-8000}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"