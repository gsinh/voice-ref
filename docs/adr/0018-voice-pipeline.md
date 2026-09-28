# 0018. Voice: LiveKit for audio, the orchestrator for thinking

- **Status:** Accepted
- **Date:** 2026-09-28

## Context
Phase 2 adds voice. The risk is a second brain: a voice agent with its own prompts, tools
and guardrails that drifts from the text path. Voice also has its own hard problems:
turn-taking, barge-in, latency per stage, and running speech models on a 2-vCPU host.

## Decision
- **LiveKit Agents (1.8) runs the audio loop**: Silero VAD, STT, TTS, interruptions,
  transcripts to the browser. LiveKit Cloud carries the media; the worker connects out.
- **The orchestrator stays the only brain.** A small LiveKit LLM plugin
  (`OrchestratorLLM`) forwards each caller utterance to `/api/chat` and speaks the reply.
  Same LangGraph graph, same OTP, same confirmations, same MCP tools as the text chat.
  An import contract forbids the worker from importing any backend module.
- **Turns are never retried.** A turn can resume a paused confirmation; replaying it after
  a timeout could act twice. The plugin forces zero retries and apologises instead.
- **Caller ID is a token attribute** minted by the BFF for a known demo caller, never
  something the caller says. The agent reads it; the browser cannot change it.
- **STT** is any OpenAI-compatible transcription endpoint (Groq `whisper-large-v3-turbo`).
- **TTS is Kokoro, locally**, as a small LiveKit plugin (or any OpenAI-compatible speech
  endpoint by config). The fp32 model, not int8: measured ~4x faster on x86 CPUs without
  VNNI. Long sentences are spoken clause by clause so the first audio isn't held up.
- **Spoken one-time codes** ("one two three…", "double five", "for" → 4) are normalised in
  the graph, so voice and text share one check.
- **Latency is measured per turn** from LiveKit's metrics (end of utterance, orchestrator,
  TTS first audio) and published to the call page with the orchestrator's trace.

## What the local end-to-end test showed
Self-hosted LiveKit, real Silero and Kokoro, scripted STT and LLM, headless Chromium with a
synthesised caller:
- two real bugs, both fixed: the worker registered with an empty agent name (LiveKit reads
  it at import time), and first-time Kokoro downloads exceeded LiveKit's process start-up
  timeout;
- LiveKit's default of one warm process per core, each loading Kokoro, saturated the CPU
  until the worker reported itself full; now one warm process by default;
- measured on this sandbox's CPU: turns of 1.7 s and 3.2 s voice-to-voice, where Kokoro
  was the largest stage. A faster CPU, a GPU (native Kokoro on the Mac) or a hosted TTS
  are the levers, all configuration.

## Alternatives considered
- **A speech-to-speech model.** See ADR-0003: it would be a second, opaque brain.
- **LiveKit's own LLM with our tools.** Duplicates the graph and its guardrails.
- **Streaming TTS.** Kokoro isn't streaming; sentence and clause chunking gets most of the
  benefit.

## Principle
**One brain, many transports.** Voice is an adapter around the same conversation logic,
so every guardrail is written, tested and audited once.
