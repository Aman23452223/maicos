"""Normalization + dedup helpers (no fake data)."""
from __future__ import annotations

import re
from urllib.parse import urlparse


def norm_email(v: str | None) -> str | None:
    if not v:
        return None
    v = v.strip().lower()
    return v if "@" in v else None


def norm_name(v: str | None) -> str:
    v = (v or "").strip().lower()
    v = re.sub(r"\s+", " ", v)
    v = re.sub(r"\b(pvt|ltd|llc|inc|corp|llp|co)\b\.?", "", v).strip()
    return v[:255]


def domain_of(url_or_domain: str | None) -> str | None:
    if not url_or_domain:
        return None
    s = url_or_domain.strip().lower()
    if "://" not in s:
        s = "https://" + s
    try:
        h = urlparse(s).hostname or ""
        h = h.removeprefix("www.")
        return h or None
    except Exception:
        return None
