from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcp_server import Settings, create_router


def test_info() -> None:
    app = FastAPI()
    app.include_router(create_router(Settings()), prefix="/x")
    assert TestClient(app).get("/x/").json() == {"module": "mcp_server", "status": "skeleton"}
