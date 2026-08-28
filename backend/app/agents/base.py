"""Agent base class and registry (PRD §7, FR-06).

Each agent is a class with:
  * `name` - the registry key
  * `allowed_tools` - the authorized tool surface
  * `run(task, context)` - the unit of work

The agent runtime records every tool call, handles retries, and routes
irreversible actions through the approval center.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Protocol

from app.core.context import Principal


@dataclass
class AgentTask:
    title: str
    description: str
    input: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentContext:
    db: Any
    principal: Principal
    workflow_id: str
    task_id: str
    run_id: str
    shared: dict[str, Any] = field(default_factory=dict)
    log: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class AgentResult:
    output: dict[str, Any] = field(default_factory=dict)
    needs_approval: dict[str, Any] | None = None
    error: str | None = None


class Agent(Protocol):
    name: str
    description: str
    allowed_tools: ClassVar[list[str]]

    def run(self, task: AgentTask, ctx: AgentContext) -> AgentResult: ...

    def execute_approved(
        self, approval: dict, ctx: AgentContext
    ) -> AgentResult:
        """Replay a previously-approved action.

        Default: raise NotImplementedError so the engine can fall
        back to its connector-level replay path. Agents that need
        richer semantics (e.g. creating a real invoice after a
        finance approval) override this.
        """
        raise NotImplementedError


_REGISTRY: dict[str, Agent] = {}


def register(agent: Any) -> None:
    _REGISTRY[agent.name] = agent


def get(name: str) -> Agent:
    if name not in _REGISTRY:
        raise KeyError(f"agent not registered: {name}")
    return _REGISTRY[name]


def list_agents() -> list[dict[str, Any]]:
    return [
        {"name": a.name, "description": a.description, "allowed_tools": a.allowed_tools}
        for a in _REGISTRY.values()
    ]


