"""Integration agent: honest connection-gated answers (generic, no industry logic)."""
from __future__ import annotations

from typing import ClassVar

from app.agents.base import AgentContext, AgentResult, AgentTask
from app.agents.registry import register


class IntegrationAgent:
    name = "integrations"
    description = "Answers about authorized integrations; never fabricates data."
    allowed_tools: ClassVar[list[str]] = []

    def execute_approved(self, approval: dict, ctx: AgentContext) -> AgentResult:
        payload = approval.get("payload", {})
        if payload.get("_code_push_approved"):
            from app.integrations.catalog import execute_action

            out = execute_action(
                str(payload.get("provider", "")), str(payload.get("action", "")),
                {k: v for k, v in payload.items() if not k.startswith("_")},
                workspace_id=ctx.principal.workspace_id)
            if not out.get("ok"):
                return AgentResult(error=out.get("error") or out.get("status"))
            return AgentResult(output=out)
        raise NotImplementedError

    def run(self, task: AgentTask, ctx: AgentContext) -> AgentResult:
        from app.integrations.catalog import execute_action, get_entry

        provider = str(task.input.get("provider", "")).lower()
        action = str(task.input.get("action", ""))
        if not provider or not get_entry(provider):
            return AgentResult(error=f"unknown integration provider: {provider or '?'}")
        if provider == "github" and action == "build_pr":
            merged = dict(task.input.get("payload", {}))
            if task.input.get("_answer_repo") and not str(merged.get("repo", "")).strip():
                merged["repo"] = str(task.input["_answer_repo"]).strip()
            if task.input.get("_answer_branch") and not str(merged.get("branch", "")).strip():
                merged["branch"] = str(task.input["_answer_branch"]).strip()
            task.input["payload"] = merged
            return self._build_pr(task, ctx)
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

    def _build_pr(self, task: AgentTask, ctx: AgentContext) -> AgentResult:
        """AI code push: ask for missing pieces, then require approval."""
        import re as _re

        payload = dict(task.input.get("payload", {}))
        if not str(payload.get("repo", "")).strip():
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
                    output={"provider": "github"})
        if task.input.get("_answer_repo") and not str(payload.get("repo", "")).strip():
            payload["repo"] = str(task.input["_answer_repo"]).strip()
        if not str(payload.get("branch", "")).strip():
            return AgentResult(
                needs_input={
                    "question": ("Which NEW branch name should the code go to? "
                                 "(Never direct-to-main.)"),
                    "field": "_answer_branch",
                },
                output={"provider": "github"})
        if task.input.get("_answer_branch") and not str(payload.get("branch", "")).strip():
            payload["branch"] = str(task.input["_answer_branch"]).strip()
        if not str(payload.get("requirements", "")).strip():
            payload["requirements"] = task.description
        if not payload.get("_code_push_approved"):
            return AgentResult(
                needs_approval={
                    "action": "push_code",
                    "target_system": "github",
                    "description": (f"Generate code from requirements and push to "
                                    f"{payload['repo']} branch {payload['branch']} as PR. "
                                    f"Review + CI required before merge."),
                    "payload": {"_code_push_approved": True,
                                "_operation": "code.push",
                                **{k: v for k, v in payload.items()
                                   if k in ("provider", "action", "repo", "branch",
                                            "base", "requirements", "stack")},
                                "provider": "github", "action": "build_pr"},
                })
        from app.integrations.catalog import execute_action

        out = execute_action("github", "build_pr", payload,
                             workspace_id=ctx.principal.workspace_id)
        if not out.get("ok"):
            return AgentResult(output={"provider": "github", "status": out.get("status"),
                                       "message": out.get("error") or out.get("status")})
        return AgentResult(output=out)


register(IntegrationAgent())
