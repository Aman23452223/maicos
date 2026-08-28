"""Sales / CRM Agent (PRD §6.1, §7)."""
from __future__ import annotations

from typing import ClassVar

from app.agents.base import AgentContext, AgentResult, AgentTask
from app.agents.registry import register
from app.agents.runtime import call_tool


class SalesCRMAgent:
    name = "sales_crm"
    description = "Qualifies leads, manages contacts and pipeline through the CRM."
    allowed_tools: ClassVar[list[str]] = [
        "crm.contact.create",
        "crm.contact.update",
        "crm.contact.get",
        "crm.company.upsert",
        "crm.deal.create",
        "crm.deal.update_stage",
        "crm.activity.record",
    ]

    def run(self, task: AgentTask, ctx: AgentContext) -> AgentResult:
        action = task.input.get("action", "create_contact")
        if action == "create_contact":
            company_from_upstream = (ctx.shared.get("company") or {}).get("company") or {}
            company_name = (
                task.input.get("company")
                or company_from_upstream.get("name")
            )
            res = call_tool(
                ctx,
                "crm",
                "contact.create",
                {
                    "name": task.input.get("name"),
                    "email": task.input.get("email"),
                    "company": company_name,
                    "company_id": company_from_upstream.get("id"),
                },
            )
            if not res["ok"]:
                return AgentResult(error=res.get("message") or "crm create failed")
            return AgentResult(output={"contact": res["data"]})
        if action == "company.upsert":
            res = call_tool(
                ctx,
                "crm",
                "company.upsert",
                {
                    "name": task.input.get("name"),
                    "domain": task.input.get("domain"),
                },
            )
            if not res["ok"]:
                return AgentResult(error=res.get("message") or "crm company upsert failed")
            return AgentResult(output={"company": res["data"]})
        if action == "create_deal":
            res = call_tool(
                ctx,
                "crm",
                "deal.create",
                {
                    "name": task.input.get("name", "New Deal"),
                    "amount": task.input.get("amount"),
                    "contact_id": task.input.get("contact_id"),
                },
            )
            if not res["ok"]:
                return AgentResult(error=res.get("message") or "crm deal create failed")
            return AgentResult(output={"deal": res["data"]})
        if action == "qualify_lead":
            return AgentResult(
                output={
                    "score": task.input.get("score", 50),
                    "tier": "high" if task.input.get("score", 0) >= 70 else "standard",
                }
            )
        return AgentResult(error=f"unknown sales action: {action}")


register(SalesCRMAgent())

