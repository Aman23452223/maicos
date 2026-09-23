"""In-process sliding-window rate limiter (single-process guard).

Documented limitation: counters live in memory, so each worker process
enforces independently. Safe default for abuse containment, not a
distributed quota system.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

_WINDOWS: dict[str, deque[float]] = defaultdict(deque)

MAX_COMMANDS_PER_MINUTE = 30


def check(key: str, limit: int = MAX_COMMANDS_PER_MINUTE,
          window_s: int = 60) -> tuple[bool, int]:
    """Returns (allowed, retry_after_seconds)."""
    now = time.monotonic()
    q = _WINDOWS[key]
    while q and q[0] <= now - window_s:
        q.popleft()
    if len(q) >= limit:
        return False, int(q[0] + window_s - now) + 1
    q.append(now)
    return True, 0
