from fastapi import APIRouter

from banking_api.settings import Settings


def create_router(settings: Settings) -> APIRouter:
    router = APIRouter(tags=["banking_api"])

    @router.get("/")
    async def info() -> dict[str, str]:
        return {"module": "banking_api", "status": "skeleton"}

    return router
