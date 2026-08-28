"""Pydantic schemas for API request/response."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)


class WorkspaceOut(BaseModel):
    id: str
    name: str
    autonomy_level: int


class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: str = Field(min_length=8)
    roles: list[str] = Field(default_factory=lambda: ["member"])


class UserOut(BaseModel):
    id: str
    email: EmailStr
    name: str
    roles: list[str]


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class CommandIn(BaseModel):
    objective: str = Field(min_length=1)
    conversation_id: str | None = None


class WorkflowOut(BaseModel):
    id: str
    title: str
    objective: str
    state: str
    plan: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class TaskOut(BaseModel):
    id: str
    agent_name: str
    title: str
    description: str
    state: str
    depends_on: list[str]
    output: dict[str, Any]
    error: str | None


class ApprovalOut(BaseModel):
    id: str
    workflow_id: str
    task_id: str | None
    action: str
    target_system: str
    description: str
    payload: dict[str, Any]
    status: str
    requested_by_agent: str
    created_at: datetime


class ApprovalDecisionIn(BaseModel):
    decision: str  # APPROVE | REJECT
    note: str | None = None


class AgentOut(BaseModel):
    id: str
    name: str
    description: str
    capabilities: list[str]
    allowed_tools: list[str]
    enabled: bool


class ToolOut(BaseModel):
    id: str
    name: str
    connector: str
    operations: list[str]
    enabled: bool


class DocumentCreate(BaseModel):
    name: str
    mime_type: str = "text/plain"
    access_roles: list[str] = Field(default_factory=list)
    content_base64: str | None = None
    text: str | None = None


class DocumentOut(BaseModel):
    id: str
    name: str
    mime_type: str
    access_roles: list[str]
    indexed: bool


class AuditOut(BaseModel):
    id: int
    actor: str
    action: str
    target_type: str
    target_id: str
    details: dict[str, Any]
    created_at: datetime

