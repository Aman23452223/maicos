"""BusinessProfile DB service + URL ingestion (Phases 1-2, 26)."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.audit.service import record
from app.intel.crawler import crawl_site, validate_url
from app.intel.profiles import extract_profile, llm_enhance
from app.models.orm import BusinessProfile, Document
from app.rag.index import get_index

DEFAULT_SCORING = {
    "industry_match": 30, "location_match": 20, "company_size_match": 15,
    "need_signal": 20, "contactability": 15, "version": "v1",
}


def get_or_create_profile(db: Session, *, company_id: str) -> BusinessProfile:
    p = db.query(BusinessProfile).filter(BusinessProfile.company_id == company_id).first()
    if p:
        return p
    p = BusinessProfile(company_id=company_id, scoring_rules=dict(DEFAULT_SCORING))
    db.add(p)
    db.flush()
    return p


def analyze_website(db: Session, *, company_id: str, url: str,
                    actor: str = "user", use_llm: bool = True) -> dict[str, Any]:
    url = validate_url(url)
    pages = crawl_site(url)
    if not pages:
        return {"ok": False, "error": "fetch failed for all pages", "website_url": url}
    profile = extract_profile(pages, url)
    if use_llm:
        profile = llm_enhance(profile)
    bp = get_or_create_profile(db, company_id=company_id)
    bp.website_url = url
    if profile.get("company_name"):
        bp.business_name = profile["company_name"][:255]
    bp.description = (profile.get("description") or "")[:4000]
    bp.products_services = (profile.get("services") or [])[:30]
    if profile.get("target_customer"):
        bp.target_customer = str(profile["target_customer"])[:2000]
    bp.profile_json = profile
    # full text for RAG
    full_text = "\n\n".join(
        f"## {p.url}\n{p.title}\n{p.text}" for p in pages
    )[:60000]
    # dedup: same URL already ingested?
    existing = (
        db.query(Document)
        .filter(Document.company_id == company_id, Document.source == f"url:{url}")
        .first()
    )
    doc_id = None
    if existing is None:
        from app.rag.service import add_document
        doc = add_document(
            db, company_id=company_id, name=f"Website: {url}",
            mime_type="text/plain", access_roles=[], text=full_text,
        )
        doc.source = f"url:{url}"
        doc_id = doc.id
    else:
        doc_id = existing.id
        get_index().add(
            workspace_id=company_id, document_id=existing.id,
            document_name=existing.name, text=full_text, access_roles=[],
        )
        existing.indexed = True
    record(db, company_id=company_id, actor=actor, action="website.analyzed",
           target_type="business_profile", target_id=bp.id,
           details={"url": url, "pages": len(pages), "document_id": doc_id})
    db.flush()
    return {"ok": True, "profile": profile, "document_id": doc_id,
            "pages_crawled": len(pages)}
