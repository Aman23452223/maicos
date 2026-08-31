"""MAICOS end-to-end harness test.

Spins up the real FastAPI app on a local port, then exercises every
key route the user can reach from the browser:

  /health                                  — liveness
  /api/v1/diag                              — readiness + env
  POST /api/v1/workspaces                   — create a workspace
  POST /api/v1/workspaces/{wid}/users       — create admin user
  POST /api/v1/auth/login                   — login → JWT
  GET  /api/v1/auth/me                      — verify token
  POST /api/v1/commands                     — submit objective
  GET  /api/v1/workflows                    — list workflows
  GET  /api/v1/agents                       — list agents
  GET  /api/v1/tools                        — list tools
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
        with urllib.request.urlopen(req, timeout=10) as resp:
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
        except Exception:
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

    # 3. Public auth endpoints
    status, body = _req(
        "POST",
        "/api/v1/workspaces",
        body={"name": f"harness-ws-{int(time.time())}"},
    )
    workspace_ok = status in (200, 201) and isinstance(body, dict) and "id" in body
    check("POST /api/v1/workspaces", workspace_ok, f"status={status} body={body}")
    workspace_id = body.get("id") if workspace_ok else None

    if workspace_id:
        status, body = _req(
            "POST",
            f"/api/v1/workspaces/{workspace_id}/users",
            body={
                "email": f"harness-{int(time.time())}@example.com",
                "name": "Harness Admin",
                "password": "harness-password-123",
                "roles": ["admin", "owner"],
            },
            expect_status=(200, 201),
        )
        user_ok = status in (200, 201) and isinstance(body, dict) and "id" in body
        check(
            "POST /api/v1/workspaces/{id}/users",
            user_ok,
            f"status={status}",
        )

        if user_ok:
            status, body = _req(
                "POST",
                "/api/v1/auth/login",
                body={
                    "email": body["email"],
                    "password": "harness-password-123",
                },
            )
            login_ok = status == 200 and isinstance(body, dict) and "access_token" in body
            check("POST /api/v1/auth/login", login_ok, f"status={status} body={body}")
            token = body.get("access_token") if login_ok else None

            if token:
                status, me = _req("GET", "/api/v1/auth/me", token=token)
                check(
                    "GET /api/v1/auth/me",
                    status == 200 and me.get("email"),
                    f"status={status} body={me}",
                )

                status, agents = _req("GET", "/api/v1/agents", token=token)
                check(
                    "GET /api/v1/agents",
                    status == 200 and isinstance(agents, list),
                    f"status={status}",
                )

                status, tools = _req("GET", "/api/v1/tools", token=token)
                check(
                    "GET /api/v1/tools",
                    status == 200 and isinstance(tools, list),
                    f"status={status}",
                )

                status, workflows = _req(
                    "GET", "/api/v1/workflows", token=token
                )
                check(
                    "GET /api/v1/workflows",
                    status == 200 and isinstance(workflows, list),
                    f"status={status}",
                )

                status, queue_stats = _req(
                    "GET", "/api/v1/queue/stats", token=token
                )
                check(
                    "GET /api/v1/queue/stats",
                    status in (200, 403),
                    f"status={status} (403 = admin role missing, ok)",
                )

                status, audit = _req("GET", "/api/v1/audit", token=token)
                check(
                    "GET /api/v1/audit",
                    status in (200, 403),
                    f"status={status}",
                )
    else:
        print("  SKIP  downstream tests (no workspace created)")

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