"""FastAPI application for the backend process."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from gateway.composition import (
    PREFIXES,
    ModuleSettings,
    build_mcp,
    mount_modules,
    readiness_checks,
)
from gateway.health import health_router
from gateway.logging import configure_logging
from gateway.settings import Settings


def create_app(settings: Settings | None = None, modules: ModuleSettings | None = None) -> FastAPI:
    settings = settings or Settings()
    modules = modules or ModuleSettings.from_env()
    configure_logging(settings.service_name, settings.log_level)

    mcp = build_mcp(modules)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        # Mounted ASGI apps don't get lifespan events, so the host runs the MCP one.
        # Routers' own lifespans (e.g. the bank's connection pool) are merged by FastAPI.
        async with mcp.lifespan():
            yield

    app = FastAPI(title="voice-ref backend", lifespan=lifespan)
    app.include_router(health_router(readiness_checks(modules)))
    mount_modules(app, modules, mcp)

    @app.get("/", tags=["meta"])
    async def root() -> dict[str, object]:
        return {"service": settings.service_name, "modules": PREFIXES}

    return app
