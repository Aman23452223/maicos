from fastapi import APIRouter

from app.api.v1 import (
    approvals,
    auth,
    automation,
    growth,
    intel,
    knowledge,
    queue,
    registry,
    settings,
    workflows,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(workflows.router)
api_router.include_router(approvals.router)
api_router.include_router(registry.router)
api_router.include_router(knowledge.router)
api_router.include_router(automation.router)
api_router.include_router(settings.router)
api_router.include_router(queue.router)
api_router.include_router(intel.router)
api_router.include_router(growth.router)

