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
