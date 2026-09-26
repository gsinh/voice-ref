from fastapi.testclient import TestClient

from voiceref_common import ServiceSettings, create_app


async def _ok() -> None:
    return None


async def _fail() -> None:
    raise ConnectionError("db down")


def test_liveness_ignores_dependencies() -> None:
    app = create_app(ServiceSettings(), {"db": _fail})
    assert TestClient(app).get("/healthz").json() == {"status": "ok"}


def test_readiness_ok() -> None:
    app = create_app(ServiceSettings(), {"db": _ok})
    resp = TestClient(app).get("/readyz")
    assert resp.status_code == 200
    assert resp.json()["checks"] == {"db": "ok"}


def test_readiness_reports_failing_check() -> None:
    app = create_app(ServiceSettings(), {"db": _ok, "cache": _fail})
    resp = TestClient(app).get("/readyz")
    assert resp.status_code == 503
    assert resp.json()["checks"] == {"db": "ok", "cache": "error: ConnectionError"}
