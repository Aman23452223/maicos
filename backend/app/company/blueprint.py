"""Startup Creation Engine: IDEA -> reviewable COMPANY BLUEPRINT.

Research-backed where providers exist; everything else is explicitly
labeled assumption/recommendation — never presented as verified fact.
Nothing executes without approval; applying a blueprint writes draft
profile + goals + memory only.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session


def generate(idea: str, *, research: dict[str, Any] | None = None) -> dict[str, Any]:
    idea = (idea or "").strip()
    if not idea:
        raise ValueError("idea is required")
    researched = bool(research)
    sections = {
        "concept": {"status": "assumption",
                    "text": f"Business concept derived from idea: {idea[:500]}"},
        "problem": {"status": "assumption",
                    "text": "Problem statement to validate with 10 customer interviews."},
        "target_market": {"status": "assumption", "text": "TBD from research."},
        "icp": {"status": "assumption",
                "text": "Draft ICP: early adopters with the painful problem and budget."},
        "value_proposition": {"status": "recommendation",
                              "text": "One-line promise + proof to be defined."},
        "competitors": {"status": "researched" if researched else "assumption",
                        "text": str((research or {}).get("summary", "Not researched yet."))},
        "business_model": {"status": "recommendation",
                           "text": "Subscription + usage hybrid recommended as default."},
        "revenue_model": {"status": "recommendation",
                          "text": "MRR base + usage overage (see monetization)."},
        "pricing_hypothesis": {"status": "assumption",
                               "text": "3-tier starter/growth/scale to be validated."},
        "gtm": {"status": "recommendation",
                "text": "Founder-led outreach -> content -> partnerships."},
        "product_strategy": {"status": "recommendation",
                             "text": "Single-player MVP, then collaboration, then platform."},
        "mvp_scope": {"status": "recommendation",
                      "text": "Smallest testable slice: one workflow end-to-end."},
        "tech_strategy": {"status": "recommendation",
                          "text": "Boring stack, Postgres-first, deploy on Railway/Vercel."},
        "operations": {"status": "recommendation",
                       "text": "Weekly review cadence + approval gates on spend/sends."},
        "hiring_plan": {"status": "assumption",
                        "text": "Founder + contractors first; hires after revenue."},
        "marketing": {"status": "recommendation",
                      "text": "ICP content + 20 outreach/day + weekly demo."},
        "sales": {"status": "recommendation",
                  "text": "Discovery-first pipeline with follow-up sequences."},
        "financial_assumptions": {"status": "assumption",
                                  "text": "CAC, churn and pricing are guesses until measured."},
        "launch_plan": {"status": "recommendation",
                        "text": "Private beta (10 users) -> public launch -> iterate."},
        "kpis": {"status": "recommendation",
                 "text": "Activation, retention, revenue, CAC payback."},
        "initial_workforce": {"status": "recommendation",
                              "text": "Research + Product + Engineering + Growth workers."},
    }
    return {"idea": idea, "researched": researched, "sections": sections,
            "notice": "Review before applying. Assumptions are NOT facts."}


def apply_blueprint(db: Session, *, company_id: str, blueprint: dict,
                    actor: str = "user") -> dict[str, Any]:
    """Write blueprint drafts (profile/goals/memory). Reviewable + reversible."""
    from app.company.brain import remember
    from app.intel.service import get_or_create_profile

    bp = get_or_create_profile(db, company_id=company_id)
    sections = blueprint.get("sections", {})
    if not bp.business_name:
        bp.business_name = str(blueprint.get("idea", ""))[:255]
    goals = list(bp.business_goals or [])
    for g in ("Validate problem with 10 interviews", "Ship MVP slice",
              "First 10 beta users"):
        if not any(x.get("text") == g for x in goals):
            import uuid as _uuid
            goals.append({"id": str(_uuid.uuid4())[:8], "text": g, "status": "active"})
    bp.business_goals = goals
    remember(db, company_id=company_id, kind="AI_RECOMMENDATION",
             key="blueprint:applied",
             value=f"Blueprint applied ({len(sections)} sections).", actor=actor)
    db.commit()
    return {"ok": True, "goals_added": 3, "sections": len(sections)}
