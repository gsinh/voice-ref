from fastapi import FastAPI
from fastapi.testclient import TestClient

from orchestrator import Settings, create_router


def test_info() -> None:
    app = FastAPI()
    app.include_router(create_router(Settings()), prefix="/x")
    assert TestClient(app).get("/x/").json() == {"module": "orchestrator", "status": "skeleton"}
