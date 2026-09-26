from fastapi import APIRouter

from orchestrator.settings import Settings


def create_router(settings: Settings) -> APIRouter:
    router = APIRouter(tags=["orchestrator"])

    @router.get("/")
    async def info() -> dict[str, str]:
        return {"module": "orchestrator", "status": "skeleton"}

    return router
