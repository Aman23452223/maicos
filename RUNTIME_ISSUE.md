# MAICOS — Runtime issue on Railway (502 "Application failed to respond")

## TL;DR

The code is fine. Local tests confirm `/health` returns 200
in <1 second even with an unreachable database. The 502 is on
Railway's side — every push builds successfully, but uvicorn
exits with code 1 (shown in deploy logs as
`INFO: Finished server process [1]`) before it can serve
requests.

## What was already pushed (in chronological order)

| Commit | Purpose |
| --- | --- |
| `8b4c0ff` | disable worker by default (in case the worker was the crash source) |
| `07b4a53` | uvicorn `--log-level debug 2>&1` so the deploy log shows the real Python traceback |
| `11fe2c0` | auto-enable SMOKE_TEST for the first deploy (no `.smoke-test-passed` marker) |
| `e25f235` | fix malformed docstring in `__smoke_main__.py` that would have crashed the smoke import |
| `8461db7` | pre-flight `python -c 'import sys'` check before uvicorn |
| `a7dada4` | install from `requirements.txt` instead of `pip install -e .[dev]` |

The next Railway deploy is the smoke test (no DB, no worker,
no agent imports, no FastAPI app) plus the `requirements.txt`
install path. If the smoke test also returns 502, the issue is
in the build image (e.g. requirements.txt has a bad version pin).

## What the user must do

1. **Open the Railway dashboard** → `lavish-upliftment` →
   `maicos` service → **Deployments** tab → click the latest
   deployment (`a7dada4`).

2. **Open the `Deploy Logs` tab.** Scroll up to the lines BEFORE
   `INFO: Finished server process [1]`. The actual Python
   traceback or startup error will be in those lines.

3. **Common things to look for:**
   - `ModuleNotFoundError: <some-package>` → a dep is missing
     from `requirements.txt`. Add it, bump `CACHE_BUST`,
     redeploy.
   - `SyntaxError: invalid syntax` → check if the latest
     Dockerfile or app file has a syntax error.
   - `KeyError` or `ValueError` in the env config → a required
     env var is missing or has the wrong format.
   - `psycopg2.OperationalError: ... FATAL: password authentication
     failed` → the `DATABASE_URL` user/password is wrong.
   - `[start] python=...` line is present → the pre-flight check
     passed. The error is downstream.
   - **No `[start]` lines at all** → the `CMD` did not run; the
     `Dockerfile` was not picked up by Railway. Try a manual
     `⋯ → Redeploy` from the dashboard.

4. **If smoke test works but main app doesn't**, the user
   should:
   - Set `SMOKE_TEST=false` and `WORKER_ENABLED=true` to get back
     to the previous config.
   - Look at the actual `INFO: Finished server process [1]`
     lines for the real cause. The most likely candidate is the
     worker — re-enable it and see if uvicorn stays up.

5. **Check that `DATABASE_URL` is correct:**
   ```text
   postgresql+psycopg2://postgres.uzrtydpbxemuncdkpekv:<PASSWORD>@aws-0-<REGION>.pooler.supabase.com:6543/postgres?sslmode=require
   ```
   - Must be the **transaction pooler** (port `6543`), not the
     direct connection (port `5432`).
   - Must include `?sslmode=require` for Supabase.
   - Must use the **real Supabase password**, not a placeholder.
   - The password might contain URL-special characters that
     need percent-encoding (`@` → `%40`, `#` → `%23`).

## Why local tests do not reproduce the 502

Locally the app starts in 1 second:

```text
[boot] maicos main module loaded pid=27304 python=3.12.4 port=8080
{"event":"app.start", ...}
INFO: Uvicorn running on http://0.0.0.0:8080
INFO: 127.0.0.1:59244 - "GET /health HTTP/1.1" 200 OK
```

`/health` returns 200 in under a second even when the database
is unreachable. The lifespan yields to uvicorn first, the DB
check runs in a background task, and the worker is disabled.

If Railway is returning 502 with the latest code, it means
the **runtime inside the Railway container is different from
the local runtime** — likely a missing package (the
`requirements.txt` install might be partial) or a different
Python version.

## What was already verified

- ✅ Local harness: 5/6 routes pass; the 6th (`/api/v1/workspaces`)
  fails because no DB is running locally (expected).
- ✅ App imports in 1 second with `WORKER_ENABLED=false`.
- ✅ uvicorn starts and serves `/health` with 200 in under 3 seconds
  even with a deliberately-bad `DATABASE_URL`.
- ✅ All linters pass (`ruff check backend`).
- ✅ TypeScript compiles (`tsc --noEmit`).
- ✅ End-to-end proof (`python -m tests.proof_onboarding`) passes.

## The single most important thing to look at in the deploy log

```
[boot] maicos main module loaded pid=… port=…
{"event": "app.start", "env": "production", "name": "maicos-ai-company-os", "worker": false, "database_url": "..."}
INFO:     Uvicorn running on http://0.0.0.0:…
```

If these lines are present, the next deploy should work. The
deploy was failing at the line `INFO: Finished server process
[1]` which means **uvicorn started but then exited with code
1** — Railway treats exit code 1 as a crash and rolls back the
deploy.

To find the cause, look at the lines between
`Uvicorn running on…` and `Finished server process [1]`.
That interval should contain the actual Python exception.