"""End-to-end smoke test against the in-memory connector backend.

This exercises the orchestrator path without a database so the MVP can
be validated before Postgres is wired up. The full system uses SQLAlchemy
+ Alembic for persistence.
"""
from __future__ import annotations

import os
import sys

# Allow running with `python -m` from the backend directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import agents  # noqa: F401  (registers agents + connectors)
from app.agents.base import AgentContext, AgentTask
from app.agents.implementations.ai_manager import build_plan
from app.agents.implementations.communication import CommunicationAgent
from app.agents.implementations.knowledge import KnowledgeAgent
from app.agents.implementations.sales_crm import SalesCRMAgent
from app.agents.runtime import call_tool
from app.core.context import Principal


def main() -> int:
    principal = Principal(
        user_id="user-1",
        workspace_id="ws-1",
        roles=("owner",),
    )

    plan = build_plan("Onboard the new client ABC.")
    assert plan["intent"] == "onboard_client", plan
    assert {t["agent"] for t in plan["tasks"]} == {
        "sales_crm",
        "project_ops",
        "communication",
    }, plan

    ctx = AgentContext(
        db=None,
        principal=principal,
        workflow_id="wf-1",
        task_id="t-1",
        run_id="r-1",
        shared={"agent_name": "sales_crm"},
    )
    sales = SalesCRMAgent()
    res = sales.run(
        AgentTask(title="Create contact", description="", input={"action": "create_contact", "name": "Alice", "email": "[email protected]"}),
        ctx,
    )
    assert res.error is None, res
    assert "contact" in res.output

    ctx.shared = {"agent_name": "communication"}
    # Sending an external message should request approval (default policy).
    com = CommunicationAgent()
    res = com.run(
        AgentTask(title="Send welcome", description="", input={"action": "send", "to": "[email protected]", "subject": "Hi", "body": "Welcome"}),
        ctx,
    )
    assert res.needs_approval is not None, res
    assert res.needs_approval["action"] == "send_external_communication"

    ctx.shared = {"agent_name": "knowledge"}
    kn = KnowledgeAgent()
    res = kn.run(AgentTask(title="Search", description="Find SOP", input={"query": "refund policy"}), ctx)
    assert "results" in res.output

    # Verify the safe tool call path authorizes correctly.
    ctx.shared = {"agent_name": "communication"}
    ok = call_tool(ctx, "email", "message.draft", {"to": "[email protected]"})
    assert ok["ok"] and ok["confirmed"]

    print("smoke test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
