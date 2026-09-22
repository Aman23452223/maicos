"""BusinessProfile DB service + typed URL intelligence (research only).

Analysis types: my_business | competitor | prospect (default my_business).
- my_business: updates workspace BusinessProfile + knowledge tagged business.
- competitor: separate intel record, NEVER overwrites BusinessProfile.
- prospect: separate intel record, convertible to CRM lead.
Re-analysis merges into the same (workspace, type, URL) row.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.audit.service import record
from app.intel.crawler import crawl_site, validate_url
from app.intel.profiles import extract_profile, llm_enhance
from app.models.orm import BusinessIntelAnalysis, BusinessProfile, Document
from app.rag.index import get_index

DEFAULT_SCORING = {
    "industry_match": 30, "location_match": 20, "company_size_match": 15,
    "need_signal": 20, "contactability": 15, "version": "v1",
}

ANALYSIS_TYPES = ("my_business", "competitor", "prospect")


def normalize_url(url: str) -> str:
    url = validate_url(url)
    p = urlparse(url)
    host = (p.hostname or "").lower().removeprefix("www.")
    path = (p.path or "/").rstrip("/") or "/"
    return f"{p.scheme}://{host}{path}"


def get_or_create_profile(db: Session, *, company_id: str) -> BusinessProfile:
    p = db.query(BusinessProfile).filter(BusinessProfile.company_id == company_id).first()
    if p:
        return p
    p = BusinessProfile(company_id=company_id, scoring_rules=dict(DEFAULT_SCORING))
    db.add(p)
    db.flush()
    return p


def _merge_profile(old: dict, new: dict) -> dict:
    """Merge re-analysis: new non-empty values win; lists union."""
    merged = dict(old or {})
    for k, v in (new or {}).items():
        if isinstance(v, list):
            merged[k] = list(dict.fromkeys([*merged.get(k, []), *v]))[:30]
        elif v not in (None, "", [], {}) or k not in merged:
            merged[k] = v
    return merged


def analyze_website(db: Session, *, company_id: str, url: str,
                    actor: str = "user", use_llm: bool = True,
                    analysis_type: str = "my_business") -> dict[str, Any]:
    if analysis_type not in ANALYSIS_TYPES:
        raise ValueError(f"analysis_type must be one of {ANALYSIS_TYPES}")
    url = validate_url(url)
    norm = normalize_url(url)
    pages = crawl_site(url)
    if not pages:
        return {"ok": False, "error": "fetch failed for all pages",
                "website_url": url, "analysis_type": analysis_type}
    profile = extract_profile(pages, url)
    if use_llm:
        profile = llm_enhance(profile)
    now = datetime.now(UTC)
    full_text = "\n\n".join(
        f"## {p.url}\n{p.title}\n{p.text}" for p in pages
    )[:60000]

    # Re-analysis: same workspace + type + URL -> merge, version++
    existing = (
        db.query(BusinessIntelAnalysis)
        .filter(BusinessIntelAnalysis.company_id == company_id,
                BusinessIntelAnalysis.analysis_type == analysis_type,
                BusinessIntelAnalysis.normalized_url == norm)
        .first()
    )
    if existing is not None:
        merged = _merge_profile(existing.profile or {}, profile)
        existing.profile = merged
        existing.version = (existing.version or 1) + 1
        existing.status = "ready"
        existing.last_analyzed_at = now
        analysis = existing
        profile = merged
        is_update = True
    else:
        analysis = BusinessIntelAnalysis(
            company_id=company_id, analysis_type=analysis_type,
            source_url=url, normalized_url=norm, profile=profile,
            status="ready", version=1, last_analyzed_at=now)
        db.add(analysis)
        db.flush()
        is_update = False

    # my_business ONLY touches the workspace BusinessProfile.
    if analysis_type == "my_business":
        bp = get_or_create_profile(db, company_id=company_id)
        bp.website_url = url
        if profile.get("company_name"):
            bp.business_name = profile["company_name"][:255]
        bp.description = (profile.get("description") or "")[:4000]
        bp.products_services = (profile.get("services") or [])[:30]
        if profile.get("target_customer"):
            bp.target_customer = str(profile["target_customer"])[:2000]
        if profile.get("geography"):
            bp.geography = str(profile["geography"])[:255]
        bp.profile_json = profile
    else:
        bp = None

    # Knowledge Vault with source metadata (retrievable by agents).
    tag = f"intel:{analysis_type}:{norm}"
    doc = (
        db.query(Document)
        .filter(Document.company_id == company_id, Document.source == tag)
        .first()
    )
    if doc is None:
        from app.rag.service import add_document
        doc = add_document(
            db, company_id=company_id, name=f"Intel [{analysis_type}]: {url}",
            mime_type="text/plain", access_roles=[], text=full_text)
        doc.source = tag
    else:
        get_index().add(
            workspace_id=company_id, document_id=doc.id,
            document_name=doc.name, text=full_text, access_roles=[])
        doc.indexed = True
    try:
        from app.rag.vector_store import ingest_chunks
        ingest_chunks(db, company_id=company_id, document_id=doc.id,
                      source=tag, source_url=url, text=full_text,
                      access_roles=[])
    except Exception:
        pass
    analysis.document_id = doc.id
    record(db, company_id=company_id, actor=actor, action="website.analyzed",
           target_type="business_intel", target_id=analysis.id,
           details={"url": url, "type": analysis_type, "pages": len(pages),
                    "document_id": doc.id, "version": analysis.version,
                    "updated": is_update})
    db.flush()
    return {"ok": True, "profile": profile, "document_id": doc.id,
            "pages_crawled": len(pages), "analysis_id": analysis.id,
            "analysis_type": analysis_type, "version": analysis.version,
            "updated": is_update, "saved_to_knowledge": True}


def list_analyses(db: Session, *, company_id: str,
                  analysis_type: str | None = None) -> list[dict[str, Any]]:
    q = db.query(BusinessIntelAnalysis).filter(
        BusinessIntelAnalysis.company_id == company_id)
    if analysis_type:
        q = q.filter(BusinessIntelAnalysis.analysis_type == analysis_type)
    return [{
        "id": a.id, "type": a.analysis_type, "url": a.source_url,
        "company_name": (a.profile or {}).get("company_name", ""),
        "version": a.version, "status": a.status,
        "last_analyzed_at": a.last_analyzed_at.isoformat() if a.last_analyzed_at else None,
        "document_id": a.document_id,
    } for a in q.order_by(BusinessIntelAnalysis.updated_at.desc()).limit(100).all()]


def convert_prospect_to_lead(db: Session, *, company_id: str,
                             analysis_id: str, actor: str = "user") -> dict[str, Any]:
    from app.leads.providers import Prospect
    from app.leads.service import import_prospects

    a = db.get(BusinessIntelAnalysis, analysis_id)
    if not a or a.company_id != company_id:
        return {"ok": False, "error": "analysis not found"}
    if a.analysis_type != "prospect":
        return {"ok": False, "error": "only prospect analyses convert to leads"}
    prof = a.profile or {}
    emails = prof.get("emails") or []
    out = import_prospects(db, company_id=company_id, prospects=[Prospect(
        company_name=str(prof.get("company_name", ""))[:255],
        website=str(prof.get("website_url", ""))[:500],
        domain=str(prof.get("domain", ""))[:255],
        email=str(emails[0]) if emails else "",
        location=str(prof.get("geography", ""))[:255],
        industry=str((prof.get("industries_served") or [""])[0])[:120],
        source="intel_prospect", source_url=a.source_url)], actor=actor)
    db.flush()
    return {"ok": True, **out}
