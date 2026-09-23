"""business memory table

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "business_memory",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), index=True),
        sa.Column("kind", sa.String(60), server_default="fact", index=True),
        sa.Column("key", sa.String(200), server_default="", index=True),
        sa.Column("value", sa.Text(), server_default=""),
        sa.Column("meta", sa.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_memory_ws_kind_key", "business_memory",
                    ["company_id", "kind", "key"])


def downgrade() -> None:
    op.drop_index("ix_memory_ws_kind_key", table_name="business_memory")
    op.drop_table("business_memory")
