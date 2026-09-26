"""Per-turn trace: which decisions were made, by whom, and where the time went.

This is the raw material for the observability page and the latency budget
(ADR-0013). Phase 3 also exports it as OpenTelemetry spans.
"""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from orchestrator.ports import Decision


@dataclass
class TurnRecorder:
    started: float = field(default_factory=time.perf_counter)
    events: list[dict[str, Any]] = field(default_factory=list)

    def decision(self, question: str, d: Decision) -> None:
        self.events.append(
            {
                "type": "decision",
                "question": question,
                "label": d.label,
                "confidence": d.confidence,
                "source": d.source,
                "latency_ms": d.latency_ms,
                "notes": d.notes,
            }
        )

    @contextmanager
    def timed(self, kind: str, name: str) -> Iterator[dict[str, Any]]:
        event: dict[str, Any] = {"type": kind, "name": name, "ok": True}
        start = time.perf_counter()
        try:
            yield event
        except Exception as exc:
            event["ok"] = False
            event["error"] = type(exc).__name__
            raise
        finally:
            event["latency_ms"] = round((time.perf_counter() - start) * 1000, 1)
            self.events.append(event)

    def total_ms(self) -> float:
        return round((time.perf_counter() - self.started) * 1000, 1)
