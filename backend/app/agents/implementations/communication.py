"""Communication Agent (PRD §13, §28).

Drafts are automatic. Sends require approval per PRD §14 unless the
workspace's autonomy level permits Level 2 execution.
"""
from __future__ import annotations

from typing import ClassVar

from app.agents.base import AgentContext, AgentResult, AgentTask
from app.agents.registry import register
from app.agents.runtime import call_tool
from app.approvals.service import requires_approval


class CommunicationAgent:
    name = "communication"
    description = "Drafts and (when authorized) sends messages via email/WhatsApp."
    allowed_tools: ClassVar[list[str]] = [
        "email.message.draft",
        "email.message.send",
    ]

    def execute_approved(self, approval: dict, ctx: AgentContext) -> AgentResult:
        """After approval, actually send the email through the connector."""
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
            return AgentResult(
                error=res.get("message") or "email provider did not confirm send"
            )
        return AgentResult(output={"sent": res["data"]})

    def run(self, task: AgentTask, ctx: AgentContext) -> AgentResult:
        action = task.input.get("action", "draft")
        if action == "draft":
            # Personalize the draft using upstream task output. The
            # finance `find_overdue` task returns a list of invoices;
            # if present, we include the customer names and amounts in
            # the subject + body so the message is concrete.
            to, subject, body = self._personalise_draft(task, ctx)
            res = call_tool(
                ctx,
                "email",
                "message.draft",
                {"to": to, "subject": subject, "body": body},
            )
            if not (res["ok"] and res["confirmed"]):
                return AgentResult(error=res.get("message") or "draft failed")
            return AgentResult(output={"draft": res["data"]})
        if action == "send":
            if requires_approval("send_external_communication"):
                return AgentResult(
                    needs_approval={
                        "action": "send_external_communication",
                        "target_system": "email",
                        "description": f"Send email to {task.input.get('to')}",
                        "payload": {
                            "_operation": "message.send",
                            "to": task.input.get("to"),
                            "subject": task.input.get("subject"),
                            "body": task.input.get("body"),
                        },
                    }
                )
            res = call_tool(
                ctx,
                "email",
                "message.send",
                {
                    "to": task.input.get("to"),
                    "subject": task.input.get("subject"),
                    "body": task.input.get("body"),
                },
            )
            if not (res["ok"] and res["confirmed"]):
                return AgentResult(
                    error=res.get("message") or "email provider did not confirm send"
                )
            return AgentResult(output={"sent": res["data"]})
        return AgentResult(error=f"unknown communication action: {action}")

    @staticmethod
    def _personalise_draft(
        task: AgentTask, ctx: AgentContext
    ) -> tuple[str, str, str]:
        # `ctx.shared` carries the upstream task's output dict directly
        # (not a row wrapper), so we read the named keys from it.
        upstream = ctx.shared.get("find_overdue") or {}
        overdue = upstream.get("overdue") or []
        to = task.input.get("to", "list")
        subject = task.input.get("subject", "Following up")
        body = task.input.get("body", "Hi,")
        if overdue and to == "list":
            customers = ", ".join(
                inv.get("customer", "customer") for inv in overdue
            )
            amounts = ", ".join(
                f"${inv.get('amount', 0):.2f}" for inv in overdue
            )
            subject = f"Payment reminder: {customers}"
            body = (
                f"Hi,\n\nThis is a friendly reminder that the following "
                f"invoices are past due: {customers} "
                f"(amounts: {amounts}).\n\nPlease arrange payment at your "
                f"earliest convenience.\n\nThank you."
            )
        return to, subject, body


register(CommunicationAgent())
