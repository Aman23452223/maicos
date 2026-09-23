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

    @staticmethod
    def _auto_approved(ctx: AgentContext, channel: str) -> bool:
        """Workspace owner can opt channels out of approval (comms_policy)."""
        try:
            from app.intel.service import get_or_create_profile

            bp = get_or_create_profile(ctx.db, company_id=ctx.principal.workspace_id)
            auto = ((bp.comms_policy or {}).get("auto_approve") or [])
            return channel in [str(a).lower() for a in auto]
        except Exception:
            return False

    def _deliver(self, ctx: AgentContext, channel: str,
                 payload: dict) -> dict:
        """Route to the real channel sender. Email keeps the legacy
        approval-gated connector; WhatsApp uses the Meta provider."""
        if channel == "whatsapp":
            from app.comms.providers import MESSAGING

            out = MESSAGING.send(to=str(payload.get("to", "")),
                                 body=str(payload.get("body", "")),
                                 channel="whatsapp")
            # Normalize provider schema (error) to agent schema (message).
            if not out.get("ok") and "message" not in out:
                out["message"] = out.get("error") or out.get("status")
            out.setdefault("confirmed", bool(out.get("ok")))
            return out
        res = call_tool(
            ctx, "email", "message.send",
            {"to": payload.get("to"), "subject": payload.get("subject"),
             "body": payload.get("body")},
        )
        return {"ok": res["ok"], "confirmed": res.get("confirmed", False),
                "data": res.get("data"), "message": res.get("message")}

    def execute_approved(self, approval: dict, ctx: AgentContext) -> AgentResult:
        """After approval, actually send through the approved channel."""
        payload = approval.get("payload", {})
        channel = str(payload.get("channel", "email")).lower()
        res = self._deliver(ctx, channel, payload)
        if not (res.get("ok") and res.get("confirmed", res.get("ok"))):
            return AgentResult(
                error=res.get("message") or f"{channel} provider did not confirm send"
            )
        return AgentResult(output={"sent": res.get("data"), "channel": channel})

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
            channel = str(task.input.get("channel", "email")).lower()
            if channel not in ("email", "whatsapp"):
                return AgentResult(error=f"unsupported channel: {channel} "
                                         "(email/whatsapp only; stories are not "
                                         "supported by any provider API)")
            if not (task.input.get("to") or "").strip():
                return AgentResult(error="no recipient found: include an email "
                                         "address (email) or phone number (WhatsApp) "
                                         "in your command")
            payload = {
                "_operation": "message.send",
                "channel": channel,
                "to": task.input.get("to"),
                "subject": task.input.get("subject"),
                "body": task.input.get("body"),
            }
            if (requires_approval("send_external_communication")
                    and not self._auto_approved(ctx, channel)):
                return AgentResult(
                    needs_approval={
                        "action": "send_external_communication",
                        "target_system": channel,
                        "description": f"Send {channel} to {task.input.get('to')}",
                        "payload": payload,
                    }
                )
            res = self._deliver(ctx, channel, payload)
            if not (res.get("ok") and res.get("confirmed", res.get("ok"))):
                return AgentResult(
                    error=res.get("message") or f"{channel} provider did not confirm send"
                )
            return AgentResult(output={"sent": res.get("data"), "channel": channel})
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
