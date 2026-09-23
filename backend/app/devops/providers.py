"""Real DevOps adapters. No token -> NOT_CONFIGURED. Never fake deploys."""
from __future__ import annotations

import os


def _h() -> dict:
    out = {}
    if os.environ.get("GITHUB_TOKEN"):
        out["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    return out


def github_repo_info(repo: str) -> dict:
    """Read-only repo metadata (requires GITHUB_TOKEN)."""
    if not os.environ.get("GITHUB_TOKEN"):
        return {"ok": False, "status": "NOT_CONFIGURED",
                "error": "GITHUB_TOKEN not configured"}
    try:
        import httpx
        r = httpx.get(f"https://api.github.com/repos/{repo}", headers=_h(),
                      timeout=15.0)
    except Exception as exc:
        return {"ok": False, "status": "PROVIDER_ERROR", "error": str(exc)[:300]}
    if r.status_code == 401:
        return {"ok": False, "status": "INVALID_CONFIGURATION",
                "error": "GitHub token rejected"}
    if r.status_code != 200:
        return {"ok": False, "status": "PROVIDER_ERROR",
                "error": f"GitHub HTTP {r.status_code}"}
    d = r.json()
    return {"ok": True, "status": "OK",
            "data": {"full_name": d.get("full_name"),
                     "default_branch": d.get("default_branch"),
                     "open_issues": d.get("open_issues_count")}}


def github_open_pr(repo: str, title: str, head: str, base: str,
                   body: str = "") -> dict:
    """Open a PR (requires token + approval upstream)."""
    if not os.environ.get("GITHUB_TOKEN"):
        return {"ok": False, "status": "NOT_CONFIGURED",
                "error": "GITHUB_TOKEN not configured"}
    try:
        import httpx
        r = httpx.post(f"https://api.github.com/repos/{repo}/pulls",
                       headers={**_h(), "Accept": "application/vnd.github+json"},
                       json={"title": title, "head": head, "base": base,
                             "body": body}, timeout=15.0)
    except Exception as exc:
        return {"ok": False, "status": "PROVIDER_ERROR", "error": str(exc)[:300]}
    if r.status_code not in (200, 201):
        return {"ok": False, "status": "PROVIDER_ERROR",
                "error": f"GitHub HTTP {r.status_code}: {r.text[:200]}"}
    return {"ok": True, "status": "OK", "data": {"url": r.json().get("html_url")}}


def vercel_deployments(project: str) -> dict:
    if not os.environ.get("VERCEL_TOKEN"):
        return {"ok": False, "status": "NOT_CONFIGURED",
                "error": "VERCEL_TOKEN not configured"}
    try:
        import httpx
        r = httpx.get("https://api.vercel.com/v6/deployments",
                      headers={"Authorization": f"Bearer {os.environ['VERCEL_TOKEN']}"},
                      params={"projectId": project, "limit": 5}, timeout=15.0)
    except Exception as exc:
        return {"ok": False, "status": "PROVIDER_ERROR", "error": str(exc)[:300]}
    if r.status_code == 403:
        return {"ok": False, "status": "INVALID_CONFIGURATION",
                "error": "Vercel token rejected"}
    if r.status_code != 200:
        return {"ok": False, "status": "PROVIDER_ERROR",
                "error": f"Vercel HTTP {r.status_code}"}
    return {"ok": True, "status": "OK",
            "data": [{"url": d.get("url"), "state": d.get("state")}
                     for d in r.json().get("deployments", [])]}


def railway_status() -> dict:
    if not os.environ.get("RAILWAY_TOKEN"):
        return {"ok": False, "status": "NOT_CONFIGURED",
                "error": "RAILWAY_TOKEN not configured"}
    try:
        import httpx
        r = httpx.post("https://backboard.railway.com/graphql/v2",
                       headers={"Authorization": f"Bearer {os.environ['RAILWAY_TOKEN']}"},
                       json={"query": "{ me { email } }"}, timeout=15.0)
    except Exception as exc:
        return {"ok": False, "status": "PROVIDER_ERROR", "error": str(exc)[:300]}
    if r.status_code != 200:
        return {"ok": False, "status": "PROVIDER_ERROR",
                "error": f"Railway HTTP {r.status_code}"}
    return {"ok": True, "status": "OK", "data": r.json().get("data", {})}
