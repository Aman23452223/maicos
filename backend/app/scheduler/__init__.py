"""Scheduled and event-triggered workflow entry points (FR-14, §13)."""
from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler

_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler()
    return _scheduler


def start() -> None:
    s = get_scheduler()
    if not s.running:
        s.start()


def shutdown() -> None:
    s = get_scheduler()
    if s.running:
        s.shutdown(wait=False)

