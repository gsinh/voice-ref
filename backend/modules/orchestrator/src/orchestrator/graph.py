"""The conversation graph (ADR-0004).

    START → understand ─┬─ needs auth, not verified ─→ authenticate ─┐
                        ├─ balance / transactions ─→ account_agent   │ (then the
                        ├─ lost_card ─→ load_cards → choose_card     │  intent's
                        │              → confirm_block → block_card  │  route)
                        ├─ agent ─→ handoff                          │
                        ├─ other ─→ general_agent                    │
                        └─ unsure ─→ clarify  ◄──────────────────────┘

Rules this graph enforces in code, not in prompts:
- Account data needs a verified caller (mock OTP). Customer identity comes from the
  caller ID, never from what the model says.
- The LLM only ever gets read-only tools. `block_card` is called by deterministic code,
  after an explicit confirmation, with a single-use confirmation token (ADR-0006).
- When the system can't tell whether the customer confirmed, it does *not* act.
- Human-in-the-loop points use `interrupt()`. LangGraph re-runs an interrupted node from
  the top on resume, so nodes that interrupt have no side effects before the interrupt.
"""

import re
from dataclasses import dataclass
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.runtime import Runtime
from langgraph.types import interrupt

from orchestrator import prompts, questions
from orchestrator.ports import CustomerDirectory, DecisionPort, ToolsProvider
from orchestrator.telemetry import TurnRecorder
from signed_tokens import issue_confirmation

ACCOUNT_TOOLS = ("get_account_balance", "get_recent_transactions", "get_transaction_details")
MAX_TOOL_ROUNDS = 4
HISTORY_WINDOW = 12

Outcome = Literal[
    "answered", "card_blocked", "not_confirmed", "auth_failed", "handoff", "unclear", "error"
]


class State(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    caller_phone: str
    customer_id: str | None
    customer_name: str | None
    authenticated: bool
    intent: str | None
    intent_text: str  # what the customer said that set the intent
    cards: dict[str, str]  # card_id -> description, active cards only
    target_card: str | None
    outcome: Outcome | None


@dataclass(frozen=True)
class Deps:
    llm: BaseChatModel
    decisions: DecisionPort
    directory: CustomerDirectory
    tools: ToolsProvider
    signing_key: str
    demo_otp: str
    max_otp_attempts: int
    intent_threshold: float
    confirm_threshold: float


@dataclass(frozen=True)
class GraphContext:
    """Per-run context (LangGraph `context_schema`): dependencies plus this turn's trace."""

    deps: Deps
    recorder: TurnRecorder


Rt = Runtime[GraphContext]


def _say(text: str, outcome: Outcome | None = None) -> dict[str, Any]:
    update: dict[str, Any] = {"messages": [AIMessage(text)]}
    if outcome:
        update["outcome"] = outcome
    return update


def _last_human(state: State) -> str:
    for message in reversed(state.get("messages", [])):
        if isinstance(message, HumanMessage):
            return str(message.content)
    return ""


def _digits(text: str) -> str:
    """'1 2 3 4 5 6', '123-456' and 'one two...' transcribed as digits all normalise."""
    return re.sub(r"\D", "", text)


# ---- nodes ---------------------------------------------------------------------------


async def understand(state: State, runtime: Rt) -> dict[str, Any]:
    deps, rec = runtime.context.deps, runtime.context.recorder
    text = _last_human(state)
    decision = await deps.decisions.choose(questions.intent(deps.intent_threshold), text)
    rec.decision("intent", decision)
    return {"intent": decision.label, "intent_text": text, "outcome": None}


async def authenticate(state: State, runtime: Rt) -> dict[str, Any]:
    """Caller ID identifies the customer; a one-time code proves it's them.

    The code the customer says is never written to the transcript.
    """
    deps, rec = runtime.context.deps, runtime.context.recorder
    with rec.timed("lookup", "customer_by_phone"):
        customer = await deps.directory.by_phone(state.get("caller_phone", ""))
    if customer is None:
        return _say(
            "I couldn't find an account linked to this phone number. "
            "Let me connect you to a colleague who can help.",
            "handoff",
        )

    transcript: list[BaseMessage] = []
    prompt = (
        f"To keep your account safe, I've sent a six-digit code to your phone ending "
        f"{customer.phone[-4:]}. Please tell me the code."
    )
    for _ in range(deps.max_otp_attempts):
        answer = str(interrupt({"kind": "otp", "prompt": prompt}))
        transcript += [AIMessage(prompt), HumanMessage("[one-time code withheld]")]
        if _digits(answer) == deps.demo_otp:
            return {
                "messages": transcript,
                "customer_id": customer.id,
                "customer_name": customer.name,
                "authenticated": True,
            }
        prompt = "That code didn't match. Please check the message and tell me the code again."

    return {
        "messages": [
            *transcript,
            AIMessage("I'm sorry, I couldn't verify you. Let me connect you to a colleague."),
        ],
        "outcome": "auth_failed",
    }


async def _run_tool(rec: TurnRecorder, tool: BaseTool, call: dict[str, Any]) -> ToolMessage:
    try:
        with rec.timed("tool", tool.name):
            result = await tool.ainvoke(call)
    except Exception as exc:  # the model sees the failure and can apologise
        return ToolMessage(f"error: {exc}", tool_call_id=call["id"], name=tool.name)
    if isinstance(result, ToolMessage):
        return result
    return ToolMessage(str(result), tool_call_id=call["id"], name=tool.name)


async def account_agent(state: State, runtime: Rt) -> dict[str, Any]:
    """LLM with read-only tools: balance and transactions."""
    deps, rec = runtime.context.deps, runtime.context.recorder
    customer_id = state.get("customer_id")
    if not customer_id:
        return _say("I need to verify you before I can look at your account.", "error")
    try:
        all_tools = await deps.tools.for_customer(customer_id)
        tools = {name: all_tools[name] for name in ACCOUNT_TOOLS if name in all_tools}
        model = deps.llm.bind_tools(list(tools.values()))
        history = list(state.get("messages", []))[-HISTORY_WINDOW:]
        system = SystemMessage(prompts.account_agent(state.get("customer_name") or "the customer"))
        new: list[BaseMessage] = []
        for _ in range(MAX_TOOL_ROUNDS):
            with rec.timed("llm", "account_agent") as ev:
                reply = await model.ainvoke([system, *history, *new])
                _record_usage(ev, reply)
            new.append(reply)
            calls = getattr(reply, "tool_calls", None) or []
            if not calls:
                return {"messages": new, "outcome": "answered"}
            for call in calls:
                tool = tools.get(call["name"])
                if tool is None:  # the model asked for something it wasn't given
                    new.append(
                        ToolMessage("error: unknown tool", tool_call_id=call["id"], name="none")
                    )
                    continue
                new.append(await _run_tool(rec, tool, {**call, "type": "tool_call"}))
        return {
            "messages": [*new, AIMessage("Sorry, that took too long. Could you ask again?")],
            "outcome": "error",
        }
    except Exception:
        # Phase 3 replaces this with the fallback controller (deterministic flow / handoff).
        return _say("Sorry, I'm having trouble reaching your account right now.", "error")


async def general_agent(state: State, runtime: Rt) -> dict[str, Any]:
    deps, rec = runtime.context.deps, runtime.context.recorder
    history = list(state.get("messages", []))[-HISTORY_WINDOW:]
    try:
        with rec.timed("llm", "general_agent") as ev:
            reply = await deps.llm.ainvoke([SystemMessage(prompts.general_agent()), *history])
            _record_usage(ev, reply)
    except Exception:
        return _say("Sorry, I'm having trouble right now. Please try again in a moment.", "error")
    return {"messages": [AIMessage(str(reply.content))], "outcome": "answered"}


async def load_cards(state: State, runtime: Rt) -> dict[str, Any]:
    deps, rec = runtime.context.deps, runtime.context.recorder
    customer_id = state.get("customer_id") or ""
    try:
        with rec.timed("tool", "get_card_status"):
            cards = await deps.tools.call(customer_id, "get_card_status", {})
    except Exception:
        return _say("Sorry, I can't reach the card system right now.", "error")
    active = {c["card_id"]: c["card"] for c in cards if c.get("status") == "active"}
    if not active:
        return {**_say("You don't have any active cards to block.", "answered"), "cards": {}}
    return {"cards": active, "target_card": None}


async def choose_card(state: State, runtime: Rt) -> dict[str, Any]:
    """One active card: that's the one. Several: let the customer's words decide, and ask
    only if that isn't clear."""
    deps, rec = runtime.context.deps, runtime.context.recorder
    cards = state.get("cards", {})
    if len(cards) == 1:
        return {"target_card": next(iter(cards))}

    question = questions.card_choice(deps.intent_threshold, cards)
    # The words that started this request ("block my credit card"), not the latest
    # message, which may be the one-time-code step in between.
    decision = await deps.decisions.choose(question, state.get("intent_text", ""))
    rec.decision("card", decision)
    if decision.label:
        return {"target_card": decision.label}

    options = " or ".join(f"your {d}" for d in cards.values())
    prompt = f"Which card should I block: {options}?"
    answer = str(interrupt({"kind": "card_choice", "prompt": prompt}))
    decision = await deps.decisions.choose(question, answer)
    rec.decision("card", decision)
    transcript = [AIMessage(prompt), HumanMessage(answer)]
    if decision.label:
        return {"messages": transcript, "target_card": decision.label}
    return {
        "messages": [
            *transcript,
            AIMessage("I couldn't tell which card you meant, so I haven't blocked anything."),
        ],
        "outcome": "unclear",
    }


async def confirm_block(state: State, runtime: Rt) -> dict[str, Any]:
    """Explicit confirmation for an irreversible action. Unclear twice means no."""
    deps, rec = runtime.context.deps, runtime.context.recorder
    card = state.get("cards", {}).get(state.get("target_card") or "", "card")
    question = questions.confirmation(deps.confirm_threshold, f"permanently block {card}")
    prompt = (
        f"Just to confirm: you want me to permanently block your {card}. "
        "This can't be undone. Shall I go ahead?"
    )
    transcript: list[BaseMessage] = []
    for _ in range(2):
        answer = str(interrupt({"kind": "confirmation", "prompt": prompt}))
        transcript += [AIMessage(prompt), HumanMessage(answer)]
        decision = await deps.decisions.choose(question, answer)
        rec.decision("confirmation", decision)
        if decision.label == questions.CONFIRM:
            return {"messages": transcript}
        if decision.label == questions.DECLINE:
            break
        prompt = f"Sorry, I didn't catch that. Should I block your {card}? Please say yes or no."
    return {
        "messages": [*transcript, AIMessage(f"Okay, I haven't blocked your {card}.")],
        "outcome": "not_confirmed",
    }


async def block_card(state: State, runtime: Rt) -> dict[str, Any]:
    """Deterministic: no LLM decides to call this, and the reply is a fixed template."""
    deps, rec = runtime.context.deps, runtime.context.recorder
    customer_id = state.get("customer_id") or ""
    card_id = state.get("target_card") or ""
    card = state.get("cards", {}).get(card_id, "card")
    token = issue_confirmation(deps.signing_key, customer_id, "block_card", card_id)
    try:
        with rec.timed("tool", "block_card"):
            await deps.tools.call(
                customer_id,
                "block_card",
                {"card_id": card_id, "reason": "reported lost", "confirmation_token": token},
            )
    except Exception:
        return _say(
            "I couldn't block the card just now. Let me connect you to a colleague straight away.",
            "handoff",
        )
    return _say(
        f"Done. Your {card} is now blocked, so no one can use it. "
        "A replacement will be sent to your registered address.",
        "card_blocked",
    )


async def handoff(state: State, runtime: Rt) -> dict[str, Any]:
    # Phase 3: create a handoff case in Kestra with the conversation context.
    return _say("Of course. I'm connecting you to one of our team now.", "handoff")


async def clarify(state: State, runtime: Rt) -> dict[str, Any]:
    return _say(
        "Sorry, I didn't quite get that. I can check your balance, explain a transaction, "
        "or block a lost card. What would you like to do?",
        "unclear",
    )


# ---- routing -------------------------------------------------------------------------

Route = Literal[
    "authenticate", "account_agent", "load_cards", "handoff", "general_agent", "clarify", "__end__"
]


def _route_intent(state: State) -> Route:
    match state.get("intent"):
        case questions.BALANCE | questions.TRANSACTIONS:
            return "account_agent"
        case questions.LOST_CARD:
            return "load_cards"
        case questions.AGENT:
            return "handoff"
        case questions.OTHER:
            return "general_agent"
        case _:
            return "clarify"


def after_understand(state: State) -> Route:
    if state.get("intent") in questions.NEEDS_AUTH and not state.get("authenticated"):
        return "authenticate"
    return _route_intent(state)


def after_authenticate(state: State) -> Route:
    return _route_intent(state) if state.get("authenticated") else "__end__"


def continue_unless_done(next_node: str) -> Any:
    def route(state: State) -> str:
        return END if state.get("outcome") else next_node

    return route


def build_graph() -> StateGraph[State, GraphContext]:
    g = StateGraph(State, context_schema=GraphContext)
    for node in (
        understand,
        authenticate,
        account_agent,
        general_agent,
        load_cards,
        choose_card,
        confirm_block,
        block_card,
        handoff,
        clarify,
    ):
        g.add_node(node.__name__, node)

    g.add_edge(START, "understand")
    g.add_conditional_edges("understand", after_understand)
    g.add_conditional_edges("authenticate", after_authenticate)
    g.add_conditional_edges("load_cards", continue_unless_done("choose_card"))
    g.add_conditional_edges("choose_card", continue_unless_done("confirm_block"))
    g.add_conditional_edges("confirm_block", continue_unless_done("block_card"))
    for terminal in ("account_agent", "general_agent", "block_card", "handoff", "clarify"):
        g.add_edge(terminal, END)
    return g


# ---- helpers -------------------------------------------------------------------------


def _record_usage(event: dict[str, Any], reply: Any) -> None:
    usage = getattr(reply, "usage_metadata", None) or {}
    event["input_tokens"] = usage.get("input_tokens")
    event["output_tokens"] = usage.get("output_tokens")
