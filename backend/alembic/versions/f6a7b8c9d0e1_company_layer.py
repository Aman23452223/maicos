"""company operating layer: decisions, signals, initiatives, projects, events

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "company_decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), index=True),
        sa.Column("title", sa.String(255), server_default=""),
        sa.Column("context", sa.Text(), server_default=""),
        sa.Column("decided_by", sa.String(120), server_default=""),
        sa.Column("status", sa.String(40), server_default="decided", index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "company_signals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), index=True),
        sa.Column("kind", sa.String(40), server_default="issue", index=True),
        sa.Column("severity", sa.String(40), server_default="medium", index=True),
        sa.Column("title", sa.String(255), server_default=""),
        sa.Column("detail", sa.Text(), server_default=""),
        sa.Column("status", sa.String(40), server_default="open", index=True),
        sa.Column("meta", sa.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_signal_ws_kind_status", "company_signals",
                    ["company_id", "kind", "status"])
    op.create_table(
        "company_initiatives",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), index=True),
        sa.Column("goal_id", sa.String(40), nullable=True, index=True),
        sa.Column("title", sa.String(255), server_default=""),
        sa.Column("status", sa.String(40), server_default="planned", index=True),
        sa.Column("progress", sa.Integer(), server_default="0"),
        sa.Column("workflow_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "company_projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), index=True),
        sa.Column("name", sa.String(255), server_default=""),
        sa.Column("owner", sa.String(120), nullable=True),
        sa.Column("deadline", sa.String(64), nullable=True),
        sa.Column("status", sa.String(40), server_default="active", index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "company_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), index=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("company_projects.id"), index=True),
        sa.Column("title", sa.String(255), server_default=""),
        sa.Column("state", sa.String(40), server_default="PENDING", index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "company_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), index=True),
        sa.Column("type", sa.String(120), index=True),
        sa.Column("payload", sa.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
    )
    op.create_index("ix_event_ws_type_created", "company_events",
                    ["company_id", "type", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_event_ws_type_created", table_name="company_events")
    op.drop_table("company_events")
    op.drop_table("company_tasks")
    op.drop_table("company_projects")
    op.drop_table("company_initiatives")
    op.drop_index("ix_signal_ws_kind_status", table_name="company_signals")
    op.drop_table("company_signals")
    op.drop_table("company_decisions")
