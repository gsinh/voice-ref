from fastapi.testclient import TestClient

from orchestrator.main import app


def test_liveness() -> None:
    assert TestClient(app).get("/healthz").json() == {"status": "ok"}
