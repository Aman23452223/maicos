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
        """Workspace owner can opt channels out of approval (risk policy)."""
        from app.policy.risk import workspace_allows

        return workspace_allows(ctx.db, company_id=ctx.principal.workspace_id,
                                action="send_external_communication",
                                channel=channel)

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
        if payload.get("_bulk_approved"):
            # Re-run the bulk task with approval stamped in input.
            return self.run(
                AgentTask(title="Bulk send", description="",
                          input={"action": "bulk_send",
                                 "_bulk_approved": True,
                                 "channel": payload.get("channel", "email"),
                                 "subject": payload.get("subject"),
                                 "body": payload.get("body"),
                                 "bulk_query": payload.get("bulk_query", ""),
                                 "list": payload.get("list", "")}),
                ctx)
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
        if action == "bulk_send":
            return self._bulk_send(task, ctx)
        if action == "send_digest":
            from app.company.digest import send_to_owner

            res = send_to_owner(ctx.db, company_id=ctx.principal.workspace_id)
            if not res.get("ok"):
                return AgentResult(error=res.get("error") or "digest failed")
            ctx.db.commit()
            return AgentResult(output={"digest": "sent", "to": "owner"})
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

    def _resolve_recipients(self, task: AgentTask, ctx: AgentContext) -> tuple[list, str]:
        """Resolve bulk recipients from the workspace lead sheet.

        Priority: explicit names -> named list -> all leads. Returns
        (recipients, how) where how explains the selection.
        """
        from sqlalchemy import or_

        from app.models.orm import Lead

        ws = ctx.principal.workspace_id
        q = (task.input.get("bulk_query") or task.description or "")
        # explicit answer from a clarification round?
        answered = (task.input.get("_answer") or "").strip()
        names: list[str] = []
        import re as _re
        # quoted names first ("Aman", 'Neha')
        names += _re.findall(r'"([^"]+)"', q) + _re.findall(r"'([^']+)'", q)
        if answered and not names:
            names += [n.strip() for n in _re.split(r"[,;]| and ", answered) if n.strip()]
        # "X and Y" / "X, Y" style: only when it looks like names, not sentences
        if not names and not any(
                k in q.lower() for k in ("all", "sabko", "every", "sheet", "everyone")):
            parts = [n.strip() for n in _re.split(r",| and ", q) if n.strip()]
            # strip command words
            stripped = []
            for p in parts:
                p2 = _re.sub(r"(?i)\b(send|email|message|whatsapp|msg|to|bhej|kar|ko|ke|par)\b", "", p).strip()
                if p2 and len(p2.split()) <= 3:
                    stripped.append(p2)
            names = stripped
        if names:
            conds = []
            for n in names[:20]:
                like = f"%{n}%"
                conds += [Lead.company_name.ilike(like)]
            rows = (ctx.db.query(Lead).filter(Lead.company_id == ws, or_(*conds)).limit(50).all()
                    if conds else [])
            return rows, f"named ({', '.join(names[:10])})"
        if any(k in q.lower() for k in ("all", "sabko", "every", "sheet", "everyone")) or answered:
            rows = (ctx.db.query(Lead).filter(Lead.company_id == ws,
                                              Lead.opted_out.is_(False))
                    .order_by(Lead.score.desc()).limit(200).all())
            tag = (task.input.get("list") or "").strip()
            if tag:
                rows = [r for r in rows if tag.lower() in (r.source or "").lower()]
                return rows, f"list '{tag}'"
            return rows, "all contacts"
        return [], ""

    def _bulk_send(self, task: AgentTask, ctx: AgentContext) -> AgentResult:
        from app.core.idempotency import execute_once
        from app.leads.service import touch_contacted

        channel = str(task.input.get("channel", "email")).lower()
        if channel not in ("email", "whatsapp"):
            return AgentResult(error="bulk send supports email/whatsapp only")
        recipients, how = self._resolve_recipients(task, ctx)
        if not recipients:
            # Ask like I ask you: which contacts?
            return AgentResult(
                        needs_input={
                            "question": ("Kaunse contacts ko bheju? Naam batao "
                                         '("Aman, Neha") ya "all" likho poori sheet ke liye.'),
                            "field": "_answer",
                        },
                        output={"channel": channel},
                    )
        subject = str(task.input.get("subject", "Message from MAICOS"))
        template = str(task.input.get("body") or task.description or "")
        # If not yet approved (or auto-approved), gate once for the batch.
        if (not task.input.get("_bulk_approved")
                and not self._auto_approved(ctx, channel)):
            from app.approvals.service import requires_approval

            if requires_approval("send_external_communication"):
                preview = [r.company_name for r in recipients[:3]]
                return AgentResult(
                    needs_approval={
                        "action": "send_external_communication",
                        "target_system": f"{channel}:bulk",
                        "description": (f"Bulk {channel} to {len(recipients)} "
                                        f"contacts ({how}): {', '.join(preview)}..."),
                        "payload": {"_operation": "message.send",
                                    "_bulk_approved": True,
                                    "channel": channel,
                                    "subject": subject, "body": template,
                                    "bulk_query": task.input.get("bulk_query", ""),
                                    "list": task.input.get("list", "")},
                    })
        sent, failed = [], []
        for r in recipients:
            addr = (r.email or "") if channel == "email" else (r.phone or "")
            if not addr:
                failed.append({"lead": r.company_name, "error": f"no {channel} address"})
                continue
            body = template.replace("{{name}}", r.company_name).replace(
                "{{company}}", r.company_name)
            key = f"{ctx.workflow_id}:{ctx.task_id}:{channel}:{r.id}"

            def _one(addr=addr, body=body):
                return self._deliver(ctx, channel, {"to": addr, "subject": subject,
                                                    "body": body})

            try:
                res = execute_once(ctx.db, company_id=ctx.principal.workspace_id,
                                   key=key, payload={"to": addr, "body": body}, fn=_one)
            except Exception as exc:
                failed.append({"lead": r.company_name, "error": str(exc)[:200]})
                continue
            if res.get("ok"):
                sent.append(r.company_name)
                touch_contacted(ctx.db, company_id=ctx.principal.workspace_id, lead_id=r.id)
            else:
                failed.append({"lead": r.company_name,
                               "error": str(res.get("error") or res.get("message"))[:200]})
        ctx.db.commit()
        if sent and not failed:
            return AgentResult(output={"sent": len(sent), "channel": channel, "how": how})
        if sent:
            return AgentResult(output={"sent": len(sent), "failed": failed,
                                       "channel": channel, "how": how},
                               error=f"{len(failed)} of {len(recipients)} failed")
        return AgentResult(error=f"bulk {channel} failed for all {len(recipients)}: "
                                 f"{str(failed[:2])[:300]}")

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
