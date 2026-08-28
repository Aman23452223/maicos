"""FastAPI application factory."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import agents  # noqa: F401  (registers agents + connectors)
from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.scheduler import shutdown as scheduler_shutdown
from app.scheduler import start as scheduler_start


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    log = get_logger("app")
    s = get_settings()
    log.info("app.start", env=s.app_env, name=s.app_name)
    scheduler_start()
    yield
    scheduler_shutdown()
    log.info("app.stop")


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="Multi-Agent AI Company OS", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()

