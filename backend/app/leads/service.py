"""Lead CRUD + dedup + enrichment + qualification/scoring (Phases 4-6)."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.audit.service import record
from app.intel.service import get_or_create_profile
from app.leads.normalize import domain_of, norm_email, norm_name
from app.leads.providers import Prospect
from app.models.orm import CrmActivity, Lead, LeadStatus


def _bp_rules(db: Session, company_id: str) -> tuple[dict, dict]:
    bp = get_or_create_profile(db, company_id=company_id)
    return (bp.icp or {}, bp.scoring_rules or {})


def find_duplicate(db: Session, *, company_id: str, p: Prospect) -> Lead | None:
    em = norm_email(p.email)
    if em:
        hit = db.query(Lead).filter(
            Lead.company_id == company_id, Lead.normalized_email == em).first()
        if hit:
            return hit
    dom = domain_of(p.domain or p.website)
    if dom:
        hit = db.query(Lead).filter(
            Lead.company_id == company_id, Lead.domain == dom).first()
        if hit:
            return hit
    if p.external_id:
        hit = db.query(Lead).filter(
            Lead.company_id == company_id, Lead.external_id == p.external_id).first()
        if hit:
            return hit
    nm = norm_name(p.company_name)
    if nm:
        hit = db.query(Lead).filter(
            Lead.company_id == company_id, Lead.normalized_name == nm).first()
        if hit:
            return hit
    return None


def import_prospects(db: Session, *, company_id: str, prospects: list[Prospect],
                     actor: str = "user") -> dict[str, Any]:
    created, deduped = 0, 0
    ids: list[str] = []
    for p in prospects:
        if not p.company_name.strip():
            continue
        dup = find_duplicate(db, company_id=company_id, p=p)
        if dup:
            deduped += 1
            ids.append(dup.id)
            continue
        lead = Lead(
            company_id=company_id, company_name=p.company_name.strip()[:255],
            normalized_name=norm_name(p.company_name),
            website=(p.website or "")[:500], domain=domain_of(p.domain or p.website),
            email=(p.email or None), normalized_email=norm_email(p.email),
            phone=(p.phone or "")[:64], location=(p.location or "")[:255],
            industry=(p.industry or "")[:120], source=(p.source or "manual")[:120],
            source_url=(p.source_url or "")[:500],
            external_id=(p.external_id or None), notes=(p.notes or "")[:4000],
            enriched_json=dict(p.extra or {}),
        )
        db.add(lead)
        db.flush()
        ids.append(lead.id)
        created += 1
    record(db, company_id=company_id, actor=actor, action="leads.imported",
           target_type="lead", target_id=f"{created} created",
           details={"created": created, "deduped": deduped})
    db.flush()
    return {"created": created, "deduped": deduped, "ids": ids}


def enrich_lead(db: Session, *, company_id: str, lead_id: str,
                actor: str = "system") -> dict[str, Any]:
    """Deterministic enrichment from website if present; no fake data."""
    lead = db.get(Lead, lead_id)
    if not lead or lead.company_id != company_id:
        return {"ok": False, "error": "lead not found"}
    signals: dict[str, Any] = {}
    if lead.website and not lead.enriched_json.get("website_fetched"):
        try:
            from app.intel.crawler import fetch_page
            _, page = fetch_page(lead.website)
            signals["website_title"] = page.title
            signals["website_emails"] = page.emails[:5]
            signals["website_phones"] = page.phones[:5]
            signals["website_fetched"] = True
            if page.emails and not lead.email:
                lead.email = page.emails[0][:255]
                lead.normalized_email = norm_email(lead.email)
            merged = dict(lead.enriched_json or {})
            merged.update(signals)
            lead.enriched_json = merged
        except Exception as exc:
            signals["website_error"] = str(exc)[:300]
    lead.enrichment_status = "enriched" if signals.get("website_fetched") else lead.enrichment_status
    db.flush()
    record(db, company_id=company_id, actor=actor, action="lead.enriched",
           target_type="lead", target_id=lead.id, details=signals)
    return {"ok": True, "signals": signals}


def score_lead(icp: dict, rules: dict, lead: Lead) -> tuple[int, dict]:
    """Deterministic 0-100 scoring. Rules configurable; defaults sum to 100."""
    r = {
        "industry_match": int(rules.get("industry_match", 30)),
        "location_match": int(rules.get("location_match", 20)),
        "company_size_match": int(rules.get("company_size_match", 15)),
        "need_signal": int(rules.get("need_signal", 20)),
        "contactability": int(rules.get("contactability", 15)),
    }
    reasons: dict[str, Any] = {}
    total = 0
    # industry
    want_ind = str((icp.get("industries") or icp.get("industry") or "")).lower()
    if want_ind and want_ind in (lead.industry or "").lower():
        total += r["industry_match"]; reasons["industry_match"] = r["industry_match"]
    else:
        reasons["industry_match"] = 0
    # location
    want_loc = str(icp.get("geography") or icp.get("location") or "").lower()
    if want_loc and want_loc in (lead.location or "").lower():
        total += r["location_match"]; reasons["location_match"] = r["location_match"]
    else:
        reasons["location_match"] = 0 if want_loc else r["location_match"] // 2
        if not want_loc:
            total += r["location_match"] // 2
    # company size: optional enriched field
    if (lead.enriched_json or {}).get("company_size"):
        total += r["company_size_match"]; reasons["company_size_match"] = r["company_size_match"]
    else:
        reasons["company_size_match"] = 0
    # need signal: website/notes keywords
    blob = f"{lead.notes} {lead.enriched_json}".lower()
    if any(k in blob for k in ("need", "looking", "requirement", "hire", "project")):
        total += r["need_signal"]; reasons["need_signal"] = r["need_signal"]
    else:
        reasons["need_signal"] = 0
    # contactability
    if lead.email or lead.phone:
        total += r["contactability"]; reasons["contactability"] = r["contactability"]
    else:
        reasons["contactability"] = 0
    return max(0, min(100, total)), reasons


def qualify_lead(db: Session, *, company_id: str, lead_id: str,
                 actor: str = "system", threshold: int = 60) -> dict[str, Any]:
    lead = db.get(Lead, lead_id)
    if not lead or lead.company_id != company_id:
        return {"ok": False, "error": "lead not found"}
    icp, rules = _bp_rules(db, company_id)
    version = str(rules.get("version", "v1"))
    score, reasons = score_lead(icp, rules, lead)
    lead.score = score
    lead.score_reasons = reasons
    lead.score_version = version
    if lead.opted_out:
        lead.status = LeadStatus.DISQUALIFIED
    elif score >= threshold:
        lead.status = LeadStatus.QUALIFIED
    elif score >= threshold - 20:
        lead.status = LeadStatus.NURTURE
    else:
        lead.status = LeadStatus.DISQUALIFIED
    db.flush()
    db.add(CrmActivity(company_id=company_id, lead_id=lead.id, kind="qualification",
                       subject=f"score={score} status={lead.status.value}",
                       body="", meta={"reasons": reasons, "version": version},
                       created_by=actor))
    record(db, company_id=company_id, actor=actor, action="lead.qualified",
           target_type="lead", target_id=lead.id,
           details={"score": score, "status": lead.status.value})
    return {"ok": True, "score": score, "status": lead.status.value, "reasons": reasons}


def touch_contacted(db: Session, *, company_id: str, lead_id: str) -> None:
    lead = db.get(Lead, lead_id)
    if not lead or lead.company_id != company_id:
        return
    now = datetime.now(UTC)
    lead.last_contacted_at = now
    lead.follow_up_count = (lead.follow_up_count or 0) + 1
    if lead.status == LeadStatus.QUALIFIED:
        lead.status = LeadStatus.CONTACTED
    db.flush()
