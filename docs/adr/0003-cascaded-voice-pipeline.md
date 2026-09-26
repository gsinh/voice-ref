# 0003. Cascaded STT → LLM → TTS over speech-to-speech

- **Status:** Accepted
- **Date:** 2026-09-26

## Context
Speech-to-speech models (a single model that hears and speaks) can have the lowest
latency and the most natural prosody. A cascaded pipeline (VAD → STT → text agent →
TTS) has more hops.

## Decision
Use a cascaded pipeline. Silero VAD, Groq Whisper STT, a text-based LangGraph agent,
and Kokoro TTS.

## Alternatives considered
- **Speech-to-speech (e.g. realtime audio models).** Fewer hops, but the reasoning step
  is opaque, text-level guardrails and audit are harder, and it ties us to one vendor.

## Consequences
- Every stage has a text boundary that can be logged, evaluated, guarded and audited.
  For a bank, that matters more than the last 200 ms.
- The same agent serves text chat and voice, so evals run on text.
- Each stage can be swapped independently. We must engineer latency deliberately:
  streaming everywhere, and System-1 decisions instead of LLM calls where possible
  (ADR-0005).

## Principle
Choose **observability and control** over raw latency when the domain is regulated.
