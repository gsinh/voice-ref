"""The voice agent: LiveKit handles audio, the orchestrator does the thinking (ADR-0018).

    caller mic -> LiveKit -> Silero VAD -> STT (Groq Whisper) -> OrchestratorLLM
    (POST /api/chat: the same LangGraph graph as the text chat) -> Kokoro TTS -> caller

One process serves many calls. Heavy models (VAD, Kokoro) load once per process in
`prewarm`; each call gets its own session and conversation id.
"""

import asyncio
import logging
from typing import Any

import httpx
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    tts,
)
from livekit.plugins import openai, silero

from voice_worker.kokoro_tts import KokoroTTS, load_kokoro
from voice_worker.orchestrator_llm import OrchestratorClient, OrchestratorLLM
from voice_worker.settings import Settings, get_settings
from voice_worker.turn_metrics import TOPIC, TurnMetrics, encode

log = logging.getLogger("voice_worker")

CALLER_PHONE_ATTRIBUTE = "caller_phone"


def prewarm(proc: JobProcess) -> None:
    settings = get_settings()
    proc.userdata["vad"] = silero.VAD.load()
    if settings.tts_provider == "kokoro":
        proc.userdata["kokoro"] = load_kokoro(settings.kokoro_dir, settings.kokoro_model)


def build_tts(settings: Settings, proc: JobProcess) -> tts.TTS[Any]:
    if settings.tts_provider == "kokoro":
        return KokoroTTS(proc.userdata["kokoro"], settings.tts_voice, settings.tts_speed)
    return openai.TTS(
        base_url=settings.tts_base_url,
        api_key=settings.tts_api_key.get_secret_value(),
        model=settings.tts_model,
        voice=settings.tts_voice,
    )


server = AgentServer(setup_fnc=prewarm)


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    settings = get_settings()
    await ctx.connect()
    caller = await ctx.wait_for_participant()
    # Caller ID comes from the token the BFF minted, like ANI on a phone line. Never from
    # anything the caller says.
    caller_phone = caller.attributes.get(CALLER_PHONE_ATTRIBUTE, "")
    conversation_id = f"voice-{ctx.room.name}"

    client = OrchestratorClient(settings.orchestrator_url, settings.orchestrator_timeout_s)
    brain = OrchestratorLLM(client, conversation_id, caller_phone)
    session: AgentSession[None] = AgentSession(
        vad=ctx.proc.userdata["vad"],
        stt=openai.STT(
            base_url=settings.stt_base_url,
            api_key=settings.stt_key(),
            model=settings.stt_model,
            language=settings.stt_language,
        ),
        llm=brain,
        tts=build_tts(settings, ctx.proc),
    )

    turns = TurnMetrics()
    pending: set[asyncio.Task[None]] = set()

    @session.on("metrics_collected")
    def _on_metrics(ev: MetricsCollectedEvent) -> None:
        summary = turns.add(ev.metrics, brain.last_turn)
        if summary is not None:
            log.info("turn latency", extra={"conversation": conversation_id, **summary["stages"]})
            task = asyncio.create_task(_publish(ctx.room, summary))
            pending.add(task)  # keep a reference so it isn't garbage-collected mid-flight
            task.add_done_callback(pending.discard)

    ctx.add_shutdown_callback(client.aclose)
    # No instructions: the orchestrator owns every prompt.
    await session.start(agent=Agent(instructions=""), room=ctx.room)
    await session.say(settings.greeting)


async def _publish(room: rtc.Room, summary: dict[str, object]) -> None:
    try:
        await room.local_participant.publish_data(encode(summary), reliable=True, topic=TOPIC)
    except Exception:  # metrics are best-effort; never break the call over them
        log.warning("could not publish turn metrics", exc_info=True)


def check_stt_model(settings: Settings) -> None:
    """Providers retire models (ADR-0008). Say so at startup instead of on every turn."""
    try:
        resp = httpx.get(
            f"{settings.stt_base_url.rstrip('/')}/models",
            headers={"Authorization": f"Bearer {settings.stt_key() or 'none'}"},
            timeout=5,
        )
        ids = (
            {m.get("id") for m in resp.json().get("data", [])} if resp.status_code == 200 else set()
        )
        if ids and settings.stt_model not in ids:
            log.error("STT model not offered by provider", extra={"model": settings.stt_model})
    except (httpx.HTTPError, ValueError):
        log.warning("could not check STT model with provider", extra={"url": settings.stt_base_url})
