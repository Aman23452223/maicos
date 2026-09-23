"""BusinessProfile extraction: deterministic + optional LLM assist."""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from app.intel.crawler import PageData

SERVICE_HINTS = [
    "development", "design", "marketing", "consulting", "software",
    "website", "mobile app", "saas", "seo", "cloud", "support",
    "delivery", "restaurant", "food", "hotel", "clinic", "education",
    "real estate", "manufacturing", "e-commerce", "service",
]


def _domain(url: str) -> str:
    try:
        return urlparse(url).hostname or ""
    except Exception:
        return ""


def extract_profile(pages: list[PageData], base_url: str) -> dict[str, Any]:
    """Deterministic extraction. Never requires LLM."""
    if not pages:
        return {"website_url": base_url, "error": "no pages fetched"}
    home = pages[0]
    all_text = "\n".join(p.text for p in pages)[:20000]
    low = all_text.lower()
    # company name: title before separators
    name = home.title.split("|")[0].split("-")[0].split(":")[0].strip()[:200]
    if not name:
        name = _domain(base_url)
    services = _extract_services(pages, all_text, name)
    # industries / geo heuristics
    industries = sorted({h for h in SERVICE_HINTS if h in low})[:10]
    emails = sorted({e for p in pages for e in p.emails})[:10]
    phones = sorted({t for p in pages for t in p.phones})[:10]
    social = sorted({s for p in pages for s in p.social_links})[:20]
    ctas = sorted({c for p in pages for c in p.ctas})[:20]
    desc = home.meta_description or all_text[:600]
    offers = _extract_offers(all_text)
    pricing = _extract_pricing(all_text)
    menu = _extract_menu(all_text)
    hours = _extract_hours(all_text)
    faqs = _extract_faqs(pages)
    # Generic deterministic audience/geography inference (no industry hardcode):
    # derive from location signals + CTA intent + top services.
    geography = _infer_geography(all_text, phones)
    target_customer = _infer_audience(all_text, services[:3], ctas, geography)
    return {
        "website_url": base_url,
        "domain": _domain(base_url),
        "company_name": name,
        "description": desc[:2000],
        "services": services,
        "products": [],
        "industries_served": industries,
        "target_customer": target_customer,
        "geography": geography,
        "pricing_info": pricing,
        "offers": offers,
        "menu": menu,
        "opening_hours": hours,
        "faqs": faqs,
        "emails": emails,
        "phones": phones,
        "social_links": social,
        "ctas": ctas,
        "keywords": industries,
        "value_propositions": services[:5],
        "pages_crawled": len(pages),
        "extraction": "deterministic",
    }


def _extract_offers(text: str) -> list[str]:
    """Sentences with offer/discount/deal intent (generic keywords)."""
    out: list[str] = []
    for sent in re.split(r"[.\n•|]+", text):
        s = sent.strip()
        if 8 < len(s) < 200 and any(
            k in s.lower() for k in ("offer", "discount", "% off", "deal",
                                     "coupon", "promo", "happy hour", "combo",
                                     "free delivery", "buy 1 get")
        ):
            if s not in out:
                out.append(s)
        if len(out) >= 10:
            break
    return out


def _extract_pricing(text: str) -> str:
    """First pricing-like snippets (currency + amount). Generic."""
    hits = re.findall(r"(?:₹|\$|€|£|Rs\.?)\s?[\d,]+(?:\.\d{1,2})?", text)
    if not hits:
        m = re.search(r"\b(price|pricing|starting at|from)\b.{0,60}", text, re.IGNORECASE)
        return m.group(0).strip()[:300] if m else ""
    seen: list[str] = []
    for h in hits:
        if h not in seen:
            seen.append(h)
        if len(seen) >= 8:
            break
    return ("Prices seen: " + ", ".join(seen))[:500]


def _extract_menu(text: str) -> list[str]:
    """Food/service menu-like lines (generic menu section heuristics)."""
    out: list[str] = []
    for sent in re.split(r"[.\n•|]+", text):
        s = sent.strip()
        if 4 < len(s) < 140 and any(
            k in s.lower() for k in ("menu", "starter", "mains", "biryani",
                                     "dessert", "drinks", "platter", "thali",
                                     "pizza", "burger", "combo meal")
        ):
            if s not in out:
                out.append(s)
        if len(out) >= 15:
            break
    return out


def _extract_hours(text: str) -> str:
    m = re.search(
        r"((?:open|opening|hours|timing)[^.\n]{0,120}|"
        r"\b\d{1,2}\s?(?:am|pm)\s?[-–to]+\s?\d{1,2}\s?(?:am|pm))",
        text, re.IGNORECASE,
    )
    return m.group(1).strip()[:300] if m else ""


def _extract_faqs(pages: list[PageData]) -> list[dict[str, str]]:
    """Question-like sentences with following answer (generic)."""
    faqs: list[dict[str, str]] = []
    for p in pages:
        for sent in re.split(r"[.\n]+", p.text):
            s = sent.strip()
            if 12 < len(s) < 200 and s.endswith("?"):
                if len(faqs) < 10:
                    faqs.append({"question": s, "page": p.url})
    return faqs


def _extract_services(pages: list[PageData], all_text: str, site_name: str) -> list[str]:
    """Services from headings, nav links and list items first (specific),
    hint-sentence scan as fallback. Title echoes excluded."""
    seen: list[str] = []

    def add(s: str) -> None:
        s = re.sub(r"\s+", " ", s).strip(" -–—•|")
        if (len(s) < 3 or len(s) > 120 or s.lower() == site_name.lower()
                or s in seen):
            return
        seen.append(s)

    nav_texts: list[str] = []
    for p in pages:
        for link in p.links:
            t = (link.get("text") or "").strip()
            if 2 < len(t) < 60 and t.lower() not in ("home", "login", "sign in"):
                nav_texts.append(t)
    # headings that look like offerings (skip generic hero fluff)
    for p in pages:
        for h in p.headings:
            if any(k in h.lower() for k in ("service", "offer", "solution", "product",
                                            "menu", "repair", "clean", "book",
                                            "hire", "plan", "price")):
                add(h)
    # nav items mentioning offerings
    for t in nav_texts:
        if any(k in t.lower() for k in SERVICE_HINTS):
            add(t)
    # list items (menus, feature bullets)
    for p in pages:
        for li in p.list_items[:40]:
            if 4 < len(li) < 120:
                add(li)
            if len(seen) >= 15:
                break
    # fallback: hint sentences from body
    if len(seen) < 5:
        for sent in re.split(r"[.\n•|]+", all_text):
            s = sent.strip()
            if 8 < len(s) < 160 and any(h in s.lower() for h in SERVICE_HINTS):
                add(s)
            if len(seen) >= 15:
                break
    return seen[:15]


def _infer_geography(text: str, phones: list[str]) -> str:
    """Generic location signals: city-like patterns + phone country hints."""
    import re

    # explicit "in <Place>" / city, state patterns (generic, not hardcoded list)
    m = re.search(
        r"\bin\s+([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,2}\s*,\s*[A-Z][A-Za-z.'-]+)",
        text,
    )
    if m:
        return m.group(1).strip()[:120]
    m = re.search(r"([A-Z][A-Za-z]+,\s*[A-Za-z]+\s*\d{5,6})", text)
    if m:
        return m.group(1).strip()[:120]
    joined_phones = " ".join(phones)
    if "+91" in joined_phones or "08328" in joined_phones:
        # country-level hint only; city comes from text when present
        city = re.search(r"\b([A-Z][a-z]+)\b", text)
        return f"{city.group(1)}, India" if city else "India"
    return ""


def _infer_audience(
    text: str, services: list[str], ctas: list[str], geography: str
) -> str:
    """Specific audience from detected nouns + geo + intent (no templates)."""
    low = text.lower()
    # service nouns actually present on the site
    nouns = sorted({h for h in SERVICE_HINTS if h in low})
    # who-terms the site itself uses
    who: list[str] = []
    for pat in (r"(?:for|serve|serving|trusted by)\s+([a-z][a-z\s&,'-]{2,60})",):
        for m in re.finditer(pat, low):
            cand = m.group(1).strip(" ,.-")
            if 3 < len(cand) < 70 and cand not in who:
                who.append(cand)
            if len(who) >= 3:
                break
    intents: list[str] = []
    if any(k in low for k in ("book", "table", "reserve", "order", "menu", "appointment")):
        intents.append("book/order")
    if any(k in low for k in ("quote", "demo", "trial", "sign up", "contact", "hire")):
        intents.append("get quotes/demos")
    parts: list[str] = []
    if who:
        parts.append("Who: " + "; ".join(who))
    if nouns:
        parts.append("Needs: " + ", ".join(nouns[:6]))
    elif services:
        parts.append("Needs: " + ", ".join(s.lower() for s in services[:3]))
    if geography:
        parts.append(f"Where: {geography}")
    if intents:
        parts.append("Intent: " + ", ".join(intents))
    if ctas:
        parts.append("Entry: " + ", ".join(ctas[:3]))
    if not parts:
        return "Could not determine audience from public content."
    return " | ".join(parts)[:1000]


def llm_enhance(profile: dict[str, Any], objective: str = "") -> dict[str, Any]:
    """Optional LLM assist for target_customer/positioning. Safe fallback."""
    try:
        from app.llm.gateway import LLMRequest, get_llm
    except Exception:
        return profile
    try:
        llm = get_llm()
        sys = ("You are a business analyst. Given website facts, infer target "
               "customers, positioning and ICP in 6 lines or less as JSON with keys "
               "target_customer, positioning, icp_industries, icp_geography.")
        import json

        user = json.dumps(profile)[:4000] + (f"\nContext: {objective}" if objective else "")
        out = llm.complete(LLMRequest(system=sys, user=user, json_mode=True)).text
        data = json.loads(out)
        for k in ("target_customer", "positioning", "icp_industries", "icp_geography"):
            if data.get(k):
                profile[k] = data[k]
        profile["extraction"] = "deterministic+llm"
    except Exception:
        pass
    return profile
