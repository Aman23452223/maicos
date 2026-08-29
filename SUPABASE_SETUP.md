# Supabase setup for MAICOS

This guide wires MAICOS to a Supabase project for the **database**
and optional **client-side auth**. It is written so that **no secret
ever appears in chat, screenshots, or this repository** — every
credential lives either in `backend/.env` (local) or in the platform
secret stores (GitHub Actions, Vercel, Railway).

> **If a key was ever pasted into chat, treat it as public** — revoke
> it at the Supabase dashboard *first*, then continue. The publishable
> (anon) key is designed to be shipped in the frontend bundle, but the
> DB password and service-role key **must never leave your local `.env`
> or your platform's secret store**.

---

## 1. Create the Supabase project (one-time)

1. https://supabase.com/dashboard → **New project**
2. Pick a region close to where the backend will run
3. Save the **database password** the moment it is generated — you
   will not be shown it again

Record these three values (do **not** paste them into chat):

| What | Where it lives |
| --- | --- |
| Project URL (`https://<ref>.supabase.co`) | `frontend/.env.local` |
| Anon / publishable key (`sb_publishable_…` or legacy `anon`) | `frontend/.env.local` |
| Database password (set during project creation) | `backend/.env` |

---

## 2. Backend → Supabase Postgres

### 2.1 Get the connection string

Open **Supabase → Project → Settings → Database → Connection string**.
You will see three modes. For MAICOS:

- **Transaction pooler** (port `6543`) → `DATABASE_URL` for the FastAPI
  app. PgBouncer pools short-lived connections, which is what FastAPI
  wants under load.
- **Direct connection** (port `5432`) → use only for Alembic migrations
  (`alembic upgrade head`), because migrations open long-lived sessions.

Both URIs look like:
```
postgresql://postgres.<project-ref>:<PASSWORD>@aws-0-<region>.pooler.supabase.com:<PORT>/postgres
```

Add a `?sslmode=require` parameter for Supabase (PgBouncer on 6543 is
TLS-terminated; the direct connection is too). SQLAlchemy accepts the
URL with the prefix `postgresql+psycopg2://`.

### 2.2 Populate `backend/.env`

```
DATABASE_URL=postgresql+psycopg2://postgres.<ref>:<PASSWORD>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require
VECTOR_BACKEND=pgvector
```

`backend/.env` is already in `.gitignore`. Confirm with:

```bash
git check-ignore -v backend/.env
# expected: backend/.gitignore:20:.env    backend/.env
```

### 2.3 Verify (no migrations, no writes)

```bash
cd backend
python -m scripts.verify_supabase
```

The script will:
- connect with TLS,
- print the Postgres version,
- confirm the `vector` extension is installed (Supabase enables it
  per-project under **Database → Extensions**),
- exit non-zero with a clear message if anything is wrong.

### 2.4 Run migrations

```bash
cd backend
# Use the DIRECT connection (port 5432) for Alembic
DATABASE_URL='postgresql+psycopg2://postgres.<ref>:<PASSWORD>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require' \
  alembic upgrade head
```

After that, the FastAPI app uses the pooled URL.

---

## 3. Enable pgvector

Supabase → **Database → Extensions** → search `vector` → **Enable**.
Required by the knowledge agent for RAG.

If `verify_supabase` reports the extension is missing, this is the only
manual step you have to repeat per project.

---

## 4. Frontend Supabase auth (optional)

MAICOS already has its own backend auth (`/v1/auth/login`). Supabase
auth is an **optional** identity layer for the frontend — useful when
you want hosted password / magic-link / OAuth flows, or Supabase
Realtime subscriptions.

### 4.1 Populate `frontend/.env.local`

```
NEXT_PUBLIC_SUPABASE_URL=https://<ref>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=sb_publishable_...   # or legacy anon JWT
NEXT_PUBLIC_SUPABASE_ENABLED=true
```

These three variables are read by `frontend/src/lib/supabase.ts`. With
`NEXT_PUBLIC_SUPABASE_ENABLED=true`, the app mounts
`<SupabaseAuthProvider>` and exposes:

- `/login` — password sign-in, magic-link sign-in, account creation
- `useSupabaseAuth()` — session state, `signInWithPassword`,
  `signUp`, `signInWithOtp`, `signOut`, `getAccessToken`

Setting `NEXT_PUBLIC_SUPABASE_ENABLED=false` (or leaving the values
blank) leaves the app fully functional — Supabase UI simply hides
itself.

### 4.2 Mirror env vars to Vercel

In Vercel → **Project → Settings → Environment Variables**, add the
same three keys for **Production**, **Preview**, and **Development**.
Without these, preview deploys will treat Supabase as disabled.

---

## 5. CI / CD secrets

In the GitHub repo → **Settings → Secrets and variables → Actions**:

| Secret | What it is |
| --- | --- |
| `SUPABASE_DB_URL` | Backend `DATABASE_URL` (transaction pooler) |
| `SUPABASE_DB_URL_DIRECT` | Backend `DATABASE_URL` (port 5432) — for Alembic in CI |
| `SUPABASE_PROJECT_URL` | `https://<ref>.supabase.co` |
| `SUPABASE_ANON_KEY` | anon / publishable key |

`.github/workflows/backend.yml` already runs Alembic migrations — it
must read `SUPABASE_DB_URL_DIRECT` (not the pooled one) so the
migration can hold its session.

---

## 6. Row-Level Security (recommended for multi-tenant data)

Supabase exposes the same Postgres tables the backend writes to. If you
ever use the Supabase JS SDK directly from the frontend (Realtime,
Storage, etc.), **enable RLS on those schemas** — otherwise the anon
key can read every row.

MAICOS keeps its primary read/write path behind the FastAPI API and
uses the **service-role** key only inside the backend (never in the
frontend). If you decide to expose tables to the anon role, write RLS
policies that check `auth.uid()` and the `workspace_id`.

---

## 7. Rotating credentials

- **Anon key** — rotate from Supabase → **Project → Settings → API →
  Roll new anon key**. Update `frontend/.env.local` and the matching
  Vercel env var; redeploy.
- **Database password** — Supabase → **Project → Settings → Database →
  Reset database password**. Update `backend/.env`, the GitHub secret
  `SUPABASE_DB_URL(_DIRECT)`, and any host (Railway, Render) env vars.
  Existing pooled connections will fail over within ~60 seconds.

---

## 8. Checklist

- [ ] Supabase project created, region chosen, password saved locally
- [ ] `pgvector` extension enabled
- [ ] `backend/.env` populated with transaction-pooler URL (port 6543)
- [ ] `python -m scripts.verify_supabase` passes
- [ ] `alembic upgrade head` ran against the direct connection (port 5432)
- [ ] `frontend/.env.local` populated; `NEXT_PUBLIC_SUPABASE_ENABLED=true`
- [ ] Vercel env vars mirror the three frontend keys
- [ ] GitHub secrets `SUPABASE_DB_URL`, `SUPABASE_DB_URL_DIRECT`,
      `SUPABASE_PROJECT_URL`, `SUPABASE_ANON_KEY` set
- [ ] `.env` files confirmed gitignored:
      `git check-ignore -v backend/.env frontend/.env.local`