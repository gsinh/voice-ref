"""Liveness and readiness endpoints.

- `/healthz` (liveness): the process is up. Never checks dependencies, otherwise a
  database blip would make the orchestrator restart every container.
- `/readyz` (readiness): the service can do useful work. Checks only the service's
  *own* hard dependencies (e.g. its database), not other services, so one failure
  doesn't cascade into every service reporting unready.
"""

import asyncio
from collections.abc import Awaitable, Callable, Mapping

import psycopg
from fastapi import APIRouter, Response, status

ReadinessCheck = Callable[[], Awaitable[None]]
"""Raises on failure, returns None on success."""

CHECK_TIMEOUT_S = 2.0


def postgres_check(database_url: str) -> ReadinessCheck:
    async def check() -> None:
        async with await psycopg.AsyncConnection.connect(
            database_url, connect_timeout=int(CHECK_TIMEOUT_S)
        ) as conn:
            await conn.execute("SELECT 1")

    return check


def health_router(checks: Mapping[str, ReadinessCheck]) -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/readyz")
    async def readyz(response: Response) -> dict[str, object]:
        results: dict[str, str] = {}
        for name, check in checks.items():
            try:
                await asyncio.wait_for(check(), timeout=CHECK_TIMEOUT_S)
                results[name] = "ok"
            except Exception as exc:  # any failure means "not ready"
                results[name] = f"error: {type(exc).__name__}"
        ready = all(v == "ok" for v in results.values())
        if not ready:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "ok" if ready else "unavailable", "checks": results}

    return router
