"""platform: document_chunks, pipelines, campaigns, payments

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), index=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), index=True),
        sa.Column("source", sa.String(255), server_default="upload", index=True),
        sa.Column("source_url", sa.String(500), nullable=True),
        sa.Column("chunk_index", sa.Integer(), server_default="0"),
        sa.Column("text", sa.Text(), server_default=""),
        sa.Column("content_hash", sa.String(64), index=True),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("embedding_model", sa.String(120), server_default=""),
        sa.Column("access_roles", sa.JSON(), server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_chunk_ws_hash", "document_chunks", ["company_id", "content_hash"])
    op.create_index("ix_chunk_ws_doc", "document_chunks", ["company_id", "document_id"])
    op.create_table(
        "pipelines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), index=True),
        sa.Column("name", sa.String(120), server_default="Sales", index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "pipeline_stages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), index=True),
        sa.Column("pipeline_id", sa.String(36), sa.ForeignKey("pipelines.id"), index=True),
        sa.Column("name", sa.String(120), index=True),
        sa.Column("position", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "campaigns",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), index=True),
        sa.Column("name", sa.String(120), index=True),
        sa.Column("goal", sa.Text(), server_default=""),
        sa.Column("icp", sa.JSON(), server_default="{}"),
        sa.Column("target_segment", sa.String(255), server_default=""),
        sa.Column("geography", sa.String(255), server_default=""),
        sa.Column("lead_source", sa.String(120), server_default="manual"),
        sa.Column("status", sa.String(40), server_default="draft", index=True),
        sa.Column("metrics", sa.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "payment_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), index=True),
        sa.Column("opportunity_id", sa.String(36), sa.ForeignKey("opportunities.id"), nullable=True, index=True),
        sa.Column("provider", sa.String(60), server_default="manual", index=True),
        sa.Column("amount", sa.Integer(), server_default="0"),
        sa.Column("currency", sa.String(10), server_default="INR"),
        sa.Column("status", sa.String(40), server_default="pending", index=True),
        sa.Column("provider_ref", sa.String(255), nullable=True, index=True),
        sa.Column("meta", sa.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("payment_requests")
    op.drop_table("campaigns")
    op.drop_table("pipeline_stages")
    op.drop_table("pipelines")
    op.drop_index("ix_chunk_ws_doc", table_name="document_chunks")
    op.drop_index("ix_chunk_ws_hash", table_name="document_chunks")
    op.drop_table("document_chunks")
