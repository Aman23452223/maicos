"""SQLAlchemy engine + session factory (PRD §15 PostgreSQL)."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


_settings = get_settings()
# Connect timeout = 5s so a missing DATABASE_URL fails fast instead of
# hanging each request for 30+ seconds (which makes the platform
# return 502). `pool_pre_ping=True` keeps stale connections out of the
# pool after Postgres restarts.
engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    future=True,
    connect_args={"connect_timeout": 5},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

