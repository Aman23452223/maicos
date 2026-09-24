"""Leads/CRM/followups/proposals/analytics routes (Phases 3-20)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.analytics.metrics import funnel, operations, pipeline, weekly_report
from app.core.context import Principal
from app.core.security import get_current_principal
from app.crm.providers import convert_lead_to_contact
from app.db.session import get_db
from app.docs_gen.proposals import create as create_proposal
from app.leads.providers import Prospect, get as get_provider
from app.leads.responses import ingest as ingest_response
from app.leads.service import enrich_lead, import_prospects, qualify_lead
from app.models.orm import CrmActivity, Lead, LeadStatus, Opportunity
from app.scheduling.followups import execute_due, schedule_sequence

router = APIRouter(tags=["growth"])


class DiscoverIn(BaseModel):
    query: str
    provider: str = "search"
    limit: int = 20


class ImportIn(BaseModel):
    prospects: list[dict]
    auto_qualify: bool = False


class FollowupIn(BaseModel):
    lead_id: str
    days: list[int] | None = None
    channel: str = "email"


class InboundIn(BaseModel):
    channel: str = "email"
    from_address: str
    body: str


class ProposalIn(BaseModel):
    kind: str = "proposal"
    title: str = "Proposal"
    context: dict = {}
    lead_id: str | None = None
    opportunity_id: str | None = None


@router.post("/leads/discover")
def discover(payload: DiscoverIn, p: Principal = Depends(get_current_principal),
             db: Session = Depends(get_db)):
    try:
        provider = get_provider(payload.provider)
    except KeyError:
        raise HTTPException(status_code=400, detail="unknown provider")
    res = provider.discover(payload.query, limit=min(max(payload.limit, 1), 100))
    # Honest statuses: never invent leads
    return {"status": res.status, "message": res.message,
            "prospects": [vars(x) for x in res.prospects]}


@router.post("/leads/import")
def import_leads(payload: ImportIn, p: Principal = Depends(get_current_principal),
                 db: Session = Depends(get_db)):
    prospects = []
    for r in payload.prospects[:500]:
        try:
            prospects.append(Prospect(
                company_name=str(r.get("company_name") or r.get("name") or ""),
                website=str(r.get("website") or ""), domain=str(r.get("domain") or ""),
                email=str(r.get("email") or ""), phone=str(r.get("phone") or ""),
                location=str(r.get("location") or ""), industry=str(r.get("industry") or ""),
                source=str(r.get("source") or "manual"),
                source_url=str(r.get("source_url") or ""),
                external_id=str(r.get("external_id") or ""), notes=str(r.get("notes") or "")))
        except Exception:
            continue
    out = import_prospects(db, company_id=p.workspace_id, prospects=prospects,
                           actor=p.user_id)
    if payload.auto_qualify:
        for lid in out.get("ids", []):
            qualify_lead(db, company_id=p.workspace_id, lead_id=lid, actor=p.user_id)
    db.commit()
    return out


@router.post("/leads/import-csv")
async def import_csv(file: UploadFile = File(...), list_name: str = "",
                     p: Principal = Depends(get_current_principal),
                     db: Session = Depends(get_db)):
    """Upload a contact sheet (CSV). Columns: company_name/name, email,
    phone, location, industry, website, notes. Tagged source=list:<name>."""
    from app.leads.providers import CsvImportProvider

    raw = await file.read()
    try:
        content = raw.decode("utf-8-sig")
    except Exception:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 text")
    prospects = CsvImportProvider().parse(content)
    if not prospects:
        raise HTTPException(status_code=422, detail="no rows parsed")
    tag = f"list:{list_name.strip()}" if list_name.strip() else "csv_import"
    for pr in prospects:
        pr.source = tag
    out = import_prospects(db, company_id=p.workspace_id, prospects=prospects,
                           actor=p.user_id)
    for lid in out.get("ids", []):
        qualify_lead(db, company_id=p.workspace_id, lead_id=lid, actor=p.user_id)
    db.commit()
    return {**out, "source": tag}


@router.get("/leads")
def list_leads(status: str | None = None, limit: int = 50,
               p: Principal = Depends(get_current_principal),
               db: Session = Depends(get_db)):
    q = db.query(Lead).filter(Lead.company_id == p.workspace_id)
    if status:
        try:
            q = q.filter(Lead.status == LeadStatus(status.upper()))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    rows = q.order_by(Lead.score.desc()).limit(min(max(limit, 1), 200)).all()
    return [{"id": l.id, "company_name": l.company_name, "email": l.email,
             "location": l.location, "industry": l.industry, "status": l.status.value,
             "score": l.score, "source": l.source} for l in rows]


@router.post("/leads/{lead_id}/enrich")
def enrich(lead_id: str, p: Principal = Depends(get_current_principal),
           db: Session = Depends(get_db)):
    out = enrich_lead(db, company_id=p.workspace_id, lead_id=lead_id, actor=p.user_id)
    if not out.get("ok"):
        raise HTTPException(status_code=404, detail=out.get("error"))
    db.commit()
    return out


@router.post("/leads/{lead_id}/qualify")
def qualify(lead_id: str, p: Principal = Depends(get_current_principal),
            db: Session = Depends(get_db)):
    out = qualify_lead(db, company_id=p.workspace_id, lead_id=lead_id, actor=p.user_id)
    if not out.get("ok"):
        raise HTTPException(status_code=404, detail=out.get("error"))
    db.commit()
    return out


@router.post("/leads/{lead_id}/convert")
def convert(lead_id: str, p: Principal = Depends(get_current_principal),
            db: Session = Depends(get_db)):
    out = convert_lead_to_contact(db, company_id=p.workspace_id, lead_id=lead_id)
    if not out.get("ok"):
        raise HTTPException(status_code=422, detail=out.get("error"))
    db.commit()
    return out


@router.post("/followups/schedule")
def sched(payload: FollowupIn, p: Principal = Depends(get_current_principal),
          db: Session = Depends(get_db)):
    out = schedule_sequence(db, company_id=p.workspace_id, lead_id=payload.lead_id,
                            days=payload.days, channel=payload.channel, actor=p.user_id)
    if not out.get("ok"):
        raise HTTPException(status_code=404, detail=out.get("error"))
    db.commit()
    return out


@router.post("/followups/run-due")
def run_due(p: Principal = Depends(get_current_principal),
            db: Session = Depends(get_db)):
    out = execute_due(db, company_id=p.workspace_id, actor=p.user_id)
    db.commit()
    return out


@router.post("/inbound")
def inbound(payload: InboundIn, p: Principal = Depends(get_current_principal),
            db: Session = Depends(get_db)):
    out = ingest_response(db, company_id=p.workspace_id, channel=payload.channel,
                          from_address=payload.from_address, body=payload.body,
                          actor=p.user_id)
    db.commit()
    return out


@router.post("/opportunities")
def create_opp(payload: dict, p: Principal = Depends(get_current_principal),
               db: Session = Depends(get_db)):
    o = Opportunity(company_id=p.workspace_id, lead_id=payload.get("lead_id"),
                    title=str(payload.get("title", "Opportunity"))[:255],
                    amount=int(payload.get("amount") or 0),
                    stage=str(payload.get("stage", "new"))[:80])
    db.add(o)
    db.flush()
    db.commit()
    return {"id": o.id, "stage": o.stage}


@router.get("/opportunities")
def list_opps(stage: str | None = None, limit: int = 100,
              p: Principal = Depends(get_current_principal),
              db: Session = Depends(get_db)):
    q = db.query(Opportunity).filter(Opportunity.company_id == p.workspace_id)
    if stage:
        q = q.filter(Opportunity.stage == stage)
    rows = q.order_by(Opportunity.updated_at.desc()).limit(min(max(limit, 1), 200)).all()
    return [{"id": o.id, "title": o.title, "amount": o.amount, "stage": o.stage,
             "status": o.status, "lead_id": o.lead_id, "owner": o.owner} for o in rows]


@router.patch("/opportunities/{opp_id}")
def patch_opp(opp_id: str, payload: dict,
              p: Principal = Depends(get_current_principal),
              db: Session = Depends(get_db)):
    o = db.get(Opportunity, opp_id)
    if not o or o.company_id != p.workspace_id:
        raise HTTPException(status_code=404, detail="not found")
    if "stage" in payload:
        o.stage = str(payload["stage"])[:80]
    if "status" in payload:
        if str(payload["status"]) not in ("open", "won", "lost"):
            raise HTTPException(status_code=400, detail="bad status")
        o.status = str(payload["status"])
    if "amount" in payload:
        o.amount = int(payload["amount"] or 0)
    if "owner" in payload:
        o.owner = str(payload["owner"])[:120] if payload["owner"] else None
    db.commit()
    return {"id": o.id, "stage": o.stage, "status": o.status}


@router.post("/proposals")
def make_proposal(payload: ProposalIn, p: Principal = Depends(get_current_principal),
                  db: Session = Depends(get_db)):
    try:
        doc = create_proposal(db, company_id=p.workspace_id, kind=payload.kind,
                              title=payload.title, context=payload.context,
                              lead_id=payload.lead_id,
                              opportunity_id=payload.opportunity_id, actor=p.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return {"id": doc.id, "status": doc.status, "content": doc.content[:2000]}


@router.get("/analytics/funnel")
def funnel_r(p: Principal = Depends(get_current_principal),
             db: Session = Depends(get_db)):
    return funnel(db, company_id=p.workspace_id)


@router.get("/analytics/pipeline")
def pipeline_r(p: Principal = Depends(get_current_principal),
               db: Session = Depends(get_db)):
    return pipeline(db, company_id=p.workspace_id)


@router.get("/analytics/operations")
def ops_r(p: Principal = Depends(get_current_principal),
          db: Session = Depends(get_db)):
    return operations(db, company_id=p.workspace_id)


@router.get("/reports/weekly")
def weekly(p: Principal = Depends(get_current_principal),
           db: Session = Depends(get_db)):
    return weekly_report(db, company_id=p.workspace_id)


@router.get("/insights")
def insights(p: Principal = Depends(get_current_principal),
             db: Session = Depends(get_db)):
    """Proactive business signals from real workspace data (read-only)."""
    from datetime import UTC, datetime, timedelta

    from app.models.orm import (Approval, ApprovalStatus, FollowUp, Lead,
                                LeadStatus, Task, TaskState, Workflow,
                                WorkflowState)
    from sqlalchemy import func

    now = datetime.now(UTC)
    week_ago = now - timedelta(days=7)
    day_ago = now - timedelta(hours=24)
    out: list[dict] = []

    stalled = db.query(func.count(Lead.id)).filter(
        Lead.company_id == p.workspace_id,
        Lead.status == LeadStatus.QUALIFIED,
        (Lead.last_contacted_at.is_(None)) | (Lead.last_contacted_at < week_ago),
    ).scalar() or 0
    if stalled:
        out.append({"kind": "stalled_leads", "severity": "medium",
                    "message": f"{stalled} qualified lead(s) with no contact in 7 days.",
                    "action": "Run a follow-up: 'follow up with qualified leads'."})

    due = db.query(func.count(FollowUp.id)).filter(
        FollowUp.company_id == p.workspace_id, FollowUp.status == "scheduled",
        FollowUp.due_at <= now).scalar() or 0
    if due:
        out.append({"kind": "followup_due", "severity": "medium",
                    "message": f"{due} follow-up(s) due now.",
                    "action": "POST /followups/run-due (approval-gated sends)."})

    failed = db.query(func.count(Workflow.id)).filter(
        Workflow.company_id == p.workspace_id,
        Workflow.state == WorkflowState.FAILED,
        Workflow.updated_at >= day_ago).scalar() or 0
    if failed:
        out.append({"kind": "workflow_failures", "severity": "high",
                    "message": f"{failed} workflow(s) failed in the last 24h.",
                    "action": "Review Workflows, then POST /workflows/{id}/replan."})

    appr = db.query(func.count(Approval.id)).filter(
        Approval.company_id == p.workspace_id,
        Approval.status == ApprovalStatus.PENDING).scalar() or 0
    if appr:
        out.append({"kind": "approvals_waiting", "severity": "low",
                    "message": f"{appr} approval(s) waiting.",
                    "action": "Review the Approval Center."})

    old_tasks = db.query(func.count(Task.id)).filter(
        Task.state == TaskState.PENDING,
        Task.workflow_id.in_(
            db.query(Workflow.id).filter(Workflow.company_id == p.workspace_id)),
        Task.created_at < day_ago).scalar() or 0
    if old_tasks:
        out.append({"kind": "stuck_tasks", "severity": "medium",
                    "message": f"{old_tasks} task(s) pending over 24h.",
                    "action": "Resume or replan their workflows."})
    return {"type": "actual", "insights": out}


@router.get("/inbox")
def inbox(p: Principal = Depends(get_current_principal),
          db: Session = Depends(get_db)):
    """Unified support threads from inbound messages (workspace-scoped)."""
    from app.models.orm import InboundMessage, Lead

    rows = db.query(InboundMessage).filter(
        InboundMessage.company_id == p.workspace_id).order_by(
        InboundMessage.created_at.desc()).limit(100).all()
    threads: dict[str, dict] = {}
    for m in rows:
        key = m.lead_id or m.from_address
        t = threads.setdefault(key, {"lead_id": m.lead_id, "from": m.from_address,
                                     "channel": m.channel, "messages": []})
        lead = db.get(Lead, m.lead_id) if m.lead_id else None
        t["name"] = lead.company_name if lead else m.from_address
        t["messages"].append({"body": m.body, "classification": m.classification,
                              "at": m.created_at.isoformat() if m.created_at else None})
    return list(threads.values())


class InboxReplyIn(BaseModel):
    lead_id: str | None = None
    to: str = ""
    body: str = ""


@router.post("/inbox/reply")
def inbox_reply(payload: InboxReplyIn,
                p: Principal = Depends(get_current_principal),
                db: Session = Depends(get_db)):
    """Reply from the inbox. Honors auto-send policy; otherwise 409 with
    guidance to use the approval-gated Command Center flow."""
    from app.comms.providers import EMAIL
    from app.models.orm import CrmActivity, Lead

    if not payload.body.strip():
        raise HTTPException(status_code=400, detail="body required")
    to = payload.to.strip()
    if payload.lead_id:
        lead = db.get(Lead, payload.lead_id)
        if not lead or lead.company_id != p.workspace_id:
            raise HTTPException(status_code=404, detail="lead not found")
        to = to or (lead.email or "")
    if not to:
        raise HTTPException(status_code=400, detail="recipient required")
    from app.policy.risk import workspace_allows
    if not workspace_allows(db, company_id=p.workspace_id,
                            action="send_external_communication", channel="email"):
        raise HTTPException(
            status_code=409,
            detail="auto-send not enabled: enable Email auto-send in Settings, "
                   "or dispatch via Command Center for approval-gated send")
    res = EMAIL.send(to=to, subject="Re: your message", body=payload.body)
    if not res.get("ok"):
        raise HTTPException(status_code=422, detail=res.get("error") or "send failed")
    db.add(CrmActivity(company_id=p.workspace_id, lead_id=payload.lead_id,
                       kind="reply", subject="inbox reply", body=payload.body[:2000],
                       created_by=p.user_id))
    db.commit()
    return {"ok": True, "provider": res.get("provider")}


@router.get("/activities")
def activities(lead_id: str | None = None, limit: int = 50,
               p: Principal = Depends(get_current_principal),
               db: Session = Depends(get_db)):
    q = db.query(CrmActivity).filter(CrmActivity.company_id == p.workspace_id)
    if lead_id:
        q = q.filter(CrmActivity.lead_id == lead_id)
    rows = q.order_by(CrmActivity.created_at.desc()).limit(min(max(limit, 1), 200)).all()
    return [{"id": a.id, "kind": a.kind, "subject": a.subject,
             "lead_id": a.lead_id} for a in rows]
