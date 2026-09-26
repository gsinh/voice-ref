# 0008. Providers as configuration: Groq default, Ollama fallback

- **Status:** Accepted
- **Date:** 2026-09-26

## Context
We want one model family (Llama) that runs both fast (hosted) and offline (local), no
vendor lock-in, and free tiers where possible.

## Decision
- LLM: any **OpenAI-compatible endpoint**, chosen by `LLM_BASE_URL` and `LLM_MODEL`:
  **Groq** by default (`openai/gpt-oss-120b`), **Ollama** when offline (`llama3.2:3b`).
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

## Revision (Phase 1): the provider retired our model
Groq decommissioned `llama-3.3-70b-versatile` on 2026-08-16 and deprecated its other
Llama models, so every turn failed with "model does not exist". Because the model is
configuration, the fix was one env value (default now `openai/gpt-oss-120b`, Groq's
recommended replacement). Two lessons now in the code:
- `/api/status` asks the provider for its model list and says when the configured model
  isn't offered (and what is), instead of letting every turn fail.
- Decision traces carry the error message, not only its type.

A third-party model is a dependency with a lifecycle, like a library version. Pin it,
watch the provider's deprecation notices, and make a swap a config change.
