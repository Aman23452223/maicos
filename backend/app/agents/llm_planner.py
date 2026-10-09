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
Each task MUST also carry an "action" inside "input", chosen ONLY from the
allowed actions of its agent below. Never invent other actions — a task with
an unsupported action is skipped, not executed.

Allowed actions per agent:
- ai_manager: needs no action (it always returns a sub-plan)
- knowledge: analyze_website (needs "url" in input), otherwise omit action
  and give "query" to search the company knowledge vault
- sales_crm: discover (give "objective", "limit", "auto_import": true to save
  leads), import, enrich, qualify, score, deduplicate, qualify_batch,
  discover_creators, crm, select_qualified, schedule_followups, convert,
  create_contact, company.upsert, create_deal, qualify_lead
- project_ops: create_project, create_doc, list_overdue, list_projects
- communication: draft, send, bulk_send, send_digest
- finance: prepare_invoice (needs customer + amount; approval-gated),
  prepare_quotation (needs customer and/or items; draft only, never final),
  create_invoice (approval replay only — never emit directly),
  find_overdue, mark_paid, list_open
- hr: triage_hiring, start_hiring, add_candidate, list_candidates,
  advance_stage, create_onboarding_checklist
- marketing: draft_content, plan_campaign, analyze
- customer_support: classify, open_ticket, draft_reply, list_open, escalate
- analytics: funnel, pipeline, operations, summarize_context, summarize_profile,
  ceo_brief, detect_anomaly
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
