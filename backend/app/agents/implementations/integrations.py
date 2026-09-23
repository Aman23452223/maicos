"""Integration agent: honest connection-gated answers (generic, no industry logic)."""
from __future__ import annotations

from typing import ClassVar

from app.agents.base import AgentContext, AgentResult, AgentTask
from app.agents.registry import register


class IntegrationAgent:
    name = "integrations"
    description = "Answers about authorized integrations; never fabricates data."
    allowed_tools: ClassVar[list[str]] = []

    def run(self, task: AgentTask, ctx: AgentContext) -> AgentResult:
        from app.integrations.catalog import execute_action, get_entry

        provider = str(task.input.get("provider", "")).lower()
        action = str(task.input.get("action", ""))
        if not provider or not get_entry(provider):
            return AgentResult(error=f"unknown integration provider: {provider or '?'}")
        payload = dict(task.input.get("payload", {}))
        if provider == "github" and action in ("repo_info", "open_pr") \
                and not str(payload.get("repo", "")).strip():
            import re as _re

            m = _re.search(r"github\.com/([\w.-]+/[\w.-]+)",
                           f"{task.description} {task.input.get('objective', '')}")
            if m:
                payload["repo"] = m.group(1)
            else:
                return AgentResult(
                    needs_input={
                        "question": ("Which GitHub repository? Reply owner/repo "
                                     "(e.g. acme/website)."),
                        "field": "_answer_repo",
                    },
                    output={"provider": provider})
        if not action:
            # Status inquiry: honest connected/not-connected message.
            from app.integrations.catalog import verify
            v = verify(provider)
            if v.get("ok"):
                return AgentResult(output={"provider": provider, "status": "connected"})
            return AgentResult(output={
                "provider": provider, "status": "NOT_CONNECTED",
                "message": (f"{provider} is not connected for this business. "
                            f"Connect {provider} from Integrations first. "
                            f"{v.get('error', '')}"),
            })
        if task.input.get("_answer_repo") and provider == "github" \
                and not str(payload.get("repo", "")).strip():
            payload["repo"] = str(task.input["_answer_repo"]).strip()
        out = execute_action(provider, action, payload,
                             workspace_id=ctx.principal.workspace_id)
        if not out.get("ok"):
            return AgentResult(output={
                "provider": provider, "status": out.get("status"),
                "message": out.get("error") or out.get("status")})
        return AgentResult(output=out)


register(IntegrationAgent())
