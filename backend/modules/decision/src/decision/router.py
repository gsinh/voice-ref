from fastapi import APIRouter

from decision.settings import Settings


def create_router(settings: Settings) -> APIRouter:
    router = APIRouter(tags=["decision"])

    @router.get("/")
    async def info() -> dict[str, str]:
        return {"module": "decision", "status": "skeleton"}

    return router
