"""The orchestrator as a LiveKit "LLM" (ADR-0018).

LiveKit's voice pipeline needs an LLM plugin to produce each reply. This one forwards the
caller's words to the orchestrator's `/api/chat` and returns its reply, so the voice
agent runs exactly the same LangGraph graph (guardrails, OTP, confirmations) as the
text chat. Voice is a transport, not a second brain.

Retries are disabled: a turn is not idempotent (it may resume a paused confirmation),
so replaying it after a timeout could act twice.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx
from livekit.agents import APIConnectOptions, llm
from livekit.agents.llm import ChatChunk, ChoiceDelta
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, NOT_GIVEN, NotGivenOr

NO_RETRY = APIConnectOptions(max_retry=0, retry_interval=0, timeout=30)
FALLBACK_REPLY = "Sorry, I'm having trouble right now. Please try again in a moment."


@dataclass
class OrchestratorClient:
    base_url: str
    timeout_s: float = 30.0
    transport: httpx.AsyncBaseTransport | None = None  # tests inject a fake
    _http: httpx.AsyncClient | None = field(default=None, init=False, repr=False)

    async def turn(self, conversation_id: str, caller_phone: str, text: str) -> dict[str, Any]:
        if self._http is None:
            self._http = httpx.AsyncClient(
                base_url=self.base_url, timeout=self.timeout_s, transport=self.transport
            )
        resp = await self._http.post(
            "/chat",
            json={
                "conversation_id": conversation_id,
                "caller_phone": caller_phone,
                "message": text,
            },
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return data

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()


class OrchestratorLLM(llm.LLM[Any]):
    """One instance per call: it knows the conversation id and the caller ID."""

    def __init__(self, client: OrchestratorClient, conversation_id: str, caller_phone: str) -> None:
        super().__init__()
        self.client = client
        self.conversation_id = conversation_id
        self.caller_phone = caller_phone
        self.last_turn: dict[str, Any] | None = None

    @property
    def model(self) -> str:
        return "voice-ref-orchestrator"

    @property
    def provider(self) -> str:
        return "voice-ref"

    def chat(
        self,
        *,
        chat_ctx: llm.ChatContext,
        tools: list[llm.Tool] | None = None,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
        parallel_tool_calls: NotGivenOr[bool] = NOT_GIVEN,
        tool_choice: NotGivenOr[llm.ToolChoice] = NOT_GIVEN,
        extra_kwargs: NotGivenOr[dict[str, Any]] = NOT_GIVEN,
    ) -> llm.LLMStream:
        # Tools are the orchestrator's business, never LiveKit's.
        return _OrchestratorStream(self, chat_ctx=chat_ctx, tools=[], conn_options=NO_RETRY)


class _OrchestratorStream(llm.LLMStream):
    def __init__(self, owner: OrchestratorLLM, **kwargs: Any) -> None:
        super().__init__(owner, **kwargs)
        self._owner = owner

    async def _run(self) -> None:
        text = last_user_text(self._chat_ctx)
        owner = self._owner
        if not text:
            return
        try:
            turn = await owner.client.turn(owner.conversation_id, owner.caller_phone, text)
            reply = str(turn.get("reply") or FALLBACK_REPLY)
        except httpx.HTTPError:
            turn, reply = {"outcome": "error"}, FALLBACK_REPLY
        owner.last_turn = turn
        self._event_ch.send_nowait(
            ChatChunk(
                id=f"turn-{uuid.uuid4().hex[:12]}",
                delta=ChoiceDelta(role="assistant", content=reply),
            )
        )


def last_user_text(chat_ctx: llm.ChatContext) -> str:
    for item in reversed(chat_ctx.items):
        if isinstance(item, llm.ChatMessage) and item.role == "user":
            return (item.text_content or "").strip()
    return ""
