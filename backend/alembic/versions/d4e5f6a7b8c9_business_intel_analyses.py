"""business intel analyses (typed research, re-analysis merge)

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "business_intel_analyses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), index=True),
        sa.Column("analysis_type", sa.String(40), server_default="my_business", index=True),
        sa.Column("source_url", sa.String(500), server_default=""),
        sa.Column("normalized_url", sa.String(500), server_default="", index=True),
        sa.Column("profile", sa.JSON(), server_default="{}"),
        sa.Column("document_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(40), server_default="ready", index=True),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("last_analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_intel_ws_type_url", "business_intel_analyses",
                    ["company_id", "analysis_type", "normalized_url"])


def downgrade() -> None:
    op.drop_index("ix_intel_ws_type_url", table_name="business_intel_analyses")
    op.drop_table("business_intel_analyses")
