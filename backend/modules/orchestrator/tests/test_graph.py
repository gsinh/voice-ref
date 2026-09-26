"""Conversation flows, end to end through the real graph with fake edges.

The LLM is scripted, decisions are keyword rules, and the tools are in-memory, but the
tools verify confirmation tokens for real, so "the card was blocked" means a valid,
customer-bound confirmation reached the tool.
"""

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import Field

from orchestrator.decisions import CascadeDecision
from orchestrator.graph import ACCOUNT_TOOLS, Deps, build_graph
from orchestrator.ports import Customer, Decision, Question, ToolCallError
from orchestrator.service import ChatService, TurnResult
from signed_tokens import TokenError, verify_confirmation

KEY = "graph-test-key-" + "x" * 32
PHONE = "+919800000001"
OTP = "123456"


class ScriptedLLM(GenericFakeChatModel):
    bound_tools: list[str] = Field(default_factory=list)

    def bind_tools(self, tools: Any, **kwargs: Any) -> Any:
        self.bound_tools = [t.name for t in tools]
        return self


class KeywordDecisions:
    """Stands in for Laya: keyword rules, with a confidence we control."""

    def __init__(self) -> None:
        self.asked: list[str] = []

    async def choose(self, question: Question, text: str) -> Decision:
        self.asked.append(question.name)
        t = text.lower()
        label: str | None = None
        if question.name == "intent":
            label = (
                "lost_card"
                if "lost" in t or "block" in t
                else "balance"
                if "balance" in t
                else "transactions"
                if "charge" in t
                else "agent"
                if "human" in t
                else "other"
                if "hello" in t
                else None
            )
        elif question.name == "confirmation":
            label = "confirm" if "yes" in t else "decline" if "no" in t else None
        elif question.name == "card":
            label = next(
                (
                    cid
                    for cid, desc in question.options.items()
                    if cid.startswith("CARD-") and desc.split()[1] in t
                ),
                "unspecified",
            )
        return Decision(label, 0.99 if label else 0.3, "system1", 1.0)


class FakeTools:
    def __init__(self) -> None:
        self.blocked: list[str] = []
        self.cards = [
            {"card_id": "CARD-3001", "card": "Visa debit card ending 4821", "status": "active"},
            {"card_id": "CARD-3002", "card": "Visa credit card ending 9934", "status": "active"},
        ]

    async def for_customer(self, customer_id: str) -> dict[str, BaseTool]:
        def balance() -> str:
            """Balance."""
            return '[{"account": "Savings account XXXX4821", "balance": "₹82,450.00"}]'

        def transactions(limit: int = 5) -> str:
            """Transactions."""
            return '[{"transaction_id": "TXN-5001", "amount": "₹1,999.00"}]'

        def details(transaction_id: str) -> str:
            """Details."""
            return "{}"

        def block_card(card_id: str, reason: str, confirmation_token: str) -> str:
            """Should never be offered to the LLM."""
            return "blocked"

        fns: list[Callable[..., str]] = [balance, transactions, details, block_card]
        names = [*ACCOUNT_TOOLS, "block_card"]
        return {n: StructuredTool.from_function(f, name=n) for n, f in zip(names, fns, strict=True)}

    async def call(self, customer_id: str, name: str, args: dict[str, Any]) -> Any:
        if name == "get_card_status":
            return self.cards
        if name == "block_card":
            try:
                verify_confirmation(
                    KEY,
                    args["confirmation_token"],
                    customer_id=customer_id,
                    action="block_card",
                    target=args["card_id"],
                )
            except TokenError as exc:
                raise ToolCallError("confirmation required") from exc
            self.blocked.append(args["card_id"])
            return {"outcome": "blocked now"}
        raise ToolCallError(name)


class Directory:
    async def by_phone(self, phone: str) -> Customer | None:
        return Customer("CUST-1001", "Aarav Sharma", PHONE) if phone == PHONE else None


def make(llm_replies: list[AIMessage] | None = None) -> tuple[ChatService, FakeTools, ScriptedLLM]:
    llm = ScriptedLLM(messages=iter(llm_replies or []))
    tools = FakeTools()
    deps = Deps(
        llm=llm,
        decisions=KeywordDecisions(),
        directory=Directory(),
        tools=tools,
        signing_key=KEY,
        demo_otp=OTP,
        max_otp_attempts=3,
        intent_threshold=0.85,
        confirm_threshold=0.9,
    )
    graph = build_graph().compile(checkpointer=InMemorySaver())
    return ChatService(graph, deps), tools, llm


class Conversation:
    def __init__(self, service: ChatService, phone: str = PHONE) -> None:
        self.service, self.phone, self.id = service, phone, str(uuid.uuid4())

    async def say(self, text: str) -> TurnResult:
        return await self.service.turn(self.id, self.phone, text)


async def test_balance_requires_otp_then_uses_tools() -> None:
    service, _, llm = make(
        [
            AIMessage("", tool_calls=[{"name": "get_account_balance", "args": {}, "id": "c1"}]),
            AIMessage("Your savings balance is ₹82,450.00."),
        ]
    )
    chat = Conversation(service)

    first = await chat.say("What's my balance?")
    assert first.awaiting == "otp"
    assert "ending 0001" in first.reply
    assert not first.authenticated

    second = await chat.say("1 2 3 4 5 6")
    assert second.authenticated
    assert second.reply == "Your savings balance is ₹82,450.00."
    assert second.outcome == "answered"
    assert any(e["type"] == "tool" and e["name"] == "get_account_balance" for e in second.events)
    # The LLM was never offered the card-blocking tool.
    assert "block_card" not in llm.bound_tools
    assert set(llm.bound_tools) == set(ACCOUNT_TOOLS)


async def test_otp_is_never_stored_in_the_transcript() -> None:
    service, _, _ = make([AIMessage("Hi.")])
    chat = Conversation(service)
    await chat.say("my balance please")
    await chat.say("123456")
    texts = [m["text"] for m in await service.transcript(chat.id)]
    assert not any(OTP in t for t in texts)


async def test_three_wrong_codes_fail_authentication() -> None:
    service, _, _ = make()
    chat = Conversation(service)
    await chat.say("balance")
    await chat.say("000000")
    await chat.say("111111")
    last = await chat.say("222222")
    assert last.outcome == "auth_failed"
    assert not last.authenticated
    assert last.awaiting is None


async def test_unknown_caller_is_handed_off() -> None:
    service, _, _ = make()
    result = await Conversation(service, phone="+910000000000").say("balance")
    assert result.outcome == "handoff"


async def test_lost_card_full_flow_blocks_only_after_confirmation() -> None:
    service, tools, _ = make()
    chat = Conversation(service)
    await chat.say("I lost my card")
    await chat.say(OTP)  # verified; two active cards -> which one?
    status = await chat.say("the debit one")
    assert status.awaiting == "confirmation"
    assert "Visa debit card ending 4821" in status.reply
    assert tools.blocked == []  # nothing happens before an explicit yes

    done = await chat.say("yes, block it")
    assert done.outcome == "card_blocked"
    assert tools.blocked == ["CARD-3001"]


async def test_card_named_up_front_skips_the_card_question() -> None:
    service, tools, _ = make()
    chat = Conversation(service)
    await chat.say("block my credit card, I lost it")
    confirm = await chat.say(OTP)
    assert confirm.awaiting == "confirmation"
    assert "credit card ending 9934" in confirm.reply
    await chat.say("yes")
    assert tools.blocked == ["CARD-3002"]


async def test_declining_does_not_block() -> None:
    service, tools, _ = make()
    chat = Conversation(service)
    await chat.say("I lost my debit card")
    await chat.say(OTP)
    result = await chat.say("no, wait")
    assert result.outcome == "not_confirmed"
    assert tools.blocked == []


async def test_unclear_confirmation_twice_means_no() -> None:
    service, tools, _ = make()
    chat = Conversation(service)
    await chat.say("I lost my debit card")
    await chat.say(OTP)
    again = await chat.say("hmm, what does that mean?")
    assert again.awaiting == "confirmation"
    result = await chat.say("I'm not sure")
    assert result.outcome == "not_confirmed"
    assert tools.blocked == []


async def test_naming_an_already_blocked_card_does_not_target_another() -> None:
    service, tools, _ = make()
    tools.cards[0]["status"] = "blocked"  # the debit card is already blocked
    chat = Conversation(service)
    await chat.say("I lost my debit card")
    result = await chat.say(OTP)
    assert result.outcome == "answered"
    assert "debit card ending 4821 is already blocked" in result.reply
    assert result.awaiting is None
    assert tools.blocked == []


async def test_unnamed_card_with_one_active_goes_straight_to_confirmation() -> None:
    service, tools, _ = make()
    tools.cards[1]["status"] = "blocked"
    chat = Conversation(service)
    await chat.say("I lost my card")
    confirm = await chat.say(OTP)
    assert confirm.awaiting == "confirmation"
    assert "debit card ending 4821" in confirm.reply


async def test_unclear_intent_asks_to_clarify() -> None:
    service, _, _ = make()
    result = await Conversation(service).say("asdfgh")
    assert result.outcome == "unclear"


# ---- the cascade ---------------------------------------------------------------------

Q = Question("intent", "?", {"a": "A", "b": "B"}, threshold=0.85)


class Fixed:
    def __init__(self, label: str | None, confidence: float | None, fail: bool = False) -> None:
        self.label, self.confidence, self.fail, self.calls = label, confidence, fail, 0

    async def choose(self, question: Question, text: str) -> Decision:
        self.calls += 1
        if self.fail:
            raise ConnectionError
        return Decision(self.label, self.confidence, "system1", 1.0)


class LLMFixed(Fixed):
    async def choose(self, question: Question, text: str) -> Decision:
        d = await super().choose(question, text)
        return Decision(d.label, None, "llm", 1.0)


@pytest.mark.parametrize(
    ("primary", "fallback", "label", "source"),
    [
        (Fixed("a", 0.95), LLMFixed("b", None), "a", "system1"),  # confident: trust it
        (Fixed("a", 0.50), LLMFixed("b", None), "b", "llm"),  # unsure: escalate
        (Fixed("a", 0.9, fail=True), LLMFixed("b", None), "b", "llm"),  # down: escalate
        (Fixed("a", 0.5), LLMFixed("b", None, fail=True), None, "none"),  # both fail: None
    ],
)
async def test_cascade(primary: Fixed, fallback: Fixed, label: str | None, source: str) -> None:
    decision = await CascadeDecision(primary, fallback).choose(Q, "text")
    assert (decision.label, decision.source) == (label, source)


async def test_cascade_skips_llm_when_system1_is_confident() -> None:
    llm = LLMFixed("b", None)
    await CascadeDecision(Fixed("a", 0.99), llm).choose(Q, "text")
    assert llm.calls == 0


async def test_cascade_notes_say_why_things_failed() -> None:
    class NotFound:
        async def choose(self, question: Question, text: str) -> Decision:
            raise LookupError("The model x does not exist or you do not have access to it.")

    decision = await CascadeDecision(Fixed("a", 0.9, fail=True), NotFound()).choose(Q, "t")
    assert decision.source == "none"
    assert "ConnectionError" in decision.notes[0]
    assert "does not exist" in decision.notes[1]
