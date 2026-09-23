"""Startup Builder backend: idea -> validation -> blueprint -> workspace.

Generic lifecycle engine. No industry branches: stage relevance derives
from the idea text + enabled capabilities, never from hardcoded verticals.
"""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.audit.service import record

STAGES = ["idea", "validate", "strategy", "plan", "build", "test", "deploy",
          "supply", "workforce", "marketing", "acquire", "launch", "operate",
          "measure", "optimize", "scale"]


def parse_idea(idea: str) -> dict[str, Any]:
    """Extract structured understanding; label everything as user input."""
    text = (idea or "").strip()
    if not text:
        raise ValueError("idea is required")
    low = text.lower()
    geo = ""
    m = re.search(r"\bin\s+([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,2})", text)
    if m:
        geo = m.group(1).strip()[:120]
    marketplace = any(k in low for k in ("marketplace", "platform", "delivery",
                                         "connecting", "sellers", "vendors"))
    return {
        "idea": text[:2000],
        "problem": "To be validated with customer interviews.",
        "proposed_solution": text[:500],
        "business_type": "marketplace" if marketplace else "general",
        "marketplace_structure": marketplace,
        "target_customers": "To be defined in validation.",
        "geography": geo,
        "supply_side": "To be identified during validation." if marketplace else "",
        "demand_side": "To be identified during validation." if marketplace else "",
        "initial_assumptions": ["Problem exists and is painful",
                                "Customers will pay for the solution",
                                "Acquisition channels are reachable"],
        "revenue_model_hint": "Subscription + usage (to be validated).",
        "source": "USER_INPUT",
    }


def validate_idea(db: Session, *, company_id: str, idea: str) -> dict[str, Any]:
    """Market research via search provider; honest when unconfigured."""
    from app.leads.providers import get as get_provider

    findings: list[str] = []
    sources: list[str] = []
    status = "assumption_only"
    try:
        res = get_provider("search").discover(f"market alternatives {idea[:200]}",
                                              limit=5)
    except Exception:
        res = None
    if res is not None and res.ok:
        status = "researched"
        for p in res.prospects:
            findings.append(f"{p.company_name} ({p.domain})")
            sources.append(p.source_url or p.website)
    return {
        "findings": findings[:5],
        "sources": sources[:5],
        "assumptions": ["Market size unmeasured", "Willingness to pay unproven",
                        "Competitor list may be incomplete"],
        "risks": ["No paying customers yet", "Acquisition cost unknown",
                  "Supply-side onboarding effort unknown"],
        "opportunities": ["Underserved niches may exist in the target geography"],
        "open_questions": ["Who pays first?", "What is the smallest testable slice?"],
        "research_status": status,
    }


def lifecycle_status(db: Session, *, company_id: str) -> dict[str, Any]:
    """Compute stage completion from REAL workspace state (never invented)."""
    from app.analytics.metrics import funnel
    from app.models.orm import (BusinessProfile, CompanyInitiative,
                                CompanyProject, Lead, StartupBlueprint,
                                WorkspaceIntegration)

    bp = db.query(BusinessProfile).filter(
        BusinessProfile.company_id == company_id).first()
    stages: dict[str, dict[str, Any]] = {}
    idea_done = db.query(StartupBlueprint).filter(
        StartupBlueprint.company_id == company_id).count() > 0
    stages["idea"] = {"done": idea_done, "detail": "Blueprint exists" if idea_done else "No idea captured"}
    leads = db.query(Lead).filter(Lead.company_id == company_id).count()
    stages["validate"] = {"done": leads > 0, "detail": f"{leads} researched records"}
    stages["strategy"] = {"done": bool(bp and bp.icp),
                          "detail": "ICP configured" if bp and bp.icp else "ICP missing"}
    goals = (bp.business_goals or []) if bp else []
    stages["plan"] = {"done": len(goals) > 0, "detail": f"{len(goals)} goals"}
    projects = db.query(CompanyProject).filter(
        CompanyProject.company_id == company_id).count()
    inits = db.query(CompanyInitiative).filter(
        CompanyInitiative.company_id == company_id).count()
    stages["build"] = {"done": projects > 0, "detail": f"{projects} projects"}
    stages["supply"] = {"done": inits > 0, "detail": f"{inits} initiatives"}
    connected = db.query(WorkspaceIntegration).filter(
        WorkspaceIntegration.company_id == company_id,
        WorkspaceIntegration.status == "connected").count()
    stages["deploy"] = {"done": connected > 0,
                        "detail": f"{connected} integrations connected"}
    fun = funnel(db, company_id=company_id)
    stages["acquire"] = {"done": fun.get("leads_total", 0) > 0,
                         "detail": f"{fun.get('leads_total', 0)} leads"}
    stages["launch"] = {"done": fun.get("won", 0) > 0,
                        "detail": f"{fun.get('won', 0)} won"}
    for s in ("test", "workforce", "marketing", "operate", "measure",
              "optimize", "scale"):
        stages[s] = {"done": False, "detail": "Not tracked yet"}
    done = sum(1 for v in stages.values() if v["done"])
    return {"stages": stages, "readiness": round(100 * done / len(stages)),
            "done": done, "total": len(stages)}


def create_startup_workspace(db: Session, *, user_id: str,
                             name: str) -> dict[str, Any]:
    """Brand-new workspace for an approved blueprint (owner = creator)."""
    import uuid as _uuid

    from app.models.orm import Company, User, WorkspaceMembership

    user = db.get(User, user_id)
    if not user:
        raise ValueError("user not found")
    company = Company(id=str(_uuid.uuid4()), name=name[:200], status="active")
    db.add(company)
    db.flush()
    db.add(WorkspaceMembership(user_id=user.id, company_id=company.id,
                               role="owner", status="active"))
    # Point the user's primary workspace at the new company.
    user.company_id = company.id
    user.roles = ["admin", "owner"]
    record(db, company_id=company.id, actor=user_id, action="startup.created",
           target_type="workspace", target_id=company.id, details={"name": name})
    try:
        from app.company.events import emit

        emit(db, company_id=company.id, type="startup.created",
             payload={"name": name})
    except Exception:
        pass
    db.commit()
    return {"id": company.id, "name": company.name}
