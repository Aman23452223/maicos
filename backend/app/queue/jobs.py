"""Redis-backed workflow job queue (PRD §15 async workers, §13).

When REDIS_URL is empty (the default in production without Redis
configured), the queue degrades to a no-op: `enqueue` returns False
after a structured warning, `dequeue` returns None, and the worker
loop simply exits. This lets the rest of the app run end-to-end
without requiring Redis. To enable async workflows, scheduled jobs,
and event-driven workflows, set REDIS_URL in the environment.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

import redis

from app.core.config import get_settings
from app.core.logging import get_logger

QUEUE_KEY = "maicos:workflow_jobs"

log = get_logger("queue")
_disabled_warned: bool = False


def redis_enabled() -> bool:
    return bool(get_settings().redis_url.strip())


def get_redis() -> redis.Redis | None:
    if not redis_enabled():
        return None
    return redis.from_url(get_settings().redis_url, decode_responses=True)


@dataclass
class Job:
    id: str
    workflow_id: str
    workspace_id: str
    trigger: str  # "on_demand" | "scheduled" | "event"
    payload: dict[str, Any]

    def to_json(self) -> str:
        return json.dumps({
            "id": self.id,
            "workflow_id": self.workflow_id,
            "workspace_id": self.workspace_id,
            "trigger": self.trigger,
            "payload": self.payload,
        })


def enqueue(job: Job) -> bool:
    """Enqueue a workflow job. Returns True if queued, False if dropped.

    Returns False (and logs once) when Redis is not configured. Callers
    that need a guarantee should check the return value or query
    `redis_enabled()` first.
    """
    global _disabled_warned
    r = get_redis()
    if r is None:
        if not _disabled_warned:
            log.warning(
                "queue.disabled",
                reason="REDIS_URL is empty; jobs will be dropped. Set REDIS_URL to enable async workflows.",
            )
            _disabled_warned = True
        return False
    r.rpush(QUEUE_KEY, job.to_json())
    return True


def dequeue(timeout: int = 5) -> Job | None:
    r = get_redis()
    if r is None:
        return None
    item = r.blpop(QUEUE_KEY, timeout=timeout)
    if not item:
        return None
    _, raw = item
    data = json.loads(raw)
    return Job(
        id=data["id"],
        workflow_id=data["workflow_id"],
        workspace_id=data["workspace_id"],
        trigger=data["trigger"],
        payload=data["payload"],
    )


def new_job_id() -> str:
    return str(uuid.uuid4())
