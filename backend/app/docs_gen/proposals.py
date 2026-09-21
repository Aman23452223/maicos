"""Template-based proposals/quotations/SOWs. Stored, approval-gated on send."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.audit.service import record
from app.models.orm import Lead, Opportunity, ProposalDocument


def render(kind: str, ctx: dict) -> str:
    name = ctx.get("company_name") or ctx.get("title") or "Customer"
    amount = ctx.get("amount", "")
    lines = [f"# {kind.title()} for {name}", ""]
    if amount != "":
        lines.append(f"Amount: {amount}")
    for k in ("scope", "timeline", "terms", "summary"):
        if ctx.get(k):
            lines += ["", f"## {k.title()}", str(ctx[k])]
    if ctx.get("services"):
        lines += ["", "## Services"]
        for s in ctx["services"]:
            lines.append(f"- {s}")
    return "\n".join(lines)[:20000]


def create(db: Session, *, company_id: str, kind: str, title: str,
           context: dict, lead_id: str | None = None,
           opportunity_id: str | None = None, actor: str = "user") -> ProposalDocument:
    if lead_id:
        lead = db.get(Lead, lead_id)
        if not lead or lead.company_id != company_id:
            raise ValueError("lead not found")
    if opportunity_id:
        opp = db.get(Opportunity, opportunity_id)
        if not opp or opp.company_id != company_id:
            raise ValueError("opportunity not found")
    doc = ProposalDocument(company_id=company_id, lead_id=lead_id,
                           opportunity_id=opportunity_id, kind=kind,
                           title=title[:255], content=render(kind, context),
                           status="draft", meta={"context_keys": sorted(context)})
    db.add(doc)
    db.flush()
    record(db, company_id=company_id, actor=actor, action="proposal.created",
           target_type="proposal", target_id=doc.id, details={"kind": kind})
    return doc
