"""One conversational turn: resume a paused graph or start a new pass, then report."""

from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from orchestrator.graph import Deps, GraphContext, State
from orchestrator.telemetry import TurnRecorder


@dataclass(frozen=True)
class TurnResult:
    conversation_id: str
    reply: str
    awaiting: str | None  # "otp" | "card_choice" | "confirmation" | None
    intent: str | None
    authenticated: bool
    outcome: str | None
    events: list[dict[str, Any]]
    total_ms: float


class ChatService:
    def __init__(self, graph: CompiledStateGraph[Any, Any, Any, Any], deps: Deps) -> None:
        self._graph = graph
        self._deps = deps

    async def turn(self, conversation_id: str, caller_phone: str, text: str) -> TurnResult:
        config: Any = {"configurable": {"thread_id": conversation_id}}
        recorder = TurnRecorder()
        before = await self._graph.aget_state(config)
        graph_input: Any
        if before.interrupts:
            # The graph is waiting on the customer (code, card, confirmation): resume it.
            graph_input = Command(resume=text)
        else:
            graph_input = {"messages": [HumanMessage(text)], "caller_phone": caller_phone}
        await self._graph.ainvoke(
            graph_input, config, context=GraphContext(deps=self._deps, recorder=recorder)
        )

        after = await self._graph.aget_state(config)
        values: State = after.values  # type: ignore[assignment]
        if after.interrupts:
            pending = after.interrupts[0].value
            reply, awaiting = str(pending["prompt"]), str(pending["kind"])
        else:
            reply, awaiting = _last_ai_text(values), None
        return TurnResult(
            conversation_id=conversation_id,
            reply=reply,
            awaiting=awaiting,
            intent=values.get("intent"),
            authenticated=bool(values.get("authenticated")),
            outcome=values.get("outcome"),
            events=recorder.events,
            total_ms=recorder.total_ms(),
        )

    async def transcript(self, conversation_id: str) -> list[dict[str, str]]:
        config: Any = {"configurable": {"thread_id": conversation_id}}
        snapshot = await self._graph.aget_state(config)
        out: list[dict[str, str]] = []
        for m in snapshot.values.get("messages", []):
            if isinstance(m, HumanMessage):
                out.append({"role": "customer", "text": str(m.content)})
            elif isinstance(m, ToolMessage):
                out.append({"role": "tool", "name": m.name or "", "text": str(m.content)})
            elif isinstance(m, AIMessage) and m.content:
                out.append({"role": "assistant", "text": str(m.content)})
        return out


def _last_ai_text(values: State) -> str:
    for m in reversed(values.get("messages", [])):
        if isinstance(m, AIMessage) and m.content and not m.tool_calls:
            return str(m.content)
    return ""
