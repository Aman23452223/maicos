"""Webhook signature validation + replay protection (Phase 22)."""
from __future__ import annotations

import hashlib
import hmac
import os
import time


def _secret(provider: str) -> str:
    provider = (provider or "").upper()
    return os.environ.get(f"{provider}_WEBHOOK_SECRET",
                          os.environ.get("WEBHOOK_SECRET", ""))


def verify(provider: str, *, raw_body: bytes, headers: dict,
           max_skew_s: int = 300) -> tuple[bool, str]:
    """Validate HMAC-SHA256 signature. Headers: x-signature, x-timestamp.

    Generic across providers: Stripe-style (t,v1) and simple hex digest both
    accepted. Returns (ok, reason). Never processes unverified events.
    """
    secret = _secret(provider)
    if not secret:
        return False, "NOT_CONFIGURED: webhook secret not set"
    sig = str(headers.get("x-signature") or headers.get("stripe-signature") or "")
    ts = str(headers.get("x-timestamp") or "")
    if ts:
        try:
            if abs(time.time() - int(ts)) > max_skew_s:
                return False, "stale timestamp (replay protection)"
        except ValueError:
            return False, "invalid timestamp"
    if not sig:
        return False, "missing signature"
    # support "t=...,v1=..." format
    if "v1=" in sig:
        try:
            parts = dict(p.split("=", 1) for p in sig.split(",") if "=" in p)
            sig = parts.get("v1", sig)
            ts = parts.get("t", ts)
        except Exception:
            pass
    msg = (ts.encode() + b"." + raw_body) if ts else raw_body
    expected = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig.strip()):
        return False, "invalid signature"
    return True, "OK"
