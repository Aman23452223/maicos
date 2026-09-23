"""Website intelligence + business profile routes (Phases 1-2, 26)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.context import Principal
from app.core.security import get_current_principal
from app.db.session import get_db
from app.intel.service import analyze_website, get_or_create_profile

router = APIRouter(tags=["intel"])


class AnalyzeIn(BaseModel):
    url: str
    use_llm: bool = False
    analysis_type: str = "my_business"


class BusinessConfigIn(BaseModel):
    business_name: str | None = None
    industry: str | None = None
    description: str | None = None
    target_customer: str | None = None
    geography: str | None = None
    icp: dict | None = None
    scoring_rules: dict | None = None
    followup_policy: dict | None = None
    comms_policy: dict | None = None


@router.post("/intel/analyze-website")
def analyze(payload: AnalyzeIn, p: Principal = Depends(get_current_principal),
            db: Session = Depends(get_db)):
    from app.intel.service import ANALYSIS_TYPES
    if payload.analysis_type not in ANALYSIS_TYPES:
        raise HTTPException(status_code=400,
                            detail=f"analysis_type must be one of {ANALYSIS_TYPES}")
    try:
        out = analyze_website(db, company_id=p.workspace_id, url=payload.url,
                              actor=p.user_id, use_llm=payload.use_llm,
                              analysis_type=payload.analysis_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not out.get("ok"):
        raise HTTPException(status_code=422, detail=out.get("error") or "fetch failed")
    db.commit()
    return out


@router.get("/intel/analyses")
def analyses(analysis_type: str | None = None,
             p: Principal = Depends(get_current_principal),
             db: Session = Depends(get_db)):
    from app.intel.service import list_analyses
    return list_analyses(db, company_id=p.workspace_id,
                         analysis_type=analysis_type)


@router.post("/intel/prospect/{analysis_id}/convert-lead")
def prospect_to_lead(analysis_id: str,
                     p: Principal = Depends(get_current_principal),
                     db: Session = Depends(get_db)):
    from app.intel.service import convert_prospect_to_lead
    out = convert_prospect_to_lead(db, company_id=p.workspace_id,
                                   analysis_id=analysis_id, actor=p.user_id)
    if not out.get("ok"):
        raise HTTPException(status_code=404, detail=out.get("error"))
    db.commit()
    return out


@router.get("/business/profile")
def get_profile(p: Principal = Depends(get_current_principal),
                db: Session = Depends(get_db)):
    bp = get_or_create_profile(db, company_id=p.workspace_id)
    return {"business_name": bp.business_name, "industry": bp.industry,
            "description": bp.description, "target_customer": bp.target_customer,
            "geography": bp.geography, "icp": bp.icp or {},
            "scoring_rules": bp.scoring_rules or {},
            "comms_policy": bp.comms_policy or {},
            "website_url": bp.website_url, "profile": bp.profile_json or {}}


@router.put("/business/profile")
def put_profile(payload: BusinessConfigIn,
                p: Principal = Depends(get_current_principal),
                db: Session = Depends(get_db)):
    bp = get_or_create_profile(db, company_id=p.workspace_id)
    data = payload.model_dump(exclude_none=True)
    for k in ("business_name", "industry", "description", "target_customer", "geography"):
        if k in data:
            setattr(bp, k, str(data[k])[:2000])
    for k in ("icp", "scoring_rules", "followup_policy", "comms_policy"):
        if k in data and isinstance(data[k], dict):
            setattr(bp, k, data[k])
    db.commit()
    return {"ok": True}
