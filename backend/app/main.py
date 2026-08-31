"""FastAPI application factory."""
from __future__ import annotations

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    s = get_settings()
    log.info(
        "app.start",
        env=s.app_env,
        name=s.app_name,
        worker=s.worker_enabled,
    )
    # Verify database connectivity at startup so a missing DATABASE_URL
    # or bad credentials fail fast (and visibly in the deploy logs)
    # instead of producing opaque 502s on the first request.
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            log.info("db.connect_ok", url_redacted=_redact(s.database_url))
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001
        log.error("db.connect_failed", error=str(exc), url_redacted=_redact(s.database_url))
        # Do not abort — Railway will keep the container up and
        # /api/v1/diag below will surface the error to operators.

    if s.worker_enabled:
        try:
            await start_worker()
        except Exception as exc:  # noqa: BLE001
            log.error("worker.start_failed", error=str(exc))
    try:
        yield
    finally:
        if s.worker_enabled:
            try:
                await stop_worker()
            except Exception as exc:  # noqa: BLE001
                log.error("worker.stop_failed", error=str(exc))
        log.info("app.stop")


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

