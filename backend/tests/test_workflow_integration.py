"""Integration test: end-to-end client-onboarding workflow.

Replaces Postgres with SQLite in-memory so the workflow engine, agent
runtime, approval center and audit log can be exercised in CI without
external services. The production code is unchanged.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("APP_SECRET_KEY", "test-secret")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import agents  # noqa: F401  (registers agents + connectors)
from app.approvals.service import decide
from app.core.context import Principal
from app.db.session import Base
from app.models.orm import ApprovalStatus
from app.orchestrator import handle_objective
from app.workflow.engine import run as run_workflow

# Force the DB to a fresh in-memory SQLite for this test only.
engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base.metadata.create_all(engine)


def _principal() -> Principal:
    return Principal(user_id="u-1", workspace_id="ws-1", roles=("owner",))


def test_onboarding_creates_approval_for_send():
    db = Session()
    try:
        result = handle_objective(
            db, principal=_principal(), objective="Onboard the new client ABC."
        )
        assert result["state"] in {"WAITING_APPROVAL", "PARTIAL", "COMPLETED"}, result

        from app.models.orm import Approval, Workflow

        wf = db.get(Workflow, result["workflow_id"])
        approvals = (
            db.query(Approval)
            .filter(Approval.workflow_id == wf.id, Approval.status == ApprovalStatus.PENDING)
            .all()
        )
        # External communication always requires approval per PRD §14.
        assert any(a.action == "send_external_communication" for a in approvals), [
            a.action for a in approvals
        ]

        # Loop approvals and resume until the workflow finishes.
        for _ in range(10):
            approvals = (
                db.query(Approval)
                .filter(Approval.workflow_id == wf.id, Approval.status == ApprovalStatus.PENDING)
                .all()
            )
            if not approvals:
                break
            for a in approvals:
                decide(
                    db,
                    approval=a,
                    decision="APPROVE",
                    decided_by_user_id="u-1",
                )
            run_workflow(db, wf=wf, principal=_principal())
        db.commit()
        # Either completed or partial (other tasks should have run).
        assert wf.state.value in {"COMPLETED", "PARTIAL"}, wf.state.value
    finally:
        db.close()
    print("integration test OK")


if __name__ == "__main__":
    test_onboarding_creates_approval_for_send()
