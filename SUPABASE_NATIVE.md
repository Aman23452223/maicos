# MAICOS — Supabase-native architecture

> **TL;DR.** MAICOS now uses **Supabase Postgres** as the single
> source of truth. The job queue is a Postgres table with
> `FOR UPDATE SKIP LOCKED` + `pg_notify`. Scheduled jobs are stored
> in a table and dispatched every minute by `pg_cron`. There is no
> Redis and no APScheduler. Supabase Auth can replace the local
> MAICOS JWT — both paths are supported side-by-side.

---

## Why this matters

- **One service to operate.** Supabase provides the database, the
  job queue, the scheduler, the auth, the realtime channel, the
  storage bucket. Railway now only runs the FastAPI process.
- **Horizontal scale is free.** `FOR UPDATE SKIP LOCKED` lets any
  number of FastAPI replicas pull jobs without leader election.
- **Survives restarts.** Jobs sit in Postgres, not in process
  memory. A crash mid-run leaves the row in `CLAIMED` status and
  the next worker can either retry or mark it `DEAD` after N
  attempts.
- **No extra billing line.** The Postgres compute that already
  serves the API also serves the queue.

---

## Components

| Concern | Old (Redis-based) | New (Supabase-native) |
| --- | --- | --- |
| Job queue | `RPUSH` / `BLPOP` on `maicos:workflow_jobs` | `INSERT INTO workflow_jobs` + `pg_notify('maicos_jobs', id)` |
| Worker wake-up | `BLPOP` blocking call | `LISTEN maicos_jobs` (with 5 s polling fallback) |
| Job claim | implicit (BLPOP) | `UPDATE … WHERE id = (SELECT id … FOR UPDATE SKIP LOCKED LIMIT 1)` |
| Scheduler | APScheduler in-process | `INSERT INTO scheduled_jobs` + `pg_cron` every minute |
| Auth | MAICOS HS256 JWT | Supabase RS256 JWT (MAICOS HS256 still works) |
| Realtime | polling | Supabase Realtime channels (frontend) |
| Object storage | local `./var/documents` | Supabase Storage (planned, not yet wired) |

---

## Database schema (delta from earlier)

Two new tables, three new columns, two new migrations:

```
workflow_jobs        PENDING / CLAIMED / COMPLETED / FAILED / DEAD
  id, workflow_id, company_id, trigger,
  payload, status, attempts, last_error,
  claimed_by, claimed_at, created_at, finished_at,
  scheduled_job_id (FK → scheduled_jobs.id, nullable)

scheduled_jobs       run_at, dispatched, dispatched_job_id
  id, company_id, objective, run_at,
  dispatched, dispatched_job_id, created_by_user_id, created_at

users.supabase_user_id   nullable, unique, indexed
users.password_hash      nullable (was NOT NULL)
```

Two new Postgres-only bits installed by Alembic:

- **`trg_maicos_workflow_jobs_notify`** — `AFTER INSERT` trigger
  fires `pg_notify('maicos_jobs', NEW.id)`. Workers `LISTEN` to
  that channel.
- **`maicos-dispatch-scheduled-workflows`** — `pg_cron` job,
  `* * * * *`, picks due `scheduled_jobs` rows with
  `FOR UPDATE SKIP LOCKED` and inserts a `workflow_jobs` row per
  match.

Both are wrapped in dialect guards so the migrations stay
**no-ops on SQLite** (local tests) and on databases that do not
have the `pg_cron` extension (Railway Postgres).

---

## Setting up Supabase (one-time)

1. https://supabase.com/dashboard → **New project** — pick a region
   close to Railway, save the database password locally.
2. **Database → Extensions** → enable:
   - `vector` (PRD §15 — knowledge agent RAG)
   - `pg_cron` (scheduler dispatcher)
   - `pg_net` (optional, for outbound webhooks later)
3. **Settings → Database → Connection string → URI**:
   - **Transaction** pooler (port 6543) → `DATABASE_URL` for FastAPI.
   - **Direct** (port 5432) → `DATABASE_DIRECT_URL` for Alembic.
4. **Settings → API**:
   - Project URL → `SUPABASE_URL` in backend env.
   - `anon` / publishable key → `SUPABASE_ANON_KEY` in backend env.

Record these **locally** (password manager, Bitwarden, etc.) — do
**not** paste them into chat. The publishable key is the only
secret that is safe to ship in the frontend bundle, and even that
should never appear in a chat, screenshot, or PR.

---

## Backend env (Railway `maicos` service)

| Variable | Source |
| --- | --- |
| `DATABASE_URL` | Supabase transaction pooler (port 6543) |
| `DATABASE_DIRECT_URL` | Supabase direct (port 5432) — Alembic only |
| `APP_SECRET_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `CORS_ORIGINS` | exact Vercel URL, e.g. `https://maicos-7f2d-…vercel.app` |
| `CORS_ORIGIN_REGEX` | `^https://.*\.vercel\.app$` (previews) |
| `APP_ENV` | `production` |
| `WORKER_ENABLED` | `true` for single-replica, `false` when running `python -m app.workers.scheduler` as a separate service |
| `WORKER_ID` | any string, used in the `claimed_by` column |
| `SUPABASE_URL` | optional — enables Supabase Auth |
| `SUPABASE_ANON_KEY` | optional — required if `SUPABASE_URL` is set |

`REDIS_URL` and `APSCHEDULER_*` are gone — delete them from
Railway if they were carried over from the previous setup.

---

## Frontend env (Vercel `maicos-7f2d`)

| Variable | Source |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | `https://maicos-production.up.railway.app` (Production / Preview / Development) |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase publishable key |
| `NEXT_PUBLIC_SUPABASE_ENABLED` | `true` |

---

## Auth: dual-mode verification

`app/core/supabase_auth.py` decides per request:

1. If `SUPABASE_URL` is set **and** the token header carries a
   `kid`, verify against the project's JWKS and look up / provision
   the matching MAICOS user by `supabase_user_id`.
2. Otherwise, fall through to the original MAICOS HS256 path.

This means you can flip the toggle by setting/unsetting
`SUPABASE_URL` — no code change, no migration.

---

## Runbook

### First deploy (after enabling Supabase)

```powershell
# 1. Pull the new code
git pull origin main

# 2. Run migrations against the *direct* connection
cd backend
$env:DATABASE_DIRECT_URL = "postgresql+psycopg2://postgres.<ref>:<password>@aws-0-<region>.supabase.com:5432/postgres?sslmode=require"
alembic upgrade head

# 3. Push the changes; Railway auto-deploys with the new env vars
git push origin main

# 4. Verify
curl https://maicos-production.up.railway.app/health
# → {"status":"ok"}
```

### Verifying the queue is alive

After the first command of the day:

```bash
# As an admin user, fetch the JWT and call:
curl -H "Authorization: Bearer $JWT" \
     https://maicos-production.up.railway.app/api/v1/queue/stats
# → {"PENDING": 0, "COMPLETED": 17, "FAILED": 0, "DEAD": 0}
```

### Disabling the in-process worker

When you scale the API to multiple replicas, run the worker as a
separate Railway service:

```powershell
# In the new service's env:
WORKER_ENABLED=false          # in the API service
WORKER_ENABLED=true           # in the worker service
WORKER_ID=maicos-worker-1     # distinct per replica
```

Both paths point at the same Postgres, so the queue is shared
naturally.

---

## Edge cases & recovery

| Symptom | Cause | Fix |
| --- | --- | --- |
| Queue backs up | Worker is down or DB is slow | `curl /api/v1/queue/stats`; restart the API |
| Job stuck in `CLAIMED` for > N min | Worker crashed mid-run | Run `UPDATE workflow_jobs SET status='PENDING' WHERE status='CLAIMED' AND claimed_at < now() - interval '10 minutes'` |
| Scheduled job never fires | `pg_cron` not enabled in Supabase | Database → Extensions → enable `pg_cron`, then `alembic upgrade head` |
| Supabase Auth 401 with valid token | JWKS cache stale | Restart the API; new key was rotated |

---

## What stays in Railway (for now)

- **The FastAPI process.** A `Dockerfile` and a single `CMD
  ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port",
  "$PORT"]`. No Redis addon, no worker addon (unless you scale
  out).
- **A background worker service.** Optional. Same image, different
  `WORKER_ID` and `WORKER_ENABLED=true` env.

That's the whole topology: **Supabase (Postgres + Auth + Realtime
+ Storage) ⇄ FastAPI on Railway ⇄ Next.js on Vercel.**
