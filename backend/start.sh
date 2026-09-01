#!/bin/sh
# Absolute minimum CMD for Railway - the most minimal possible test.
# This will help isolate whether the 502 is a build issue or runtime issue.
echo "[start] container alive at $(date -u +%FT%TZ)"

# Check environment
echo "[start] PORT=$PORT"
echo "[start] DATABASE_URL is set: $([ -n "$DATABASE_URL" ] && echo yes || echo no)"

# Print pre-flight diagnostics
python --version
python -c "import sys; print('[start] sys.path:', sys.path[:3])"

# If SMOKE_TEST env var is set OR the main-app-passed marker doesn't exist,
# run the minimal smoke app
if [ -n "$SMOKE_TEST" ] || [ ! -f /app/.main-app-passed ]; then
    echo "[start] starting smoke test app (no DB, no worker, no migrations)"
    if [ -n "$SMOKE_TEST" ]; then
        echo "[start] SMOKE_TEST explicitly set"
    else
        echo "[start] no .main-app-passed marker - first deploy, using smoke"
    fi
    # Create the marker after smoke is verified (touch from inside uvicorn startup)
    exec uvicorn app.__smoke_main__:app --host 0.0.0.0 --port "${PORT:-8000}" --log-level info --proxy-headers --forwarded-allow-ips='*'
else
    echo "[start] .main-app-passed exists, running main app"
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --log-level info --proxy-headers --forwarded-allow-ips='*' 2>&1
fi
