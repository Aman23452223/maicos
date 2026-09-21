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
