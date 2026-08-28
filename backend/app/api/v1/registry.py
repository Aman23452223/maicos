"""Agent registry and tool / integration admin routes (FR-13)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.registry import list_agents
from app.audit.service import record
from app.core.context import Principal
from app.core.security import get_current_principal, require_role
from app.db.session import get_db
from app.integrations.base import list_connectors
from app.models.orm import Agent, Tool
from app.schemas import AgentOut, ToolOut

router = APIRouter(tags=["registry"])


@router.get("/agents", response_model=list[AgentOut])
def get_agents(
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> list[AgentOut]:
    rows = db.query(Agent).filter(Agent.company_id == p.workspace_id).all()
    if rows:
        return [
            AgentOut(
                id=a.id,
                name=a.name,
                description=a.description,
                capabilities=a.capabilities or [],
                allowed_tools=a.allowed_tools or [],
                enabled=a.enabled,
            )
            for a in rows
        ]
    # Fall back to the in-process registry so first-run users see agents.
    return [
        AgentOut(
            id=f"builtin:{a['name']}",
            name=a["name"],
            description=a["description"],
            capabilities=[],
            allowed_tools=a["allowed_tools"],
            enabled=True,
        )
        for a in list_agents()
    ]


@router.get("/tools", response_model=list[ToolOut])
def get_tools(
    p: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> list[ToolOut]:
    rows = db.query(Tool).filter(Tool.company_id == p.workspace_id).all()
    if rows:
        return [
            ToolOut(
                id=t.id,
                name=t.name,
                connector=t.connector,
                operations=t.operations or [],
                enabled=t.enabled,
            )
            for t in rows
        ]
    return [
        ToolOut(
            id=f"builtin:{c['name']}",
            name=c["name"],
            connector=c["name"],
            operations=c["operations"],
            enabled=True,
        )
        for c in list_connectors()
    ]


@router.post("/agents/{agent_id}/enable", response_model=AgentOut)
def set_agent_enabled(
    agent_id: str,
    enabled: bool,
    p: Principal = Depends(require_role("admin", "owner")),
    db: Session = Depends(get_db),
) -> AgentOut:
    a = db.get(Agent, agent_id)
    if not a or a.company_id != p.workspace_id:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="agent not found")
    a.enabled = enabled
    record(
        db,
        company_id=p.workspace_id,
        actor=p.user_id,
        action="agent.toggle",
        target_type="agent",
        target_id=a.id,
        details={"enabled": enabled},
    )
    db.commit()
    return AgentOut(
        id=a.id,
        name=a.name,
        description=a.description,
        capabilities=a.capabilities or [],
        allowed_tools=a.allowed_tools or [],
        enabled=a.enabled,
    )

