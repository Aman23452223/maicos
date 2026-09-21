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
            # Legacy demo path preserved; new path uses DB when lead_id given.
            lead_id = task.input.get("lead_id")
            if lead_id:
                try:
                    from app.leads.service import qualify_lead
                except Exception as exc:
                    return AgentResult(error=f"qualification unavailable: {exc}")
                out = qualify_lead(
                    ctx.db, company_id=ctx.principal.workspace_id,
                    lead_id=str(lead_id), actor="sales_crm",
                    threshold=int(task.input.get("threshold", 60)),
                )
                if not out.get("ok"):
                    return AgentResult(error=out.get("error") or "qualify failed")
                ctx.db.commit()
                return AgentResult(output=out)
            return AgentResult(
                output={
                    "score": task.input.get("score", 50),
                    "tier": "high" if task.input.get("score", 0) >= 70 else "standard",
                    "note": "demo fallback: pass lead_id for real DB scoring",
                }
            )
        if action in ("discover", "enrich", "deduplicate", "qualify", "score",
                      "crm", "select_qualified", "schedule_followups", "convert",
                      "import", "report"):
            try:
                return self._lifecycle(task, ctx)
            except ValueError as exc:
                return AgentResult(error=str(exc))
            except Exception as exc:
                return AgentResult(error=f"sales lifecycle failed: {exc}")
        return AgentResult(error=f"unknown sales action: {action}")

    def _lifecycle(self, task: AgentTask, ctx: AgentContext) -> AgentResult:
        from app.leads.providers import Prospect, get as get_provider
        from app.leads.service import (
            enrich_lead,
            import_prospects,
            qualify_lead,
        )

        ws = ctx.principal.workspace_id
        action = task.input.get("action")
        if action == "discover":
            provider = str(task.input.get("provider", "search"))
            try:
                p = get_provider(provider)
            except KeyError:
                return AgentResult(error=f"unknown provider: {provider}")
            res = p.discover(str(task.input.get("objective") or task.description or ""),
                             limit=int(task.input.get("limit", 20)))
            # Never fake: surface NOT_CONFIGURED honestly
            return AgentResult(output={"status": res.status, "message": res.message,
                                       "count": len(res.prospects)})
        if action == "import":
            raw = task.input.get("prospects") or []
            prospects = [Prospect(**r) if isinstance(r, dict) else r for r in raw]
            out = import_prospects(ctx.db, company_id=ws, prospects=prospects,
                                   actor="sales_crm")
            ctx.db.commit()
            return AgentResult(output=out)
        if action in ("enrich",):
            lid = str(task.input.get("lead_id", ""))
            out = enrich_lead(ctx.db, company_id=ws, lead_id=lid, actor="sales_crm")
            if not out.get("ok"):
                return AgentResult(error=out.get("error") or "enrich failed")
            ctx.db.commit()
            return AgentResult(output=out)
        if action in ("qualify", "score", "deduplicate"):
            lid = str(task.input.get("lead_id", ""))
            out = qualify_lead(ctx.db, company_id=ws, lead_id=lid, actor="sales_crm",
                               threshold=int(task.input.get("threshold", 60)))
            if not out.get("ok"):
                return AgentResult(error=out.get("error") or "qualify failed")
            ctx.db.commit()
            return AgentResult(output=out)
        if action == "crm":
            # Convert all QUALIFIED leads without contact yet (bounded)
            from app.crm.providers import convert_lead_to_contact
            from app.models.orm import Lead, LeadStatus

            rows = ctx.db.query(Lead).filter(
                Lead.company_id == ws, Lead.status == LeadStatus.QUALIFIED).limit(20).all()
            done, failed = 0, 0
            for lead in rows:
                if lead.converted_contact_id:
                    continue
                r = convert_lead_to_contact(ctx.db, company_id=ws, lead_id=lead.id)
                if r.get("ok"):
                    done += 1
                else:
                    failed += 1
            ctx.db.commit()
            return AgentResult(output={"converted": done, "failed": failed})
        if action == "select_qualified":
            from app.models.orm import Lead, LeadStatus

            rows = ctx.db.query(Lead).filter(
                Lead.company_id == ws, Lead.status == LeadStatus.QUALIFIED).limit(50).all()
            return AgentResult(output={"leads": [
                {"id": l.id, "company_name": l.company_name, "email": l.email,
                 "score": l.score} for l in rows], "count": len(rows)})
        if action == "schedule_followups":
            from app.scheduling.followups import schedule_sequence

            lid = str(task.input.get("lead_id") or "")
            if lid:
                out = schedule_sequence(ctx.db, company_id=ws, lead_id=lid)
                ctx.db.commit()
                return AgentResult(output=out)
            from app.models.orm import Lead, LeadStatus

            rows = ctx.db.query(Lead).filter(
                Lead.company_id == ws, Lead.status.in_(
                    [LeadStatus.QUALIFIED, LeadStatus.CONTACTED])).limit(20).all()
            total = 0
            for lead in rows:
                r = schedule_sequence(ctx.db, company_id=ws, lead_id=lead.id)
                total += r.get("created", 0)
            ctx.db.commit()
            return AgentResult(output={"sequences_created": total})
        if action == "convert":
            from app.crm.providers import convert_lead_to_contact

            lid = str(task.input.get("lead_id", ""))
            out = convert_lead_to_contact(ctx.db, company_id=ws, lead_id=lid)
            if not out.get("ok"):
                return AgentResult(error=out.get("error") or "convert failed")
            ctx.db.commit()
            return AgentResult(output=out)
        if action == "report":
            from app.analytics.metrics import funnel
            return AgentResult(output=funnel(ctx.db, company_id=ws))
        return AgentResult(error=f"unknown lifecycle action: {action}")


register(SalesCRMAgent())

