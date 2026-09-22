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
    return added
