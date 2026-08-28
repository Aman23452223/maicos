# MAICOS — Multi-Agent AI Company Operating System

An action-oriented AI workforce that plans, delegates, executes, verifies
and reports on real business work. A user says what they want done; the
AI Manager coordinates specialised agents, calls real tools, gates
sensitive actions behind approvals, and produces a completion summary.

> **MVP validated end-to-end.** See
> [`docs/proof-output.txt`](docs/proof-output.txt) — five real agents
> coordinate to onboard a client, change real on-disk CRM / email /
> calendar stores, gate external sends behind approval, and resume to
> completion. Zero mocks.

---

## What's in the box

```
maicos/
├── backend/        FastAPI + SQLAlchemy + Alembic
│   ├── app/        agents, orchestrator, workflow engine, approvals, RAG
│   ├── tests/      pytest suite + end-to-end proof
│   └── pyproject.toml
├── frontend/       Next.js 14 (App Router, Tailwind)
│   └── src/app/    Loopstack-inspired hero at /, dashboard after
├── infra/          docker-compose for Postgres+pgvector, Redis, backend, worker, frontend
├── docs/
│   ├── PRD-mapping.md     PRD section → file path
│   └── proof-output.txt   captured output of the end-to-end proof
├── .github/
│   ├── workflows/  backend CI · frontend CI · Vercel deploy (OIDC)
│   ├── CODEOWNERS
│   ├── dependabot.yml
│   └── PULL_REQUEST_TEMPLATE.md
├── vercel.json     Vercel project config (root = frontend)
├── DEPLOY.md       end-to-end push + deploy runbook
└── VERCEL_SETUP.md Vercel OIDC + token-fallback setup
```

---

## Agents (10)

| # | Agent         | Purpose (PRD §)              | Persistence                      |
| - | ------------- | ---------------------------- | -------------------------------- |
| 1 | ai_manager    | §5  intent → plan            | deterministic + LLM planner      |
| 2 | knowledge     | §15, §22 RAG                 | chunked token-overlap index      |
| 3 | sales_crm     | §6.1, §7                     | file-backed CRM                  |
| 4 | project_ops   | §11                          | file-backed + CRM activity       |
| 5 | communication | §13, §28                     | file-backed outbox + optional SMTP |
| 6 | calendar      | §14                          | file-backed events               |
| 7 | finance       | §8                           | file-backed invoices + approval-gated prep |
| 8 | hr            | §9                           | file-backed candidates + checklists |
| 9 | marketing     | §10                          | file-backed campaigns + email drafts |
| 10| customer_support | §12                       | file-backed tickets              |
| 11| analytics     | §16                          | real statistics, no persistence needed |

---

## Quick start (local)

```bash
# 1. Start Postgres + Redis (any way you like)
cd backend
cp .env.example .env
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# 2. (Optional) Run the worker for scheduled / event workflows
python -m app.workers.scheduler

# 3. Frontend
cd ../frontend
cp .env.example .env.local
npm install
npm run dev
# → http://localhost:3000
```

End-to-end proof (no DB required, runs in-process):
```bash
cd backend
python -m tests.proof_onboarding
```

---

## Documentation map

- **[`DEPLOY.md`](DEPLOY.md)** — git + GitHub + Vercel, the safe way
- **[`VERCEL_SETUP.md`](VERCEL_SETUP.md)** — OIDC setup, fallback to short-lived token
- **[`docs/PRD-mapping.md`](docs/PRD-mapping.md)** — every PRD section → file
- **[`docs/proof-output.txt`](docs/proof-output.txt)** — captured output of the end-to-end proof
- **[`backend/.env.example`](backend/.env.example)** — required env vars
- **[`infra/docker-compose.yml`](infra/docker-compose.yml)** — full stack in containers

---

## Security posture

- **No long-lived secrets in code or chat.** The Vercel deploy uses OIDC
  (short-lived tokens). `OPENROUTER_API_KEY` is optional and supplied
  via the in-app Settings page or environment.
- **Strict tenant isolation.** Every query filters by `workspace_id`;
  tool calls check `allowed_tools` per agent.
- **Approval gates.** External communication, payments, critical
  deletions, and security changes are approval-gated by default
  (PRD §14); configurable in the Settings page.
- **Verify-before-completion.** A tool result is only treated as
  successful when the provider returns an explicit confirmation
  (PRD §28).
- **Audit trail.** Every material action — workflow created, approval
  requested / decided, tool called, workflow finished — is recorded
  in `audit_log` and visible at `/audit`.
- **Budgets.** Per-workflow task cap and per-task tool-call cap
  prevent runaway loops (PRD risk section).

---

## Status

- ✅ MVP scaffold + 10 agents + 3 file-backed connectors
- ✅ Multi-tenant RBAC, audit log, approval center
- ✅ Permission-scoped RAG with chunked retrieval
- ✅ Redis-backed job queue + APScheduler + event webhooks
- ✅ Idempotency keys, workflow budgets
- ✅ LLM planner (OpenAI, Anthropic, OpenRouter) with deterministic fallback
- ✅ End-to-end proof validated against real on-disk stores
- ✅ Loopstack-inspired hero on the landing page
- ✅ Tokenless CI / CD via GitHub Actions + Vercel OIDC

Next: backend hosting (Render / Fly.io / a VM), webhook signing,
pgvector swap, voice interface, workflow builder UI.
