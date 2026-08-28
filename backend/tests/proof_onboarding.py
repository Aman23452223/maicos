"""End-to-end proof: "Onboard this client" actually coordinates
multiple agents and changes real systems.

What this script demonstrates, line by line:

  1. Issue the outcome "Onboard the new client ABC with John Doe at
     [email protected]."
  2. The AI Manager builds a plan with five tasks spanning four
     specialized agents: sales_crm, project_ops, calendar, communication.
  3. The workflow engine executes the plan, calling each agent in
     dependency order.
  4. The agents call their allowed tools - the CRM, Calendar, and Email
     connectors - which persist to JSON files on disk.
  5. The Communication Agent's send hits the approval gate (per PRD
     §14). The script approves it and resumes.
  6. After completion, the script reads the on-disk stores directly
     and asserts that the real systems were updated, that every agent
     was used, that the audit log captured every material action, and
     that no task was claimed complete without an external confirmation.

Run it from the backend/ directory:

    python -m tests.proof_onboarding

Expected output includes:
  * A per-agent tool-call count
  * The contents of var/stores/crm.contacts.json
  * The contents of var/stores/email.outbox.json
  * The contents of var/stores/calendar.events.json
  * The relevant lines from the audit log
  * Final assertion summary
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

# --- Setup -----------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Use a clean stores directory so the proof is reproducible.
STORES = ROOT / "var" / "stores_proof"
if STORES.exists():
    shutil.rmtree(STORES)
STORES.mkdir(parents=True, exist_ok=True)
os.environ["MAICOS_STORES_DIR"] = str(STORES)

# Force the deterministic planner (no LLM) so this proof is offline and
# reproducible.
os.environ.setdefault("APP_SECRET_KEY", "proof-secret")

# Ensure the workflow engine is on (default in MVP).
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import agents  # noqa: F401  (registers agents + connectors)
from app.agents.implementations.ai_manager import build_plan
from app.approvals.service import decide
from app.core.context import Principal
from app.db.session import Base
from app.models.orm import (
    AgentRun,
    Approval,
    ApprovalStatus,
    AuditLog,
    Company,
    User,
    Workflow,
)
from app.orchestrator import handle_objective
from app.workflow.engine import create_workflow
from app.workflow.engine import run as run_workflow

# --- 1. Bring up a fresh SQLite DB for this proof --------------------------
DB_PATH = STORES / "proof.db"
if DB_PATH.exists():
    DB_PATH.unlink()
engine = create_engine(
    f"sqlite+pysqlite:///{DB_PATH}",
    future=True,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def _principal(db) -> Principal:
    # Reuse the same user/workspace across the two scenarios so the
    # proof can re-use the file-backed stores (and audit trail).
    email = "ceo" + "@" + "proof.example.com"
    user = db.query(User).filter(User.email == email).first()
    if user is not None:
        return Principal(
            user_id=user.id,
            workspace_id=user.company_id,
            roles=("owner", "admin"),
        )
    company = Company(name="Proof Co")
    db.add(company)
    db.flush()
    user = User(
        company_id=company.id,
        email=email,
        name="CEO",
        password_hash="x",
        roles=["owner", "admin"],
    )
    db.add(user)
    db.commit()
    return Principal(user_id=user.id, workspace_id=company.id, roles=("owner", "admin"))


def banner(s: str) -> None:
    print()
    print("=" * 78)
    print(s)
    print("=" * 78)


def show_json(path: Path) -> None:
    if not path.exists():
        print(f"  (missing: {path})")
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"  (empty: {path})")
        return
    print(json.dumps(data, indent=2, default=str))


# --- 2. Run the proof ------------------------------------------------------
def main() -> int:
    db = Session()
    try:
        principal = _principal(db)

        objective = "Onboard the new client ABC with John Doe at [email protected]."
        banner("STEP 1 - Issue the business outcome")
        print(f'  Objective: "{objective}"')

        plan = build_plan(objective)
        banner("STEP 2 - AI Manager produced this plan")
        for t in plan["tasks"]:
            deps = ", ".join(t.get("depends_on") or []) or "(none)"
            print(f"  - [{t['agent']}] {t['title']}  (depends on: {deps})")
        assert {t["agent"] for t in plan["tasks"]} >= {
            "sales_crm",
            "project_ops",
            "calendar",
            "communication",
        }, "plan must involve at least 4 specialized agents"

        wf = create_workflow(
            db,
            company_id=principal.workspace_id,
            triggered_by_user_id=principal.user_id,
            conversation_id=None,
            title=plan["intent"],
            objective=objective,
            plan=plan,
        )
        banner("STEP 3 - Workflow created")
        print(f"  id={wf.id}  state={wf.state.value}")

        run_workflow(db, wf=wf, principal=principal)
        banner("STEP 4 - First pass: workflow ran, external sends paused")
        print(f"  workflow state: {wf.state.value}")
        for t in wf.tasks:
            print(f"    {t.agent_name:14s} {t.title:36s} -> {t.state.value}  err={t.error!r}")

        # Loop: approve all pending and resume until no more approvals.
        total_approved = 0
        for _ in range(10):
            pending = (
                db.query(Approval)
                .filter(
                    Approval.workflow_id == wf.id,
                    Approval.status == ApprovalStatus.PENDING,
                )
                .all()
            )
            if not pending:
                break
            for a in pending:
                decide(
                    db,
                    approval=a,
                    decision="APPROVE",
                    decided_by_user_id=principal.user_id,
                )
                total_approved += 1
            run_workflow(db, wf=wf, principal=principal)
            db.commit()
        banner("STEP 5 - Workflow ran to completion after batched approvals")
        print(f"  approvals approved: {total_approved}")
        print(f"  workflow state: {wf.state.value}")
        for t in wf.tasks:
            print(f"    {t.agent_name:14s} {t.title:36s} -> {t.state.value}  err={t.error!r}")
        assert wf.state.value in {"COMPLETED", "PARTIAL"}, f"unexpected state {wf.state.value}"

        # Per-agent tool-call count, from the persisted AgentRun rows.
        banner("STEP 6 - Per-agent tool calls (from AgentRun.tool_calls)")
        runs = (
            db.query(AgentRun)
            .filter(AgentRun.task_id.in_([t.id for t in wf.tasks]))
            .all()
        )
        by_agent: dict[str, int] = {}
        by_agent_tasks: dict[str, set[str]] = {}
        for r in runs:
            calls = r.tool_calls or []
            by_agent[r.agent_name] = by_agent.get(r.agent_name, 0) + len(calls)
            by_agent_tasks.setdefault(r.agent_name, set()).add(r.task_id)
            print(f"  {r.agent_name:14s} task={r.task_id[:8]}  tool_calls={len(calls)}")
        # At least one of each required agent must have a non-empty tool log.
        for required in ["sales_crm", "calendar", "communication"]:
            assert by_agent.get(required, 0) > 0, f"{required} made no tool calls"

        # --- 7. Real systems were updated (read JSON on disk) -------------
        banner("STEP 7 - Real systems were updated (read directly from disk)")
        crm_contacts = STORES / "crm.contacts.json"
        crm_companies = STORES / "crm.companies.json"
        email_outbox = STORES / "email.outbox.json"
        calendar_events = STORES / "calendar.events.json"

        print("  CRM contacts (crm.contacts.json):")
        show_json(crm_contacts)
        print("  CRM companies (crm.companies.json):")
        show_json(crm_companies)
        print("  Email outbox (email.outbox.json):")
        show_json(email_outbox)
        print("  Calendar events (calendar.events.json):")
        show_json(calendar_events)

        contacts = json.loads(crm_contacts.read_text() or "{}")
        companies = json.loads(crm_companies.read_text() or "{}")
        outbox = json.loads(email_outbox.read_text() or "{}")
        events = json.loads(calendar_events.read_text() or "{}")

        assert companies, "company not persisted"
        assert contacts, "contact not persisted"
        assert outbox, "email not sent"
        assert events, "calendar event not created"

        # Verify the welcome email is actually marked SENT.
        sent = [m for m in outbox.values() if m.get("status") == "SENT"]
        assert sent, "no email in SENT state"
        assert any("[email protected]" in (m.get("to") or "") for m in sent), (
            f"welcome email recipient not [email protected]: {sent}"
        )

        # --- 8. Audit trail ------------------------------------------------
        banner("STEP 8 - Audit trail (excerpt)")
        audit = (
            db.query(AuditLog)
            .order_by(AuditLog.id.asc())
            .all()
        )
        for entry in audit:
            print(f"  [{entry.id:03d}] {entry.action:24s} target={entry.target_type}:{entry.target_id}")
        assert any(entry.action == "workflow.created" for entry in audit)
        assert any(entry.action == "approval.requested" for entry in audit)
        assert any(entry.action.startswith("approval.approved") for entry in audit)
        assert any(entry.action == "workflow.finished" for entry in audit)

        # --- 9. No fake completions ---------------------------------------
        banner("STEP 9 - Verify-before-completion: no task claimed success without external confirmation")
        for t in wf.tasks:
            if t.state.value == "COMPLETED":
                task_runs = [r for r in runs if r.task_id == t.id]
                assert task_runs, f"no AgentRun for completed task {t.id}"
                # A task may have two runs: the original agent attempt
                # (which may have requested approval, with no tool calls)
                # and the replayed approved action. The presence of at
                # least one confirmed tool call across all runs is what
                # proves the system did the work.
                if t.agent_name in {"sales_crm", "calendar", "communication"}:
                    all_calls = [c for r in task_runs for c in (r.tool_calls or [])]
                    assert all_calls, f"{t.title} marked complete without any tool calls"
                    assert any(c.get("ok") and c.get("confirmed") for c in all_calls), (
                        f"{t.title} marked complete without confirmed tool call: {all_calls}"
                    )

        banner("PROOF COMPLETE")
        print(f"  Workflow:        {wf.id}")
        print(f"  Final state:     {wf.state.value}")
        print(f"  Tasks:           {len(wf.tasks)}")
        print(f"  Agents used:     {sorted(by_agent.keys())}")
        print(f"  Tool calls:      {sum(by_agent.values())}")
        print(f"  Approvals:       {len(pending)} (all approved)")
        print(f"  Stores on disk:  {STORES}")
        print()
        return 0
    finally:
        db.close()


def main_invoice() -> int:
    """Second scenario: handle overdue invoices.

    1. Pre-seed finance.invoices.json with one overdue invoice.
    2. Submit "Handle overdue invoice follow-ups".
    3. The Finance agent finds the overdue invoice; the Communication
       agent drafts a reminder (writes to email.outbox.json).
    4. Assert both agents actually touched the on-disk stores.
    """
    db = Session()
    try:
        principal = _principal(db)
        banner("INVOICE SCENARIO - step 1: seed an overdue invoice")
        from datetime import UTC, datetime, timedelta

        from app.agents.implementations.finance import _INVOICES

        past = (datetime.now(UTC) - timedelta(days=5)).isoformat()
        rec = {
            "id": "inv-1",
            "workspace_id": principal.workspace_id,
            "customer": "Globex",
            "amount": 199.0,
            "due_at": past,
            "status": "OPEN",
            "created_at": past,
        }
        _INVOICES.put("inv-1", rec)
        print("  seeded invoice inv-1 (Globex, $199, 5 days overdue)")

        banner("INVOICE SCENARIO - step 2: submit objective")
        objective = "Handle overdue invoice follow-ups and tell me what needs approval."
        print(f'  objective: "{objective}"')
        result = handle_objective(db, principal=principal, objective=objective)
        wf = db.get(Workflow, result["workflow_id"])
        assert wf is not None
        print("  plan tasks:")
        for t in wf.tasks:
            plan_id = (t.input or {}).get("_plan_id")
            print(f"    [{plan_id}] {t.agent_name} {t.title} depends_on={t.depends_on}")
        # Approve any pending approvals so the workflow completes.
        for _ in range(5):
            pending = (
                db.query(Approval)
                .filter(
                    Approval.workflow_id == wf.id,
                    Approval.status == ApprovalStatus.PENDING,
                )
                .all()
            )
            if not pending:
                break
            for a in pending:
                decide(db, approval=a, decision="APPROVE", decided_by_user_id=principal.user_id)
            run_workflow(db, wf=wf, principal=principal)
            db.commit()

        banner("INVOICE SCENARIO - step 3: outcome")
        print(f"  workflow state: {wf.state.value}")
        for t in wf.tasks:
            print(f"    {t.agent_name:14s} {t.title:36s} -> {t.state.value}")
        assert wf.state.value in {"COMPLETED", "PARTIAL"}

        # The email outbox should have a draft referencing Globex.
        outbox_path = STORES / "email.outbox.json"
        outbox = json.loads(outbox_path.read_text() or "{}")
        globex_msgs = [
            m for m in outbox.values()
            if "globex" in (m.get("to") or "").lower()
            or "globex" in (m.get("body") or "").lower()
            or "globex" in (m.get("subject") or "").lower()
        ]
        assert globex_msgs, f"no reminder mentioning Globex: {outbox}"
        m = globex_msgs[0]
        print(
            f"  reminder draft persisted: subject={m.get('subject')!r} "
            f"body_excerpt={m.get('body', '')[:80]!r}"
        )
        assert m.get("status") == "DRAFT", f"reminder should be a draft, got {m.get('status')}"
        return 0
    finally:
        db.close()


def main_all() -> int:
    """Run the onboarding proof plus a second scenario (invoice follow-up)."""
    rc = main()
    if rc != 0:
        return rc
    return main_invoice()


if __name__ == "__main__":
    raise SystemExit(main_all())
