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


class SearchProviderStub:
    """Placeholder for a real search/business-directory API.

    Returns NOT_CONFIGURED until SEARCH_PROVIDER_API_KEY (or similar)
    is wired. Never invents prospects.
    """
    name = "search"

    def discover(self, query: str, *, limit: int = 20,
                 filters: dict | None = None) -> DiscoveryResult:
        import os
        key = os.environ.get("SEARCH_PROVIDER_API_KEY", "")
        if not key:
            return DiscoveryResult(
                ok=False, status="NOT_CONFIGURED",
                message=("lead discovery requires a configured search provider "
                         "(set SEARCH_PROVIDER_API_KEY). No leads were invented."))
        return DiscoveryResult(ok=False, status="FAILED",
                               message="search provider integration not yet implemented for this key")


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
register(SearchProviderStub())
