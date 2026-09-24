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
    "schedule_meeting": ["schedule meeting", "meeting with", "meeting kar",
                         "schedule a call", "book a meeting", "appointment",
                         "schedule call"],
    "hiring": ["hire", "hiring", "recruit", "need developers", "need a designer",
               "looking for developers", "delivery partners", "field agents",
               "find developers", "job description"],
    "partner_acquisition": ["partner", "suppliers", "vendors",
                            "sellers", "onboard restaurants", "supply acquisition",
                            "restaurant partners"],
    "creator_campaign": ["influencer", "influencers", "creator", "creators"],
    "software_build": ["build website", "build app", "build my website", "build mvp",
                       "develop app", "prd", "product requirements"],
    "onboard_client": ["onboard", "new client", "new customer"],
    "meeting_prep": ["prepare", "meeting", "brief"],
    "create_project": ["launch", "create project", "new project"],
    "invoice_followup": ["overdue", "invoice", "payment reminder", "receivable"],
    "lead_generation": [
        "find", "prospect", "lead generation", "generate leads",
        "qualified prospects", "potential customer", "potential restaurant",
        "restaurant", "nagpur",
    ],
    "website_analysis": ["analyze website", "website", "target customer", "services"],
    "direct_send": ["send email", "send message", "send whatsapp", "email bhej",
                    "message bhej", "msg bhej", "mail kar", "whatsapp kar",
                    "email kar", "story dal", "post dal", "post kar"],
    "bulk_send": ["send to all", "sabko", "all clients", "bulk", "sheet",
                  "everyone", "entire list", "puri sheet", "sare clients"],
    "campaign": ["campaign", "festival", "diwali", "offer launch", "promotion",
                 "promote", "influencer", "sale event", "launch offer"],
    "integration_request": ["zomato", "google sheets", "instagram",
                            "order summary", "today's orders", "menu availability"],
    "lead_outreach": ["contact", "outreach", "send proposal", "prepare outreach"],
    "morning_digest": ["morning digest", "daily digest", "morning report",
                       "daily summary", "subah ki report"],
    "weekly_review": ["weekly", "report", "pipeline", "analytics", "stuck"],
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


def _plan_meeting_prep(objective: str) -> dict[str, Any]:
    return {
        "intent": "meeting_prep",
        "tasks": [
            {"id": "context", "agent": "knowledge", "title": "Gather meeting context",
             "description": f"Search knowledge for: {objective}",
             "input": {"query": objective}, "depends_on": []},
            {"id": "brief", "agent": "analytics", "title": "Prepare brief",
             "description": "Summarize context + open items for the meeting.",
             "input": {"action": "summarize_context"}, "depends_on": ["context"]},
        ],
    }


def _plan_create_project(objective: str) -> dict[str, Any]:
    return {
        "intent": "create_project",
        "tasks": [
            {"id": "project", "agent": "project_ops", "title": "Create project",
             "description": objective,
             "input": {"action": "create_project", "name": objective[:120]},
             "depends_on": []},
        ],
    }


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


def _plan_lead_generation(objective: str) -> dict[str, Any]:
    """Generic DISCOVER→ENRICH→QUALIFY→CRM→OUTREACH→REPORT primitives."""
    from app.workflow.templates import lead_generation

    plan = lead_generation()
    # carry the raw objective into the first task so agents can parse queries
    if plan["tasks"]:
        plan["tasks"][0]["input"]["objective"] = objective
    return plan


def _plan_website_analysis(objective: str) -> dict[str, Any]:
    import re

    m = re.search(r"https?://[^\s\"']+", objective)
    url = m.group(0) if m else ""
    return {
        "intent": "website_analysis",
        "tasks": [
            {
                "id": "analyze_site",
                "agent": "knowledge",
                "title": "Analyze website",
                "description": "Fetch + extract business profile + ingest to RAG.",
                "input": {"action": "analyze_website", "url": url, "objective": objective},
                "depends_on": [],
            },
            {
                "id": "report",
                "agent": "analytics",
                "title": "Summarize business profile",
                "description": "Report extracted services/target customers.",
                "input": {"action": "summarize_profile"},
                "depends_on": ["analyze_site"],
            },
        ],
    }


def _plan_integration_request(objective: str) -> dict[str, Any]:
    """Route authorized-integration questions to the integrations agent.

    Provider detected generically from the catalog names (no industry logic).
    """
    from app.integrations.catalog import CATALOG

    low = objective.lower()
    provider = next((e["provider"] for e in CATALOG if e["provider"] in low
                     or e["name"].lower() in low), "")
    action = ""
    if "order" in low:
        action = "get_orders"
    elif "menu" in low:
        action = "get_menu"
    elif "availab" in low:
        action = "update_availability"
    return {
        "intent": "integration_request",
        "tasks": [{
            "id": "integration",
            "agent": "integrations",
            "title": f"Integration: {provider or 'unknown'} {action or 'status'}",
            "description": objective,
            "input": {"provider": provider, "action": action,
                      "payload": {"query": objective}},
            "depends_on": [],
        }],
    }


def _plan_direct_send(objective: str) -> dict[str, Any]:
    """One-shot send: parse channel + recipient + content (generic)."""
    import re

    low = objective.lower()
    if any(k in low for k in ("all", "sabko", "every", "sheet", "everyone",
                              "sare clients", "entire list")):
        return _plan_bulk_send(objective)
    if any(k in low for k in ("story", "post dal", "post kar")):
        channel = "unsupported"
    elif "whatsapp" in low or "msg bhej" in low or "message bhej" in low:
        channel = "whatsapp"
    else:
        channel = "email"
    email_m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", objective)
    phone_m = re.search(r"\+?\d[\d\s\-()]{7,}\d", objective)
    to = ""
    if channel == "email" and email_m:
        to = email_m.group(0)
    elif channel == "whatsapp" and phone_m:
        to = re.sub(r"[\s\-()]", "", phone_m.group(0))
    elif email_m:
        to = email_m.group(0)
    # Content: strip the command + recipient, keep the message.
    body = re.sub(r"(?i)^.*?(bhej|kar|dal|send|post)\b", "", objective).strip()
    body = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "", body).strip(" -:,")
    subject_m = re.search(r"(?i)subject\s*[:\-]\s*(.+)", objective)
    subject = subject_m.group(1).strip()[:200] if subject_m else "Message from MAICOS"
    if channel == "unsupported":
        return {
            "intent": "direct_send",
            "tasks": [{
                "id": "unsupported",
                "agent": "communication",
                "title": "Unsupported channel",
                "description": objective,
                "input": {"action": "send", "channel": "story",
                          "to": to, "subject": subject, "body": body},
                "depends_on": [],
            }],
        }
    return {
        "intent": "direct_send",
        "tasks": [{
            "id": "send",
            "agent": "communication",
            "title": f"Send {channel}",
            "description": objective,
            "input": {"action": "send", "channel": channel, "to": to,
                      "subject": subject, "body": body or objective},
            "depends_on": [],
        }],
    }


def _plan_bulk_send(objective: str) -> dict[str, Any]:
    """One task: bulk send to sheet/named contacts (agent resolves)."""
    low = objective.lower()
    channel = "whatsapp" if ("whatsapp" in low or "msg" in low) else "email"
    import re

    subject_m = re.search(r"(?i)subject\s*[:\-]\s*(.+)", objective)
    return {
        "intent": "bulk_send",
        "tasks": [{
            "id": "bulk",
            "agent": "communication",
            "title": f"Bulk {channel} send",
            "description": objective,
            "input": {"action": "bulk_send", "channel": channel,
                      "bulk_query": objective,
                      "subject": (subject_m.group(1).strip()[:200]
                                  if subject_m else "Message from MAICOS"),
                      "body": objective},
            "depends_on": [],
        }],
    }


def _parse_meeting_datetime(objective: str) -> str | None:
    """Best-effort natural datetime -> ISO. Returns None when unclear
    (caller should ask via needs_input instead of guessing)."""
    from datetime import datetime, timedelta

    low = objective.lower()
    now = datetime.now()
    day = None
    if "day after tomorrow" in low:
        day = (now + timedelta(days=2)).date()
    elif "tomorrow" in low or "kal" in low:
        day = (now + timedelta(days=1)).date()
    elif "today" in low or "aaj" in low:
        day = now.date()
    else:
        weekdays = ["monday", "tuesday", "wednesday", "thursday",
                    "friday", "saturday", "sunday"]
        for i, wd in enumerate(weekdays):
            if wd in low:
                delta = (i - now.weekday()) % 7 or 7
                day = (now + timedelta(days=delta)).date()
                break
        if day is None:
            import re

            m = re.search(r"(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?", low)
            if m:
                d, mo = int(m.group(1)), int(m.group(2))
                y = int(m.group(3)) if m.group(3) else now.year
                if y < 100:
                    y += 2000
                try:
                    from datetime import date

                    day = date(y, mo, d)
                except ValueError:
                    return None
    if day is None:
        return None
    import re

    m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", low)
    hour, minute = 10, 0
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        mer = m.group(3)
        if mer == "pm" and hour < 12:
            hour += 12
        if mer == "am" and hour == 12:
            hour = 0
    elif "morning" in low:
        hour = 10
    elif "afternoon" in low:
        hour = 14
    elif "evening" in low:
        hour = 18
    try:
        return datetime(day.year, day.month, day.day, hour, minute).isoformat()
    except ValueError:
        return None


def _plan_schedule_meeting(objective: str) -> dict[str, Any]:
    import re

    emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", objective)
    title_m = re.search(r"(?i)meeting\s+(?:with\s+)?([A-Z][\w'.-]+(?:\s+[A-Z][\w'.-]+){0,2})",
                        objective)
    title = f"Meeting with {title_m.group(1)}" if title_m else "Meeting"
    start = _parse_meeting_datetime(objective)
    task_input: dict[str, Any] = {"action": "schedule", "title": title,
                                  "attendees": emails}
    if start:
        task_input["start"] = start
    else:
        # Don't guess the date — the agent will ask via needs_input.
        task_input["needs_date"] = True
    return {
        "intent": "schedule_meeting",
        "tasks": [{
            "id": "meeting",
            "agent": "calendar",
            "title": title,
            "description": objective,
            "input": task_input,
            "depends_on": [],
        }],
    }


def _plan_campaign(objective: str) -> dict[str, Any]:
    """Festival/promo campaign: discover -> qualify -> outreach -> follow-up -> report."""
    return {
        "intent": "campaign",
        "tasks": [
            {"id": "discover", "agent": "sales_crm", "title": "Discover prospects",
             "description": f"Find prospects matching: {objective}",
             "input": {"action": "discover", "objective": objective,
                       "auto_import": True, "limit": 15},
             "depends_on": []},
            {"id": "qualify", "agent": "sales_crm", "title": "Enrich + qualify",
             "description": "Enrich and score discovered prospects.",
             "input": {"action": "qualify_batch", "objective": objective},
             "depends_on": ["discover"]},
            {"id": "outreach", "agent": "communication",
             "title": "Draft campaign outreach",
             "description": f"Personalized campaign message for: {objective}",
             "input": {"action": "draft", "subject": "Special offer",
                       "body": objective},
             "depends_on": ["qualify"]},
            {"id": "send", "agent": "communication", "title": "Send campaign",
             "description": "Approval-gated bulk send to qualified prospects.",
             "input": {"action": "bulk_send", "channel": "email",
                       "bulk_query": objective, "subject": "Special offer",
                       "body": objective},
             "depends_on": ["outreach"]},
            {"id": "followups", "agent": "sales_crm",
             "title": "Schedule follow-ups",
             "description": "Follow-up sequence for campaign contacts.",
             "input": {"action": "schedule_followups"},
             "depends_on": ["send"]},
            {"id": "report", "agent": "analytics", "title": "Campaign report",
             "description": "Funnel + results for the campaign.",
             "input": {"action": "report"},
             "depends_on": ["followups"]},
        ],
    }


def _plan_hiring(objective: str) -> dict[str, Any]:
    return {
        "intent": "hiring",
        "tasks": [{
            "id": "triage",
            "agent": "hr",
            "title": "Clarify hiring need",
            "description": objective,
            "input": {"action": "triage_hiring", "objective": objective},
            "depends_on": [],
        }],
    }


def _plan_partner_acquisition(objective: str) -> dict[str, Any]:
    base = _plan_campaign(objective)
    base["intent"] = "partner_acquisition"
    base["tasks"][0]["title"] = "Discover partner prospects"
    base["tasks"][0]["input"]["segment"] = "partners"
    return base


def _plan_creator_campaign(objective: str) -> dict[str, Any]:
    return {
        "intent": "creator_campaign",
        "tasks": [
            {"id": "discover", "agent": "sales_crm", "title": "Discover creators",
             "description": f"Find creators matching: {objective}",
             "input": {"action": "discover_creators", "objective": objective,
                       "limit": 15},
             "depends_on": []},
            {"id": "outreach", "agent": "communication",
             "title": "Draft creator outreach",
             "description": f"Personalized outreach for: {objective}",
             "input": {"action": "draft", "subject": "Collaboration",
                       "body": objective},
             "depends_on": ["discover"]},
            {"id": "send", "agent": "communication", "title": "Send outreach",
             "description": "Approval-gated send to creators with addresses.",
             "input": {"action": "bulk_send", "channel": "email",
                       "bulk_query": objective, "subject": "Collaboration",
                       "body": objective},
             "depends_on": ["outreach"]},
            {"id": "report", "agent": "analytics", "title": "Campaign report",
             "description": "Results for the creator campaign.",
             "input": {"action": "report"},
             "depends_on": ["send"]},
        ],
    }


def _plan_software_build(objective: str) -> dict[str, Any]:
    return {
        "intent": "software_build",
        "tasks": [
            {"id": "requirements", "agent": "project_ops",
             "title": "Write PRD",
             "description": f"Requirements + PRD for: {objective}",
             "input": {"action": "create_doc", "kind": "prd",
                       "title": "PRD", "requirements": objective},
             "depends_on": []},
            {"id": "repo", "agent": "integrations",
             "title": "Inspect repository",
             "description": f"Analyze connected repo for: {objective}",
             "input": {"provider": "github", "action": "repo_info",
                       "payload": {}},
             "depends_on": ["requirements"]},
            {"id": "build_pr", "agent": "integrations",
             "title": "Generate code + open PR",
             "description": objective,
             "input": {"provider": "github", "action": "build_pr",
                       "objective": objective,
                       "payload": {"base": "main", "requirements": objective}},
             "depends_on": ["repo"]},
            {"id": "deploy_status", "agent": "integrations",
             "title": "Deployment status",
             "description": "Check staging/production deployment status.",
             "input": {"provider": "vercel", "action": "list_deployments",
                       "payload": {}},
             "depends_on": ["build_pr"]},
        ],
    }


def _plan_lead_outreach(objective: str) -> dict[str, Any]:
    from app.workflow.templates import lead_outreach

    plan = lead_outreach()
    if plan["tasks"]:
        plan["tasks"][0]["input"]["objective"] = objective
    return plan


def _plan_weekly_review(objective: str) -> dict[str, Any]:
    from app.workflow.templates import weekly_review

    return weekly_review()


def _plan_morning_digest(objective: str) -> dict[str, Any]:
    return {
        "intent": "morning_digest",
        "tasks": [{
            "id": "digest",
            "agent": "communication",
            "title": "Send morning digest",
            "description": objective,
            "input": {"action": "send_digest"},
            "depends_on": [],
        }],
    }


def build_plan(objective: str) -> dict[str, Any]:
    intent = classify(objective)
    if intent == "onboard_client":
        return _plan_onboard_client(objective)
    if intent == "schedule_meeting":
        return _plan_schedule_meeting(objective)
    if intent == "hiring":
        return _plan_hiring(objective)
    if intent == "partner_acquisition":
        return _plan_partner_acquisition(objective)
    if intent == "creator_campaign":
        return _plan_creator_campaign(objective)
    if intent == "software_build":
        return _plan_software_build(objective)
    if intent == "meeting_prep":
        return _plan_meeting_prep(objective)
    if intent == "create_project":
        return _plan_create_project(objective)
    if intent == "campaign":
        return _plan_campaign(objective)
    if intent == "lead_generation":
        return _plan_lead_generation(objective)
    if intent == "website_analysis":
        return _plan_website_analysis(objective)
    if intent == "integration_request":
        return _plan_integration_request(objective)
    if intent == "direct_send":
        return _plan_direct_send(objective)
    if intent == "bulk_send":
        return _plan_bulk_send(objective)
    if intent == "lead_outreach":
        return _plan_lead_outreach(objective)
    if intent == "weekly_review":
        return _plan_weekly_review(objective)
    if intent == "morning_digest":
        return _plan_morning_digest(objective)
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

