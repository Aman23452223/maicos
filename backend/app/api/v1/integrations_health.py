"""Workspace integration health (Phase 31). No secrets exposed."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import Principal
from app.core.security import get_current_principal
from app.db.session import get_db

router = APIRouter(tags=["integrations"])


def _env_present(*names: str) -> bool:
    return any(bool(os.environ.get(n)) for n in names)


@router.get("/integrations/status")
def status(p: Principal = Depends(get_current_principal),
           db: Session = Depends(get_db)):
    from app.capabilities.registry import enabled_for
    from app.models.orm import WorkspaceIntegration

    rows = db.query(WorkspaceIntegration).filter(
        WorkspaceIntegration.company_id == p.workspace_id).all()
    override = {r.provider: r.status for r in rows}
    providers = [
        {"provider": "search_tavily", "needs": ["SEARCH_PROVIDER_API_KEY"],
         "configured": _env_present("SEARCH_PROVIDER_API_KEY", "TAVILY_API_KEY")},
        {"provider": "email_sendgrid", "needs": ["SENDGRID_API_KEY"],
         "configured": _env_present("SENDGRID_API_KEY")},
        {"provider": "email_smtp", "needs": ["SMTP_HOST"],
         "configured": _env_present("SMTP_HOST")},
        {"provider": "crm_hubspot", "needs": ["HUBSPOT_API_KEY"],
         "configured": _env_present("HUBSPOT_API_KEY", "HUBSPOT_TOKEN")},
        {"provider": "calendar_google", "needs": ["GOOGLE_CALENDAR_CREDENTIALS"],
         "configured": _env_present("GOOGLE_CALENDAR_CREDENTIALS")},
        {"provider": "messaging_whatsapp", "needs": ["WHATSAPP_TOKEN"],
         "configured": _env_present("WHATSAPP_TOKEN")},
        {"provider": "payments", "needs": ["RAZORPAY_KEY", "STRIPE_KEY"],
         "configured": _env_present("RAZORPAY_KEY", "STRIPE_KEY")},
        {"provider": "embeddings", "needs": ["OPENAI_API_KEY"],
         "configured": _env_present("OPENAI_API_KEY")},
    ]
    out = []
    for item in providers:
        st = override.get(item["provider"],
                          "healthy" if item["configured"] else "not_configured")
        out.append({"provider": item["provider"], "status": st,
                    "needs": item["needs"],
                    "configured": item["configured"]})
    return {"workspace_id": p.workspace_id,
            "capabilities": sorted(enabled_for(db, company_id=p.workspace_id)),
            "providers": out}
