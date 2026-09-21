"""Reusable generic workflow templates (Phase 27). Configurable stages."""
from __future__ import annotations

from typing import Any


def lead_generation(stages: list[str] | None = None) -> dict[str, Any]:
    stages = stages or ["discover", "enrich", "deduplicate", "qualify", "score", "crm", "report"]
    tasks: list[dict] = []
    prev: str | None = None
    agent_for = {"discover": "sales_crm", "enrich": "sales_crm",
                 "deduplicate": "sales_crm", "qualify": "sales_crm",
                 "score": "sales_crm", "crm": "sales_crm", "report": "analytics"}
    for i, s in enumerate(stages):
        tid = f"{s}_{i}"
        tasks.append({"id": tid, "agent": agent_for.get(s, "sales_crm"),
                      "title": s.replace("_", " ").title(),
                      "description": f"Stage: {s}",
                      "input": {"action": s}, "depends_on": [prev] if prev else []})
        prev = tid
    return {"intent": "lead_generation", "tasks": tasks}


def lead_outreach() -> dict[str, Any]:
    return {"intent": "lead_outreach", "tasks": [
        {"id": "select", "agent": "sales_crm", "title": "Select qualified leads",
         "description": "Query QUALIFIED leads", "input": {"action": "select_qualified"},
         "depends_on": []},
        {"id": "personalize", "agent": "communication", "title": "Personalize outreach",
         "description": "Draft personalized messages", "input": {"action": "draft"},
         "depends_on": ["select"]},
        {"id": "send", "agent": "communication", "title": "Send outreach",
         "description": "Approval-gated send", "input": {"action": "send"},
         "depends_on": ["personalize"]},
        {"id": "followups", "agent": "sales_crm", "title": "Schedule follow-ups",
         "description": "Create follow-up sequence", "input": {"action": "schedule_followups"},
         "depends_on": ["send"]},
    ]}


def customer_onboarding() -> dict[str, Any]:
    return {"intent": "customer_onboarding", "tasks": [
        {"id": "convert", "agent": "sales_crm", "title": "Convert to customer",
         "description": "Create customer record", "input": {"action": "convert"},
         "depends_on": []},
        {"id": "project", "agent": "project_ops", "title": "Create project",
         "description": "Create delivery project", "input": {"action": "create_project"},
         "depends_on": ["convert"]},
        {"id": "docs", "agent": "knowledge", "title": "Collect documents",
         "description": "Gather onboarding docs", "input": {"query": "onboarding"},
         "depends_on": ["project"]},
    ]}


def weekly_review() -> dict[str, Any]:
    return {"intent": "weekly_review", "tasks": [
        {"id": "metrics", "agent": "analytics", "title": "Compute metrics",
         "description": "Real DB metrics", "input": {"action": "funnel"},
         "depends_on": []},
    ]}


TEMPLATES = {"lead_generation": lead_generation, "lead_outreach": lead_outreach,
             "customer_onboarding": customer_onboarding, "weekly_review": weekly_review}
