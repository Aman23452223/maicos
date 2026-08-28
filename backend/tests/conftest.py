"""Shared pytest fixtures.

Each test gets a fresh in-memory SQLite database, an initialized
workspace, an admin user, and a bearer token. The agent and connector
registries are reset between tests so module-level state doesn't leak.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("APP_SECRET_KEY", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import agents  # noqa: F401  (registers agents + connectors)
from app.agents import base as _agent_registry
from app.core.security import create_access_token, hash_password
from app.db.session import Base, get_db
from app.integrations import base as _conn_registry
from app.main import app
from app.models.orm import Company, User


@pytest.fixture
def engine():
    # StaticPool + shared in-memory DB so all connections see the same
    # schema and data, even across threads (TestClient).
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@pytest.fixture
def db(session_factory):
    s = session_factory()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def workspace_user(db):
    company = Company(name="Acme")
    db.add(company)
    db.flush()
    user = User(
        company_id=company.id,
        email="owner" + "@" + "acme.example.com",
        name="Owner",
        password_hash=hash_password("secret-123"),
        roles=["owner", "admin"],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"company": company, "user": user}


@pytest.fixture
def client(session_factory, workspace_user):
    def _override():
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    token = create_access_token(
        sub=workspace_user["user"].id,
        workspace_id=workspace_user["company"].id,
        roles=workspace_user["user"].roles,
    )
    headers = {"Authorization": f"Bearer {token}"}
    with TestClient(app) as c:
        c.headers = headers
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def fresh_registries():
    """Clear module-level registries for tests that need isolation."""
    _agent_registry._REGISTRY.clear()  # type: ignore[attr-defined]
    _conn_registry._REGISTRY.clear()  # type: ignore[attr-defined]
    import importlib

    import app.agents.implementations as impl
    import app.integrations.connectors as conn

    importlib.reload(impl)
    importlib.reload(conn)
    from app.agents import runtime as _runtime

    importlib.reload(_runtime)
    yield
