#!/bin/sh
# POSIX-compliant entrypoint for Railway and Docker containers.
echo "[start] container alive at $(date -u +%FT%TZ)"

# Diagnostic mode: if DIAGNOSE=1, just run the diagnostic and exit
if [ "$DIAGNOSE" = "1" ] || [ "$DIAGNOSE" = "true" ]; then
    exec /app/diagnose.sh
fi

PORT="${PORT:-8000}"
echo "[start] PORT=$PORT"
echo "[start] DATABASE_URL is set: $([ -n "$DATABASE_URL" ] && echo yes || echo no)"

# POSIX-compliant string length check
if [ -n "$DATABASE_URL" ]; then
    dburl_len=$(printf '%s' "$DATABASE_URL" | wc -c | tr -d ' ')
    echo "[start] DATABASE_URL length: ${dburl_len}"
fi

# Print pre-flight diagnostics
python --version
python -c "import sys; print('[start] sys.path:', sys.path[:3])"

mkdir -p /tmp
echo "alive" > /tmp/maicos-alive
echo "[start] marker written: /tmp/maicos-alive"

# Launch dual-port bridge so both 8000 and 8080 forward to $PORT
python -m app.port_bridge "$PORT" &

# If SMOKE_TEST is explicitly set to 1 or true, run the smoke app.
# Otherwise run the real production FastAPI app with all agents.
if [ "$SMOKE_TEST" = "1" ] || [ "$SMOKE_TEST" = "true" ]; then
    echo "[start] SMOKE_TEST explicitly set - running smoke app"
    exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --log-level info --proxy-headers --forwarded-allow-ips='*'
else
    echo "[start] running main production app"
    exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --log-level info --proxy-headers --forwarded-allow-ips='*'
fi
