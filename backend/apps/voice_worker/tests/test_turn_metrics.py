from livekit.agents import metrics

from voice_worker.turn_metrics import TurnMetrics


def _eou(sid: str, delay: float) -> metrics.EOUMetrics:
    return metrics.EOUMetrics(
        timestamp=0,
        end_of_utterance_delay=delay,
        transcription_delay=0.1,
        on_user_turn_completed_delay=0,
        speech_id=sid,
    )


def _llm(sid: str, ttft: float) -> metrics.LLMMetrics:
    return metrics.LLMMetrics(
        label="x", request_id="r", timestamp=0, duration=ttft, ttft=ttft, cancelled=False,
        completion_tokens=0, prompt_tokens=0, prompt_cached_tokens=0, total_tokens=0,
        tokens_per_second=0, speech_id=sid,
    )  # fmt: skip


def _tts(sid: str, ttfb: float) -> metrics.TTSMetrics:
    return metrics.TTSMetrics(
        label="x", request_id="r", timestamp=0, ttfb=ttfb, duration=1, audio_duration=1,
        cancelled=False, characters_count=10, streamed=False, speech_id=sid,
    )  # fmt: skip


def test_a_turn_is_summarised_when_its_first_audio_is_ready() -> None:
    turns = TurnMetrics()
    orch = {"intent": "balance", "outcome": "answered", "events": [{"type": "tool"}]}
    assert turns.add(_eou("s1", 0.6), orch) is None
    assert turns.add(_llm("s1", 0.9), orch) is None
    summary = turns.add(_tts("s1", 0.35), orch)
    assert summary is not None
    assert summary["stages"] == {
        "end_of_utterance_ms": 600,
        "orchestrator_ms": 900,
        "tts_first_audio_ms": 350,
    }
    assert summary["total_ms"] == 1850
    assert summary["intent"] == "balance"


def test_the_greeting_is_not_reported_as_a_turn() -> None:
    # session.say() speaks without the orchestrator: TTS metrics with no LLM stage.
    assert TurnMetrics().add(_tts("greeting", 0.3), None) is None
