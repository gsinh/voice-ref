from fastapi.testclient import TestClient

from gateway.app import create_app
from gateway.health import health_router


async def _ok() -> None:
    return None


async def _fail() -> None:
    raise ConnectionError("db down")


def _client_with_checks(**checks: object) -> TestClient:
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(health_router(checks))  # type: ignore[arg-type]
    return TestClient(app)


def test_liveness_ignores_dependencies() -> None:
    assert _client_with_checks(db=_fail).get("/healthz").json() == {"status": "ok"}


def test_readiness_ok() -> None:
    resp = _client_with_checks(db=_ok).get("/readyz")
    assert resp.status_code == 200
    assert resp.json()["checks"] == {"db": "ok"}


def test_readiness_reports_failing_check() -> None:
    resp = _client_with_checks(db=_ok, cache=_fail).get("/readyz")
    assert resp.status_code == 503
    assert resp.json()["checks"] == {"db": "ok", "cache": "error: ConnectionError"}


def test_all_modules_are_mounted() -> None:
    client = TestClient(create_app())
    assert client.get("/").json()["modules"] == {
        "orchestrator": "/api",
        "banking_api": "/bank",
        "mcp_server": "/mcp",
        "decision": "/decide",
    }
    for prefix in ("/api", "/bank", "/mcp", "/decide"):
        assert client.get(f"{prefix}/").json()["status"] == "skeleton"
