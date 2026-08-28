"""HR Agent (PRD §9).

Recruitment pipeline, onboarding, and employee request routing. All
state is persisted via the CRM activity stream and a dedicated HR
store so changes survive a restart.
"""
from __future__ import annotations

import uuid
from typing import Any, ClassVar

from app.agents.base import AgentContext, AgentResult, AgentTask
from app.agents.registry import register
from app.agents.runtime import call_tool
from app.integrations.store import JsonStore, stores_root

_CANDIDATES = JsonStore[dict[str, Any]](stores_root() / "hr.candidates.json")


def _candidates_for(workspace_id: str) -> list[dict[str, Any]]:
    return [c for c in _CANDIDATES.all() if c.get("workspace_id") == workspace_id]


class HRAgent:
    name = "hr"
    description = "Recruitment pipeline, onboarding and employee request routing."
    allowed_tools: ClassVar[list[str]] = [
        "crm.activity.record",
    ]

    def run(self, task: AgentTask, ctx: AgentContext) -> AgentResult:
        action = task.input.get("action")
        ws = ctx.principal.workspace_id
        if action == "add_candidate":
            cid = str(uuid.uuid4())
            rec = {
                "id": cid,
                "workspace_id": ws,
                "name": task.input.get("name"),
                "role": task.input.get("role"),
                "stage": "applied",
                "applied_at": task.input.get("applied_at"),
            }
            _CANDIDATES.put(cid, rec)
            call_tool(
                ctx,
                "crm",
                "activity.record",
                {"type": "candidate.added", "candidate_id": cid,
                 "role": rec["role"], "name": rec["name"]},
            )
            return AgentResult(output={"candidate": rec, "ok": True, "confirmed": True})
        if action == "list_candidates":
            return AgentResult(
                output={"candidates": _candidates_for(ws), "count": len(_candidates_for(ws))}
            )
        if action == "advance_stage":
            cid_raw = task.input.get("candidate_id")
            cid_lookup = cid_raw if isinstance(cid_raw, str) else None
            new_stage = task.input.get("stage")
            cand = _CANDIDATES.get(cid_lookup) if cid_lookup else None
            if not cand:
                return AgentResult(error=f"candidate not found: {cid}")
            cand["stage"] = new_stage
            _CANDIDATES.put(cid, cand)
            call_tool(
                ctx,
                "crm",
                "activity.record",
                {"type": "candidate.stage_changed", "candidate_id": cid, "stage": new_stage},
            )
            return AgentResult(output={"candidate": cand, "ok": True, "confirmed": True})
        if action == "create_onboarding_checklist":
            checklist = [
                "Send offer letter",
                "Collect ID and tax forms",
                "Provision laptop and accounts",
                "Schedule orientation",
                "Assign onboarding buddy",
            ]
            call_tool(
                ctx,
                "crm",
                "activity.record",
                {"type": "onboarding.checklist_created", "item_count": len(checklist)},
            )
            return AgentResult(
                output={"checklist": checklist, "ok": True, "confirmed": True}
            )
        return AgentResult(error=f"unknown HR action: {action}")


register(HRAgent())
