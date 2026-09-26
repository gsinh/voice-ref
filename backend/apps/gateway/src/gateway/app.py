"""FastAPI application for the backend process."""

from fastapi import FastAPI

from gateway.composition import PREFIXES, ModuleSettings, mount_modules, readiness_checks
from gateway.health import health_router
from gateway.logging import configure_logging
from gateway.settings import Settings


def create_app(settings: Settings | None = None, modules: ModuleSettings | None = None) -> FastAPI:
    settings = settings or Settings()
    modules = modules or ModuleSettings.from_env()
    configure_logging(settings.service_name, settings.log_level)

    app = FastAPI(title="voice-ref backend")
    app.include_router(health_router(readiness_checks(modules)))
    mount_modules(app, modules)

    @app.get("/", tags=["meta"])
    async def root() -> dict[str, object]:
        return {"service": settings.service_name, "modules": PREFIXES}

    return app
