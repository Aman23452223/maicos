"""company_tasks assignee + due date

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: str | None = "b8c9d0e1f2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("company_tasks",
                  sa.Column("assignee_user_id", sa.String(36), nullable=True, index=True))
    op.add_column("company_tasks",
                  sa.Column("due_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    try:
        op.drop_column("company_tasks", "due_at")
    except Exception:
        pass
    try:
        op.drop_column("company_tasks", "assignee_user_id")
    except Exception:
        pass
