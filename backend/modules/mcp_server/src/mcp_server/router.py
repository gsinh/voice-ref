from fastapi import APIRouter

from mcp_server.settings import Settings


def create_router(settings: Settings) -> APIRouter:
    router = APIRouter(tags=["mcp_server"])

    @router.get("/")
    async def info() -> dict[str, str]:
        return {"module": "mcp_server", "status": "skeleton"}

    return router
