"""Per-turn latency, stage by stage, published to the call so the page can show it.

LiveKit reports metrics per stage, tagged with the speech id of the reply:
  end of utterance (VAD silence + transcript ready) -> "LLM" (our orchestrator) ->
  TTS time to first audio.
When the TTS metric for a reply arrives, the turn is complete: publish a summary with the
orchestrator's own trace (decisions, tools, LLM calls) attached.
"""

import json
from dataclasses import dataclass, field
from typing import Any

from livekit.agents import metrics

TOPIC = "turn-metrics"


@dataclass
class TurnMetrics:
    eou: dict[str, float] = field(default_factory=dict)
    llm_ttft: dict[str, float] = field(default_factory=dict)

    def add(self, m: Any, orchestrator_turn: dict[str, Any] | None) -> dict[str, Any] | None:
        """Record one metric; return a finished turn summary when there is one."""
        sid = getattr(m, "speech_id", None) or ""
        if isinstance(m, metrics.EOUMetrics):
            self.eou[sid] = m.end_of_utterance_delay
        elif isinstance(m, metrics.LLMMetrics):
            self.llm_ttft[sid] = m.ttft
        elif isinstance(m, metrics.TTSMetrics) and sid in self.llm_ttft:
            eou = self.eou.pop(sid, 0.0)
            orch = self.llm_ttft.pop(sid)
            stages = {
                "end_of_utterance_ms": round(eou * 1000),
                "orchestrator_ms": round(orch * 1000),
                "tts_first_audio_ms": round(m.ttfb * 1000),
            }
            turn = orchestrator_turn or {}
            return {
                "stages": stages,
                "total_ms": sum(stages.values()),
                "intent": turn.get("intent"),
                "awaiting": turn.get("awaiting"),
                "outcome": turn.get("outcome"),
                "authenticated": turn.get("authenticated"),
                "events": turn.get("events", []),
            }
        return None


def encode(summary: dict[str, Any]) -> bytes:
    return json.dumps(summary).encode()
