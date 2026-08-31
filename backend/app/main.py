"""FastAPI application factory."""
from __future__ import annotations

import asyncio
import os
import sys

# Emit a line as the very first thing the worker process does. This
# lands in the Railway deploy log and confirms that the CMD we set in
# the Dockerfile actually ran. Helps diagnose "502 Application failed
# to respond" — if this line never appears, uvicorn never started.
print(
    f"[boot] maicos main module loaded pid={os.getpid()} "
    f"python={sys.version.split()[0]} port={os.environ.get('PORT', 'unset')}",
    flush=True,
)

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app import agents  # noqa: F401  (registers agents + connectors)
from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import SessionLocal
from app.queue.worker import start_worker, stop_worker

log = get_logger("app")


def _run_alembic_upgrade() -> tuple[bool, str]:
    r"""Run `alembic upgrade head` in-process.

    Returns (ok, error_message). Errors are non-fatal so the API still
    comes up — operators can run the migration manually from the
    Railway shell if needed.
    """
    try:
        from alembic.config import Config

        from alembic import command

        cfg = Config("alembic.ini")
        command.upgrade(cfg, "head")
        return True, ""
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    s = get_settings()
    log.info(
        "app.start",
        env=s.app_env,
        name=s.app_name,
        worker=s.worker_enabled,
        database_url=_redact(s.database_url),
    )
    # Yield to uvicorn FIRST so the process is accepting requests
    # before any background work runs. /health will respond 200
    # immediately, which is the only thing Railway's health
    # check needs.
    yield_start = asyncio.create_task(_lifespan_init(s, log, _redact))
    try:
        yield
    finally:
        # Best-effort cleanup of the background init task if still
        # running when uvicorn is shutting down.
        yield_start.cancel()
        if s.worker_enabled and not s.worker_skip:
            try:
                await stop_worker()
            except Exception as exc:  # noqa: BLE001
                log.error("worker.stop_failed", error=str(exc))
        log.info("app.stop")


async def _lifespan_init(s, log, redact) -> None:
    """All post-yield startup work: DB check, migrations, worker.

    Runs in the background so the FastAPI process is accepting
    HTTP traffic as soon as the lifespan is entered. If the DB is
    unreachable, the API still serves /health and /api/v1/diag
    (which itself reports db.ok=false), but every other route will
    return 500 until the DB comes back. The `db_startup_timeout`
    env cap (default 10s) bounds the worst-case delay.
    """
    # Verify database connectivity at startup so a missing
    # DATABASE_URL or bad credentials fail fast (and visibly in the
    # deploy logs) instead of producing opaque 502s on the first
    # request.
    db_ok = False
    db_err: str | None = None
    try:
        db_ok, db_err = await asyncio.wait_for(
            asyncio.to_thread(_check_db),
            timeout=s.db_startup_timeout,
        )
        if db_ok:
            log.info("db.connect_ok", url_redacted=redact(s.database_url))
        else:
            log.error(
                "db.connect_failed",
                error=db_err,
                url_redacted=redact(s.database_url),
            )
    except TimeoutError:
        log.error(
            "db.connect_timeout",
            timeout_seconds=s.db_startup_timeout,
            url_redacted=redact(s.database_url),
        )
    except Exception as exc:  # noqa: BLE001
        log.error("db.connect_unexpected", error=str(exc))

    # Auto-migrate on startup, but only if the DB is reachable.
    if db_ok and s.worker_enabled:
        log.info("migrate.start")
        ok, err = _run_alembic_upgrade()
        if ok:
            log.info("migrate.ok")
        else:
            log.error("migrate.failed", error=err)

    if s.worker_enabled and not s.worker_skip:
        try:
            await start_worker()
        except Exception as exc:  # noqa: BLE001
            log.error("worker.start_failed", error=str(exc))


def _check_db() -> tuple[bool, str | None]:
    """Run a SELECT 1 and report success / failure. Synchronous."""
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    finally:
        db.close()


def _redact(url: str) -> str:
    """Replace the password in a Postgres URL with *** for safe logging."""
    if "@" not in url or "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    if "@" not in rest:
        return url
    creds, host = rest.split("@", 1)
    if ":" in creds:
        user, _ = creds.split(":", 1)
        return f"{scheme}://{user}:***@{host}"
    return url


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="Multi-Agent AI Company OS", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_origin_regex=s.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)

    @app.get("/health")
    def health() -> dict:
        """Liveness — process is up, regardless of DB state."""
        return {"status": "ok"}

    @app.get("/api/v1/diag")
    def diag() -> dict:
        """Readiness — DB connectivity + env sanity.

        Public, no auth. Returns 200 even on failure (with `db.ok=false`)
        so that health checks and `curl` always get a body to inspect.
        """
        s2 = get_settings()
        info: dict = {
            "app_env": s2.app_env,
            "database_url": _redact(s2.database_url),
            "redis_url": "<unused>",
            "cors_origins": s2.cors_origins,
            "cors_origin_regex": s2.cors_origin_regex or None,
            "supabase_url": s2.supabase_url or None,
            "worker_enabled": s2.worker_enabled,
            "worker_id": s2.worker_id,
            "db": {"ok": False, "error": None},
        }
        try:
            db = SessionLocal()
            try:
                db.execute(text("SELECT 1"))
                info["db"] = {"ok": True, "error": None}
            finally:
                db.close()
        except Exception as exc:  # noqa: BLE001
            info["db"] = {"ok": False, "error": str(exc)}
        return info

    return app


app = create_app()

