# MAICOS — Good Morning Checklist

Date: 2026-09-01
Status: Backend code is 100% ready. Only Railway redeploy needed.

## TL;DR (3 steps, 5 min)

1. **Open Railway** → https://railway.com/dashboard → `lavish-upliftment` → `maicos` → **Settings** tab → **Source** → confirm `Aman23452223/maicos` on `main` branch.
2. **Deployments** tab → top-right `⋯` → **Redeploy** (will use latest commit `796ef11`).
3. Wait 60–120s for the build to finish. Open the **Deploy Logs** tab and look for:
   ```
   [start] PID=… PORT=… WORKER_ID=maicos-web-1 PYTHONUNBUFFERED=1
   [start] DATABASE_URL set: yes
   [start] running alembic upgrade head (max 15s)
   [start] alembic ok
   [start] starting uvicorn on port …
   INFO:     Uvicorn running on http://0.0.0.0:…
   ```

If you see those lines, the backend is up. Then test in this order:

```bash
# 1. Backend health (Railway direct)
curl https://maicos-production.up.railway.app/health
# Expected: {"status":"ok"}

# 2. Backend diag (env, CORS, DB status)
curl https://maicos-production.up.railway.app/api/v1/diag
# Expected: 200 with app_env, database_url (***), db.ok reported

# 3. Frontend (Vercel)
open https://frontend-psi-three-87.vercel.app/
# Expected: 200, dashboard renders, no console errors

# 4. Frontend API passthrough
open https://frontend-psi-three-87.vercel.app/api/v1/agents
# Expected: 200 with [] (empty agents list — no DB rows yet)
```

If all four return as expected, the 502 is **completely fixed** and MAICOS is fully wired end-to-end.

## What was wrong (recap)

The 502 came from Railway's hikari proxy because the upstream container was not serving HTTP within Railway's edge timeout. The root cause had two layers:

1. **The FastAPI process was blocked for ~10s at startup** while the lifespan tried to do a synchronous `SELECT 1` against a Postgres it could not reach. The Railway health check fired during this window and got 502. The web never had a chance to answer `/health`.
   - **Fix:** the lifespan now yields to uvicorn *first*; the DB check runs in a background task. `/health` returns 200 in <1 second even with no DB.
2. **Railway was not auto-deploying** even after `git push origin main`. The dashboard's "Active" deploy was an older commit (`83ec896c` — not in our history).
   - **Fix:** manual Redeploy from the Railway dashboard. Once that runs, the latest image is built and started.

## What the deploy log should look like

A successful deploy shows in order:

```
[boot] maicos main module loaded pid=42 python=3.11.10 port=8080
{"event":"app.start", "env":"production", ...}
[ok] db.connect_ok …  (or db.connect_failed with a clear reason)
[ok] alembic ok          (or alembic timed out, continuing)
[ok] worker.start        (or worker.start_failed)
INFO:     Uvicorn running on http://0.0.0.0:8080
```

If `db.connect_failed` appears, the most common cause is a wrong `DATABASE_URL` (typo, wrong region, missing `?sslmode=require`, password URL-encoded badly). Fix the env var in Railway → Variables, save, then `⋯` → Redeploy.

## Environment variables to verify (Railway → maicos → Variables)

| Variable | Example |
|---|---|
| `DATABASE_URL` | `postgresql+psycopg2://postgres.uzrtydpbxemuncdkpekv:<PASSWORD>@aws-0-<REGION>.pooler.supabase.com:6543/postgres?sslmode=require` |
| `APP_SECRET_KEY` | 32-char random string (`python -c "import secrets; print(secrets.token_urlsafe(32))"`) |
| `CORS_ORIGINS` | `https://frontend-psi-three-87.vercel.app,https://maicos-7f2d-dmfdx65zx-aman-chauhans-projects-a4bf879e.vercel.app` |
| `CORS_ORIGIN_REGEX` | `^https://.*\.vercel\.app$` |
| `APP_ENV` | `production` |
| `WORKER_ENABLED` | `true` |
| `WORKER_ID` | `maicos-web-1` |
| `SUPABASE_URL` | `https://uzrtydpbxemuncdkpekv.supabase.co` |
| `SUPABASE_ANON_KEY` | `<publishable key from .env.local>` |

## Vercel env (frontend-psi-three-87 → Settings → Environment Variables)

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://maicos-production.up.railway.app` (or leave unset — `next.config.mjs` defaults to it) |
| `NEXT_PUBLIC_SUPABASE_URL` | `https://uzrtydpbxemuncdkpekv.supabase.co` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | `<publishable key>` |
| `NEXT_PUBLIC_SUPABASE_ENABLED` | `true` |

## Failure recovery

If the redeploy shows **build failed**:

1. Click the deployment → **Build Logs** tab → scroll to the last 30 lines
2. Common causes:
   - `pip install` timeout → increase Railway build timeout in service Settings
   - Module not found → check `pyproject.toml` dependencies
   - Dockerfile syntax → ensure the latest `backend/Dockerfile` was pulled

If the redeploy shows **deploy failed** (Runtime error):

1. Click the deployment → **Deploy Logs** tab → look for `[start]` lines
2. If `[start] DATABASE_URL set: no` → the env var is not reaching the container; check Variables tab
3. If `alembic` errors → the URL might be malformed or the DB unreachable
4. If uvicorn crashes → check Python traceback at the end of the log

## Health check matrix

| URL | What it tests | Expected |
|---|---|---|
| `https://maicos-production.up.railway.app/health` | Process up | `{"status":"ok"}` |
| `https://maicos-production.up.railway.app/api/v1/diag` | Process + DB check | `{"app_env":"production","database_url":"...","db":{"ok":true}}` |
| `https://frontend-psi-three-87.vercel.app/` | Vercel frontend | 200 with sidebar visible |
| `https://frontend-psi-three-87.vercel.app/api/v1/agents` | Vercel → Railway passthrough | 200 with `[]` |

If any of these fail after the manual redeploy, paste the URL and the response — the fix is always one of:

- Wrong env var → fix in Railway Variables
- Wrong CORS origin → add the Vercel URL to `CORS_ORIGINS`
- Railway webhook broken → Settings → Source → Disconnect → Reconnect
- Stale build → `⋯` → Redeploy again

## Security note

The git remote URL contained a leaked GitHub PAT (the token has
been removed from the local repo, but the raw value was once
exposed in `git remote -v` output). **Revoke it now** at
https://github.com/settings/tokens.