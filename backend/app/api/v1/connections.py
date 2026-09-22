"""Authorized integration connections (separate from Business Intel).

- Secrets stay backend-only (env). Frontend never sees tokens.
- Every connect/disconnect/configure/action is audited per workspace.
- Agents use catalog.execute_action, never raw credentials.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.audit.service import record
from app.core.context import Principal
from app.core.security import get_current_principal, require_role
from app.db.session import get_db
from app.integrations.catalog import CATALOG, execute_action, get_entry, verify
from app.models.orm import WorkspaceIntegration

router = APIRouter(tags=["connections"])


class ConfigureIn(BaseModel):
    # Values are written to process env only (ephemeral, never echoed back).
    credentials: dict[str, str] = {}


@router.get("/integrations/catalog")
def catalog(p: Principal = Depends(get_current_principal),
            db: Session = Depends(get_db)):
    rows = db.query(WorkspaceIntegration).filter(
        WorkspaceIntegration.company_id == p.workspace_id).all()
    state = {r.provider: r for r in rows}
    out = []
    for e in CATALOG:
        r = state.get(e["provider"])
        v = verify(e["provider"])
        status = (r.status if r and r.status in ("connected", "disconnected")
                  else ("configuration_required" if not v.get("ok") else "connected"))
        out.append({
            "provider": e["provider"], "name": e["name"],
            "description": e["description"], "auth_type": e["auth_type"],
            "actions": e["actions"], "status": status,
            "detail": v.get("error", ""),
            "account": (r.meta or {}).get("account", "") if r else "",
            "note": e.get("note", ""),
        })
    return {"workspace_id": p.workspace_id, "integrations": out}


@router.post("/integrations/{provider}/connect")
def connect(provider: str, payload: dict | None = None,
            p: Principal = Depends(require_role("admin", "owner")),
            db: Session = Depends(get_db)):
    entry = get_entry(provider)
    if not entry:
        raise HTTPException(status_code=404, detail="unknown provider")
    if (payload or {}).get("url"):
        raise HTTPException(
            status_code=400,
            detail="A URL is not a credential. Public pages belong in Business Intel; "
                   "connect requires authorized API credentials.")
    v = verify(provider)
    status = "connected" if v.get("ok") else "configuration_required"
    row = db.query(WorkspaceIntegration).filter(
        WorkspaceIntegration.company_id == p.workspace_id,
        WorkspaceIntegration.provider == provider).first()
    if not row:
        row = WorkspaceIntegration(company_id=p.workspace_id, provider=provider,
                                   status=status, meta={})
        db.add(row)
    else:
        row.status = status
    meta = dict(row.meta or {})
    if payload and payload.get("account"):
        meta["account"] = str(payload["account"])[:200]
    row.meta = meta
    record(db, company_id=p.workspace_id, actor=p.user_id,
           action="integration.connect", target_type="integration",
           target_id=provider,
           details={"status": status, "verified": bool(v.get("ok")),
                    "error": v.get("error", "")[:300]})
    db.commit()
    if not v.get("ok"):
        return {"provider": provider, "status": "configuration_required",
                "detail": v.get("error", "")}
    return {"provider": provider, "status": "connected"}


@router.post("/integrations/{provider}/disconnect")
def disconnect(provider: str, p: Principal = Depends(require_role("admin", "owner")),
               db: Session = Depends(get_db)):
    if not get_entry(provider):
        raise HTTPException(status_code=404, detail="unknown provider")
    row = db.query(WorkspaceIntegration).filter(
        WorkspaceIntegration.company_id == p.workspace_id,
        WorkspaceIntegration.provider == provider).first()
    if row:
        row.status = "disconnected"
    else:
        db.add(WorkspaceIntegration(company_id=p.workspace_id, provider=provider,
                                    status="disconnected", meta={}))
    record(db, company_id=p.workspace_id, actor=p.user_id,
           action="integration.disconnect", target_type="integration",
           target_id=provider, details={})
    db.commit()
    return {"provider": provider, "status": "disconnected"}


@router.post("/integrations/{provider}/configure")
def configure(provider: str, payload: ConfigureIn,
              p: Principal = Depends(require_role("admin", "owner")),
              db: Session = Depends(get_db)):
    """Store credentials process-side only (env). Never returned."""
    from app.core.secrets import set_runtime_secret

    entry = get_entry(provider)
    if not entry:
        raise HTTPException(status_code=404, detail="unknown provider")
    saved = []
    for k, v in (payload.credentials or {}).items():
        ku = k.strip().upper()
        if ku in [e.upper() for e in entry["required_envs"]] and v:
            set_runtime_secret(ku, v)
            saved.append(ku)
    v = verify(provider)
    record(db, company_id=p.workspace_id, actor=p.user_id,
           action="integration.configure", target_type="integration",
           target_id=provider,
           details={"saved_keys": [s[:4] + "***" for s in saved],
                    "verified": bool(v.get("ok"))})
    db.commit()
    return {"provider": provider, "saved": len(saved) > 0,
            "status": "connected" if v.get("ok") else "configuration_required",
            "detail": v.get("error", "")}


@router.post("/integrations/{provider}/actions/{action}")
def run_action(provider: str, action: str, payload: dict | None = None,
               p: Principal = Depends(get_current_principal),
               db: Session = Depends(get_db)):
    """Controlled agent/operator action gateway (audited, workspace-scoped)."""
    out = execute_action(provider, action, payload or {},
                         workspace_id=p.workspace_id)
    record(db, company_id=p.workspace_id, actor=p.user_id,
           action="integration.action", target_type="integration",
           target_id=f"{provider}.{action}",
           details={"ok": bool(out.get("ok")),
                    "status": out.get("status", "")})
    db.commit()
    if not out.get("ok"):
        raise HTTPException(status_code=422, detail=out.get("error") or out.get("status"))
    return out
