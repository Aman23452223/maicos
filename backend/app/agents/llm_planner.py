"""LLM-driven planner hook (PRD §5, §11).

The deterministic `build_plan` in `ai_manager.py` is great for tests
and as a fallback. In production, this module asks the configured LLM
to produce a structured plan, then validates the result before handing
it to the workflow engine.
"""
from __future__ import annotations

import json
from typing import Any

from app.llm.gateway import LLMRequest, get_llm

_PLAN_SCHEMA_HINT = """\
Return a JSON object of the form:
{
  "intent": "<short-snake-case-name>",
  "tasks": [
    {
      "id": "<unique-within-plan>",
      "agent": "<agent-name>",
      "title": "<short>",
      "description": "<one line>",
      "input": {...},
      "depends_on": ["<other task id>"]
    }
  ]
}
Allowed agents: ai_manager, knowledge, sales_crm, project_ops, communication,
finance, hr, marketing, customer_support, analytics.
"""


def plan_with_llm(objective: str) -> dict[str, Any] | None:
    llm = get_llm()
    try:
        r = llm.complete(
            LLMRequest(
                system=(
                    "You are a workflow planner for a multi-agent company OS. "
                    "Decompose the user's business objective into a task DAG. "
                    "Only output valid JSON."
                ),
                user=f"Objective: {objective}\n\n{_PLAN_SCHEMA_HINT}",
                json_mode=True,
            )
        )
    except Exception:  # noqa: BLE001  (LLM/network/JSON failures all fall through)
        return None
    try:
        plan = json.loads(r.text)
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(plan, dict) or "tasks" not in plan:
        return None
    return plan
