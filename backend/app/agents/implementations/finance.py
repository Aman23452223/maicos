"""Finance Agent (PRD §8).

All finance state is persisted via the CRM `activity` stream (which is
file-backed) and a dedicated finance store. Invoice preparation is
always approval-gated per §14.

Quotations are drafts only: `prepare_quotation` builds a clearly
labelled quotation DRAFT (stored via the proposals architecture) and
never invents quantities, specs, taxes, discounts, stock or delivery
commitments. Anything missing lands in `unresolved_fields`. It never
issues a tax invoice, records a payment, or sends anything externally.
"""
from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

from app.agents.base import AgentContext, AgentResult, AgentTask
from app.agents.registry import register
from app.agents.runtime import call_tool
from app.integrations.store import JsonStore, stores_root

_INVOICES = JsonStore[dict[str, Any]](stores_root() / "finance.invoices.json")

# Currency-marked amounts only (₹ / Rs / INR). Bare numbers are never
# treated as prices — that would risk inventing money figures.
_PRICE_RE = re.compile(r"(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d{1,2})?)")
_QTY_RE = re.compile(r"([\d,]+(?:\.\d+)?)\s*([a-zA-Z]+)?")
_QUOTATION_ITEM_LIMIT = 25


def _invoices_for(workspace_id: str) -> list[dict[str, Any]]:
    return [i for i in _INVOICES.all() if i.get("workspace_id") == workspace_id]


class FinanceAgent:
    name = "finance"
    description = "Prepares invoices, expenses and receivable follow-ups."
    allowed_tools: ClassVar[list[str]] = [
        "crm.activity.record",
    ]

    def execute_approved(self, approval: dict, ctx: AgentContext) -> AgentResult:
        """After approval, persist the invoice and record activity."""
        action = approval.get("action", "")
        if action == "create_financial_document":
            payload = approval.get("payload", {})
            # Delegate to the create_invoice action of run().
            return self.run(
                AgentTask(title="Create invoice", description="", input={
                    "action": "create_invoice",
                    "customer": payload.get("customer"),
                    "amount": payload.get("amount"),
                    "due_in_days": payload.get("due_in_days", 30),
                }),
                ctx,
            )
        return AgentResult(error=f"no approved action handler for: {action}")

    def run(self, task: AgentTask, ctx: AgentContext) -> AgentResult:
        action = task.input.get("action")
        ws = ctx.principal.workspace_id
        if action == "prepare_invoice":
            # Always requires approval per PRD §14.
            return AgentResult(
                needs_approval={
                    "action": "create_financial_document",
                    "target_system": "finance",
                    "description": f"Prepare invoice for {task.input.get('customer')}",
                    "payload": {
                        "_operation": "invoice.create",
                        "customer": task.input.get("customer"),
                        "amount": task.input.get("amount"),
                        "due_in_days": task.input.get("due_in_days", 30),
                    },
                }
            )
        if action == "create_invoice":
            # Replay path after approval - persists to the finance store.
            iid = str(uuid.uuid4())
            due = datetime.now(UTC) + timedelta(
                days=int(task.input.get("due_in_days", 30))
            )
            rec = {
                "id": iid,
                "workspace_id": ws,
                "customer": task.input.get("customer"),
                "amount": task.input.get("amount"),
                "due_at": due.isoformat(),
                "status": "OPEN",
                "created_at": datetime.now(UTC).isoformat(),
            }
            _INVOICES.put(iid, rec)
            call_tool(
                ctx,
                "crm",
                "activity.record",
                {
                    "type": "invoice.created",
                    "invoice_id": iid,
                    "customer": rec["customer"],
                    "amount": rec["amount"],
                },
            )
            return AgentResult(output={"invoice": rec, "ok": True, "confirmed": True})
        if action == "find_overdue":
            today = datetime.now(UTC)
            overdue = [
                i
                for i in _invoices_for(ws)
                if i.get("status") != "PAID"
                and datetime.fromisoformat(i["due_at"]) < today
            ]
            return AgentResult(
                output={"overdue": overdue, "count": len(overdue)}
            )
        if action == "mark_paid":
            iid_raw = task.input.get("invoice_id")
            iid_lookup = iid_raw if isinstance(iid_raw, str) else None
            inv = _INVOICES.get(iid_lookup) if iid_lookup else None
            if not inv:
                return AgentResult(error=f"invoice not found: {iid_lookup}")
            inv["status"] = "PAID"
            _INVOICES.put(iid_lookup, inv)
            call_tool(
                ctx,
                "crm",
                "activity.record",
                {"type": "invoice.paid", "invoice_id": iid_lookup},
            )
            return AgentResult(output={"invoice": inv, "ok": True, "confirmed": True})
        if action == "list_open":
            open_invs = [
                i for i in _invoices_for(ws) if i.get("status") != "PAID"
            ]
            return AgentResult(
                output={"invoices": open_invs, "count": len(open_invs)}
            )
        if action == "prepare_quotation":
            return self._prepare_quotation(task, ctx)
        return AgentResult(error=f"unknown finance action: {action}")

    # -- Draft quotations (never a final quote, invoice, payment or send) --

    @staticmethod
    def _parse_qty(raw: Any) -> tuple[float | None, str | None]:
        """Extract (quantity, unit) from a number or a '50kg' style string."""
        if isinstance(raw, bool):
            return None, None
        if isinstance(raw, (int, float)):
            return (float(raw), None) if raw > 0 else (None, None)
        if isinstance(raw, str):
            m = _QTY_RE.search(raw.replace(",", ""))
            if m:
                try:
                    qty = float(m.group(1))
                except ValueError:
                    return None, None
                if qty <= 0:
                    return None, None
                unit = (m.group(2) or "").strip()[:20] or None
                return qty, unit
        return None, None

    @classmethod
    def _coerce_items(cls, raw: Any) -> list[dict[str, Any]]:
        """Normalize task input items into product/qty/unit/spec stubs.

        Never invents: quantity/unit/spec stay None unless explicitly given.
        """
        if isinstance(raw, dict):
            raw = [raw]
        if isinstance(raw, str):
            raw = [{"product": raw}]
        items: list[dict[str, Any]] = []
        for entry in (raw or [])[:_QUOTATION_ITEM_LIMIT]:
            if isinstance(entry, str):
                entry = {"product": entry}
            if not isinstance(entry, dict):
                continue
            product = str(entry.get("product") or entry.get("name") or "").strip()
            if not product:
                continue
            qty, unit = cls._parse_qty(entry.get("quantity"))
            if not unit:
                unit = str(entry.get("unit") or "").strip()[:20] or None
            spec = str(entry.get("spec") or entry.get("specification") or "").strip()
            items.append({
                "product": product[:120],
                "quantity": qty,
                "unit": unit,
                "spec": spec[:300] or None,
                "source": "task input",
            })
        return items

    @classmethod
    def _items_from_answer(cls, answer: str) -> list[dict[str, Any]]:
        """Parse the owner's free-text clarification reply into item stubs.

        Quantities come ONLY from numbers the owner typed; everything else
        stays unresolved. Split on newlines/semicolons (not commas — product
        names may contain them).
        """
        items: list[dict[str, Any]] = []
        for frag in re.split(r"[\n;]+", answer):
            frag = frag.strip().strip("-•* ").strip()
            if not frag:
                continue
            qty, unit = cls._parse_qty(frag)
            items.append({
                "product": frag[:120],
                "quantity": qty,
                "unit": unit,
                "spec": None,
                "source": "owner reply",
            })
            if len(items) >= _QUOTATION_ITEM_LIMIT:
                break
        return items

    @staticmethod
    def _catalogue_price(ctx: AgentContext, product: str) -> tuple[str | None, str | None]:
        """Illustrative unit price from the workspace knowledge vault.

        Returns (price_text, source_document) or (None, None). Only
        currency-marked amounts (₹/Rs/INR) count, and the snippet must
        mention the product — bare numbers are never treated as prices.
        Tenant-scoped: the index only searches this workspace's documents.
        """
        try:
            from app.rag.index import get_index

            hits = get_index().search(
                principal=ctx.principal, query=f"{product} price rate", top_k=3
            )
        except Exception:
            return None, None
        tokens = {t.lower() for t in re.findall(r"[A-Za-z0-9]+", product) if len(t) > 2}
        for hit in hits:
            snippet = str(hit.get("snippet") or "")
            low = snippet.lower()
            if tokens and not any(tok in low for tok in tokens):
                continue
            m = _PRICE_RE.search(snippet)
            if m:
                return m.group(0).strip(), str(hit.get("name") or "catalogue")
        return None, None

    def _prepare_quotation(self, task: AgentTask, ctx: AgentContext) -> AgentResult:
        """Build and store a clearly-labelled quotation DRAFT.

        Rules (no fabrication, ever):
        - No customer AND no items -> NEEDS_INPUT (task goes WAITING_INPUT),
          it does not guess either.
        - Quantities/specs/prices only from explicit input or the workspace
          catalogue; everything missing is listed in `unresolved_fields`.
        - No taxes, discounts, stock or delivery commitments are added.
        - No invoice is issued, no payment recorded, nothing sent externally.
        """
        from app.docs_gen.proposals import create as create_proposal
        from app.models.orm import Lead

        ws = ctx.principal.workspace_id
        inp = task.input or {}
        customer = str(inp.get("customer") or "").strip()
        lead = None
        lead_id = str(inp.get("lead_id") or "").strip()
        if lead_id:
            lead = ctx.db.get(Lead, lead_id)
            if not lead or lead.company_id != ws:
                return AgentResult(error="lead not found")
            customer = customer or (lead.company_name or "")

        items = self._coerce_items(inp.get("items"))
        answer = str(inp.get("_answer") or "").strip()
        if answer and not items:
            items = self._items_from_answer(answer)
        owner_note = answer[:300] if (answer and self._coerce_items(inp.get("items"))) else None

        if not customer and not items:
            return AgentResult(
                needs_input={
                    "question": ("Quotation kiske liye aur kin products ke "
                                 "liye banau? Customer ka naam aur products "
                                 "(quantity ke saath) batao — bina iske main "
                                 "andaza nahi lagaunga."),
                    "field": "_answer",
                },
                output={"draft": False, "reason": "missing customer and items"},
            )

        unresolved: list[str] = []
        if not customer:
            unresolved.append("customer (not specified)")
        if not items:
            unresolved.append("items (none provided — add products to quote)")
        body: list[str] = [
            f"# Quotation DRAFT for {customer or 'UNSPECIFIED CUSTOMER'}",
            "",
            "**DRAFT — NOT A FINAL QUOTATION.** Every line marked TBD must be "
            "confirmed with the customer before finalising. Nothing here has "
            "been sent to anyone.",
            "",
        ]
        if owner_note:
            body += [f"Owner note: {owner_note}", ""]
        indicative_total: float | None = 0.0
        total_ok = bool(items)
        for i, it in enumerate(items):
            price_text, source = self._catalogue_price(ctx, it["product"])
            qty_txt = (f"{it['quantity']:g} {it['unit'] or ''}".strip()
                       if it["quantity"] is not None else "TBD")
            if it["quantity"] is None:
                unresolved.append(f"items[{i}].quantity ({it['product']})")
            spec_txt = it["spec"] or "TBD"
            if not it["spec"]:
                unresolved.append(f"items[{i}].spec ({it['product']})")
            if price_text:
                price_txt = (f"{price_text} (illustrative — from '{source}', "
                             "verify before finalising)")
            else:
                price_txt = "TBD (not found in catalogue)"
                unresolved.append(f"items[{i}].unit_price ({it['product']})")
            body.append(f"- **{it['product']}** — Qty: {qty_txt}; Spec: {spec_txt}; "
                        f"Illustrative unit price: {price_txt}")
            if it["quantity"] is not None and price_text:
                try:
                    amt = float(re.sub(r"[^\d.]", "", price_text))
                    indicative_total = (indicative_total or 0.0) + it["quantity"] * amt
                except ValueError:
                    total_ok = False
            else:
                total_ok = False
        body += [
            "",
            ("INDICATIVE TOTAL: "
             f"{indicative_total:,.2f} (quantity x illustrative prices only)"
             if total_ok and indicative_total else
             "Total: TBD (cannot total until every line has quantity + price)"),
            "",
            "No taxes, discounts, stock availability, or delivery commitments "
            "are included — confirm all of these separately before issuing a "
            "final quotation. No invoice issued. No payment recorded. Nothing "
            "sent to the customer.",
        ]
        doc = create_proposal(
            ctx.db, company_id=ws, kind="quotation",
            title=f"Quotation DRAFT — {customer or 'unspecified customer'}",
            context={"company_name": customer or "Unspecified customer",
                     "summary": "\n".join(body)},
            lead_id=lead.id if lead else None, actor="finance",
        )
        doc.meta = {**(doc.meta or {}), "draft": True,
                    "illustrative_prices": True,
                    "unresolved_fields": unresolved}
        ctx.db.commit()
        return AgentResult(output={
            "proposal_id": doc.id, "kind": "quotation", "status": "draft",
            "customer": customer or None,
            "items": len(items), "unresolved_fields": unresolved,
            "indicative_total": indicative_total if total_ok else None,
            "sent": False, "invoiced": False, "payment_recorded": False,
        })


register(FinanceAgent())
