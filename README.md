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
| System 2 (language) | gpt-oss-120b on Groq, or Llama on Ollama offline |
| Orchestration | LangGraph, with Postgres checkpoints and `interrupt()` for confirmations |
| Tools | MCP, the LLM's only path to bank data |
| Backend | FastAPI **modular monolith**, with module boundaries enforced in CI |
| Web | Next.js SSR as a backend-for-frontend |
| Workflows / memory / tracing | Kestra, Synap, LangSmith + OpenTelemetry |
| Hosting ($0) | Hugging Face Spaces, Neon, Cloudflare Workers |

## Run it locally

Requires Docker (OrbStack or Docker Desktop), [uv](https://docs.astral.sh/uv/) and Node 22.

```bash
make setup   # install dependencies, create .env and ./secrets (random passwords, keys)
# put your Groq key in secrets/LLM_API_KEY
make up      # postgres → bootstrap + migrate + seed → backend (+ Laya sidecar) → web
open http://localhost:3000/chat
```

The first start downloads Laya's weights (a few GB) into a Docker volume. On a Mac it is
faster to run Laya natively on the Apple GPU and leave it out of the image; see the
System 1 section of `.env.example`. To work fully offline, point `LLM_BASE_URL` at
Ollama.

| URL | What |
|---|---|
| http://localhost:3000/chat | Text chat with a per-turn trace (decisions, tools, timings) |
| http://localhost:3000 | Overview and system status |
| http://localhost:7860/docs | Backend API docs |

Try, as Aarav Sharma (one-time code `123456`):
- "What's my balance?"
- "What is this ₹1,999 charge from yesterday?"
- "I've lost my debit card" → confirm → the card is blocked, once

Secrets live in `./secrets` (gitignored, private), never in `.env` or environment
variables; see ADR-0019. Upgrading from an earlier checkout? Run `make secrets` (it moves
keys over from `.env`), delete the secret lines from `.env`, and `make db-reset` once.

`make seed` resets the demo data. `make help` lists everything; `make check` runs what CI
runs.

## Status

Phases 0–1 are done: the text path works end to end, with guardrails enforced in code
(OTP, token-derived identity, confirmation tokens, idempotent blocking). Next is Phase 2:
voice (LiveKit Cloud, Silero VAD, Whisper, Kokoro). See the
[plan](docs/PLAN.md#8-phases).
