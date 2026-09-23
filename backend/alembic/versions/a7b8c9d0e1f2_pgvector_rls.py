"""pgvector column + RLS policies (Postgres only; no-op elsewhere)

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
"""
from collections.abc import Sequence

from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RLS_TABLES = ("leads", "crm_contacts", "crm_companies", "opportunities",
              "documents", "document_chunks", "business_memory", "workflows",
              "approvals")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute('ALTER TABLE "document_chunks" '
               'ADD COLUMN IF NOT EXISTS "embedding_vector" vector(1536)')
    for t in RLS_TABLES:
        op.execute(f'ALTER TABLE "{t}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'DROP POLICY IF EXISTS service_all ON "{t}"')
        op.execute(f'CREATE POLICY service_all ON "{t}" '
                   f'FOR ALL TO PUBLIC USING (true) WITH CHECK (true)')


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for t in RLS_TABLES:
        op.execute(f'DROP POLICY IF EXISTS service_all ON "{t}"')
        op.execute(f'ALTER TABLE "{t}" DISABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "document_chunks" DROP COLUMN IF EXISTS "embedding_vector"')
