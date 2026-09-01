#!/bin/sh
# Full diagnostic for Railway. Outputs everything we need to debug
# 502s without needing dashboard access.
echo "============================================================"
echo "  MAICOS RAILWAY DIAGNOSTIC — $(date -u +%FT%TZ)"
echo "============================================================"
echo ""

echo "## 1. Environment"
echo "PID: $$"
echo "User: $(whoami)"
echo "PWD: $(pwd)"
echo "PORT: $PORT"
echo ""
echo "Environment variables (filtered to relevant):"
env | grep -E "^(DATABASE_URL|SUPABASE_URL|PORT|APP_ENV|WORKER_|CORS_|REDIS|OPENAI|ANTHROPIC|APP_SECRET)" | sed -E 's#://[^:]+:[^@]+@#://USER:***@#g' | sed 's/^/  /'
echo ""
echo "All env var names (no values):"
env | cut -d= -f1 | sort | sed 's/^/  /'
echo ""

echo "## 2. DATABASE_URL validation"
if [ -z "$DATABASE_URL" ]; then
    echo "  STATUS: NOT SET - Railway is not injecting DATABASE_URL!"
    echo ""
    echo "  Possible causes:"
    echo "    1. Variable name typo (must be EXACTLY DATABASE_URL)"
    echo "    2. Variable is type 'Reference' instead of 'Raw' (must be Raw)"
    echo "    3. Variable was deleted in dashboard but deploy is using cached image"
    echo "    4. Service has 2+ services in same project, editing wrong one"
    echo ""
    echo "  FIX: Railway dashboard -> maicos service -> Variables tab"
    echo "       -> DATABASE_URL row -> three dots -> Edit"
    echo "       -> Type: Raw Variable (not Reference)"
    echo "       -> Paste the connection string from Supabase dashboard"
else
    echo "  STATUS: SET (length: ${#DATABASE_URL})"
    url="$DATABASE_URL"

    # Reject if there are unresolved placeholders
    if echo "$url" | grep -qE '<[A-Z_]+>'; then
        echo "  PLACEHOLDERS: FOUND (bad):"
        echo "$url" | grep -oE '<[A-Z_]+>' | sort -u | sed 's/^/    /'
    else
        echo "  PLACEHOLDERS: none"
    fi

    # Check protocol
    case "$url" in
        postgresql://*) echo "  PROTOCOL: WRONG (need postgresql+psycopg2)";;
        postgresql+psycopg2://*) echo "  PROTOCOL: ok";;
        *) echo "  PROTOCOL: unknown ($url)";;
    esac

    # Check for sslmode
    case "$url" in
        *sslmode=require*) echo "  SSLMODE: ok (require)";;
        *sslmode=verify-full*) echo "  SSLMODE: ok (verify-full)";;
        *) echo "  SSLMODE: MISSING (Supabase needs sslmode=require)";;
    esac

    # Show sanitized URL
    sanitized=$(echo "$url" | sed -E 's#://[^:]+:[^@]+@#://USER:***@#g')
    echo "  URL (sanitized): $sanitized"
fi
echo ""

echo "## 3. Python imports"
python --version
python -c "
import sys
print(f'  executable: {sys.executable}')
print(f'  prefix:     {sys.prefix}')
print(f'  path:       {sys.path[:3]}')
import importlib
for mod in ['fastapi', 'uvicorn', 'pydantic', 'pydantic_settings', 'sqlalchemy', 'psycopg2', 'asyncpg', 'alembic']:
    try:
        m = importlib.import_module(mod)
        print(f'  {mod}: {getattr(m, \"__version__\", \"?\")}')
    except ImportError as e:
        print(f'  {mod}: MISSING ({e})')
"
echo ""

echo "## 4. File system"
echo "Working dir contents:"
ls -la /app 2>&1 | head -25 | sed 's/^/  /'
echo ""
echo "/app writable: $(touch /app/.test_write 2>&1 && rm /app/.test_write && echo yes || echo no)"
echo ""

echo "## 5. DNS resolution"
for host in supabase.com google.com; do
    if getent hosts $host >/dev/null 2>&1; then
        ip=$(getent hosts $host | awk '{print $1}' | head -1)
        echo "  $host -> $ip"
    else
        echo "  $host -> FAILED (DNS resolution failed)"
    fi
done
if [ -n "$DATABASE_URL" ]; then
    pg_host=$(echo "$DATABASE_URL" | grep -oE '@[a-zA-Z0-9.-]+' | head -1 | sed 's/@//')
    if [ -n "$pg_host" ]; then
        echo "  DB host: $pg_host"
        if getent hosts "$pg_host" >/dev/null 2>&1; then
            ip=$(getent hosts "$pg_host" | awk '{print $1}' | head -1)
            echo "    -> $ip (resolved)"
        else
            echo "    -> FAILED (Railway cannot resolve this hostname)"
        fi
    fi
fi
echo ""

echo "## 6. TCP reachability to DB"
if [ -n "$DATABASE_URL" ]; then
    pg_host=$(echo "$DATABASE_URL" | grep -oE '@[a-zA-Z0-9.-]+' | head -1 | sed 's/@//')
    pg_port=$(echo "$DATABASE_URL" | grep -oE ':[0-9]+/' | head -1 | sed 's/[:/]//g')
    pg_port=${pg_port:-5432}
    if [ -n "$pg_host" ]; then
        echo "  Testing TCP to $pg_host:$pg_port..."
        if timeout 5 bash -c "</dev/tcp/$pg_host/$pg_port" 2>/dev/null; then
            echo "  RESULT: reachable"
        else
            echo "  RESULT: FAILED (timeout or refused)"
        fi
    fi
fi
echo ""

echo "## 7. Process and memory"
ps aux 2>/dev/null | head -5 | sed 's/^/  /'
echo ""
echo "Memory:"
free -h 2>/dev/null | grep Mem | sed 's/^/  /'
echo ""
echo "Disk:"
df -h /app 2>/dev/null | tail -1 | sed 's/^/  /'
echo ""

echo "## 8. psycopg2 connect test"
if [ -n "$DATABASE_URL" ]; then
    python -c "
import os
import sys
try:
    import psycopg2
    url = os.environ['DATABASE_URL']
    print(f'  Attempting: {url[:60]}...')
    conn = psycopg2.connect(url, connect_timeout=10)
    cur = conn.cursor()
    cur.execute('SELECT version()')
    ver = cur.fetchone()[0]
    print(f'  CONNECTED: {ver[:80]}')
    conn.close()
except Exception as e:
    print(f'  FAILED: {type(e).__name__}: {str(e)[:200]}')
" 2>&1
else
    echo "  Skipped (DATABASE_URL not set)"
fi
echo ""

echo "## 9. uvicorn test (5 second smoke)"
python -c "
import uvicorn, threading, time, urllib.request
from app.__smoke_main__ import app
def run():
    uvicorn.run(app, host='127.0.0.1', port=18799, log_level='warning')
t = threading.Thread(target=run, daemon=True)
t.start()
time.sleep(3)
try:
    r = urllib.request.urlopen('http://127.0.0.1:18799/health', timeout=3)
    print(f'  HTTP {r.status}: {r.read().decode()[:80]}')
except Exception as e:
    print(f'  FAILED: {e}')
" 2>&1
echo ""

echo "## 10. Summary"
echo "  If DATABASE_URL is not set, the only fix is updating Railway Variables."
echo "  If DATABASE_URL is set but psycopg2 fails, the URL is wrong or DB unreachable."
echo "  If uvicorn smoke test fails, the runtime environment is broken (memory/disk/Python)."
echo ""
echo "============================================================"
echo "  END OF DIAGNOSTIC"
echo "============================================================"
