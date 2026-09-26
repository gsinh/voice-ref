"""HTTP API of the orchestrator, and the composition of its real dependencies."""

import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, Request
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel, Field, SecretStr

from orchestrator.adapters import HttpCustomerDirectory, McpToolsProvider
from orchestrator.decisions import CascadeDecision, LLMDecision, SystemOneDecision
from orchestrator.graph import Deps, build_graph
from orchestrator.service import ChatService
from orchestrator.settings import Settings

log = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    conversation_id: str | None = Field(None, max_length=100)
    caller_phone: str = Field(min_length=5, max_length=20, description="Caller ID (ANI)")
    message: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    awaiting: str | None
    intent: str | None
    authenticated: bool
    outcome: str | None
    events: list[dict[str, Any]]
    total_ms: float


def build_deps(settings: Settings) -> tuple[Deps, list[Any]]:
    """Composition root for the orchestrator. Returns deps and things to close."""
    key = settings.token_signing_key.get_secret_value()
    llm_key = settings.llm_api_key.get_secret_value()
    if not llm_key:
        # Start anyway: the bank and MCP still work, and LLM calls fail gracefully per turn.
        log.warning("LLM_API_KEY is not set; LLM calls will fail (Ollama accepts any value)")
    llm = ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=SecretStr(llm_key or "not-configured"),
        model=settings.llm_model,
        temperature=0,
        timeout=settings.llm_timeout_s,
        max_retries=1,
    )
    system1 = (
        SystemOneDecision(
            settings.system1_url,
            settings.system1_api_key.get_secret_value(),
            settings.system1_timeout_s,
        )
        if settings.system1_enabled
        else None
    )
    directory = HttpCustomerDirectory(settings.bank_api_url)
    deps = Deps(
        llm=llm,
        decisions=CascadeDecision(primary=system1, fallback=LLMDecision(llm)),
        directory=directory,
        tools=McpToolsProvider(settings.mcp_url, key, settings.session_ttl_s),
        signing_key=key,
        demo_otp=settings.demo_otp,
        max_otp_attempts=settings.max_otp_attempts,
        intent_threshold=settings.intent_threshold,
        confirm_threshold=settings.confirm_threshold,
    )
    return deps, [c for c in (system1, directory) if c is not None]


def _service(request: Request) -> ChatService:
    service: ChatService = request.app.state.chat_service
    return service


Service = Annotated[ChatService, Depends(_service)]


def create_router(settings: Settings) -> APIRouter:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        pool = AsyncConnectionPool(
            settings.database_url,
            min_size=0,
            max_size=5,
            open=False,
            # What the LangGraph Postgres checkpointer requires; prepared statements off
            # so a transaction-mode pooler (e.g. Neon's) works.
            kwargs={"autocommit": True, "prepare_threshold": None, "row_factory": dict_row},
        )
        await pool.open(wait=False)
        deps, closeables = build_deps(settings)
        graph = build_graph().compile(checkpointer=AsyncPostgresSaver(pool))  # type: ignore[arg-type]
        app.state.chat_service = ChatService(graph, deps)
        try:
            yield
        finally:
            for c in closeables:
                await c.aclose()
            await pool.close()

    router = APIRouter(tags=["orchestrator"], lifespan=lifespan)

    @router.get("/")
    async def info() -> dict[str, str]:
        return {"module": "orchestrator", "status": "ok"}

    @router.post("/chat")
    async def chat(body: ChatRequest, service: Service) -> ChatResponse:
        conversation_id = body.conversation_id or str(uuid.uuid4())
        result = await service.turn(conversation_id, body.caller_phone, body.message)
        return ChatResponse(**result.__dict__)

    @router.get("/conversations/{conversation_id}")
    async def conversation(conversation_id: str, service: Service) -> dict[str, Any]:
        return {
            "conversation_id": conversation_id,
            "messages": await service.transcript(conversation_id),
        }

    return router
