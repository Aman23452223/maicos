"""Per-run helper that agents use to call external systems.

The LLM never sees raw credentials. Authorization is enforced here via
the agent's `allowed_tools` (FR-06, §18, §27).
"""
from __future__ import annotations

from app.agents.base import AgentContext
from app.agents.registry import get as get_agent
from app.integrations.base import execute_tool


def _resolve_allowed(ctx: AgentContext) -> list[str]:
    # The runtime sets `ctx.shared["agent_name"]` before invoking the agent.
    name = ctx.shared.get("agent_name")
    if not name:
        return []
    return list(get_agent(name).allowed_tools or [])


def call_tool(
    ctx: AgentContext,
    connector: str,
    operation: str,
    payload: dict,
    idempotency_key: str | None = None,
) -> dict:
    # Tool-call limit enforcement (Phase 19) at execution layer.
    from app.workflow.budget import MAX_TOOL_CALLS_PER_TASK, BudgetExceeded

    used = sum(1 for e in (ctx.log or []) if e.get("type") == "tool_call")
    if used >= MAX_TOOL_CALLS_PER_TASK:
        try:
            from app.audit.service import record

            record(
                ctx.db, company_id=ctx.principal.workspace_id,
                actor=ctx.shared.get("agent_name", "agent"),
                action="tool.limit_exceeded", target_type="task",
                target_id=ctx.task_id,
                details={"connector": connector, "operation": operation,
                         "used": used, "limit": MAX_TOOL_CALLS_PER_TASK},
            )
        except Exception:
            pass
        raise BudgetExceeded(
            f"task {ctx.task_id} exceeded {MAX_TOOL_CALLS_PER_TASK} tool calls"
        )
    result = execute_tool(
        ctx.principal,
        connector,
        operation,
        payload,
        _resolve_allowed(ctx),
        idempotency_key=idempotency_key or f"{ctx.workflow_id}:{ctx.task_id}:{connector}.{operation}",
    )
    ctx.log.append(
        {
            "type": "tool_call",
            "connector": connector,
            "operation": operation,
            "ok": result.ok,
            "confirmed": result.confirmed,
            "external_id": result.external_id,
        }
    )
    return {
        "ok": result.ok,
        "confirmed": result.confirmed,
        "data": result.data,
        "message": result.message,
        "external_id": result.external_id,
    }

