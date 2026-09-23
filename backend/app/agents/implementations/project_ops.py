"""Project Ops Agent (PRD §11) — DB-backed projects (workspace-scoped)."""
from __future__ import annotations

from typing import ClassVar

from app.agents.base import AgentContext, AgentResult, AgentTask
from app.agents.registry import register
from app.agents.runtime import call_tool
from app.models.orm import CompanyProject, CompanyTask


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
            project = CompanyProject(
                company_id=ws, name=str(task.input.get("name", "New Project"))[:255],
                owner=task.input.get("owner"), deadline=task.input.get("deadline"))
            ctx.db.add(project)
            ctx.db.flush()
            created = []
            for st in task.input.get("subtasks", []) or []:
                row = CompanyTask(company_id=ws, project_id=project.id,
                                  title=str(st)[:255])
                ctx.db.add(row)
                created.append({"id": row.id, "title": row.title, "state": "PENDING"})
            ctx.db.flush()
            call_tool(
                ctx,
                "crm",
                "activity.record",
                {"type": "project.created", "project_id": project.id,
                 "project_name": project.name,
                 "subtask_count": len(created)},
            )
            ctx.db.commit()
            return AgentResult(output={
                "project": {"id": project.id, "name": project.name,
                            "owner": project.owner, "deadline": project.deadline},
                "tasks": created})
        if action == "list_overdue":
            rows = ctx.db.query(CompanyProject).filter(
                CompanyProject.company_id == ws,
                CompanyProject.status == "active").all()
            return AgentResult(output={
                "overdue": [{"id": r.id, "name": r.name, "deadline": r.deadline}
                            for r in rows if r.deadline],
                "count": len(rows)})
        if action == "list_projects":
            rows = ctx.db.query(CompanyProject).filter(
                CompanyProject.company_id == ws).order_by(
                CompanyProject.created_at.desc()).limit(50).all()
            return AgentResult(output={
                "projects": [{"id": r.id, "name": r.name, "status": r.status,
                              "owner": r.owner} for r in rows]})
        return AgentResult(error=f"unknown project action: {action}")


register(ProjectOpsAgent())
