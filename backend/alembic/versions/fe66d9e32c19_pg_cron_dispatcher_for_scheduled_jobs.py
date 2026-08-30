"""pg_cron dispatcher for scheduled_jobs

Revision ID: fe66d9e32c19
Revises: 8f055dc11b82
Create Date: 2026-08-31 02:05:18.113923

Schedules a pg_cron job that runs every minute and:

  1. selects due rows from `scheduled_jobs` (FOR UPDATE SKIP LOCKED)
  2. inserts a `workflow_jobs` row per match (trigger = 'scheduled')
  3. marks the `scheduled_jobs` row as dispatched

pg_cron is enabled in Supabase under Database → Extensions. The
`cron.schedule()` call is wrapped in a DO block so the migration
remains a no-op when pg_cron is not installed (e.g. local dev,
Railway Postgres).
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "fe66d9e32c19"
down_revision: str | None = "8f055dc11b82"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


DISPATCHER_SQL = """
DO $$
DECLARE
    job_id int;
BEGIN
    -- Drop any prior copy so re-running this migration is idempotent.
    SELECT scheduleid INTO job_id
    FROM cron.job
    WHERE jobname = 'maicos-dispatch-scheduled-workflows';
    IF job_id IS NOT NULL THEN
        PERFORM cron.unschedule(job_id);
    END IF;

    PERFORM cron.schedule(
        'maicos-dispatch-scheduled-workflows',
        '* * * * *',
        $cmd$
        WITH due AS (
            SELECT id, company_id, objective
            FROM scheduled_jobs
            WHERE dispatched = false
              AND run_at <= now()
            ORDER BY run_at
            LIMIT 100
            FOR UPDATE SKIP LOCKED
        ),
        new_jobs AS (
            INSERT INTO workflow_jobs
                (id, company_id, trigger, payload, status, attempts, scheduled_job_id)
            SELECT
                gen_random_uuid()::text,
                due.company_id,
                'scheduled',
                jsonb_build_object(
                    'objective', due.objective,
                    'workspace_id', due.company_id
                ),
                'PENDING',
                0,
                due.id
            FROM due
            RETURNING id, scheduled_job_id
        )
        UPDATE scheduled_jobs sj
        SET dispatched = true,
            dispatched_job_id = nj.id
        FROM new_jobs nj
        WHERE sj.id = nj.scheduled_job_id;
        $cmd$
    );
END
$$;
"""


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    exists = bind.execute(
        sa.text("SELECT 1 FROM pg_extension WHERE extname = 'pg_cron'")
    ).first()
    if not exists:
        return
    op.execute(DISPATCHER_SQL)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    exists = bind.execute(
        sa.text("SELECT 1 FROM pg_extension WHERE extname = 'pg_cron'")
    ).first()
    if not exists:
        return
    op.execute(
        """
        DO $$
        DECLARE job_id int;
        BEGIN
            SELECT scheduleid INTO job_id
            FROM cron.job
            WHERE jobname = 'maicos-dispatch-scheduled-workflows';
            IF job_id IS NOT NULL THEN
                PERFORM cron.unschedule(job_id);
            END IF;
        END
        $$;
        """
    )
