"""Calendar Agent (PRD §14).

Schedules, reschedules, and cancels meetings on the connected calendar
provider. All external event creation is approval-gated per §14.
"""
from __future__ import annotations

from typing import ClassVar

from app.agents.base import AgentContext, AgentResult, AgentTask
from app.agents.registry import register
from app.agents.runtime import call_tool
from app.approvals.service import requires_approval


class CalendarAgent:
    name = "calendar"
    description = "Schedules meetings and coordinates availability."
    allowed_tools: ClassVar[list[str]] = [
        "calendar.event.create",
        "calendar.event.list",
        "calendar.availability.find",
    ]

    def execute_approved(self, approval: dict, ctx: AgentContext) -> AgentResult:
        """After approval, actually create the event on the connector."""
        payload = approval.get("payload", {})
        res = call_tool(
            ctx,
            "calendar",
            "event.create",
            {
                "title": payload.get("title", "Meeting"),
                "start": payload.get("start"),
                "end": payload.get("end"),
                "attendees": payload.get("attendees", []),
            },
        )
        if not (res["ok"] and res["confirmed"]):
            return AgentResult(error=res.get("message") or "calendar create failed")
        return AgentResult(output={"event": res["data"]})

    def run(self, task: AgentTask, ctx: AgentContext) -> AgentResult:
        action = task.input.get("action", "schedule")
        if action == "schedule":
            availability = call_tool(ctx, "calendar", "availability.find", {})
            suggested = (availability.get("data") or {}).get("suggested") or [None]
            start = task.input.get("start") or suggested[0]
            if not start:
                return AgentResult(error="no available slot")
            # Per §14, creating an external calendar event for a client
            # meeting is approval-gated.
            if requires_approval("send_external_communication"):
                return AgentResult(
                    needs_approval={
                        "action": "send_external_communication",
                        "target_system": "calendar",
                        "description": f"Schedule {task.input.get('title', 'meeting')}",
                        "payload": {
                            "_operation": "event.create",
                            "title": task.input.get("title", "Kickoff meeting"),
                            "start": start,
                            "end": task.input.get("end"),
                            "attendees": task.input.get("attendees", []),
                        },
                    }
                )
            res = call_tool(
                ctx,
                "calendar",
                "event.create",
                {
                    "title": task.input.get("title", "Kickoff meeting"),
                    "start": start,
                    "end": task.input.get("end"),
                    "attendees": task.input.get("attendees", []),
                },
            )
            if not (res["ok"] and res["confirmed"]):
                return AgentResult(error=res.get("message") or "calendar create failed")
            return AgentResult(output={"event": res["data"]})
        if action == "list":
            res = call_tool(ctx, "calendar", "event.list", {})
            return AgentResult(output=res.get("data") or {})
        return AgentResult(error=f"unknown calendar action: {action}")


register(CalendarAgent())
