"""Marketing Agent (PRD §10).

Plans campaigns and drafts content. The content draft is persisted via
the email connector's `message.draft` so the artifact is observable on
disk. External send is approval-gated per §14.
"""
from __future__ import annotations

import uuid
from typing import Any, ClassVar

from app.agents.base import AgentContext, AgentResult, AgentTask
from app.agents.registry import register
from app.agents.runtime import call_tool
from app.integrations.store import JsonStore, stores_root

_CAMPAIGNS = JsonStore[dict[str, Any]](stores_root() / "marketing.campaigns.json")


class MarketingAgent:
    name = "marketing"
    description = "Campaign planning, content drafts and lead workflows."
    allowed_tools: ClassVar[list[str]] = [
        "email.message.draft",
        "email.message.send",
        "crm.activity.record",
    ]

    def execute_approved(self, approval: dict, ctx: AgentContext) -> AgentResult:
        payload = approval.get("payload", {})
        res = call_tool(
            ctx,
            "email",
            "message.send",
            {
                "to": payload.get("to"),
                "subject": payload.get("subject"),
                "body": payload.get("body"),
            },
        )
        if not (res["ok"] and res["confirmed"]):
            return AgentResult(error=res.get("message") or "send failed")
        return AgentResult(output={"sent": res["data"]})

    def run(self, task: AgentTask, ctx: AgentContext) -> AgentResult:
        action = task.input.get("action", "draft_content")
        if action == "draft_content":
            res = call_tool(
                ctx,
                "email",
                "message.draft",
                {
                    "to": task.input.get("to", "list"),
                    "subject": task.input.get("subject", "Newsletter"),
                    "body": task.input.get("body", ""),
                },
            )
            if not (res["ok"] and res["confirmed"]):
                return AgentResult(error=res.get("message") or "draft failed")
            return AgentResult(output={"draft": res["data"]})
        if action == "plan_campaign":
            cid = str(uuid.uuid4())
            campaign = {
                "id": cid,
                "name": task.input.get("name"),
                "channels": task.input.get("channels", ["email"]),
                "steps": [
                    "Audience segmentation",
                    "Content draft",
                    "Approval",
                    "Send",
                    "Measure",
                ],
            }
            _CAMPAIGNS.put(cid, {**campaign, "workspace_id": ctx.principal.workspace_id})
            call_tool(
                ctx,
                "crm",
                "activity.record",
                {"type": "campaign.planned", "campaign_id": cid, "name": campaign["name"]},
            )
            return AgentResult(output={"campaign": campaign})
        if action == "analyze":
            return AgentResult(
                output={
                    "open_rate": task.input.get("open_rate", 0.0),
                    "ctr": task.input.get("ctr", 0.0),
                    "note": "Connect to a real analytics source for production numbers.",
                }
            )
        return AgentResult(error=f"unknown marketing action: {action}")


register(MarketingAgent())
