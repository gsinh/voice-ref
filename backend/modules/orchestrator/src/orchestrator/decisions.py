"""System 1 / System 2 decisions (ADR-0005).

- `SystemOneDecision`: any service speaking `POST /v1/systemone` (the Laya sidecar, or
  hosted Jev: same wire format). Fast, bounded, with calibrated confidence.
- `LLMDecision`: the same question answered by the LLM as a constrained choice.
- `CascadeDecision`: trust System 1 when it is confident; otherwise ask the LLM; if the
  LLM fails too, say so (label None) and let the caller choose the safe path.
"""

import time
from typing import Any

import httpx
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from orchestrator.ports import Decision, DecisionPort, Question


def _describe(exc: Exception) -> str:
    """Error type plus a short message, so the trace says *why* (e.g. model not found)."""
    message = str(exc).strip().splitlines()[0][:160] if str(exc).strip() else ""
    return f"{type(exc).__name__}: {message}" if message else type(exc).__name__


def _ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 1)


class SystemOneDecision:
    def __init__(self, base_url: str, api_key: str = "", timeout_s: float = 3.0) -> None:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._http = httpx.AsyncClient(base_url=base_url, timeout=timeout_s, headers=headers)

    async def choose(self, question: Question, text: str) -> Decision:
        start = time.perf_counter()
        body = {
            "state": {"customer_said": text},
            "questions": {
                question.name: {
                    "type": "choice",
                    "instructions": question.instructions,
                    "criteria": question.options,
                }
            },
        }
        resp = await self._http.post("/v1/systemone", json=body)
        resp.raise_for_status()
        answer = resp.json()["answers"][question.name]
        label = answer["choice"]
        if label not in question.options:
            raise ValueError(f"system1 returned unknown label {label!r}")
        return Decision(label, float(answer["confidence"]), "system1", _ms(start))

    async def aclose(self) -> None:
        await self._http.aclose()


class LLMDecision:
    def __init__(self, llm: BaseChatModel) -> None:
        self._llm = llm

    async def choose(self, question: Question, text: str) -> Decision:
        start = time.perf_counter()
        schema: dict[str, Any] = {
            "title": "choose_option",
            "description": "Record the single best option.",
            "type": "object",
            "properties": {"label": {"type": "string", "enum": list(question.options)}},
            "required": ["label"],
        }
        options = "\n".join(f"- {k}: {v}" for k, v in question.options.items())
        structured = self._llm.with_structured_output(schema, method="function_calling")
        result = await structured.ainvoke(
            [
                SystemMessage(
                    f"{question.instructions}\nChoose exactly one option:\n{options}\n"
                    "Judge only what the customer said."
                ),
                HumanMessage(text),
            ]
        )
        label = result.get("label") if isinstance(result, dict) else None
        if label not in question.options:
            raise ValueError(f"llm returned unknown label {label!r}")
        # An LLM's self-reported confidence isn't calibrated, so we don't pretend it is.
        return Decision(label, None, "llm", _ms(start))


class CascadeDecision:
    def __init__(self, primary: DecisionPort | None, fallback: DecisionPort) -> None:
        self._primary = primary
        self._fallback = fallback

    async def choose(self, question: Question, text: str) -> Decision:
        start = time.perf_counter()
        notes: list[str] = []
        if self._primary is not None:
            try:
                first = await self._primary.choose(question, text)
                if first.confidence is not None and first.confidence >= question.threshold:
                    return first
                notes.append(
                    f"system1 chose {first.label} at {first.confidence:.2f}"
                    f" < {question.threshold}: escalating"
                )
            except Exception as exc:  # degrade, don't fail the turn
                notes.append(f"system1 unavailable ({_describe(exc)}): escalating")
        try:
            second = await self._fallback.choose(question, text)
            return Decision(second.label, second.confidence, second.source, _ms(start), notes)
        except Exception as exc:
            notes.append(f"llm unavailable ({_describe(exc)})")
            return Decision(None, None, "none", _ms(start), notes)
