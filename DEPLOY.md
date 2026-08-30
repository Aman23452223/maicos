# MAICOS — Deployment & CI Runbook

This is a complete, secure, no-leaks procedure to put MAICOS on GitHub
and Vercel. Read it top to bottom before running any command.

---

## 0. Revoke leaked tokens (do this FIRST, do not skip)

The following credentials were pasted in chat and **must be revoked
immediately**. Treat them as public.

| Service  | What leaked          | Where to revoke / rotate |
| --------- | -------------------- | ------------------------- |
| GitHub    | `ghp_6clWA4USIXw…`   | https://github.com/settings/tokens → Delete |
| Vercel    | `vcp_2mflJux4EmQg…`  | https://vercel.com/account/tokens → Revoke |

After revoking, create new tokens **only if you really need them** —
for Vercel you usually don't (see §3 below for the tokenless flow).

> **Why this matters.** Anyone with those tokens can read / write
> your private repos, deploy to your Vercel projects, and rack up
> billing on your account. The whole point of tokens is that they
> stay secret.

---

## 1. Repository layout (already in place)

```
maicos/
├── backend/                 FastAPI + SQLAlchemy + Alembic
│   ├── app/                 business logic
│   ├── tests/               pytest suite + proof
│   ├── pyproject.toml
│   ├── alembic/             migrations
│   ├── .env.example         template (no real values)
│   └── Dockerfile
├── frontend/                Next.js 14
│   ├── src/app/             routes (root page is the hero)
│   ├── package.json
│   ├── next.config.mjs
│   ├── tailwind.config.ts
│   └── Dockerfile
├── infra/
│   └── docker-compose.yml   Postgres+pgvector, backend, frontend (no Redis)
├── docs/
│   ├── PRD-mapping.md
│   └── proof-output.txt
├── .github/
│   └── workflows/
│       ├── backend-ci.yml   (existing) backend lint + test
│       └── ci.yml           (new) full repo CI
├── vercel.json              (new) Vercel config for the frontend
└── README.md
```

---

## 2. Push to GitHub (tokenless, secure)

On your local machine, in the project root:

```bash
# 1. Initialise a fresh repo (skip if already a git repo)
git init
git checkout -b main

# 2. Make sure secrets are NOT in the commit. Verify:
git status
#   - .env must be absent (the .env.example is fine)
#   - var/ (proof stores) should be ignored
```

If you don't have a `.gitignore`, add at minimum:

```gitignore
.env
var/
__pycache__/
*.pyc
node_modules/
.next/
.vercel/
```

```bash
# 3. Stage and commit
git add .
git commit -m "feat: MVP + Loopstack-inspired hero + CI"
```

Create an empty repo on https://github.com/new (do NOT init with README).
GitHub now has two safe ways to push without typing a token into chat:

**Option A — GitHub CLI (recommended).** Install from https://cli.github.com,
authenticate interactively with `gh auth login`, then:

```bash
gh repo create maicos --private --source=. --remote=origin --push
```

**Option B — SSH.** Add an SSH key to your GitHub account, then:

```bash
git remote add origin git@github.com:<your-username>/maicos.git
git push -u origin main
```

> **Never paste a PAT into chat, screenshots, or config files.** If you
> must use a PAT locally, use the Git Credential Manager
> (`gh auth login` or `git config --global credential.helper manager`)
> so the token is stored in the OS keychain, not in plain text.

---

## 3. Deploy the frontend to Vercel (no long-lived token)

Vercel integrates with GitHub via the **Vercel GitHub App** (no token
needed at all), or via **OIDC** for CI-driven deploys. Full OIDC
setup is in **[VERCEL_SETUP.md](./VERCEL_SETUP.md)**. Quick version:

1. https://vercel.com/new → Import `maicos`
   - **Root Directory:** `frontend`
   - **Build Command:** `npm run build`
2. In Vercel project settings, enable **OIDC for GitHub**.
3. Add the resulting OIDC token to GitHub secrets as
   `VERCEL_OIDC_TOKEN`. Also add `NEXT_PUBLIC_API_URL` and, if you
   use hosted Supabase auth, the three Supabase env vars
   (`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`,
   `NEXT_PUBLIC_SUPABASE_ENABLED=true`) — see
   **[SUPABASE_SETUP.md](./SUPABASE_SETUP.md)** §4.2.
4. Branch protection on `main` (require PR + status checks).
5. Push → PR preview URL; merge → production URL.

If OIDC is unavailable in your plan, see §5 of `VERCEL_SETUP.md` for
the short-lived classic-token fallback (rotate, don't paste).

### If you self-host the backend (Render / Fly.io / a VM)

1. Deploy the backend somewhere reachable from the public internet
2. Set `DATABASE_URL`, `APP_SECRET_KEY`, `CORS_ORIGINS` in the
   backend's environment (use the host's secret store, not a `.env`
   file). The Postgres database also serves the job queue and
   scheduled jobs — **no Redis, no APScheduler** is needed.
3. Put the public URL into Vercel's `NEXT_PUBLIC_API_URL`
4. CORS: add your Vercel domain to the backend's `CORS_ORIGINS`

---

## 4. CI / CD (already wired)

There are three workflows under `.github/workflows/`:

- **`backend.yml`** — ruff + mypy + pytest on every push to `backend/**`
- **`frontend.yml`** — tsc + lint + `next build` on every push to
  `frontend/**`
- **`vercel.yml`** — Vercel preview (PR) + production (push to `main`)
  using OIDC; no long-lived token

Required GitHub secrets:

- `VERCEL_OIDC_TOKEN` — see VERCEL_SETUP.md
- `NEXT_PUBLIC_API_URL` — public URL of the backend
- `SUPABASE_DB_URL` — transaction-pooler connection string (see SUPABASE_SETUP.md §5)
- `SUPABASE_DB_URL_DIRECT` — direct connection string (port 5432) for Alembic
- (Optional) `SUPABASE_PROJECT_URL`, `SUPABASE_ANON_KEY` — only if backend
  talks to Supabase APIs directly
- (Optional) `OPENROUTER_API_KEY` — enables the live LLM smoke test

---

## 5. Day-to-day workflow

- Make a feature branch, push it, open a PR.
- CI runs automatically. Both backend and frontend must be green.
- Merge to `main` → Vercel auto-deploys.
- For data changes: write an Alembic migration under `backend/alembic/versions/`
  and bump the head.

---

## 6. If you ever need a token again

- **GitHub PATs:** create at https://github.com/settings/tokens
  - Classic token, `repo` + `workflow` only, **30-day expiry**.
  - Use it through the Git Credential Manager; never paste it into
    a file, chat, or `git remote set-url`.
- **Vercel tokens:** you should rarely need one. The GitHub App
  covers most cases. If you do (e.g. CI deploys), create a
  **project-scoped** token with a short expiry.

---

## 7. What to commit, what to NEVER commit

✅ Safe to commit:
- `*.py`, `*.ts`, `*.tsx`, `*.md`, `*.yml`
- `pyproject.toml`, `package.json`, `vercel.json`
- `.env.example`
- `alembic/versions/*.py`

🚫 NEVER commit:
- `.env`, `.env.local`, `.env.production`
- `var/`, `__pycache__/`, `node_modules/`, `.next/`
- API keys, database URLs with passwords, signing secrets
- `*.sqlite`, `*.db`
