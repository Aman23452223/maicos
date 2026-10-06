"""MAICOS end-to-end harness test.

Spins up the real FastAPI app on a local port, then exercises every
key route the user can reach from the browser:

  /health                                  — liveness
  /api/v1/diag                              — readiness + env
  POST /api/v1/auth/register                — create account + workspace + JWT
  POST /api/v1/auth/login                   — login → JWT
  GET  /api/v1/auth/me                      — verify token
  GET  /api/v1/workspaces                   — auto-created workspace
  POST /api/v1/company/decisions            — write path
  POST /api/v1/commands                     — full lead pipeline (regression)
  GET  /api/v1/workflows                    — list workflows
  GET  /api/v1/agents                       — list agents
  GET  /api/v1/tools                        — list tools
  GET  /api/v1/leads                        — leads persisted by pipeline
  GET  /api/v1/queue/stats                  — queue stats
  GET  /api/v1/audit                        — audit log

For routes that need a working DATABASE_URL pointing at Postgres, the
test uses the URL the user provides via $MAICOS_HARNESS_DATABASE_URL.
Without that, the harness runs in "schema-less" mode and just hits
routes that don't need the DB.

Exit code 0 = all routes returned as expected.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

# Force a non-default port so we don't conflict with any running dev server
PORT = int(os.environ.get("MAICOS_HARNESS_PORT", "18800"))
BASE = f"http://127.0.0.1:{PORT}"
REQUEST_TIMEOUT = int(os.environ.get("MAICOS_HARNESS_TIMEOUT", "60"))

# Either use the user's DB (if they set MAICOS_HARNESS_DATABASE_URL) or
# run with a fake URL that fails on the first DB-touching route. Either
# way, /health and /diag should return 200.
if "MAICOS_HARNESS_DATABASE_URL" in os.environ:
    os.environ["DATABASE_URL"] = os.environ["MAICOS_HARNESS_DATABASE_URL"]
os.environ.setdefault("APP_SECRET_KEY", "harness-secret")
os.environ.setdefault("APP_ENV", "harness")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
os.environ.setdefault("WORKER_ENABLED", "true")
os.environ.setdefault("WORKER_ID", "harness")
os.environ.setdefault("PORT", str(PORT))


def _req(
    method: str,
    path: str,
    *,
    body: Any | None = None,
    token: str | None = None,
    expect_status: tuple[int, ...] = (200, 201),
) -> tuple[int, dict | str]:
    url = f"{BASE}{path}"
    data = None
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        # Real Postgres + schema bootstrap on first call can be slow.
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return exc.code, raw
    except Exception as exc:  # noqa: BLE001
        return 0, str(exc)


PASSED: list[str] = []
FAILED: list[tuple[str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    if ok:
        PASSED.append(name)
        print(f"  PASS  {name}")
    else:
        FAILED.append((name, detail))
        print(f"  FAIL  {name}  {detail}")


def main() -> int:
    # Import after env is set
    import uvicorn

    from app.main import app

    server_error: list[str] = []

    def run() -> None:
        try:
            uvicorn.run(
                app,
                host="127.0.0.1",
                port=PORT,
                log_level="error",
            )
        except Exception as exc:  # noqa: BLE001
            server_error.append(repr(exc))

    t = threading.Thread(target=run, daemon=True)
    t.start()
    # Wait for uvicorn to start
    for _ in range(40):
        try:
            urllib.request.urlopen(f"{BASE}/health", timeout=1)
            break
        except Exception:  # noqa: BLE001
            time.sleep(0.25)
    else:
        print("server failed to start:", server_error)
        return 2

    print(f"=== Harness against {BASE} ===\n")

    # 1. Liveness
    status, body = _req("GET", "/health")
    check("GET /health", status == 200, str(body))

    # 2. Readiness + env
    status, body = _req("GET", "/api/v1/diag")
    check(
        "GET /api/v1/diag",
        status == 200,
        f"status={status}",
    )
    if isinstance(body, dict):
        check(
            "diag exposes app_env",
            "app_env" in body,
            str(list(body.keys())),
        )
        check(
            "diag exposes database_url (redacted)",
            "database_url" in body
            and "***" in body.get("database_url", ""),
            str(body.get("database_url", "")),
        )
        check(
            "diag reports db.ok (true|false)",
            "db" in body and isinstance(body["db"], dict) and "ok" in body["db"],
            str(body.get("db")),
        )

    # 3. Public auth endpoints — register creates the workspace + JWT.
    #    (POST /api/v1/workspaces is authenticated; anonymous creation was
    #    removed when multi-tenant auth landed.)
    stamp = int(time.time())
    email = f"harness-{stamp}@example.com"
    password = "harness-password-123"

    status, body = _req(
        "POST",
        "/api/v1/auth/register",
        body={"email": email, "password": password, "name": "Harness Admin"},
    )
    register_ok = status in (200, 201) and isinstance(body, dict) and "access_token" in body
    check("POST /api/v1/auth/register", register_ok, f"status={status} body={body}")
    token = body.get("access_token") if register_ok else None

    if token:
        status, me = _req("GET", "/api/v1/auth/me", token=token)
        check("GET /api/v1/auth/me",
              status == 200 and me.get("email"),
              f"status={status} body={me}")

        status, wss = _req("GET", "/api/v1/workspaces", token=token)
        workspace_ok = status == 200 and isinstance(wss, list) and wss
        check("GET /api/v1/workspaces (auto-created)", workspace_ok,
              f"status={status} body={wss}")
        workspace_id = wss[0]["id"] if workspace_ok else None

        # Sign in again with the same credentials -> proves password login.
        status, body = _req("POST", "/api/v1/auth/login",
                            body={"email": email, "password": password})
        login_ok = status == 200 and isinstance(body, dict) and "access_token" in body
        check("POST /api/v1/auth/login", login_ok, f"status={status} body={body}")

        # Unauthenticated access must be rejected.
        status, _ = _req("GET", "/api/v1/leads")
        check("GET /api/v1/leads without token is 401", status == 401,
              f"status={status}")

        for name, path in [("GET /api/v1/agents", "/api/v1/agents"),
                           ("GET /api/v1/tools", "/api/v1/tools"),
                           ("GET /api/v1/workflows", "/api/v1/workflows"),
                           ("GET /api/v1/leads", "/api/v1/leads"),
                           ("GET /api/v1/company/team", "/api/v1/company/team")]:
            status, out = _req("GET", path, token=token)
            check(name, status == 200 and isinstance(out, list),
                  f"status={status}")

        status, cat = _req("GET", "/api/v1/integrations/catalog", token=token)
        check("GET /api/v1/integrations/catalog",
              status == 200 and isinstance(cat, dict) and "integrations" in cat,
              f"status={status} keys={list(cat) if isinstance(cat, dict) else type(cat)}")

        for name, path in [("GET /api/v1/queue/stats", "/api/v1/queue/stats"),
                           ("GET /api/v1/audit", "/api/v1/audit")]:
            status, _ = _req("GET", path, token=token)
            check(name, status in (200, 403), f"status={status}")

        # Write path + the lead pipeline that used to dead-end after discover.
        status, dec = _req("POST", "/api/v1/company/decisions", token=token,
                           body={"title": "Harness decision", "context": "harness"})
        check("POST /api/v1/company/decisions",
              status in (200, 201) and isinstance(dec, dict) and "id" in dec,
              f"status={status} body={dec}")

        status, wf = _req(
            "POST", "/api/v1/commands", token=token,
            body={"objective": "Find qualified B2B SaaS prospects and add them to CRM"},
        )
        wf_ok = status in (200, 201) and isinstance(wf, dict) and "id" in wf
        check("POST /api/v1/commands (lead pipeline)", wf_ok,
              f"status={status} body={wf}")

        if wf_ok:
            wf_id = wf["id"]
            # The worker runs the DAG in the background; poll to a terminal state.
            terminal = {"COMPLETED", "PARTIAL", "FAILED", "CANCELLED",
                        "WAITING_APPROVAL", "WAITING_INPUT"}
            final: dict = {}
            deadline = time.time() + 180
            while time.time() < deadline:
                time.sleep(5)
                status, final = _req("GET", f"/api/v1/workflows/{wf_id}",
                                     token=token)
                if status == 200 and final.get("state") in terminal:
                    break

            status, runs = _req("GET", f"/api/v1/workflows/{wf_id}/runs",
                                token=token)
            errors = [r for r in (runs or []) if r.get("error")]
            check("lead pipeline runs without agent errors", status == 200 and not errors,
                  f"status={status} errors={[r.get('error') for r in errors]}")

            status, leads = _req("GET", "/api/v1/leads", token=token)
            check("discover persisted leads into CRM", status == 200 and bool(leads),
                  f"status={status} count={len(leads or [])}")

            check("lead pipeline completes (not PARTIAL)",
                  final.get("state") == "COMPLETED",
                  f"state={final.get('state')}")
    else:
        print("  SKIP  downstream tests (registration failed)")

    print()
    print(f"=== Summary: {len(PASSED)} passed, {len(FAILED)} failed ===")
    if FAILED:
        for name, detail in FAILED:
            print(f"  - {name}: {detail}")
    return 0 if not FAILED else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(2)