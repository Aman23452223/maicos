"""Redis-backed workflow job queue (PRD §15 async workers, §13)."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

import redis

from app.core.config import get_settings

QUEUE_KEY = "maicos:workflow_jobs"


def get_redis() -> redis.Redis:
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


def enqueue(job: Job) -> None:
    get_redis().rpush(QUEUE_KEY, job.to_json())


def dequeue(timeout: int = 5) -> Job | None:
    r = get_redis()
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
