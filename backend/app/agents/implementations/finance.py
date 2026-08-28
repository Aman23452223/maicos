"""Finance Agent (PRD §8).

All finance state is persisted via the CRM `activity` stream (which is
file-backed) and a dedicated finance store. Invoice preparation is
always approval-gated per §14.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

from app.agents.base import AgentContext, AgentResult, AgentTask
from app.agents.registry import register
from app.agents.runtime import call_tool
from app.integrations.store import JsonStore, stores_root

_INVOICES = JsonStore[dict[str, Any]](stores_root() / "finance.invoices.json")


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
                return AgentResult(error=f"invoice not found: {iid}")
            inv["status"] = "PAID"
            _INVOICES.put(iid, inv)
            call_tool(
                ctx,
                "crm",
                "activity.record",
                {"type": "invoice.paid", "invoice_id": iid},
            )
            return AgentResult(output={"invoice": inv, "ok": True, "confirmed": True})
        if action == "list_open":
            open_invs = [
                i for i in _invoices_for(ws) if i.get("status") != "PAID"
            ]
            return AgentResult(
                output={"invoices": open_invs, "count": len(open_invs)}
            )
        return AgentResult(error=f"unknown finance action: {action}")


register(FinanceAgent())
