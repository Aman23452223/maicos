"""OAuth connect flows (Google, Meta). Real redirects; no secrets to frontend.

Without provider client credentials configured, returns NOT_CONFIGURED
with exact setup steps instead of a fake URL.
"""
from __future__ import annotations

import os
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.audit.service import record
from app.core.context import Principal
from app.core.security import get_current_principal
from app.db.session import get_db

router = APIRouter(tags=["oauth"])

OAUTH_CONFIG: dict[str, dict] = {
    "google": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": ("https://www.googleapis.com/auth/calendar "
                   "https://www.googleapis.com/auth/spreadsheets"),
        "env_id": "GOOGLE_OAUTH_CLIENT_ID",
        "env_secret": "GOOGLE_OAUTH_CLIENT_SECRET",
        "env_redirect": "GOOGLE_OAUTH_REDIRECT",
    },
    "meta": {
        "auth_url": "https://www.facebook.com/v19.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v19.0/oauth/access_token",
        "scopes": "whatsapp_business_messaging,instagram_basic,pages_show_list",
        "env_id": "META_APP_ID",
        "env_secret": "META_APP_SECRET",
        "env_redirect": "META_OAUTH_REDIRECT",
    },
}


def _redirect_base() -> str:
    return (os.environ.get("OAUTH_REDIRECT_BASE", "").rstrip("/")
            or "https://maicos-production.up.railway.app")


@router.get("/integrations/{provider}/oauth/start")
def oauth_start(provider: str, p: Principal = Depends(get_current_principal),
                db: Session = Depends(get_db)):
    cfg = OAUTH_CONFIG.get(provider)
    if not cfg:
        raise HTTPException(status_code=404, detail="oauth not supported for provider")
    _ = (db, p)
    cid = os.environ.get(cfg["env_id"], "")
    if not cid:
        raise HTTPException(
            status_code=422,
            detail=(f"NOT_CONFIGURED: set {cfg['env_id']} (+ {cfg['env_secret']}) "
                    f"in Railway Variables, then retry. Steps: provider console -> "
                    f"OAuth client -> redirect URI "
                    f"{_redirect_base()}/api/v1/integrations/{provider}/oauth/callback"))
    redirect = os.environ.get(cfg["env_redirect"],
                              f"{_redirect_base()}/api/v1/integrations/{provider}/oauth/callback")
    params = {"client_id": cid, "redirect_uri": redirect, "response_type": "code",
              "scope": cfg["scopes"],
              "state": f"{p.workspace_id}:{p.user_id}"}
    return {"auth_url": f"{cfg['auth_url']}?{urlencode(params)}"}


@router.get("/integrations/{provider}/oauth/callback")
def oauth_callback(provider: str, code: str = "", state: str = "",
                   error: str = ""):
    """Provider redirects here. Exchanges code server-side; token never
    touches the browser beyond this redirect (ephemeral process storage;
    persist via Railway Variables for permanence)."""
    from sqlalchemy.orm import Session as _Session

    from app.core.secrets import set_runtime_secret
    from app.db.session import SessionLocal

    cfg = OAUTH_CONFIG.get(provider)
    if not cfg:
        raise HTTPException(status_code=404, detail="oauth not supported for provider")
    if error:
        raise HTTPException(status_code=400, detail=f"provider refused: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="missing code")
    secret = os.environ.get(cfg["env_secret"], "")
    cid = os.environ.get(cfg["env_id"], "")
    if not secret or not cid:
        raise HTTPException(status_code=422, detail="NOT_CONFIGURED: app secret missing")
    redirect = os.environ.get(cfg["env_redirect"],
                              f"{_redirect_base()}/api/v1/integrations/{provider}/oauth/callback")
    try:
        import httpx
        r = httpx.post(cfg["token_url"],
                       data={"client_id": cid, "client_secret": secret,
                             "redirect_uri": redirect, "code": code,
                             "grant_type": "authorization_code"}, timeout=20.0)
        data = r.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"token exchange failed: {exc}") from exc
    token = data.get("access_token", "")
    if not token:
        raise HTTPException(status_code=502,
                            detail=f"no access_token: {str(data)[:200]}")
    set_runtime_secret(f"{provider.upper()}_OAUTH_TOKEN", token)
    ws = (state.split(":")[0] or "") if state else ""
    db: _Session = SessionLocal()
    try:
        from app.models.orm import WorkspaceIntegration

        if ws:
            row = db.query(WorkspaceIntegration).filter(
                WorkspaceIntegration.company_id == ws,
                WorkspaceIntegration.provider == provider).first()
            if not row:
                row = WorkspaceIntegration(company_id=ws, provider=provider,
                                           status="connected",
                                           meta={"via": "oauth"})
                db.add(row)
            else:
                row.status = "connected"
            record(db, company_id=ws, actor="oauth",
                   action="integration.oauth_connected", target_type="integration",
                   target_id=provider, details={})
            db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/?oauth=connected", status_code=302)
