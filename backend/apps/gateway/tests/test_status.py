"""/api/status must say when the configured model isn't offered (providers retire them)."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from orchestrator import Settings, create_router


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    import httpx

    real_get = httpx.AsyncClient.get

    async def fake_get(self: httpx.AsyncClient, url: str, **kwargs: Any) -> httpx.Response:
        if url.endswith("/models"):
            data = [{"id": "openai/gpt-oss-120b"}, {"id": "qwen/qwen3.6-27b"}]
            return httpx.Response(200, json={"data": data}, request=httpx.Request("GET", url))
        return await real_get(self, url, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    settings = Settings(
        token_signing_key="k" * 32,
        llm_model="llama-3.3-70b-versatile",
        llm_api_key="gsk_test",
        system1_url="http://127.0.0.1:9",  # nothing listens here
    )
    app = FastAPI()
    app.include_router(create_router(settings), prefix="/api")
    yield TestClient(app)


def test_retired_model_is_reported_with_alternatives(client: TestClient) -> None:
    llm = client.get("/api/status").json()["llm"]
    assert llm["available"] is False
    assert llm["problem"] == "model not offered by this provider"
    assert "openai/gpt-oss-120b" in llm["offered"]


def test_unreachable_system1_explains_itself(client: TestClient) -> None:
    system1 = client.get("/api/status").json()["system1"]
    assert system1["reachable"] is False
    assert "loading" in system1["problem"]
