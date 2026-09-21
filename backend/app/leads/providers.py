"""Provider-based lead discovery (Phase 3).

No hard-coded vendor. No fake success: unconfigured search returns
NOT_CONFIGURED instead of invented leads.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class Prospect:
    company_name: str = ""
    website: str = ""
    domain: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    industry: str = ""
    source: str = "manual"
    source_url: str = ""
    external_id: str = ""
    notes: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class DiscoveryResult:
    ok: bool
    status: str  # OK | NOT_CONFIGURED | FAILED
    prospects: list[Prospect] = field(default_factory=list)
    message: str = ""


class LeadDiscoveryProvider(Protocol):
    name: str

    def discover(self, query: str, *, limit: int = 20,
                 filters: dict[str, Any] | None = None) -> DiscoveryResult: ...


class ManualProvider:
    """Leads supplied directly by user/API. Always available."""
    name = "manual"

    def discover(self, query: str, *, limit: int = 20,
                 filters: dict | None = None) -> DiscoveryResult:
        return DiscoveryResult(ok=False, status="NOT_CONFIGURED",
                               message="manual provider needs explicit prospect list; use import endpoints")


class CsvImportProvider:
    name = "csv_import"

    def parse(self, content: str) -> list[Prospect]:
        out: list[Prospect] = []
        reader = csv.DictReader(io.StringIO(content))
        for row in reader:
            out.append(Prospect(
                company_name=(row.get("company_name") or row.get("name") or "").strip(),
                website=(row.get("website") or "").strip(),
                domain=(row.get("domain") or "").strip(),
                email=(row.get("email") or "").strip(),
                phone=(row.get("phone") or "").strip(),
                location=(row.get("location") or "").strip(),
                industry=(row.get("industry") or "").strip(),
                source="csv_import", notes=(row.get("notes") or "").strip(),
            ))
        return out

    def discover(self, query: str, *, limit: int = 20,
                 filters: dict | None = None) -> DiscoveryResult:
        return DiscoveryResult(ok=False, status="NOT_CONFIGURED",
                               message="csv provider needs file content via import endpoint")


class TavilySearchProvider:
    """Real search via Tavily API (https://tavily.com).

    Key from env SEARCH_PROVIDER_API_KEY or TAVILY_API_KEY (never hardcoded).
    Results normalized into Prospect objects. No fabrication.
    """
    name = "search"

    def discover(self, query: str, *, limit: int = 20,
                 filters: dict | None = None) -> DiscoveryResult:
        import os
        from urllib.parse import urlparse

        key = os.environ.get("SEARCH_PROVIDER_API_KEY",
                             os.environ.get("TAVILY_API_KEY", ""))
        if not key:
            return DiscoveryResult(
                ok=False, status="NOT_CONFIGURED",
                message=("lead discovery requires a configured search provider "
                         "(set SEARCH_PROVIDER_API_KEY). No leads were invented."))
        if not query.strip():
            return DiscoveryResult(ok=False, status="FAILED",
                                   message="empty query")
        limit = min(max(int(limit or 5), 1), 20)
        try:
            import httpx
        except Exception as exc:
            return DiscoveryResult(ok=False, status="FAILED",
                                   message=f"http client unavailable: {exc}")
        try:
            resp = httpx.post(
                "https://api.tavily.com/search",
                json={"api_key": key, "query": query,
                      "max_results": limit, "search_depth": "advanced",
                      "include_answer": False},
                timeout=25.0,
            )
        except Exception as exc:
            return DiscoveryResult(ok=False, status="PROVIDER_ERROR",
                                   message=f"tavily request failed: {exc}"[:300])
        if resp.status_code in (401, 403):
            return DiscoveryResult(ok=False, status="INVALID_CONFIGURATION",
                                   message="tavily key rejected (401/403)")
        if resp.status_code == 429:
            return DiscoveryResult(ok=False, status="PROVIDER_ERROR",
                                   message="tavily rate limit (429)")
        if resp.status_code != 200:
            return DiscoveryResult(ok=False, status="PROVIDER_ERROR",
                                   message=f"tavily HTTP {resp.status_code}"[:200])
        try:
            data = resp.json()
        except Exception:
            return DiscoveryResult(ok=False, status="PROVIDER_ERROR",
                                   message="tavily returned non-JSON")
        prospects: list[Prospect] = []
        for item in data.get("results", [])[:limit]:
            url = str(item.get("url", ""))
            title = str(item.get("title", "")).strip()[:200]
            try:
                host = (urlparse(url).hostname or "").removeprefix("www.")
            except Exception:
                host = ""
            name = title.split("|")[0].split("-")[0].strip()[:200] or host
            if not name and not url:
                continue
            prospects.append(Prospect(
                company_name=name, website=url, domain=host,
                location=str((filters or {}).get("location", ""))[:255],
                industry=str((filters or {}).get("industry", ""))[:120],
                source="tavily_search", source_url=url,
                external_id=url,
                notes=str(item.get("content", ""))[:1000],
            ))
        if not prospects:
            return DiscoveryResult(ok=False, status="PROVIDER_ERROR",
                                   message="tavily returned zero results")
        return DiscoveryResult(ok=True, status="OK", prospects=prospects,
                               message=f"{len(prospects)} prospects from Tavily")


_REGISTRY: dict[str, LeadDiscoveryProvider] = {}


def register(p: LeadDiscoveryProvider) -> None:
    _REGISTRY[p.name] = p


def get(name: str) -> LeadDiscoveryProvider:
    if name not in _REGISTRY:
        raise KeyError(f"unknown discovery provider: {name}")
    return _REGISTRY[name]


def available() -> list[str]:
    return sorted(_REGISTRY)


register(ManualProvider())
register(CsvImportProvider())
register(TavilySearchProvider())
# Back-compat alias for older imports/tests
SearchProviderStub = TavilySearchProvider
