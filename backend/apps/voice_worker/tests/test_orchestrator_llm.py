import json
from typing import Any

import httpx
from livekit.agents import llm

from voice_worker.orchestrator_llm import (
    FALLBACK_REPLY,
    OrchestratorClient,
    OrchestratorLLM,
    last_user_text,
)


def _ctx(*turns: tuple[str, str]) -> llm.ChatContext:
    ctx = llm.ChatContext()
    for role, text in turns:
        ctx.add_message(role=role, content=text)  # type: ignore[arg-type]
    return ctx


async def _reply(brain: OrchestratorLLM, ctx: llm.ChatContext) -> str:
    out = []
    async with brain.chat(chat_ctx=ctx) as stream:
        async for chunk in stream:
            if chunk.delta and chunk.delta.content:
                out.append(chunk.delta.content)
    return "".join(out)


async def test_forwards_the_latest_utterance_with_call_identity() -> None:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"reply": "Your balance is ₹82,450.00.", "intent": "x"})

    client = OrchestratorClient("http://orch/api", transport=httpx.MockTransport(handler))
    brain = OrchestratorLLM(client, "voice-room-1", "+919800000001")
    ctx = _ctx(("assistant", "Welcome."), ("user", "old"), ("assistant", "…"), ("user", "balance?"))

    assert await _reply(brain, ctx) == "Your balance is ₹82,450.00."
    assert seen == [
        {"conversation_id": "voice-room-1", "caller_phone": "+919800000001", "message": "balance?"}
    ]
    assert brain.last_turn is not None and brain.last_turn["intent"] == "x"


async def test_a_failed_turn_is_not_retried_and_the_caller_hears_an_apology() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503)

    client = OrchestratorClient("http://orch/api", transport=httpx.MockTransport(handler))
    brain = OrchestratorLLM(client, "c", "+91")
    assert await _reply(brain, _ctx(("user", "yes, block it"))) == FALLBACK_REPLY
    assert calls == 1  # a turn may resume a confirmation: never replay it


def test_last_user_text_ignores_assistant_messages() -> None:
    assert last_user_text(_ctx(("user", "a"), ("assistant", "b"))) == "a"
    assert last_user_text(_ctx(("assistant", "b"))) == ""
