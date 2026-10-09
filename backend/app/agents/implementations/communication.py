"""Communication Agent (PRD §13, §28).

Drafts are automatic. Sends require approval per PRD §14 unless the
workspace's autonomy level permits Level 2 execution.
"""
from __future__ import annotations

import re
from typing import Any, ClassVar

from app.agents.base import AgentContext, AgentResult, AgentTask
from app.agents.registry import register
from app.agents.runtime import call_tool
from app.approvals.service import requires_approval

_EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$")
_BILLING_HINTS = ("billing", "missing", "kyc", "gst", "invoice",
                  "quotation", "payment", "dues", "document")


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
            to, subject, body, info = self._compose_draft(task, ctx)
            res = call_tool(
                ctx,
                "email",
                "message.draft",
                {"to": to, "subject": subject, "body": body},
            )
            if not (res["ok"] and res["confirmed"]):
                return AgentResult(error=res.get("message") or "draft failed")
            out: dict[str, Any] = {"draft": res["data"], "purpose": info["purpose"]}
            if info["missing"]:
                out["missing"] = info["missing"]
            return AgentResult(output=out)
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
    def _valid_email(value: Any) -> bool:
        return bool(value and _EMAIL_RE.match(str(value).strip()))

    def _crm_recipient(
        self, ctx: AgentContext, customer: str | None
    ) -> tuple[str | None, str | None]:
        """(email, contact_name) from CRM records, tenant-scoped. Never invents."""
        if not customer:
            return None, None
        from app.models.orm import CrmContact, Customer, Lead

        ws = ctx.principal.workspace_id
        like = f"%{customer}%"
        lead = (
            ctx.db.query(Lead)
            .filter(Lead.company_id == ws, Lead.company_name.ilike(like))
            .order_by(Lead.score.desc())
            .first()
        )
        if lead is not None and self._valid_email(lead.email):
            return str(lead.email).strip(), None
        contact = (
            ctx.db.query(CrmContact)
            .filter(CrmContact.company_id == ws, CrmContact.name.ilike(like))
            .first()
        )
        if contact is not None and self._valid_email(contact.email):
            return str(contact.email).strip(), (contact.name or "").strip() or None
        cust = (
            ctx.db.query(Customer)
            .filter(Customer.company_id == ws, Customer.name.ilike(like))
            .first()
        )
        if cust is not None and self._valid_email(cust.email):
            return str(cust.email).strip(), (cust.name or "").strip() or None
        return None, None

    def _draft_identity(
        self, task: AgentTask, ctx: AgentContext
    ) -> tuple[str | None, str | None, str | None, list[str]]:
        """Resolve (customer, contact_name, email, missing).

        Precedence: explicit task input, then upstream task outputs, then
        CRM lookup. Anything unresolvable is reported in `missing` — never
        invented (no "list", no placeholder addresses).
        """
        inp = task.input or {}
        customer = str(inp.get("customer") or "").strip() or None
        contact_name = str(inp.get("contact_name") or inp.get("name") or "").strip() or None
        raw_to = inp.get("to") or inp.get("email") or ""
        email = str(raw_to).strip() if self._valid_email(raw_to) else None
        for _key, out in (ctx.shared or {}).items():
            if not isinstance(out, dict):
                continue
            comp = out.get("company") if isinstance(out.get("company"), dict) else {}
            cont = out.get("contact") if isinstance(out.get("contact"), dict) else {}
            if not customer and comp.get("name"):
                customer = str(comp["name"])[:120]
            if not contact_name and cont.get("name"):
                contact_name = str(cont["name"])[:120]
            if not email:
                for cand in (cont.get("email"), comp.get("email")):
                    if self._valid_email(cand):
                        email = str(cand).strip()
                        break
        if customer and not email:
            crm_email, crm_name = self._crm_recipient(ctx, customer)
            email = email or crm_email
            contact_name = contact_name or crm_name
        missing: list[str] = []
        if not email:
            missing.append("recipient email address (not found in CRM)")
        if not customer:
            missing.append("customer name")
        return customer, contact_name, email, missing

    def _business_info(
        self, task: AgentTask, ctx: AgentContext
    ) -> tuple[str, list[str], str, str]:
        """(business_name, offerings, audience) from the workspace profile.

        Falls back to the task's `_workspace` context; the knowledge vault
        supplies a catalogue note. Empty when unknown — never invented.
        """
        ws = ctx.principal.workspace_id
        name, offerings, audience = "", [], ""
        try:
            from app.models.orm import BusinessProfile

            bp = (
                ctx.db.query(BusinessProfile)
                .filter(BusinessProfile.company_id == ws)
                .first()
            )
            if bp is not None:
                name = (bp.business_name or "").strip()
                for s in (bp.products_services or [])[:5]:
                    if isinstance(s, dict):
                        s = s.get("name") or s.get("title") or ""
                    s = str(s).strip()
                    if s:
                        offerings.append(s[:80])
                audience = (bp.target_customer or "").strip()[:200]
        except Exception:
            pass
        wctx = (task.input or {}).get("_workspace") or {}
        if not name and isinstance(wctx, dict):
            name = str(wctx.get("business_name") or "").strip()
        catalogue_note = ""
        if not offerings:
            try:
                from app.rag.index import get_index

                hits = get_index().search(
                    principal=ctx.principal,
                    query=f"{name or 'business'} products services offered",
                    top_k=1,
                )
                if hits:
                    catalogue_note = str(hits[0].get("snippet") or "")[:300]
            except Exception:
                pass
        return name, offerings, audience, catalogue_note

    @staticmethod
    def _draft_purpose(task: AgentTask) -> str:
        inp = task.input or {}
        purpose = str(inp.get("purpose") or inp.get("template") or "").strip().lower()
        if purpose in ("welcome", "billing_request"):
            return purpose
        hay = f"{task.title} {task.description}".lower()
        if any(k in hay for k in _BILLING_HINTS):
            return "billing_request"
        return "welcome"

    @staticmethod
    def _missing_billing_fields(ctx: AgentContext) -> list[str]:
        """Fields the upstream gap analysis actually flagged (deduped)."""
        seen: list[str] = []
        for _key, out in (ctx.shared or {}).items():
            if not isinstance(out, dict):
                continue
            for m in out.get("missing") or []:
                s = str(m).strip()
                if s and s not in seen:
                    seen.append(s)
                if len(seen) >= 10:
                    return seen
        return seen

    def _welcome_subject_body(
        self, *, customer: str | None, contact_name: str | None,
        business: str, offerings: list[str], audience: str,
    ) -> tuple[str, str]:
        who = customer or "your account"
        if business and customer:
            subject = f"Welcome to {business}, {customer}"
        elif business:
            subject = f"Welcome to {business}"
        else:
            subject = "Welcome aboard!"
        greet = contact_name or customer or "there"
        paras = [f"Hi {greet},"]
        if business:
            paras.append(
                f"Welcome aboard {business}! We're delighted to have {who} with us.")
        else:
            paras.append(f"Welcome aboard! We're delighted to have {who} with us.")
        if offerings:
            sent = f"As a quick reminder, we offer {', '.join(offerings)}"
            sent += f" for {audience}." if audience else "."
            paras.append(sent)
        paras.append(
            "Your onboarding is underway — your account manager will reach out "
            "shortly with next steps, billing setup, and your welcome checklist.")
        paras.append(
            "If you have any questions in the meantime, simply reply to this email.")
        paras.append(
            f"Warm regards,\n{business} Team" if business
            else "Warm regards,\nCustomer Success Team")
        return subject, "\n\n".join(paras)

    def _billing_subject_body(
        self, *, customer: str | None, contact_name: str | None,
        business: str, missing_fields: list[str],
    ) -> tuple[str, str]:
        who = customer or "your account"
        subject = f"Billing details needed for {who}"
        if business:
            subject += f" — {business}"
        greet = contact_name or customer or "there"
        paras = [f"Hi {greet},"]
        lead = f"As part of onboarding {who}"
        lead += f" with {business}" if business else ""
        lead += (", we need a few billing details to prepare your "
                 "account and quotation.")
        paras.append(lead)
        if missing_fields:
            paras.append("Our records show the following are still pending:")
            paras.extend(f"- {m}" for m in missing_fields)
        else:
            paras.append(
                "Our records show some billing details are still pending. "
                "Typically this includes your GST number, billing address, and "
                "preferred payment terms — please share whichever applies.")
        paras.append(
            "Please reply to this email with the details at your convenience, "
            "and we will take it from there.")
        paras.append(
            f"Warm regards,\n{business} Team" if business
            else "Warm regards,\nCustomer Success Team")
        return subject, "\n\n".join(paras)

    def _compose_draft(
        self, task: AgentTask, ctx: AgentContext
    ) -> tuple[str, str, str, dict[str, Any]]:
        """Resolve recipient, subject and body — real values only.

        Explicit planner-provided subject/body win when substantive
        (>= 50 chars of body); otherwise the email is composed from the
        CRM record + workspace knowledge base. Placeholders ("list",
        "Hi,") are never kept. Returns (to, subject, body, info) where
        info carries purpose/customer/missing for the task output.
        """
        inp = task.input or {}
        # Legacy path (unchanged): overdue-invoice payment reminder.
        upstream = ctx.shared.get("find_overdue") or {}
        overdue = upstream.get("overdue") or []
        if overdue and (inp.get("to", "list") == "list"):
            customers = ", ".join(
                inv.get("customer", "customer") for inv in overdue
            )
            amounts = ", ".join(
                f"${inv.get('amount', 0):.2f}" for inv in overdue
            )
            subject = f"Payment reminder: {customers}"
            body = (
                "Hi,\n\nThis is a friendly reminder that the following "
                f"invoices are past due: {customers} "
                f"(amounts: {amounts}).\n\nPlease arrange payment at your "
                "earliest convenience.\n\nThank you."
            )
            to = ""
            for inv in overdue:
                email, _ = self._crm_recipient(ctx, str(inv.get("customer") or ""))
                if email:
                    to = email
                    break
            missing = [] if to else ["recipient email address (not found in CRM)"]
            return to, subject, body, {"purpose": "payment_reminder",
                                       "customer": customers or None,
                                       "missing": missing}

        customer, contact_name, email, missing = self._draft_identity(task, ctx)
        business, offerings, audience, catalogue_note = self._business_info(task, ctx)
        purpose = self._draft_purpose(task)
        if purpose == "billing_request":
            gen_subject, gen_body = self._billing_subject_body(
                customer=customer, contact_name=contact_name,
                business=business,
                missing_fields=self._missing_billing_fields(ctx))
        else:
            gen_subject, gen_body = self._welcome_subject_body(
                customer=customer, contact_name=contact_name,
                business=business, offerings=offerings, audience=audience)
            if catalogue_note and not offerings:
                gen_body += f"\n\nFrom our catalogue: {catalogue_note}"
        explicit_subject = str(inp.get("subject") or "").strip()
        explicit_body = str(inp.get("body") or "")
        subject = explicit_subject or gen_subject
        body = explicit_body if len(explicit_body.strip()) >= 50 else gen_body
        return (email or "", subject, body,
                {"purpose": purpose, "customer": customer, "missing": missing})

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
