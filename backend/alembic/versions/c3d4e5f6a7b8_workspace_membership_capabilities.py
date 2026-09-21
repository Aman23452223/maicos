"""workspace membership + business context + integrations

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(bind, table: str, col: str) -> bool:
    insp = sa.inspect(bind)
    try:
        return col in [c["name"] for c in insp.get_columns(table)]
    except Exception:
        return False


def upgrade() -> None:
    bind = op.get_bind()
    for col, typ, default in [
        ("slug", sa.String(120), None),
        ("status", sa.String(40), "active"),
        ("config", sa.JSON(), None),
        ("plan", sa.JSON(), None),
        ("updated_at", sa.DateTime(timezone=True), None),
    ]:
        if not _has_column(bind, "companies", col):
            op.add_column("companies", sa.Column(col, typ, server_default=default) if isinstance(default, str) else sa.Column(col, typ))
    try:
        op.create_index("ix_companies_slug", "companies", ["slug"], unique=False)
    except Exception:
        pass
    op.create_table(
        "workspace_memberships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), index=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), index=True),
        sa.Column("role", sa.String(40), server_default="member", index=True),
        sa.Column("status", sa.String(40), server_default="active", index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_membership_user_ws", "workspace_memberships", ["user_id", "company_id"], unique=True)
    op.create_table(
        "workspace_integrations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), index=True),
        sa.Column("provider", sa.String(120), index=True),
        sa.Column("status", sa.String(40), server_default="not_configured", index=True),
        sa.Column("meta", sa.JSON(), server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_wsintegration_ws_provider", "workspace_integrations", ["company_id", "provider"], unique=True)
    for col in ["customer_segments", "business_goals", "enabled_capabilities",
                "working_hours", "timezone"]:
        if not _has_column(bind, "business_profiles", col):
            typ = sa.JSON() if col != "timezone" else sa.String(80)
            op.add_column("business_profiles", sa.Column(col, typ))


def downgrade() -> None:
    op.drop_index("ix_wsintegration_ws_provider", table_name="workspace_integrations")
    op.drop_table("workspace_integrations")
    op.drop_index("ix_membership_user_ws", table_name="workspace_memberships")
    op.drop_table("workspace_memberships")
    for col in ["customer_segments", "business_goals", "enabled_capabilities",
                "working_hours", "timezone"]:
        try:
            op.drop_column("business_profiles", col)
        except Exception:
            pass
    for col in ["updated_at", "plan", "config", "status", "slug"]:
        try:
            op.drop_column("companies", col)
        except Exception:
            pass
