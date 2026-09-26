# Enterprise Voice AI Reference

A production-inspired voice agent for a retail bank's customer-service line, built as an
enterprise architecture problem: business outcomes first, then guardrails, latency,
observability, failure handling, evaluation and cost.

Customers call and say *"What's my balance?"*, *"What's this ₹1,999 charge?"* or *"I
lost my card"*. The agent answers from the bank's systems of record through MCP tools.
It never takes a sensitive action without explicit confirmation and a deterministic,
audited tool call.

- **Plan:** [`docs/PLAN.md`](docs/PLAN.md)
- **Decisions and trade-offs:** [`docs/adr/`](docs/adr/)

## Architecture at a glance

| Concern | Choice |
|---|---|
| Media / VAD | LiveKit Cloud, Silero |
| STT / TTS | Groq Whisper / Kokoro |
| System 1 (fast decisions) | Laya: intent, confirmation, risk, with calibrated confidence |
| System 2 (language) | Llama on Groq, or Ollama offline |
| Orchestration | LangGraph, with Postgres checkpoints and `interrupt()` for confirmations |
| Tools | MCP, the LLM's only path to bank data |
| Backend | FastAPI **modular monolith**, with module boundaries enforced in CI |
| Web | Next.js SSR as a backend-for-frontend |
| Workflows / memory / tracing | Kestra, Synap, LangSmith + OpenTelemetry |
| Hosting ($0) | Hugging Face Spaces, Neon, Cloudflare Workers |

## Run it locally

Requires Docker (OrbStack or Docker Desktop), [uv](https://docs.astral.sh/uv/) and Node 22.

```bash
make setup   # install dependencies, create .env
make up      # postgres → migrate + seed → backend → web, waits until healthy
open http://localhost:3000
```

| URL | What |
|---|---|
| http://localhost:3000 | Web app (system status for now) |
| http://localhost:7860/docs | Backend API docs |
| http://localhost:7860/readyz | Backend readiness |

Other commands: `make help`. Run `make check` to run everything CI runs.

## Status

Phase 0 (skeleton) is done. Next is Phase 1: the text path with LangGraph, Laya, MCP and
the three use cases. See the phase table in the [plan](docs/PLAN.md#8-phases).
