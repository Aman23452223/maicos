# PRD → Code map

| PRD ref | Module |
|---|---|
| §3 / §10 / §33 MVP scope | `backend/app/agents`, `backend/app/workflow`, `backend/app/integrations` |
| §4 pipeline (UNDERSTAND→…→REPORT) | `orchestrator/__init__.py` |
| §5 AI Manager | `agents/implementations/ai_manager.py` |
| §6–§16 specialized agents | `agents/implementations/{sales_crm,project_ops,communication,knowledge}.py` |
| §14 / §20 approval model | `approvals/service.py`, `api/v1/approvals.py` |
| §15 backend architecture | `app/main.py`, `app/api/v1/*` |
| §17 / §26 data entities | `models/orm.py` |
| §18 / §27 security & governance | `core/security.py`, `core/secrets.py`, `core/context.py` |
| §19 agent execution state | `models/orm.py` (WorkflowState / TaskState), `workflow/engine.py` |
| §20 UX requirements | `frontend/src/app/page.tsx` (hero), `frontend/src/app/{workflows,approvals,agents,integrations,knowledge,audit}` |
| §21 integrations | `integrations/connectors/{crm,email,calendar}.py` |
| §22 RAG | `agents/implementations/knowledge.py`, `rag/service.py` |
| §24 UI sections | `frontend/src/app/{page.tsx,command,workflows,approvals,agents,integrations,knowledge,audit}` |
| §25 backend arch. | `app/main.py` |
| §27 LLM-credential boundary | `core/secrets.py`, `integrations/base.py` |
| §28 verify-before-completion | `integrations/connectors/email.py` (confirmed flag), `workflow/engine.py` |
| §29 error handling | `workflow/engine.py` (PARTIAL state, retries) |
| §30 autonomy levels | `core/config.py` (`default_autonomy_level`), `approvals/service.py` |
| §13 / FR-14 scheduled + event | `scheduler/__init__.py` |
| FR-01 workspaces | `api/v1/auth.py` |
| FR-02 tenant isolation + RBAC | `core/security.py`, `core/context.py` |
| FR-03 outcome-based NL | `api/v1/workflows.py` (`/commands`) |
| FR-04 executable plan | `agents/implementations/ai_manager.py` |
| FR-05 multi-agent delegation | `workflow/engine.py` |
| FR-06 tool scopes | `integrations/base.py` (`execute_tool`), `agents/runtime.py` |
| FR-07 read/write external systems | `integrations/connectors/*` |
| FR-08 task dependencies | `workflow/engine.py` (`_topo_ready`, `depends_on`) |
| FR-09 approval checkpoints | `approvals/service.py` |
| FR-10 verify before complete | `ToolResult.confirmed`, `workflow/engine.py` |
| FR-11 audit | `audit/service.py`, `api/v1/knowledge.py` |
| FR-12 retries / unrecoverable surfacing | `workflow/engine.py` (MAX_ATTEMPTS, FAILED) |
| FR-13 admin enable/disable | `api/v1/registry.py` |
| FR-14 scheduled / event | `scheduler/__init__.py` |
