"""Idempotent schema repair for production (safe additive changes only).

Background: early MAICOS databases were created with
`Base.metadata.create_all`, which never ALTERs existing tables, and the
Alembic chain is broken on those DBs (initial revision tries to CREATE an
existing table). Result: new columns on pre-existing tables are missing
and endpoints 500 with UndefinedColumn.

`ensure_schema` closes that gap without destructive operations:
- missing tables  -> CREATE TABLE
- missing columns -> ALTER TABLE ... ADD COLUMN (nullable unless the model
  defines a server_default)
It never drops/renames/alters existing columns.
"""
from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.db.session import Base


RLS_TABLES = (
    "leads", "crm_contacts", "crm_companies", "opportunities", "documents",
    "document_chunks", "business_memory", "workflows", "approvals",
)


def ensure_postgres_extras(engine: Engine) -> dict[str, list[str]]:
    """pgvector + RLS on Postgres only. All guarded; never raises."""
    from sqlalchemy import text

    done: dict[str, list[str]] = {"pgvector": [], "rls": []}
    if engine.dialect.name != "postgresql":
        return done
    with engine.begin() as conn:
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            done["pgvector"].append("extension vector")
        except Exception:
            pass
        try:
            conn.execute(text(
                'ALTER TABLE "document_chunks" '
                'ADD COLUMN IF NOT EXISTS "embedding_vector" vector(1536)'))
            done["pgvector"].append("document_chunks.embedding_vector")
        except Exception:
            pass
        insp_tables = set()
        try:
            from sqlalchemy import inspect as _inspect
            insp_tables = set(_inspect(conn).get_table_names())
        except Exception:
            pass
        for t in RLS_TABLES:
            if t not in insp_tables:
                continue
            try:
                conn.execute(text(f'ALTER TABLE "{t}" ENABLE ROW LEVEL SECURITY'))
                conn.execute(text(
                    f'DROP POLICY IF EXISTS service_all ON "{t}"; '
                    f'CREATE POLICY service_all ON "{t}" '
                    f'FOR ALL TO PUBLIC USING (true) WITH CHECK (true)'))
                done["rls"].append(t)
            except Exception:
                continue
    return done


def ensure_schema(engine: Engine) -> dict[str, list[str]]:
    """Create missing tables/columns. Returns what was added."""
    from sqlalchemy.schema import CreateTable

    added: dict[str, list[str]] = {"tables": [], "columns": []}
    with engine.begin() as conn:
        insp = inspect(conn)
        existing = set(insp.get_table_names())
        for table_name, table in Base.metadata.tables.items():
            if table_name not in existing:
                conn.execute(CreateTable(table))
                added["tables"].append(table_name)
                continue
            cols = {c["name"] for c in insp.get_columns(table_name)}
            from sqlalchemy import DateTime as _DateTime

            is_pg = engine.dialect.name == "postgresql"
            for col in table.columns:
                if col.name in cols:
                    continue
                coltype = col.type.compile(dialect=engine.dialect)
                # Postgres: keep timestamp defaults. SQLite forbids
                # non-constant ADD COLUMN defaults, so add nullable there;
                # ORM client defaults + onupdate cover new writes.
                if (is_pg and isinstance(col.type, _DateTime)
                        and col.server_default is not None):
                    default = " DEFAULT CURRENT_TIMESTAMP"
                else:
                    default = ""
                # No IF NOT EXISTS (SQLite lacks it); the inspector check
                # above already guarantees the column is missing.
                conn.execute(
                    text(f'ALTER TABLE "{table_name}" '
                         f'ADD COLUMN "{col.name}" {coltype}{default}')
                )
                added["columns"].append(f"{table_name}.{col.name}")
    try:
        added.update(ensure_postgres_extras(engine))
    except Exception:
        pass
    return added
