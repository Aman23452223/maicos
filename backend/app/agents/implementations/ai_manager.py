"""AI Manager / Orchestrator (PRD §5).

The MVP manager is a deterministic planner that:
  1. Classifies the user objective into a workflow template.
  2. Generates a task DAG.
  3. Delegates tasks to specialized agents.
  4. Verifies results and reports.
"""
from __future__ import annotations

from typing import Any, ClassVar

from app.agents.base import AgentContext, AgentResult, AgentTask
from app.agents.registry import register
from app.llm.gateway import LLMRequest, get_llm

INTENTS = {
    "onboard_client": ["onboard", "new client", "new customer"],
    "meeting_prep": ["prepare", "meeting", "brief"],
    "create_project": ["launch", "create project", "new project"],
    "invoice_followup": ["overdue", "invoice", "payment reminder", "receivable"],
    "lead_followup": ["follow up", "follow-up", "inactive lead"],
}


def classify(objective: str) -> str:
    """Pick the best-matching intent by checking intents in order.

    More specific intents (invoice, project) are tried before the
    generic lead-followup so that "Handle overdue invoice follow-ups"
    routes to finance, not to a lead workflow.
    """
    text = objective.lower()
    for intent, keywords in INTENTS.items():
        if any(k in text for k in keywords):
            return intent
    return "generic"


def _plan_onboard_client(objective: str) -> dict[str, Any]:
    # Try to extract a contact name and email from the objective. The
    # LLM-driven planner will do this more reliably, but the
    # deterministic planner is the safe fallback used in the proof.
    import re

    email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", objective)
    email = email_match.group(0) if email_match else "[email protected]"

    name_match = re.search(r"contact\s+([A-Z][\w'.-]+(?:\s+[A-Z][\w'.-]+)*)", objective, re.IGNORECASE)
    if not name_match:
        # Try "with NAME" / "for NAME" / "by NAME" / "ABC Corp with John"
        name_match = re.search(
            r"(?:with|for|by|contact|lead)\s+([A-Z][\w'.-]+(?:\s+[A-Z][\w'.-]+)*)",
            objective,
        )
    contact_name = name_match.group(1) if name_match else "New Contact"

    return {
        "intent": "onboard_client",
        "tasks": [
            {
                "id": "company",
                "agent": "sales_crm",
                "title": "Upsert client company",
                "description": "Create or update the client company in CRM.",
                "input": {"action": "company.upsert", "name": _company_name(objective)},
                "depends_on": [],
            },
            {
                "id": "contact",
                "agent": "sales_crm",
                "title": "Create primary contact",
                "description": f"Create contact {contact_name} for the new client.",
                "input": {
                    "action": "create_contact",
                    "name": contact_name,
                    "email": email,
                },
                "depends_on": ["company"],
            },
            {
                "id": "project",
                "agent": "project_ops",
                "title": "Create onboarding project",
                "description": "Create the onboarding project and standard tasks.",
                "input": {
                    "action": "create_project",
                    "name": "Client Onboarding",
                    "subtasks": [
                        "Kickoff meeting",
                        "Documentation handover",
                        "Initial training",
                    ],
                },
                "depends_on": ["contact"],
            },
            {
                "id": "kickoff",
                "agent": "calendar",
                "title": "Schedule kickoff meeting",
                "description": "Schedule the kickoff meeting on the calendar.",
                "input": {
                    "action": "schedule",
                    "title": "Client kickoff",
                    "attendees": [email],
                },
                "depends_on": ["project"],
            },
            {
                "id": "welcome_email",
                "agent": "communication",
                "title": "Send welcome email",
                "description": f"Send a welcome message to {contact_name}.",
                "input": {
                    "action": "send",
                    "to": email,
                    "subject": "Welcome",
                    "body": f"Hi {contact_name}, welcome aboard. We are excited to get started.",
                },
                "depends_on": ["project"],
            },
        ],
    }


def _company_name(objective: str) -> str:
    """Extract a company name from a free-form onboarding objective.

    Looks for patterns like "onboard ABC", "ABC Inc", "client ACME".
    Falls back to a sensible default.
    """
    import re

    m = re.search(
        r"(?:onboard|onboarding)\s+(?:the\s+)?(?:new\s+)?(?:client\s+)?"
        r"([A-Z][\w&.'-]*(?:\s+[A-Z][\w&.'-]*){0,3})",
        objective,
    )
    if m:
        return m.group(1)
    m = re.search(
        r"client\s+([A-Z][\w&.'-]+(?:\s+[A-Z][\w&.'-]+){0,3})", objective
    )
    if m:
        return m.group(1)
    return "New Client"


def _plan_lead_followup(objective: str) -> dict[str, Any]:
    return {
        "intent": "lead_followup",
        "tasks": [
            {
                "id": "context",
                "agent": "knowledge",
                "title": "Retrieve lead context",
                "description": "Search for any context about the lead in knowledge base.",
                "input": {"query": objective},
                "depends_on": [],
            },
            {
                "id": "draft",
                "agent": "communication",
                "title": "Draft follow-up",
                "description": "Draft a personalized follow-up message.",
                "input": {"action": "draft", "subject": "Following up", "body": "Hi,"},
                "depends_on": ["context"],
            },
        ],
    }


def _plan_invoice_followup(objective: str) -> dict[str, Any]:
    """Find overdue invoices and request approval to send reminders."""
    return {
        "intent": "invoice_followup",
        "tasks": [
            {
                "id": "find_overdue",
                "agent": "finance",
                "title": "Find overdue invoices",
                "description": "List all invoices past their due date.",
                "input": {"action": "find_overdue"},
                "depends_on": [],
            },
            {
                "id": "draft_reminders",
                "agent": "communication",
                "title": "Draft reminder messages",
                "description": "Draft a friendly payment reminder for each overdue invoice.",
                "input": {
                    "action": "draft",
                    "subject": "Payment reminder",
                    "body": "Friendly reminder that invoice is past due.",
                },
                "depends_on": ["find_overdue"],
            },
        ],
    }


def _plan_generic(objective: str) -> dict[str, Any]:
    return {
        "intent": "generic",
        "tasks": [
            {
                "id": "search",
                "agent": "knowledge",
                "title": "Search company knowledge",
                "description": objective,
                "input": {"query": objective},
                "depends_on": [],
            }
        ],
    }


def build_plan(objective: str) -> dict[str, Any]:
    intent = classify(objective)
    if intent == "onboard_client":
        return _plan_onboard_client(objective)
    if intent == "lead_followup":
        return _plan_lead_followup(objective)
    if intent == "invoice_followup":
        return _plan_invoice_followup(objective)
    return _plan_generic(objective)


class AIManagerAgent:
    name = "ai_manager"
    description = "Central orchestrator. Plans and delegates to specialized agents."
    allowed_tools: ClassVar[list[str]] = []

    def run(self, task: AgentTask, ctx: AgentContext) -> AgentResult:
        objective = task.input.get("objective") or task.description
        plan = build_plan(objective)
        return AgentResult(output={"plan": plan})


register(AIManagerAgent())


def llm_summarize_workflow(workflow_state: dict[str, Any]) -> str:
    """Optional natural-language summary for the completion report (PRD §20)."""
    llm = get_llm()
    sys = "You are a concise business operations assistant."
    user = (
        "Summarize the following workflow result in 3-6 short lines for a manager. "
        "Be honest about what failed and what still needs attention.\n\n"
        f"{workflow_state}"
    )
    try:
        return llm.complete(LLMRequest(system=sys, user=user)).text.strip()
    except Exception:  # noqa: BLE001  (LLM optional in MVP)
        return "Workflow finished. Review the per-task status for details."

