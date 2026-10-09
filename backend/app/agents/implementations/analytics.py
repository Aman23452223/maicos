"""Analytics Agent (PRD §16).

Computes KPIs and surfaces anomalies. The MVP is deterministic and
data-source agnostic; real implementations would query the data
warehouse or analytics store.
"""
from __future__ import annotations

import statistics
from typing import ClassVar

from app.agents.base import AgentContext, AgentResult, AgentTask
from app.agents.registry import register


class AnalyticsAgent:
    name = "analytics"
    description = "Computes KPIs, trends and anomalies over company data."
    allowed_tools: ClassVar[list[str]] = []

    def run(self, task: AgentTask, ctx: AgentContext) -> AgentResult:
        action = task.input.get("action", "summarize")
        if action == "summarize_context":
            # Summarize the task's REAL upstream outputs. The engine seeds
            # `shared` from this task's `depends_on` (keyed by upstream plan
            # ids), so read every entry — never a hardcoded key. An optional
            # `required_fields` list turns this into a missing-information
            # analysis: each field is checked against the evidence, verbatim.
            import json as _json

            focus = str(task.input.get("focus") or task.description or "").strip()
            required = task.input.get("required_fields") or []
            if isinstance(required, str):
                required = [required]
            required = [str(f).strip() for f in required if str(f).strip()][:20]

            upstream = [(k, v) for k, v in (ctx.shared or {}).items()
                        if k != "agent_name" and isinstance(v, dict) and v]
            if not upstream:
                return AgentResult(
                    error="no upstream outputs to summarize (check the task's depends_on)")
            snippets: list[str] = []
            for _key, out in upstream:
                for r in (out.get("results") or [])[:5]:
                    if isinstance(r, dict) and r.get("snippet"):
                        snippets.append(str(r["snippet"])[:300])
            evidence = "\n".join(
                _json.dumps(out, default=str)[:4000] for _key, out in upstream
            )[:12000]
            low = evidence.lower()
            missing: list[str] = []
            present: dict[str, str] = {}
            for field in required:
                idx = low.find(field.lower())
                if idx < 0:
                    missing.append(field)
                else:
                    start = max(0, idx - 60)
                    present[field] = evidence[start:idx + len(field) + 60].strip()
            query = ""
            for _key, out in upstream:
                if out.get("query"):
                    query = str(out["query"])[:200]
                    break
            return AgentResult(output={
                "focus": focus,
                "query": query,
                "brief": " | ".join(snippets[:5])[:2000],
                "sources": len(snippets),
                "upstream_tasks": len(upstream),
                "missing": missing,
                "present": present})
        if action == "summarize_profile":
            # Generic: summarize upstream analyze_site profile (no industry logic).
            upstream = ctx.shared.get("analyze_site") or {}
            profile = upstream.get("profile") or {}
            if not profile:
                return AgentResult(error="no upstream website profile to summarize")
            services = profile.get("services") or []
            return AgentResult(output={
                "website_url": upstream.get("website_url", ""),
                "company_name": profile.get("company_name", ""),
                "services": services[:10],
                "target_customers": profile.get("target_customer", ""),
                "geography": profile.get("geography", ""),
                "ctas": (profile.get("ctas") or [])[:10],
                "pages_crawled": upstream.get("pages_crawled", 0),
                "summary": (
                    f"{profile.get('company_name', 'Business')} offers "
                    f"{'; '.join(services[:3]) or 'listed services'} "
                    f"for {profile.get('target_customer', 'its audience')}"
                )[:1000],
            })
        if action in ("funnel", "pipeline", "operations", "report", "weekly_report"):
            try:
                from app.analytics.metrics import (
                    funnel as _funnel,
                    operations as _ops,
                    pipeline as _pipe,
                    weekly_report as _weekly,
                )
            except Exception as exc:
                return AgentResult(error=f"analytics store unavailable: {exc}")
            ws = ctx.principal.workspace_id
            if action == "funnel":
                return AgentResult(output=_funnel(ctx.db, company_id=ws))
            if action == "pipeline":
                return AgentResult(output=_pipe(ctx.db, company_id=ws))
            if action == "operations":
                return AgentResult(output=_ops(ctx.db, company_id=ws))
            return AgentResult(output=_weekly(ctx.db, company_id=ws))
        series: list[float] = task.input.get("series", []) or []
        if action == "summarize" and series:
            return AgentResult(
                output={
                    "count": len(series),
                    "mean": round(statistics.fmean(series), 3),
                    "stdev": round(statistics.pstdev(series), 3) if len(series) > 1 else 0.0,
                    "min": min(series),
                    "max": max(series),
                }
            )
        if action == "detect_anomaly" and series:
            mean = statistics.fmean(series)
            sd = statistics.pstdev(series) if len(series) > 1 else 0.0
            anomalies = [
                {"index": i, "value": v}
                for i, v in enumerate(series)
                if sd > 0 and abs(v - mean) > 2 * sd
            ]
            return AgentResult(output={"mean": mean, "stdev": sd, "anomalies": anomalies})
        if action == "ceo_brief":
            explicit = task.input.get("summary")
            if explicit and str(explicit).strip():
                return AgentResult(
                    output={
                        "summary": str(explicit)[:1000],
                        "needs_attention": task.input.get("needs_attention", []),
                        "source": "caller",
                    }
                )
            # No caller text: compose strictly from this workspace's real
            # records. Never fall back to example numbers.
            return self._real_ceo_brief(ctx)

    @staticmethod
    def _real_ceo_brief(ctx: AgentContext) -> AgentResult:
        """CEO brief computed only from verified workspace records.

        Every sentence below is backed by a DB/store count in this
        workspace. Empty areas are reported as empty — never filled
        with example figures.
        """
        from datetime import UTC, datetime

        from app.analytics.metrics import funnel as _funnel
        from app.analytics.metrics import operations as _ops
        from app.analytics.metrics import pipeline as _pipe

        ws = ctx.principal.workspace_id
        fun = _funnel(ctx.db, company_id=ws)
        pipe = _pipe(ctx.db, company_id=ws)
        ops = _ops(ctx.db, company_id=ws)

        try:
            from app.agents.implementations.finance import _invoices_for
            today = datetime.now(UTC)
            overdue = []
            for inv in _invoices_for(ws):
                if inv.get("status") == "PAID":
                    continue
                try:
                    due = datetime.fromisoformat(str(inv.get("due_at", "")))
                except ValueError:
                    continue
                if due < today:
                    overdue.append(inv)
        except Exception:
            overdue = []

        lines: list[str] = []
        needs: list[dict[str, str]] = []
        total = int(fun.get("leads_total", 0) or 0)
        if total:
            unit = "lead" if total == 1 else "leads"
            lines.append(
                f"{total} {unit} in CRM "
                f"({fun.get('contacted', 0)} contacted, "
                f"{fun.get('responded', 0)} responded, "
                f"{fun.get('meetings', 0)} in meetings, "
                f"{fun.get('won', 0)} won; "
                f"response rate {fun.get('response_rate', 0)}, "
                f"conversion {fun.get('conversion_rate', 0)}).")
        else:
            lines.append("No leads in CRM yet.")
        value = int(pipe.get("total_value", 0) or 0)
        if value:
            lines.append(f"Open pipeline value {value}.")
        else:
            lines.append("No open pipeline value recorded.")
        if overdue:
            names = ", ".join(
                str(i.get("customer") or "customer") for i in overdue[:5])
            lines.append(
                f"{len(overdue)} invoices overdue ({names}"
                f"{', …' if len(overdue) > 5 else ''}).")
            needs.append({"kind": "overdue_invoices",
                          "detail": f"{len(overdue)} overdue: {names}"})
        else:
            lines.append("No invoices overdue.")
        pending = int(ops.get("approvals_pending", 0) or 0)
        if pending:
            lines.append(f"{pending} approvals waiting for review.")
            needs.append({"kind": "approvals_pending",
                          "detail": f"{pending} approvals waiting"})
        stuck = int(ops.get("qualified_not_contacted", 0) or 0)
        if stuck:
            lines.append(f"{stuck} qualified leads never contacted.")
            needs.append({"kind": "stuck_leads",
                          "detail": f"{stuck} qualified, never contacted"})
        sched = int(ops.get("followups_scheduled", 0) or 0)
        if sched:
            lines.append(f"{sched} follow-ups scheduled.")
        return AgentResult(output={
            "summary": " ".join(lines)[:2000],
            "needs_attention": needs,
            "source": "actual",
            "metrics": {"funnel": fun, "pipeline": pipe, "operations": ops,
                        "overdue_invoices": len(overdue)},
        })
        return AgentResult(error=f"unknown analytics action: {action}")


register(AnalyticsAgent())
