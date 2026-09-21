# MAICOS Multi-Tenant Business-Aware Platform

One generic core + many isolated workspaces. No industry-specific code.

## Model

`Company` = workspace (`slug`, `status`, `config`, `plan`).
`WorkspaceMembership(user_id, company_id, role, status)` — OWNER/ADMIN/MEMBER.
`BusinessProfile` per workspace: name, industry, services, segments, goals,
ICP, scoring/qualification rules, capabilities, working hours, timezone.
`WorkspaceIntegration(provider, status)` — health without secrets.

## Auth flows

- Register → workspace created → user OWNER (+ membership row).
- Login → token bound to one workspace.
- `GET /api/v1/workspaces` lists memberships; `POST /api/v1/auth/switch`
  returns a token for another workspace (membership enforced).
- `POST /api/v1/workspaces` (auth) creates workspace, creator OWNER.
- Cross-workspace user creation is 403.

## Capabilities / plans

Registry: `app/capabilities/registry.py` (20 generic capabilities, no
industry entries). Plans: starter/growth/scale map to capability sets.
Default for legacy workspaces: all (backward compat). Explicit
`enabled_capabilities` on BusinessProfile opts into gating.
Disabled capability at runtime: `NOT_ENABLED` (never fake success).

## Planner

`orchestrator.handle_objective` loads membership role + business profile +
capabilities, injects `_workspace` into every task input, drops tasks whose
capability is disabled, records context in audit. Agents keep working on
`principal.workspace_id` (current workspace CRM/knowledge/analytics).

## Isolation

Every business table carries `company_id`; APIs filter by token workspace;
RAG (lexical + vector store) filters by workspace + roles; workers/approvals
persist `company_id`; resume verifies token workspace == workflow workspace;
unsigned webhooks rejected when `WEBHOOK_SECRET` is set.

## Integrations health

`GET /api/v1/integrations/status` → capabilities + per-provider
`healthy`/`not_configured` (env-derived, secrets never exposed).

## Env vars

Required: `DATABASE_URL`, `APP_SECRET_KEY`.
Optional per provider: `SEARCH_PROVIDER_API_KEY`/`TAVILY_API_KEY`,
`SENDGRID_API_KEY`, `SMTP_HOST`/`SMTP_PORT`/`SMTP_FROM`,
`HUBSPOT_API_KEY`, `GOOGLE_CALENDAR_CREDENTIALS`, `WHATSAPP_TOKEN`,
`RAZORPAY_KEY`, `STRIPE_KEY`, `OPENAI_API_KEY` (+`EMBEDDING_PROVIDER`,
`EMBEDDING_MODEL`), `WEBHOOK_SECRET`, `PARALLEL_ENABLED`.

## Migrations

- `a1b2c3d4e5f6` CRM foundation
- `b2c3d4e5f6a7` vectors/pipelines/campaigns/payments
- `c3d4e5f6a7b8` workspace membership/capabilities/integrations
Run `alembic upgrade head` (Postgres) — SQLite tests use `create_all`.
