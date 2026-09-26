"""Common FastAPI bootstrap so every service starts, logs and reports health the same way."""

from collections.abc import Mapping

import uvicorn
from fastapi import FastAPI

from voiceref_common.health import ReadinessCheck, health_router
from voiceref_common.logging import configure_logging
from voiceref_common.settings import ServiceSettings


def create_app(
    settings: ServiceSettings,
    readiness_checks: Mapping[str, ReadinessCheck] | None = None,
    **fastapi_kwargs: object,
) -> FastAPI:
    configure_logging(settings.service_name, settings.log_level)
    app = FastAPI(title=settings.service_name, **fastapi_kwargs)  # type: ignore[arg-type]
    app.include_router(health_router(readiness_checks or {}))
    return app


def run(app_path: str, settings: ServiceSettings) -> None:
    """Port binding (factor VII): the service is self-contained and exports HTTP on a port.

    Uvicorn handles SIGTERM by finishing in-flight requests before exiting (factor IX).
    """
    uvicorn.run(
        app_path,
        host=settings.host,
        port=settings.port,
        log_config=None,  # keep our JSON logging
        timeout_graceful_shutdown=10,
    )
