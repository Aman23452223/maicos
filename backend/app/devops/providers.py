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


def github_create_files_pr(repo: str, branch: str, base: str,
                           files: list[dict], title: str,
                           body: str = "") -> dict:
    """Create branch + commit given files + open PR (Git Data API).

    Real pushes only; approval is enforced upstream by the caller.
    Bounds: <=10 files, <=4000 chars each.
    """
    if not os.environ.get("GITHUB_TOKEN"):
        return {"ok": False, "status": "NOT_CONFIGURED",
                "error": "GITHUB_TOKEN not configured"}
    files = [f for f in (files or [])
             if f.get("path") and f.get("content")][:10]
    if not files:
        return {"ok": False, "status": "FAILED", "error": "no files to push"}
    for f in files:
        f["content"] = str(f["content"])[:4000]
    if not branch or branch == base:
        return {"ok": False, "status": "FAILED",
                "error": "a new branch name is required (never direct-to-main)"}
    try:
        import base64

        import httpx

        h = {**_h(), "Accept": "application/vnd.github+json"}
        base_url = f"https://api.github.com/repos/{repo}"
        ref = httpx.get(f"{base_url}/git/ref/heads/{base}", headers=h,
                        timeout=15.0)
        if ref.status_code != 200:
            return {"ok": False, "status": "PROVIDER_ERROR",
                    "error": f"base branch lookup HTTP {ref.status_code}"}
        base_sha = ref.json()["object"]["sha"]
        blobs = []
        for f in files:
            b = httpx.post(f"{base_url}/git/blobs", headers=h,
                           json={"content": base64.b64encode(
                               f["content"].encode()).decode(),
                                 "encoding": "base64"}, timeout=15.0)
            if b.status_code not in (200, 201):
                return {"ok": False, "status": "PROVIDER_ERROR",
                        "error": f"blob HTTP {b.status_code}"}
            blobs.append({"path": f["path"], "mode": "100644",
                          "type": "blob", "sha": b.json()["sha"]})
        tree = httpx.post(f"{base_url}/git/trees", headers=h,
                          json={"base_tree": base_sha, "tree": blobs},
                          timeout=15.0)
        if tree.status_code not in (200, 201):
            return {"ok": False, "status": "PROVIDER_ERROR",
                    "error": f"tree HTTP {tree.status_code}"}
        commit = httpx.post(f"{base_url}/git/commits", headers=h,
                            json={"message": title[:200],
                                  "tree": tree.json()["sha"],
                                  "parents": [base_sha]}, timeout=15.0)
        if commit.status_code not in (200, 201):
            return {"ok": False, "status": "PROVIDER_ERROR",
                    "error": f"commit HTTP {commit.status_code}"}
        ref_up = httpx.post(f"{base_url}/git/refs", headers=h,
                            json={"ref": f"refs/heads/{branch}",
                                  "sha": commit.json()["sha"]}, timeout=15.0)
        if ref_up.status_code not in (200, 201):
            return {"ok": False, "status": "PROVIDER_ERROR",
                    "error": f"branch HTTP {ref_up.status_code}: "
                             f"{ref_up.text[:150]}"}
    except Exception as exc:
        return {"ok": False, "status": "PROVIDER_ERROR", "error": str(exc)[:300]}
    return github_open_pr(repo, title, branch, base,
                          body + "\n\nFiles generated by MAICOS. Review required.")


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
