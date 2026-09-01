#!/bin/sh
# Railway diagnostic — runs in the deployed container and dumps
# everything we need to debug 502s without needing dashboard access.
echo "============================================================"
echo "  MAICOS RAILWAY DIAGNOSTIC"
echo "  $(date -u +%FT%TZ)"
echo "============================================================"
echo ""

echo "## Container"
echo "  PID:        $$"
echo "  User:       $(whoami 2>&1)"
echo "  Workdir:    $(pwd)"
echo "  Ulimit:     $(ulimit -n)"
echo ""

echo "## Python"
python --version
python -c "import sys; print('  Version:   ', sys.version.split()[0]); print('  Path:      ', sys.executable); print('  Sys.path:  ', sys.path[:3])"
echo ""

echo "## Environment (sorted)"
env | sort | sed 's/^/  /'
echo ""

echo "## DATABASE_URL (sanitized)"
if [ -n "$DATABASE_URL" ]; then
    url="$DATABASE_URL"
    # redact password
    url_sanitized=$(echo "$url" | sed -E 's#://[^:]+:[^@]+@#://USER:***@#g')
    echo "  Set:       yes (length: ${#DATABASE_URL})"
    echo "  Sanitized: $url_sanitized"
    # check for unresolved placeholders
    if echo "$DATABASE_URL" | grep -qE '<[A-Z_]+>'; then
        echo "  WARNING:   contains unresolved placeholders!"
        echo "$DATABASE_URL" | grep -oE '<[A-Z_]+>' | sort -u | sed 's/^/    - /'
    fi
    # check protocol
    if echo "$DATABASE_URL" | grep -qE '^postgresql\+psycopg2:'; then
        echo "  Protocol:  ok (postgresql+psycopg2)"
    else
        echo "  Protocol:  WRONG (need postgresql+psycopg2)"
    fi
    # check for sslmode
    if echo "$DATABASE_URL" | grep -qE 'sslmode=require'; then
        echo "  sslmode:   ok"
    else
        echo "  sslmode:   MISSING (need ?sslmode=require for Supabase pooler)"
    fi
else
    echo "  Set:       NO — env var is empty or not set"
fi
echo ""

echo "## Test psycopg2 connect (if DATABASE_URL set)"
if [ -n "$DATABASE_URL" ]; then
    python -c "
import os, sys
try:
    import psycopg2
    url = os.environ['DATABASE_URL']
    print(f'  Parsing URL: {url[:60]}...')
    conn = psycopg2.connect(url, connect_timeout=5)
    cur = conn.cursor()
    cur.execute('SELECT version()')
    ver = cur.fetchone()[0]
    print(f'  Connected: yes')
    print(f'  Postgres:  {ver[:80]}')
    conn.close()
except Exception as e:
    print(f'  FAILED:    {type(e).__name__}: {str(e)[:200]}')
" 2>&1
fi
echo ""

echo "## Network / DNS"
python -c "
import socket
hosts = ['supabase.com', 'google.com']
for h in hosts:
    try:
        ip = socket.gethostbyname(h)
        print(f'  {h}: {ip}')
    except Exception as e:
        print(f'  {h}: FAILED ({type(e).__name__})')
"
echo ""

echo "## Free disk and memory"
df -h /app 2>/dev/null | tail -1 | sed 's/^/  Disk: /'
free -h 2>/dev/null | grep Mem | sed 's/^/  Memory: /'
echo ""

echo "## Network to Supabase"
if [ -n "$DATABASE_URL" ]; then
    host=$(echo "$DATABASE_URL" | grep -oE '@[a-zA-Z0-9.-]+' | head -1 | sed 's/@//')
    if [ -n "$host" ]; then
        echo "  Testing TCP to $host:5432..."
        if timeout 5 bash -c "</dev/tcp/$host/5432" 2>/dev/null; then
            echo "  TCP: reachable"
        else
            echo "  TCP: FAILED (connection refused or timeout)"
        fi
    fi
fi
echo ""

echo "## Files in /app"
ls -la /app 2>&1 | head -20 | sed 's/^/  /'
echo ""

echo "## Active process (PID 1 should be uvicorn)"
ps aux 2>/dev/null | head -5 | sed 's/^/  /'
echo ""

echo "============================================================"
echo "  END OF DIAGNOSTIC"
echo "============================================================"
