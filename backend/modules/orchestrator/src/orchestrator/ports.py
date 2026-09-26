"""The orchestrator's ports (ADR-0014): the seams where a second adapter exists or tests
need a fake. Everything else uses its library directly."""

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from langchain_core.tools import BaseTool


@dataclass(frozen=True)
class Question:
    """A bounded choice: pick one label. Labels are semantic words, never yes/no
    (Laya can follow boolean-looking labels instead of their descriptions)."""

    name: str
    instructions: str
    options: dict[str, str]
    threshold: float


DecisionSource = Literal["system1", "llm", "none"]


@dataclass(frozen=True)
class Decision:
    label: str | None  # None: nobody was confident enough
    confidence: float | None
    source: DecisionSource
    latency_ms: float
    notes: list[str] = field(default_factory=list)


class DecisionPort(Protocol):
    async def choose(self, question: Question, text: str) -> Decision: ...


@dataclass(frozen=True)
class Customer:
    id: str
    name: str
    phone: str


class CustomerDirectory(Protocol):
    """Identify a caller from their phone number (the IVR's caller ID)."""

    async def by_phone(self, phone: str) -> Customer | None: ...


class ToolCallError(Exception):
    """The tool ran and reported a failure (MCP `isError`), or its result was unusable."""


class ToolsProvider(Protocol):
    """Banking tools, bound to one authenticated customer."""

    async def for_customer(self, customer_id: str) -> dict[str, BaseTool]:
        """Tools for an LLM to call. Failures come back as text the model can read."""
        ...

    async def call(self, customer_id: str, name: str, args: dict[str, Any]) -> Any:
        """A direct, deterministic call. Returns the structured result or raises
        `ToolCallError`, so code (not a model) can tell success from failure."""
        ...
