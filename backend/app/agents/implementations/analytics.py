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
            return AgentResult(
                output={
                    "summary": task.input.get(
                        "summary",
                        "Sales up 12%. Two invoices overdue. One project blocked.",
                    ),
                    "needs_attention": task.input.get("needs_attention", []),
                }
            )
        return AgentResult(error=f"unknown analytics action: {action}")


register(AnalyticsAgent())
