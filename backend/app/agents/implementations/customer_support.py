"""Customer Support Agent (PRD §12).

Classifies tickets, drafts responses, and escalates exceptions. Ticket
state is persisted via the CRM activity stream and a dedicated
support store.
"""
from __future__ import annotations

import uuid
from typing import Any, ClassVar

from app.agents.base import AgentContext, AgentResult, AgentTask
from app.agents.registry import register
from app.agents.runtime import call_tool
from app.integrations.store import JsonStore, stores_root

_TICKETS = JsonStore[dict[str, Any]](stores_root() / "support.tickets.json")


def _tickets_for(workspace_id: str) -> list[dict[str, Any]]:
    return [t for t in _TICKETS.all() if t.get("workspace_id") == workspace_id]


class CustomerSupportAgent:
    name = "customer_support"
    description = "Ticket classification, knowledge-grounded responses, escalation."
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
        action = task.input.get("action", "classify")
        ws = ctx.principal.workspace_id
        if action == "classify":
            text = (task.input.get("text") or task.description or "").lower()
            category = "general"
            for kw, cat in [
                ("refund", "billing"),
                ("invoice", "billing"),
                ("bug", "technical"),
                ("error", "technical"),
                ("feature", "product"),
            ]:
                if kw in text:
                    category = cat
                    break
            return AgentResult(output={"category": category})
        if action == "open_ticket":
            tid = str(uuid.uuid4())
            ticket = {
                "id": tid,
                "workspace_id": ws,
                "subject": task.input.get("subject"),
                "category": task.input.get("category", "general"),
                "priority": task.input.get("priority", "normal"),
                "status": "open",
            }
            _TICKETS.put(tid, ticket)
            call_tool(
                ctx,
                "crm",
                "activity.record",
                {
                    "type": "ticket.opened",
                    "ticket_id": tid,
                    "subject": ticket["subject"],
                    "category": ticket["category"],
                },
            )
            return AgentResult(output={"ticket": ticket})
        if action == "draft_reply":
            res = call_tool(
                ctx,
                "email",
                "message.draft",
                {
                    "to": task.input.get("to"),
                    "subject": f"Re: {task.input.get('subject', '')}",
                    "body": task.input.get("body", "Thank you for reaching out."),
                },
            )
            if not (res["ok"] and res["confirmed"]):
                return AgentResult(error=res.get("message") or "draft failed")
            return AgentResult(output={"draft": res["data"]})
        if action == "list_open":
            open_t = [t for t in _tickets_for(ws) if t.get("status") == "open"]
            return AgentResult(output={"tickets": open_t, "count": len(open_t)})
        if action == "escalate":
            return AgentResult(
                needs_approval={
                    "action": "send_external_communication",
                    "target_system": "email",
                    "description": f"Escalate to human: {task.input.get('reason', '')}",
                    "payload": {
                        "_operation": "message.send",
                        "to": task.input.get("to"),
                        "subject": f"[Escalation] {task.input.get('subject', 'Ticket')}",
                        "body": task.input.get("body", "Escalating to a human for review."),
                    },
                }
            )
        return AgentResult(error=f"unknown support action: {action}")


register(CustomerSupportAgent())
