"""startup blueprints + workforce roles

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: str | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "startup_blueprints",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), index=True),
        sa.Column("idea", sa.Text(), server_default=""),
        sa.Column("sections", sa.JSON(), server_default="{}"),
        sa.Column("status", sa.String(40), server_default="draft", index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "workforce_roles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), index=True),
        sa.Column("title", sa.String(255), server_default=""),
        sa.Column("kind", sa.String(40), server_default="ai", index=True),
        sa.Column("status", sa.String(40), server_default="planned", index=True),
        sa.Column("detail", sa.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("workforce_roles")
    op.drop_table("startup_blueprints")
