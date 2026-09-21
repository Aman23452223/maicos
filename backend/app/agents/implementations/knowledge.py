"""Knowledge Agent (PRD §15, §22) - permission-scoped RAG."""
from __future__ import annotations

from typing import ClassVar

from app.agents.base import AgentContext, AgentResult, AgentTask
from app.agents.registry import register
from app.rag.index import get_index


class KnowledgeAgent:
    name = "knowledge"
    description = "Searches company documents, SOPs and policies with permission scoping."
    allowed_tools: ClassVar[list[str]] = []

    def run(self, task: AgentTask, ctx: AgentContext) -> AgentResult:
        action = (task.input.get("action") or "").strip()
        if action == "analyze_website":
            url = (task.input.get("url") or "").strip()
            if not url:
                import re

                m = re.search(
                    r"https?://[^\s\"']+",
                    f"{task.input.get('objective', '')} {task.description}",
                )
                url = m.group(0) if m else ""
            if not url:
                return AgentResult(error="analyze_website requires a URL")
            try:
                from app.intel.service import analyze_website
            except Exception as exc:
                return AgentResult(error=f"website intelligence unavailable: {exc}")
            try:
                out = analyze_website(
                    ctx.db, company_id=ctx.principal.workspace_id, url=url,
                    actor=ctx.principal.user_id, use_llm=False,
                )
            except ValueError as exc:
                return AgentResult(error=str(exc))
            except Exception as exc:
                return AgentResult(error=f"website analysis failed: {exc}")
            if not out.get("ok"):
                return AgentResult(error=out.get("error") or "fetch failed")
            ctx.db.commit()
            return AgentResult(output={"website_url": url,
                                       "profile": out.get("profile", {}),
                                       "document_id": out.get("document_id"),
                                       "pages_crawled": out.get("pages_crawled", 0)})
        query = (task.input.get("query") or task.description or "").strip()
        if not query:
            return AgentResult(error="knowledge agent requires a query")
        results = get_index().search(principal=ctx.principal, query=query)
        return AgentResult(
            output={
                "query": query,
                "results": results,
                "count": len(results),
            }
        )


register(KnowledgeAgent())
