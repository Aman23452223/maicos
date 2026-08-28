"""Per-workflow execution budgets (PRD risk: agent loops / cost explosion)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BudgetExceeded(Exception):
    reason: str

    def __str__(self) -> str:
        return self.reason


# Sensible defaults; expose via settings in production.
MAX_TASK_ATTEMPTS = 2
MAX_TASKS_PER_WORKFLOW = 50
MAX_TOOL_CALLS_PER_TASK = 10
MAX_RUNNING_SECONDS = 120


def check_workflow(task_count: int) -> None:
    if task_count > MAX_TASKS_PER_WORKFLOW:
        raise BudgetExceeded(
            f"workflow has {task_count} tasks, max is {MAX_TASKS_PER_WORKFLOW}"
        )


def check_task(tool_call_count: int) -> None:
    if tool_call_count > MAX_TOOL_CALLS_PER_TASK:
        raise BudgetExceeded(
            f"task exceeded {MAX_TOOL_CALLS_PER_TASK} tool calls"
        )
