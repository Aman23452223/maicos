"""Company Operating System API (manager, blueprint, software, signals)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.audit.service import record
from app.core.context import Principal
from app.core.security import get_current_principal, require_role
from app.db.session import get_db
from app.models.orm import (
    CompanyDecision,
    CompanyEvent,
    CompanyInitiative,
    CompanyProject,
    CompanySignal,
)

router = APIRouter(tags=["company"])


class RunIn(BaseModel):
    objective: str
    plan_review: bool = True


@router.post("/company/run")
def company_run(payload: RunIn, p: Principal = Depends(get_current_principal),
                db: Session = Depends(get_db)):
    """Outcome-first execution via the AI Company Manager."""
    from app.company.manager import run_outcome

    if not payload.objective.strip():
        raise HTTPException(status_code=400, detail="objective required")
    return run_outcome(db, principal=p, objective=payload.objective,
                       plan_review=payload.plan_review)


@router.post("/company/checkup")
def company_checkup(p: Principal = Depends(get_current_principal),
                    db: Session = Depends(get_db)):
    from app.company.checkup import run_checkup

    return run_checkup(db, company_id=p.workspace_id, actor=p.user_id)


@router.post("/company/investigate")
def company_investigate(payload: dict,
                        p: Principal = Depends(get_current_principal),
                        db: Session = Depends(get_db)):
    from app.company.manager import investigate

    q = str(payload.get("question", "")).strip()
    if not q:
        raise HTTPException(status_code=400, detail="question required")
    return investigate(db, principal=p, question=q)


@router.get("/company/context")
def company_context(p: Principal = Depends(get_current_principal),
                    db: Session = Depends(get_db)):
    from app.company.brain import load_company_context

    return load_company_context(db, company_id=p.workspace_id)


class BlueprintIn(BaseModel):
    idea: str
    research_query: str | None = None


@router.post("/company/blueprint")
def blueprint_generate(payload: BlueprintIn,
                       p: Principal = Depends(get_current_principal),
                       db: Session = Depends(get_db)):
    from app.company.blueprint import generate

    if not payload.idea.strip():
        raise HTTPException(status_code=400, detail="idea required")
    research = None
    if payload.research_query:
        from app.capabilities.registry import enabled_for
        if "lead_discovery" in enabled_for(db, company_id=p.workspace_id):
            from app.leads.providers import get as get_provider
            res = get_provider("search").discover(payload.research_query, limit=5)
            if res.ok:
                research = {"summary": "; ".join(
                    f"{x.company_name} ({x.domain})" for x in res.prospects[:5])}
    return generate(payload.idea, research=research)


@router.post("/company/blueprint/apply")
def blueprint_apply(payload: dict, p: Principal = Depends(get_current_principal),
                    db: Session = Depends(get_db)):
    from app.company.blueprint import apply_blueprint

    bp = payload.get("blueprint") or {}
    if not bp.get("sections"):
        raise HTTPException(status_code=400, detail="blueprint.sections required")
    return apply_blueprint(db, company_id=p.workspace_id, blueprint=bp,
                           actor=p.user_id)


@router.get("/company/workforce")
def workforce(intent: str = "lead_generation",
              p: Principal = Depends(get_current_principal),
              db: Session = Depends(get_db)):
    from app.capabilities.registry import enabled_for
    from app.company.brain import load_company_context
    from app.company.workforce import compose

    ctx = load_company_context(db, company_id=p.workspace_id)
    return compose(intent, sorted(enabled_for(db, company_id=p.workspace_id)),
                   context=ctx)


class SoftwareIn(BaseModel):
    repo: str = ""
    title: str = ""
    plan_markdown: str = ""
    head: str = ""
    base: str = "main"
    project: str = ""
    provider: str = ""
    url: str = ""


@router.post("/company/software/analyze")
def software_analyze(payload: SoftwareIn,
                     p: Principal = Depends(get_current_principal),
                     db: Session = Depends(get_db)):
    from app.company.software import analyze_repo

    _ = (db, p)
    return analyze_repo(payload.repo)


class BuildIn(BaseModel):
    repo: str = ""
    branch: str = ""
    base: str = "main"
    requirements: str = ""
    stack: str = ""
    confirmed: bool = False


@router.post("/company/software/generate")
def software_generate(payload: BuildIn,
                      p: Principal = Depends(get_current_principal),
                      db: Session = Depends(get_db)):
    """Review artifact only: LLM-generated files, never pushed."""
    from app.company.software import generate_code

    _ = (db, p)
    if not payload.requirements.strip():
        raise HTTPException(status_code=400, detail="requirements required")
    return generate_code(payload.requirements, stack_hint=payload.stack)


@router.post("/company/software/build-pr")
def software_build_pr(payload: BuildIn,
                      p: Principal = Depends(require_role("admin", "owner")),
                      db: Session = Depends(get_db)):
    from app.company.software import build_pr

    if not payload.confirmed:
        raise HTTPException(status_code=422, detail="confirmed:true required (code push)")
    out = build_pr(payload.repo, requirements=payload.requirements,
                   branch=payload.branch, base=payload.base or "main",
                   stack_hint=payload.stack)
    record(db, company_id=p.workspace_id, actor=p.user_id,
           action="software.build_pr", target_type="repo",
           target_id=payload.repo, details={"ok": out.get("ok")})
    db.commit()
    if not out.get("ok"):
        raise HTTPException(status_code=422, detail=out.get("error") or out.get("status"))
    return out


@router.post("/company/software/plan-pr")
def software_plan_pr(payload: SoftwareIn,
                     p: Principal = Depends(get_current_principal),
                     db: Session = Depends(get_db)):
    from app.company.software import plan_as_pr

    out = plan_as_pr(payload.repo, title=payload.title,
                     plan_markdown=payload.plan_markdown,
                     head=payload.head, base=payload.base)
    record(db, company_id=p.workspace_id, actor=p.user_id,
           action="software.plan_pr", target_type="repo",
           target_id=payload.repo, details={"ok": out.get("ok")})
    db.commit()
    if not out.get("ok"):
        raise HTTPException(status_code=422, detail=out.get("error") or out.get("status"))
    return out


@router.get("/company/software/deploy-status")
def software_deploy_status(provider: str, project: str = "",
                           p: Principal = Depends(get_current_principal),
                           db: Session = Depends(get_db)):
    from app.company.software import deployment_status

    _ = (db, p)
    return deployment_status(provider, project)


@router.post("/company/software/smoke-test")
def software_smoke(payload: SoftwareIn,
                   p: Principal = Depends(get_current_principal),
                   db: Session = Depends(get_db)):
    from app.company.software import smoke_test

    _ = (db, p)
    return smoke_test(payload.url)


@router.get("/company/decisions")
def list_decisions(p: Principal = Depends(get_current_principal),
                   db: Session = Depends(get_db)):
    rows = db.query(CompanyDecision).filter(
        CompanyDecision.company_id == p.workspace_id).order_by(
        CompanyDecision.created_at.desc()).limit(100).all()
    return [{"id": r.id, "title": r.title, "context": r.context,
             "decided_by": r.decided_by, "status": r.status} for r in rows]


class DecisionIn(BaseModel):
    title: str
    context: str = ""


@router.post("/company/decisions")
def add_decision(payload: DecisionIn,
                 p: Principal = Depends(get_current_principal),
                 db: Session = Depends(get_db)):
    from app.company.brain import remember

    row = CompanyDecision(company_id=p.workspace_id, title=payload.title[:255],
                          context=payload.context[:4000], decided_by=p.user_id)
    db.add(row)
    db.flush()
    remember(db, company_id=p.workspace_id, kind="DECISION", key=payload.title[:200],
             value=payload.context[:2000] or payload.title, actor=p.user_id)
    record(db, company_id=p.workspace_id, actor=p.user_id, action="decision.recorded",
           target_type="decision", target_id=row.id, details={})
    db.commit()
    return {"id": row.id}


@router.get("/company/signals")
def list_signals(kind: str | None = None, status: str = "open",
                 p: Principal = Depends(get_current_principal),
                 db: Session = Depends(get_db)):
    q = db.query(CompanySignal).filter(CompanySignal.company_id == p.workspace_id)
    if kind:
        q = q.filter(CompanySignal.kind == kind)
    if status:
        q = q.filter(CompanySignal.status == status)
    rows = q.order_by(CompanySignal.created_at.desc()).limit(100).all()
    return [{"id": r.id, "kind": r.kind, "severity": r.severity, "title": r.title,
             "detail": r.detail, "status": r.status} for r in rows]


@router.post("/company/signals/{signal_id}/resolve")
def resolve_signal(signal_id: str, p: Principal = Depends(get_current_principal),
                   db: Session = Depends(get_db)):
    row = db.get(CompanySignal, signal_id)
    if not row or row.company_id != p.workspace_id:
        raise HTTPException(status_code=404, detail="not found")
    row.status = "resolved"
    db.commit()
    return {"ok": True}


@router.get("/company/initiatives")
def list_initiatives(p: Principal = Depends(get_current_principal),
                     db: Session = Depends(get_db)):
    rows = db.query(CompanyInitiative).filter(
        CompanyInitiative.company_id == p.workspace_id).order_by(
        CompanyInitiative.created_at.desc()).limit(100).all()
    return [{"id": r.id, "goal_id": r.goal_id, "title": r.title,
             "status": r.status, "progress": r.progress,
             "workflow_id": r.workflow_id} for r in rows]


class InitiativeIn(BaseModel):
    title: str
    goal_id: str | None = None


@router.post("/company/initiatives")
def add_initiative(payload: InitiativeIn,
                   p: Principal = Depends(get_current_principal),
                   db: Session = Depends(get_db)):
    row = CompanyInitiative(company_id=p.workspace_id, goal_id=payload.goal_id,
                            title=payload.title[:255])
    db.add(row)
    db.commit()
    return {"id": row.id}


@router.get("/company/projects")
def list_projects(p: Principal = Depends(get_current_principal),
                  db: Session = Depends(get_db)):
    rows = db.query(CompanyProject).filter(
        CompanyProject.company_id == p.workspace_id).order_by(
        CompanyProject.created_at.desc()).limit(100).all()
    return [{"id": r.id, "name": r.name, "owner": r.owner,
             "deadline": r.deadline, "status": r.status} for r in rows]


class StaffTaskIn(BaseModel):
    title: str
    project_id: str | None = None
    assignee_user_id: str | None = None
    due_at: str | None = None


@router.post("/company/tasks")
def create_staff_task(payload: StaffTaskIn,
                      p: Principal = Depends(get_current_principal),
                      db: Session = Depends(get_db)):
    """Assign work to a human teammate (staff sees it in My Tasks)."""
    from app.models.orm import CompanyTask, User

    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="title required")
    project_id = payload.project_id
    if project_id:
        from app.models.orm import CompanyProject
        proj = db.get(CompanyProject, project_id)
        if not proj or proj.company_id != p.workspace_id:
            raise HTTPException(status_code=404, detail="project not found")
    else:
        from app.models.orm import CompanyProject
        proj = CompanyProject(company_id=p.workspace_id, name="General")
        db.add(proj)
        db.flush()
        project_id = proj.id
    if payload.assignee_user_id:
        u = db.get(User, payload.assignee_user_id)
        if not u or u.company_id != p.workspace_id:
            raise HTTPException(status_code=404, detail="teammate not in this workspace")
    due = None
    if payload.due_at:
        try:
            from datetime import datetime
            due = datetime.fromisoformat(payload.due_at)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="bad due_at") from exc
    row = CompanyTask(company_id=p.workspace_id, project_id=project_id,
                      title=payload.title[:255],
                      assignee_user_id=payload.assignee_user_id, due_at=due)
    db.add(row)
    db.flush()
    record(db, company_id=p.workspace_id, actor=p.user_id, action="task.assigned",
           target_type="task", target_id=row.id,
           details={"assignee": payload.assignee_user_id})
    db.commit()
    return {"id": row.id}


@router.get("/company/tasks/mine")
def my_tasks(p: Principal = Depends(get_current_principal),
             db: Session = Depends(get_db)):
    from app.models.orm import CompanyTask

    rows = db.query(CompanyTask).filter(
        CompanyTask.company_id == p.workspace_id,
        CompanyTask.assignee_user_id == p.user_id).order_by(
        CompanyTask.created_at.desc()).limit(100).all()
    return [{"id": r.id, "title": r.title, "state": r.state,
             "project_id": r.project_id,
             "due_at": r.due_at.isoformat() if r.due_at else None} for r in rows]


@router.post("/company/tasks/{task_id}/state")
def staff_task_state(task_id: str, payload: dict,
                     p: Principal = Depends(get_current_principal),
                     db: Session = Depends(get_db)):
    from app.models.orm import CompanyTask

    row = db.get(CompanyTask, task_id)
    if not row or row.company_id != p.workspace_id:
        raise HTTPException(status_code=404, detail="not found")
    # Only assignee, admin or owner may update.
    if row.assignee_user_id and row.assignee_user_id != p.user_id \
            and "owner" not in p.roles and "admin" not in p.roles:
        raise HTTPException(status_code=403, detail="not your task")
    state = str(payload.get("state", "")).upper()
    if state not in ("PENDING", "RUNNING", "COMPLETED", "FAILED"):
        raise HTTPException(status_code=400, detail="bad state")
    row.state = state
    db.commit()
    return {"ok": True, "state": row.state}


@router.get("/company/team")
def team(p: Principal = Depends(get_current_principal),
         db: Session = Depends(get_db)):
    """Human teammates of this workspace (for assignment dropdowns)."""
    from app.models.orm import User

    rows = db.query(User).filter(User.company_id == p.workspace_id,
                                 User.is_active.is_(True)).all()
    return [{"id": u.id, "name": u.name, "email": u.email, "roles": u.roles or []}
            for u in rows]


class AutopilotIn(BaseModel):
    enabled: bool = False
    max_spend_month: int = 0
    auto_channels: list[str] = []
    auto_invoice_below: int = 0
    auto_replan: bool = False


@router.get("/company/autopilot")
def get_autopilot(p: Principal = Depends(get_current_principal),
                  db: Session = Depends(get_db)):
    from app.policy.risk import autopilot
    return autopilot(db, company_id=p.workspace_id)


@router.put("/company/autopilot")
def put_autopilot(payload: AutopilotIn,
                  p: Principal = Depends(require_role("admin", "owner")),
                  db: Session = Depends(get_db)):
    from app.intel.service import get_or_create_profile
    from app.models.orm import Company

    bp = get_or_create_profile(db, company_id=p.workspace_id)
    co = db.get(Company, p.workspace_id)
    cfg = dict((co.config or {}) if co else {})
    data = payload.model_dump()
    data["auto_channels"] = [str(c).lower() for c in data.get("auto_channels", [])
                             if str(c).lower() in ("email", "whatsapp")]
    cfg["autopilot"] = data
    if co is not None:
        co.config = cfg
    # Mirror channels into comms auto-approve so sends obey one switch.
    comms = dict(bp.comms_policy or {})
    comms["auto_approve"] = data["auto_channels"]
    bp.comms_policy = comms
    record(db, company_id=p.workspace_id, actor=p.user_id, action="autopilot.updated",
           target_type="workspace", target_id=p.workspace_id, details=data)
    db.commit()
    return {"ok": True, **data}


@router.post("/company/collections/run")
def collections_run(p: Principal = Depends(get_current_principal),
                    db: Session = Depends(get_db)):
    """Money collection: overdue invoices -> reminders; old ones escalate."""
    from datetime import UTC, datetime

    from app.models.orm import CompanySignal

    from app.agents.implementations.finance import _invoices_for

    now = datetime.now(UTC)
    created, escalated = 0, 0
    for inv in _invoices_for(p.workspace_id):
        if inv.get("status") == "PAID":
            continue
        try:
            due = datetime.fromisoformat(inv["due_at"])
        except Exception:
            continue
        days = (now - due).days
        if days <= 0:
            continue
        if days > 7:
            exists = db.query(CompanySignal).filter(
                CompanySignal.company_id == p.workspace_id,
                CompanySignal.title == f"Overdue: {inv.get('customer')}",
                CompanySignal.status == "open").first()
            if not exists:
                db.add(CompanySignal(
                    company_id=p.workspace_id, kind="issue", severity="high",
                    title=f"Overdue: {inv.get('customer')}",
                    detail=f"${inv.get('amount', 0)} overdue {days} days. Escalated."))
                escalated += 1
        else:
            created += 1
    record(db, company_id=p.workspace_id, actor=p.user_id, action="collections.run",
           target_type="workspace", target_id=p.workspace_id,
           details={"remind": created, "escalated": escalated})
    db.commit()
    return {"remind_due": created, "escalated": escalated,
            "note": "Run 'Handle overdue invoice follow-ups' to send the reminders."}


@router.post("/company/digest/schedule")
def digest_schedule(payload: dict,
                    p: Principal = Depends(get_current_principal),
                    db: Session = Depends(get_db)):
    """Schedule the morning briefing daily (uses existing scheduler)."""
    from app.orchestrator import schedule as schedule_wf

    run_at = str(payload.get("run_at", ""))
    if not run_at:
        from datetime import UTC, datetime, timedelta
        run_at = (datetime.now(UTC) + timedelta(days=1)).replace(
            hour=3, minute=30, second=0, microsecond=0).isoformat()
    return schedule_wf(db, principal=p,
                       objective="Send the morning business digest.",
                       run_at_iso=run_at)


@router.get("/company/events")
def list_events(type: str | None = None, limit: int = 50,
                p: Principal = Depends(get_current_principal),
                db: Session = Depends(get_db)):
    q = db.query(CompanyEvent).filter(CompanyEvent.company_id == p.workspace_id)
    if type:
        q = q.filter(CompanyEvent.type == type)
    rows = q.order_by(CompanyEvent.created_at.desc()).limit(min(max(limit, 1), 200)).all()
    return [{"id": r.id, "type": r.type, "payload": r.payload or {},
             "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in rows]


@router.get("/company/autonomy")
def autonomy(p: Principal = Depends(get_current_principal),
             db: Session = Depends(get_db)):
    """Autonomy levels 0-5 + per-action classification for this workspace."""
    from app.policy.risk import RISK_LEVELS

    _ = (db, p)
    action_level = {
        "research": 0, "draft": 1, "run_tests": 1, "create_branch": 2,
        "send_external_communication": 3, "deploy_staging": 3,
        "deploy_production": 5, "execute_payment": 5, "hire_human": 5,
        "delete_production_data": 5, "change_security": 5,
    }
    return {
        "levels": {
            "0": "Observe only", "1": "Analyze and recommend",
            "2": "Reversible low-risk actions", "3": "Approved workflows",
            "4": "High-autonomy under policy", "5": "Human approval required",
        },
        "actions": action_level,
        "risk": RISK_LEVELS,
    }


@router.get("/usage")
def usage(p: Principal = Depends(get_current_principal),
          db: Session = Depends(get_db)):
    """Workspace usage/cost estimate (labeled estimate, from real records)."""
    from sqlalchemy import func

    from app.models.orm import AgentRun, Task, Workflow

    tasks = db.query(func.count(Task.id)).filter(Task.workflow_id.in_(
        db.query(Workflow.id).filter(Workflow.company_id == p.workspace_id))).scalar() or 0
    tool_calls = 0
    for (calls,) in db.query(AgentRun.tool_calls).filter(
            AgentRun.company_id == p.workspace_id).all():
        tool_calls += sum(1 for e in (calls or []) if e.get("type") == "tool_call")
    return {"type": "estimate", "tasks": tasks, "tool_calls": tool_calls,
            "note": "Counts from persisted records; LLM-token costs not metered."}
