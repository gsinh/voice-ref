"""The whole text path over real HTTP, with only the LLM faked:

    /api/chat -> LangGraph (Postgres checkpoints) -> ChatOpenAI -> fake OpenAI endpoint
                                                  -> MCP client -> /mcp -> /bank -> Postgres

The fake speaks the OpenAI chat-completions wire format, so the real `ChatOpenAI` client,
its tool-calling format and structured-output decisions are all exercised. System 1 is
disabled, so every decision goes through the LLM fallback.

Needs TEST_BANK_DATABASE_URL and TEST_ORCHESTRATOR_DATABASE_URL (migrated database).
"""

import json
import os
import socket
import threading
import time
import uuid
from collections.abc import Iterator
from importlib.resources import files
from typing import Any

import httpx
import psycopg
import pytest
import uvicorn
from fastapi import APIRouter

BANK_URL = os.environ.get("TEST_BANK_DATABASE_URL")
ORCH_URL = os.environ.get("TEST_ORCHESTRATOR_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not (BANK_URL and ORCH_URL), reason="TEST_BANK/ORCHESTRATOR_DATABASE_URL not set"
)
PHONE = "+919800000001"


def _completion(message: dict[str, Any]) -> dict[str, Any]:
    finish = "tool_calls" if message.get("tool_calls") else "stop"
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 0,
        "model": "fake",
        "choices": [{"index": 0, "message": message, "finish_reason": finish}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


def _call(name: str, args: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            }
        ],
    }


def _choose(system: str, said: str) -> str:
    """Keyword rules standing in for the model's judgement on bounded questions."""
    s = said.lower()
    if "- confirm:" in system:
        return "confirm" if "yes" in s else "decline"
    if "- balance:" in system:
        if "lost" in s or "block" in s:
            return "lost_card"
        return "balance" if "balance" in s else "transactions" if "charge" in s else "other"
    for line in system.splitlines():  # card question: "- CARD-3001: Visa debit card ..."
        if line.startswith("- CARD-") and line.split()[3] in s:  # the card type
            return line[2:].split(":")[0]
    return "unspecified" if "- unspecified:" in system else "other"


def fake_llm_router() -> APIRouter:
    router = APIRouter()

    @router.get("/v1/models")
    async def models() -> dict[str, Any]:
        return {"object": "list", "data": [{"id": "fake-model", "object": "model"}]}

    @router.post("/v1/chat/completions")
    async def completions(body: dict[str, Any]) -> dict[str, Any]:
        messages = body["messages"]
        tool_names = [t["function"]["name"] for t in body.get("tools", [])]
        if tool_names == ["choose_option"]:  # a structured decision
            system = messages[0]["content"]
            said = messages[-1]["content"]
            return _completion(_call("choose_option", {"label": _choose(system, said)}))
        last = messages[-1]
        if last["role"] == "tool":  # answer from what the tool returned
            return _completion({"role": "assistant", "content": f"Here you go: {last['content']}"})
        if "get_account_balance" in tool_names:
            return _completion(_call("get_account_balance", {}))
        return _completion({"role": "assistant", "content": "Hello! How can I help?"})

    return router


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port: int = s.getsockname()[1]
        return port


@pytest.fixture(scope="module")
def base_url() -> Iterator[str]:
    assert BANK_URL and ORCH_URL
    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    mp = pytest.MonkeyPatch()
    for k, v in {
        "TOKEN_SIGNING_KEY": "chat-e2e-key-" + "x" * 32,
        "BANK_DATABASE_URL": BANK_URL,
        "ORCHESTRATOR_DATABASE_URL": ORCH_URL,
        "MCP_BANKING_API_URL": f"{base}/bank",
        "ORCHESTRATOR_MCP_URL": f"{base}/mcp/",
        "ORCHESTRATOR_BANK_API_URL": f"{base}/bank",
        "LLM_BASE_URL": f"{base}/fake-llm/v1",
        "LLM_API_KEY": "test",
        "LLM_MODEL": "fake-model",
        "SYSTEM1_ENABLED": "false",
    }.items():
        mp.setenv(k, v)
    from gateway.app import create_app

    app = create_app()
    app.include_router(fake_llm_router(), prefix="/fake-llm")
    server = uvicorn.Server(uvicorn.Config(app, port=port, log_config=None))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started:
        if not thread.is_alive() or time.monotonic() > deadline:
            pytest.fail("test server failed to start")
        time.sleep(0.05)
    yield base
    server.should_exit = True
    thread.join(timeout=5)
    mp.undo()


@pytest.fixture(autouse=True)
def _seed() -> None:
    assert BANK_URL
    with psycopg.connect(BANK_URL) as conn:
        conn.execute((files("banking_api") / "seed.sql").read_text().encode())


class Chat:
    def __init__(self, base_url: str) -> None:
        self.url = f"{base_url}/api/chat"
        self.id = str(uuid.uuid4())

    def say(self, text: str) -> dict[str, Any]:
        body = {"conversation_id": self.id, "caller_phone": PHONE, "message": text}
        resp = httpx.post(self.url, json=body, timeout=30)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return data


def test_balance_over_the_real_stack(base_url: str) -> None:
    chat = Chat(base_url)
    first = chat.say("What's my balance?")
    assert first["awaiting"] == "otp"
    assert first["intent"] == "balance"

    answer = chat.say("123456")
    assert answer["authenticated"] is True
    assert "₹82,450.00" in answer["reply"]  # formatted by the MCP server, from Postgres
    kinds = [(e["type"], e.get("name")) for e in answer["events"]]
    assert ("tool", "get_account_balance") in kinds


def test_block_card_over_the_real_stack(base_url: str) -> None:
    chat = Chat(base_url)
    chat.say("I lost my debit card, please block it")
    confirm = chat.say("123456")
    assert confirm["awaiting"] == "confirmation"
    assert "Visa debit card ending 4821" in confirm["reply"]

    done = chat.say("yes")
    assert done["outcome"] == "card_blocked"
    assert BANK_URL
    with psycopg.connect(BANK_URL) as conn:
        row = conn.execute("SELECT status FROM cards WHERE id = 'CARD-3001'").fetchone()
    assert row == ("blocked",)


def test_state_survives_between_requests(base_url: str) -> None:
    """Checkpoints are in Postgres: a new HTTP request resumes the paused graph."""
    chat = Chat(base_url)
    assert chat.say("balance please")["awaiting"] == "otp"
    transcript = httpx.get(f"{base_url}/api/conversations/{chat.id}", timeout=10).json()
    assert transcript["messages"][0] == {"role": "customer", "text": "balance please"}


def test_status_checks_the_model_with_the_provider(base_url: str) -> None:
    status = httpx.get(f"{base_url}/api/status", timeout=10).json()
    assert status["llm"]["available"] is True
    assert status["system1"] == {"enabled": False}
