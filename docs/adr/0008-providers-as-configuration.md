# 0008. Providers as configuration: Groq default, Ollama fallback

- **Status:** Accepted
- **Date:** 2026-09-26

## Context
We want one model family (Llama) that runs both fast (hosted) and offline (local), no
vendor lock-in, and free tiers where possible.

## Decision
- LLM: Llama via **Groq** by default, via **Ollama** when offline. Selected by
  `LLM_PROVIDER` and `LLM_MODEL`, built with LangChain's `init_chat_model`.
- STT: Groq Whisper by default, faster-whisper offline.
- TTS: Kokoro by default, Piper as an alternative.
- Media: LiveKit Cloud by default, self-hosted LiveKit as an option.
- On macOS, Ollama runs natively (Metal) and containers reach it at
  `host.docker.internal:11434`.

## Alternatives considered
- **Our own provider interface.** LangChain and LiveKit plugins already are that
  interface. Wrapping them again adds code and no value.

## Consequences
Swapping a provider is an env change. Evals can compare providers on the same dataset.
Free-tier rate limits apply, so the eval runner paces itself.

## Principle
**Dependency inversion** by configuration, and **KISS**: don't wrap an abstraction
you already have.
