"""Sales / CRM Agent (PRD §6.1, §7)."""
from __future__ import annotations

from typing import ClassVar

from app.agents.base import AgentContext, AgentResult, AgentTask
from app.agents.registry import register
from app.agents.runtime import call_tool

# Enrichment does a live website fetch per lead (~15s timeout each), so the
# batch size is bounded to keep a single workflow run predictable.
ENRICH_BATCH_LIMIT = 10


def _score_row(db, ws, lead, threshold: int, actor: str = "sales_crm") -> dict | None:
    """Score one lead; return the honest outcome entry (None on failure).

    The entry reports the status the lead actually holds now — callers
    must not relabel "scored" as "qualified".
    """
    from app.leads.service import qualify_lead

    before = lead.status.value if hasattr(lead.status, "value") else str(lead.status)
    r = qualify_lead(db, company_id=ws, lead_id=lead.id,
                     actor=actor, threshold=threshold)
    if not r.get("ok"):
        return None
    from app.leads.service import lead_quality_flag

    entry = {"lead_id": lead.id, "lead_name": lead.company_name,
             "score": r.get("score"), "status": r.get("status"),
             "previous_status": before,
             "reasons": r.get("reasons") or {}}
    flag = lead_quality_flag(lead)
    if flag is not None:
        entry["quality_flag"] = flag
    if r.get("review_flag") is not None:
        entry["review_flag"] = r.get("review_flag")
    return entry


def _summarize_scoring(entries: list[dict]) -> dict:
    """Honest roll-up: scored vs actually-attained statuses."""
    became: dict[str, int] = {}
    for e in entries:
        became[e["status"]] = became.get(e["status"], 0) + 1
    return {"scored": len(entries), "became": became,
            "became_qualified": became.get("QUALIFIED", 0),
            "leads": entries[:50]}


def _duplicate_groups(db, ws: str, limit: int = 50) -> list[dict]:
    """Name/domain collisions worth a human look. Reported only —
    nothing is merged or deleted automatically."""
    from collections import defaultdict

    from app.models.orm import Lead

    rows = db.query(Lead).filter(Lead.company_id == ws).limit(200).all()
    groups: dict[str, list] = defaultdict(list)
    for lead in rows:
        key = (lead.normalized_name or "").strip()
        if key:
            groups[f"name:{key}"].append(lead)
        dom = (lead.domain or "").strip().lower()
        if dom:
            groups[f"domain:{dom}"].append(lead)
    out = []
    for key, members in groups.items():
        if len(members) > 1:
            out.append({"key": key, "count": len(members),
                        "lead_names": [m.company_name for m in members[:5]],
                        "lead_ids": [m.id for m in members[:5]]})
        if len(out) >= limit:
            break
    return out


def _followup_ineligibility(lead, status: str) -> str:
    """Why this lead gets no follow-up sequence (honest, specific)."""
    score = int(lead.score or 0)
    if getattr(lead, "opted_out", False):
        return "opted out of contact"
    if status == "DISQUALIFIED":
        return f"disqualified (score {score}, needs 60+ to qualify)"
    if status == "NEW":
        return "not yet qualified — run qualification first"
    if status == "NURTURE":
        return (f"nurture band (score {score}) — below the follow-up bar "
                f"(QUALIFIED or CONTACTED)")
    if status in ("RESPONDED", "MEETING", "PROPOSAL", "WON", "LOST"):
        return f"already past follow-ups (status {status})"
    return f"status {status} is not follow-up eligible"


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
        if action in ("discover", "discover_creators", "enrich", "deduplicate",
                      "qualify", "score", "crm", "select_qualified",
                      "schedule_followups", "convert", "import", "report",
                      "qualify_batch"):
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
            if not res.ok:
                # Never fake: surface NOT_CONFIGURED honestly
                return AgentResult(output={"status": res.status, "message": res.message,
                                           "count": 0})
            out = {"status": res.status, "message": res.message,
                   "count": len(res.prospects)}
            if task.input.get("auto_import"):
                imp = import_prospects(ctx.db, company_id=ws,
                                       prospects=res.prospects, actor="sales_crm")
                ctx.db.commit()
                out["imported"] = imp
            else:
                out["prospects"] = [vars(x) for x in res.prospects[:20]]
            return AgentResult(output=out)
        if action == "qualify_batch":
            # Enrich (website -> email) then qualify every NEW lead.
            from app.models.orm import Lead, LeadStatus

            new_leads = ctx.db.query(Lead).filter(
                Lead.company_id == ws, Lead.status == LeadStatus.NEW).limit(50).all()
            if not new_leads:
                return AgentResult(output={"scored": 0, "became_qualified": 0,
                                            "considered": 0,
                                            "message": "no NEW leads to qualify"})
            done = 0
            for lead in new_leads[:10]:
                if lead.website:
                    try:
                        enrich_lead(ctx.db, company_id=ws, lead_id=lead.id,
                                    actor="sales_crm")
                    except Exception:
                        pass
            entries: list[dict] = []
            failed = 0
            threshold = int(task.input.get("threshold", 60))
            for lead in new_leads:
                try:
                    entry = _score_row(ctx.db, ws, lead, threshold)
                    if entry is None:
                        failed += 1
                    else:
                        entries.append(entry)
                except Exception:
                    failed += 1
                    continue
            ctx.db.commit()
            out = _summarize_scoring(entries)
            from sqlalchemy import func as _func

            _settled = dict(
                ctx.db.query(Lead.status, _func.count(Lead.id))
                .filter(Lead.company_id == ws,
                        Lead.status != LeadStatus.NEW)
                .group_by(Lead.status).all()
            )
            out.update({"failed": failed, "batch": True,
                        "considered": len(new_leads),
                        "skipped_settled": {
                            (s.value if hasattr(s, "value") else str(s)): c
                            for s, c in _settled.items()}})
            return AgentResult(output=out)
        if action == "discover_creators":
            from app.leads.creators import discover as discover_creators

            res = discover_creators(
                str(task.input.get("objective") or task.description or ""),
                limit=int(task.input.get("limit", 15)))
            if not res.get("ok"):
                return AgentResult(output={"status": res.get("status"),
                                           "message": res.get("message"), "count": 0})
            creators = res["creators"]
            out = import_prospects(ctx.db, company_id=ws, prospects=creators,
                                   actor="sales_crm")
            ctx.db.commit()
            return AgentResult(output={"status": "OK", "count": len(creators),
                                       "imported": out})
        if action == "import":
            raw = task.input.get("prospects") or []
            prospects = [Prospect(**r) if isinstance(r, dict) else r for r in raw]
            out = import_prospects(ctx.db, company_id=ws, prospects=prospects,
                                   actor="sales_crm")
            ctx.db.commit()
            return AgentResult(output=out)
        if action in ("enrich",):
            lid = str(task.input.get("lead_id", ""))
            if not lid:
                # Stage-level run (no single lead in scope): enrich every NEW
                # lead in the workspace instead of failing the whole workflow.
                from app.models.orm import Lead, LeadStatus

                rows = ctx.db.query(Lead).filter(
                    Lead.company_id == ws, Lead.status == LeadStatus.NEW
                ).limit(10).all()
                done, failed = 0, 0
                for lead in rows:
                    r = enrich_lead(ctx.db, company_id=ws, lead_id=lead.id,
                                    actor="sales_crm")
                    if r.get("ok"):
                        done += 1
                    else:
                        failed += 1
                ctx.db.commit()
                return AgentResult(output={"enriched": done, "failed": failed,
                                           "batch": True})
            out = enrich_lead(ctx.db, company_id=ws, lead_id=lid, actor="sales_crm")
            if not out.get("ok"):
                return AgentResult(error=out.get("error") or "enrich failed")
            ctx.db.commit()
            return AgentResult(output=out)
        if action in ("qualify", "score", "deduplicate"):
            lid = str(task.input.get("lead_id", ""))
            if not lid:
                # Stage-level run: score every lead still in play.
                from app.models.orm import Lead, LeadStatus

                rows = ctx.db.query(Lead).filter(
                    Lead.company_id == ws,
                    Lead.status.notin_([LeadStatus.DISQUALIFIED, LeadStatus.LOST]),
                ).limit(50).all()
                entries: list[dict] = []
                failed = 0
                threshold = int(task.input.get("threshold", 60))
                for lead in rows:
                    entry = _score_row(ctx.db, ws, lead, threshold)
                    if entry is None:
                        failed += 1
                    else:
                        entries.append(entry)
                ctx.db.commit()
                out = _summarize_scoring(entries)
                from sqlalchemy import func as _func2

                _excluded = dict(
                    ctx.db.query(Lead.status, _func2.count(Lead.id))
                    .filter(Lead.company_id == ws,
                            Lead.status.in_([LeadStatus.DISQUALIFIED,
                                             LeadStatus.LOST]))
                    .group_by(Lead.status).all()
                )
                out.update({"failed": failed, "batch": True,
                            "action": action,
                            "considered": len(rows),
                            "excluded_settled": {
                                (s.value if hasattr(s, "value") else str(s)): c
                                for s, c in _excluded.items()}})
                if action == "deduplicate":
                    out["possible_duplicate_groups"] = \
                        _duplicate_groups(ctx.db, ws)
                return AgentResult(output=out)
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
            from app.scheduling.followups import PRIORITY_RULE, lead_priority

            if not rows:
                # No eligible leads is an honest empty — explain it instead
                # of returning a bare zero: status breakdown plus per-lead
                # reasons so the report shows WHY nothing was scheduled.
                from sqlalchemy import func as _func

                counts = dict(
                    ctx.db.query(Lead.status, _func.count(Lead.id))
                    .filter(Lead.company_id == ws)
                    .group_by(Lead.status).all()
                )
                breakdown = {(s.value if hasattr(s, "value") else str(s)): c
                             for s, c in counts.items()}
                skipped = []
                for cand in (ctx.db.query(Lead)
                             .filter(Lead.company_id == ws)
                             .order_by(Lead.score.desc()).limit(20).all()):
                    status = (cand.status.value if hasattr(cand.status, "value")
                              else str(cand.status))
                    skipped.append({
                        "lead_id": cand.id, "lead_name": cand.company_name,
                        "status": status, "score": int(cand.score or 0),
                        "reason": _followup_ineligibility(cand, status),
                    })
                ctx.db.commit()
                return AgentResult(output={
                    "sequences_created": 0, "leads": [], "eligible": 0,
                    "reason": ("No QUALIFIED or CONTACTED leads to schedule. "
                               "Qualify leads first (score 60+ qualifies)."),
                    "lead_status_breakdown": breakdown,
                    "ineligible_leads": skipped})
            total = 0
            items: list[dict] = []
            for lead in rows:
                r = schedule_sequence(ctx.db, company_id=ws, lead_id=lead.id)
                total += r.get("created", 0)
                items.append({
                    "lead_id": lead.id, "lead_name": lead.company_name,
                    "lead_status": (lead.status.value
                                    if hasattr(lead.status, "value") else str(lead.status)),
                    "lead_score": int(lead.score or 0),
                    "priority": lead_priority(lead), "priority_rule": PRIORITY_RULE,
                    "created": r.get("created", 0),
                    "already_scheduled": r.get("already_scheduled", 0),
                    "created_followup_ids": r.get("created_followup_ids", []),
                    "due_dates": [f.get("due_at") for f in r.get("followups", [])],
                })
            eligible_ids = {lead.id for lead in rows}
            skipped = []
            for cand in (ctx.db.query(Lead)
                         .filter(Lead.company_id == ws,
                                 Lead.id.notin_(eligible_ids))
                         .order_by(Lead.score.desc()).limit(20).all()):
                status = (cand.status.value if hasattr(cand.status, "value")
                          else str(cand.status))
                skipped.append({
                    "lead_id": cand.id, "lead_name": cand.company_name,
                    "status": status, "score": int(cand.score or 0),
                    "reason": _followup_ineligibility(cand, status),
                })
            ctx.db.commit()
            return AgentResult(output={"sequences_created": total, "leads": items,
                                       "eligible": len(rows), "skipped": skipped})
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

