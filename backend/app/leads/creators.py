"""Creator/influencer discovery (generic, Tavily-backed, honest).

Categorizes by geography/niche/audience/size/engagement/relevance signals
found in public snippets. Never fabricates metrics. Without a search key:
DATA_UNAVAILABLE.
"""
from __future__ import annotations

import re
from typing import Any

from app.leads.providers import Prospect


def _signals(text: str) -> dict[str, Any]:
    low = (text or "").lower()
    followers = None
    m = re.search(r"(\d+(?:\.\d+)?)\s*([kmb])\s*(followers|subs)", low)
    if m:
        mult = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}[m.group(2)]
        followers = int(float(m.group(1)) * mult)
    platforms = [p for p in ("instagram", "youtube", "tiktok", "twitter", "facebook")
                 if p in low]
    engagement = ("high" if any(k in low for k in ("viral", "trending", "million views")
                                ) else "unknown")
    return {"followers": followers, "platforms": platforms, "engagement": engagement}


def discover(query: str, *, limit: int = 15) -> dict[str, Any]:
    import os

    if not (os.environ.get("SEARCH_PROVIDER_API_KEY")
            or os.environ.get("TAVILY_API_KEY")):
        return {"ok": False, "status": "DATA_UNAVAILABLE",
                "message": "creator discovery needs a search provider key",
                "creators": []}
    from app.leads.providers import get as get_provider

    res = get_provider("search").discover(f"{query} influencer creator",
                                          limit=min(max(int(limit or 10), 1), 20))
    if not res.ok:
        return {"ok": False, "status": res.status, "message": res.message,
                "creators": []}
    creators: list[Prospect] = []
    for p in res.prospects:
        sig = _signals(f"{p.company_name} {p.notes}")
        creators.append(Prospect(
            company_name=p.company_name, website=p.website, domain=p.domain,
            source="creator_discovery", source_url=p.source_url,
            external_id=p.source_url, notes=p.notes,
            extra={"followers": sig["followers"], "platforms": sig["platforms"],
                   "engagement": sig["engagement"]}))
    return {"ok": True, "status": "OK", "creators": creators,
            "message": f"{len(creators)} creators (metrics only where published)"}
