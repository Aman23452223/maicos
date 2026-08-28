"""Project / Operations Agent (PRD §11).

Creates projects and tasks; tracks deadlines and status. The MVP
implementation records projects through the CRM's activity stream so
the change is observable in the same on-disk store as the other
business records.
"""
from __future__ import annotations

import uuid
from typing import Any, ClassVar

from app.agents.base import AgentContext, AgentResult, AgentTask
from app.agents.registry import register
from app.agents.runtime import call_tool

_PROJECTS: dict[str, list[dict[str, Any]]] = {}


class ProjectOpsAgent:
    name = "project_ops"
    description = "Creates projects and tasks; tracks deadlines and status."
    allowed_tools: ClassVar[list[str]] = [
        "crm.activity.record",
    ]

    def run(self, task: AgentTask, ctx: AgentContext) -> AgentResult:
        action = task.input.get("action", "create_project")
        ws = ctx.principal.workspace_id
        if action == "create_project":
            pid = str(uuid.uuid4())
            project = {
                "id": pid,
                "name": task.input.get("name", "New Project"),
                "owner": task.input.get("owner"),
                "deadline": task.input.get("deadline"),
            }
            _PROJECTS.setdefault(ws, []).append(project)
            subtasks = task.input.get("subtasks", [])
            created = [
                {
                    "id": str(uuid.uuid4()),
                    "project_id": pid,
                    "title": st,
                    "state": "PENDING",
                }
                for st in subtasks
            ]
            # Record the project creation in the CRM activity stream so
            # the change is observable on disk and auditable.
            call_tool(
                ctx,
                "crm",
                "activity.record",
                {
                    "type": "project.created",
                    "project_id": pid,
                    "project_name": project["name"],
                    "subtask_count": len(created),
                },
            )
            return AgentResult(output={"project": project, "tasks": created})
        if action == "list_overdue":
            return AgentResult(output={"overdue": []})
        return AgentResult(error=f"unknown project action: {action}")


register(ProjectOpsAgent())

