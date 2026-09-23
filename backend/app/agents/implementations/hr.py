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

    def _start_hiring(self, task: AgentTask, ctx: AgentContext) -> AgentResult:
        """Human hiring pipeline start: role record + approval-gated plan."""
        from app.models.orm import WorkforceRole

        ws = ctx.principal.workspace_id
        role_title = str(task.input.get("role", "") or "").strip()
        if not role_title:
            import re as _re
            m = _re.search(r"(?:hire|hiring|recruit|need|looking for)\s+(?:a\s+|an\s+)?([A-Za-z][\w\s/-]{2,60})",
                           f"{task.input.get('objective', '')} {task.description}",
                           _re.IGNORECASE)
            role_title = m.group(1).strip() if m else ""
        if not role_title:
            return AgentResult(
                needs_input={"question": "Which role should I hire for? (title + key requirements)",
                             "field": "_answer"}, output={})
        row = WorkforceRole(company_id=ws, title=role_title[:255], kind="human",
                            status="sourcing")
        ctx.db.add(row)
        ctx.db.flush()
        call_tool(ctx, "crm", "activity.record",
                  {"type": "hiring.started", "role": role_title, "role_id": row.id})
        ctx.db.commit()
        return AgentResult(
            needs_approval={
                "action": "hire_human",
                "target_system": "hr",
                "description": (f"Start hiring pipeline for '{role_title}': source, "
                                f"screen, shortlist, interview, offer. Human decisions "
                                f"at every stage."),
                "payload": {"_operation": "hiring.start", "role_id": row.id,
                            "role": role_title},
            })

    def execute_approved(self, approval: dict, ctx: AgentContext) -> AgentResult:
        payload = approval.get("payload", {})
        if payload.get("_operation") == "hiring.start":
            return AgentResult(output={"hiring": "approved",
                                       "role_id": payload.get("role_id"),
                                       "next": "sourcing -> screening -> interview -> offer"})
        raise NotImplementedError

    def run(self, task: AgentTask, ctx: AgentContext) -> AgentResult:
        action = task.input.get("action")
        ws = ctx.principal.workspace_id
        if action == "triage_hiring":
            # Mandatory AI-vs-human distinction. Decisive keywords route
            # directly; ambiguous requests ask instead of guessing.
            text = f"{task.input.get('objective', '')} {task.description}".lower()
            human_hit = any(k in text for k in
                            ("hire", "hiring", "recruit", "salary", "payroll",
                             "employee", "resume", "interview", "onboard human"))
            ai_hit = any(k in text for k in
                         ("ai agent", "ai worker", "automate", "bot ", "code it",
                          "build it with ai"))
            if human_hit and not ai_hit:
                return self._start_hiring(task, ctx)
            if ai_hit and not human_hit:
                return AgentResult(output={
                    "route": "ai_workforce",
                    "message": ("Routed to AI workforce planning. Describe the software "
                                "outcome and the engineering plan will be composed.")})
            return AgentResult(
                needs_input={
                    "question": ("Do you want (A) HUMAN hires — recruitment pipeline "
                                 "with approvals, or (B) AI workers — software built by "
                                 "the AI workforce? Reply A or B."),
                    "field": "_answer",
                },
                output={})
        if action == "start_hiring":
            return self._start_hiring(task, ctx)
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
                return AgentResult(error=f"candidate not found: {cid_lookup}")
            cand["stage"] = new_stage
            _CANDIDATES.put(cid_lookup, cand)
            call_tool(
                ctx,
                "crm",
                "activity.record",
                {"type": "candidate.stage_changed", "candidate_id": cid_lookup, "stage": new_stage},
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
