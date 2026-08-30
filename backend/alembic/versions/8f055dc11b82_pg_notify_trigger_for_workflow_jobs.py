"""pg_notify trigger for workflow_jobs

Revision ID: 8f055dc11b82
Revises: 9250bed55e39
Create Date: 2026-08-31 02:05:00.158275

Adds a trigger that fires `pg_notify('maicos_jobs', <new_id>)` whenever
a new row is inserted into `workflow_jobs`. Workers subscribe to that
channel and wake up the moment a job is enqueued, instead of
busy-polling.
"""
from collections.abc import Sequence

from alembic import op

revision: str = "8f055dc11b82"
down_revision: str | None = "9250bed55e39"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE OR REPLACE FUNCTION maicos_notify_new_job()
        RETURNS TRIGGER AS $$
        BEGIN
            PERFORM pg_notify('maicos_jobs', NEW.id::text);
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_maicos_workflow_jobs_notify ON workflow_jobs;
        CREATE TRIGGER trg_maicos_workflow_jobs_notify
        AFTER INSERT ON workflow_jobs
        FOR EACH ROW
        EXECUTE FUNCTION maicos_notify_new_job();
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP TRIGGER IF EXISTS trg_maicos_workflow_jobs_notify ON workflow_jobs;")
    op.execute("DROP FUNCTION IF EXISTS maicos_notify_new_job();")
