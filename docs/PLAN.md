# Enterprise Voice AI Reference — Build Plan

A production-inspired reference implementation of an enterprise voice agent for a
retail bank's customer-service line. It exists to show how a Solutions Architect takes
a customer requirement from **business problem → architecture → working system →
measurement → production concerns**, and to be a place to learn good architecture by
building it.

> Decisions and their trade-offs live in [`docs/adr/`](adr/). This file is the map;
> the ADRs are the reasoning.

---

## 1. Customer scenario

A large Indian retail bank handles millions of calls a month through a menu-driven IVR
("Press 1 for account information…"). It wants customers to simply say:

- "What's my account balance?"
- "Why was I charged ₹1,999 yesterday?"
- "I lost my card."

…while keeping its existing systems of record and its human contact-centre agents.

## 2. Business outcomes first

| Outcome | KPI | Where we measure it |
|---|---|---|
| Automation | Containment rate (resolved without a human) | Kestra post-call flow → `/observability` |
| Customer experience | Turn latency p50/p95, CSAT proxy | Per-turn metrics |
| Accuracy | Task completion, intent accuracy | Eval suite |
| Reliability | Successful call completion under faults | Fault toggles + fallback metrics |
| Economics | Cost per automated interaction | `/cost` calculator, token accounting |
| Safety | Unconfirmed sensitive actions (target: 0) | Eval suite + audit log |

> "I start with the business outcome and then design the architecture required to achieve it."

## 3. Demo use cases (three, done well)

1. **Account balance** — authenticate, call a read-only tool, answer naturally.
2. **Explain a transaction** — retrieve recent transactions, reason about which one the
   customer means, explain it. Tool calling + reasoning.
3. **Lost card** — high-risk action: detect → explicit confirmation → deterministic tool
   with a confirmation token → audit → async follow-up workflow. Guardrails.

## 4. Architecture

```
 CUSTOMER (browser)
   │  HTTPS                                   │ WebRTC audio
   ▼                                          ▼
 Next.js SSR — Cloudflare Workers (BFF)     LiveKit Cloud (media edge near the user)
   │  server-to-server, HF token                ▲
   ▼                                            │ outbound
┌──────────── Hugging Face Space: backend (private, Docker) ─────────────────────┐
│  process 1: gateway (FastAPI) — modular monolith                                │
│    /api     orchestrator  LangGraph: understand → authenticate (OTP)            │
│                           → account agent | card flow | general | handoff      │
│    /mcp     mcp_server    MCP tools (identity from session token) ──► /bank     │
│    /bank    banking_api   mock system of record                                 │
│  process 2: laya-serve    127.0.0.1:8100 — System 1 decisions (or hosted Jev)   │
│  process 2b: agentgateway 127.0.0.1:15000 — LLM + MCP policy, failover (Ph. 3)  │
│  process 3: voice worker  Silero VAD · Groq Whisper · Kokoro TTS → /api/chat   │
└──────────────────────────────────────────────────────────────────────────────────┘
        │                          │                          │
        ▼                          ▼                          ▼
  Neon Postgres (free)     Kestra — second HF Space     Groq · LangSmith · Synap
  bank, orchestrator,      (open source, Neon DB)       (outbound APIs)
  kestra databases         async flows, schedules

  Cloudflare cron trigger ── keep-alive pings to both Spaces
```

### System 1 / System 2

| | System 1 — **Laya** | System 2 — **LLM** (gpt-oss on Groq, Llama on Ollama) |
|---|---|---|
| Job | Bounded decisions: pick a label, a score, yes/no | Language: reasoning, tool use, natural replies |
| Latency | Tens of ms (to be measured) | Hundreds of ms |
| Output | Typed answer + calibrated confidence | Free text / tool calls |
| Used for | Intent, confirmation, risk, escalation, safety | Agents, fallback when System 1 is unsure |

The **confidence-gated cascade**: act on Laya when confidence ≥ threshold, escalate to
Llama when it isn't, ask a clarifying question when both are unsure. Thresholds are env
config, tuned from eval data.

### Guardrails (enforced outside the LLM)

| Risk | Example | Rule |
|---|---|---|
| Low | "What's my balance?" | Read-only tool, requires authenticated session |
| Medium | "Show recent transactions" | Authenticated session |
| High | "Block my card" | `interrupt()` → explicit confirmation (Laya yes/no ≥ threshold) → single-use confirmation token → MCP tool verifies token → audit log → idempotency key |

The LLM only ever sees MCP tools. It never sees the database, and it cannot mint a
confirmation token.

### Failure engineering

Fault toggles (`/faults`): MCP down, LLM timeout, added latency, STT failure.
Timeouts + circuit breakers on every external call feed a **fallback controller** that
routes to a deterministic flow or a human handoff. Conversation state lives in the
LangGraph Postgres checkpointer, so a handoff carries customer, auth status, intent,
summary and tool results — the customer never starts again.

### Memory vs system of record

Long-term memory (Synap, or a local Postgres store) holds **context only** — preferences,
"called yesterday about the ₹1,999 charge". Balances, card status and transactions always
come from the banking API via MCP. PII is redacted before memory writes. Recall happens
once after auth; writes happen async after the call.

### Sync vs async

The voice turn does the minimum synchronously. Everything durable and slow runs in
**Kestra**: `lost_card_followup`, `post_call_processing`, `human_handoff`, `nightly_evals`,
`db_backup`.

## 5. Technology stack

| Layer | Default | Offline / alternative |
|---|---|---|
| Media | LiveKit Cloud | Self-hosted LiveKit (compose profile) |
| VAD | Silero | — |
| STT | Groq Whisper | faster-whisper container |
| System 1 | Laya's server (`laya-serve`) as a localhost sidecar; natively on the Mac GPU in dev | Hosted Jev (same API), or `LLMDecision` |
| System 2 | `openai/gpt-oss-120b` on Groq (Groq retired its Llama 3.3 model; ADR-0008) | Llama on Ollama (native on the Mac: `llama3.2:3b`) |
| Orchestration | LangGraph + Postgres checkpointer | — |
| Tools | MCP (FastMCP, streamable HTTP) + `langchain-mcp-adapters` | — |
| AI gateway | agentgateway sidecar: LLM failover, per-tool authz, rate limits, OTel (Phase 3) | Direct URLs (Phase 1–2) |
| TTS | Kokoro | Piper |
| Memory | Synap | LangGraph `PostgresStore` |
| Workflows | Kestra open source, in its own HF Space | Local container (`workflows` profile) |
| Tracing | LangSmith + OpenTelemetry | OTel only |
| Backend | FastAPI modular monolith (Python 3.12, uv) | — |
| Frontend | Next.js (App Router, SSR, BFF) on Cloudflare Workers | Container locally; Vercel Hobby if Workers limits bite |
| Data | Neon Postgres (free tier) | Postgres 17 container locally |
| Delivery | GitHub Actions → HF Space git repos + `wrangler` to Workers | — |
| Edge | Cloudflare Workers (web), private HF Space (backend) | — |

## 6. Architecture principles, and where each one appears

| Principle | Where it appears |
|---|---|
| **KISS / YAGNI** | Use LangChain's model abstraction and LiveKit's plugins instead of wrapping them. Three agents, not ten. One deployable backend. A compose profile appears only in the phase that needs it. |
| **12-Factor** | Config in env (`pydantic-settings`), backing services attached by URL, stateless processes (state in Postgres), JSON logs to stdout, graceful SIGTERM, same images in dev and prod, one-off admin jobs via `docker compose run`. |
| **SRP** | One job per module: router routes, policy decides, tools act, audit records. |
| **OCP** | New agent = new graph node; new provider = new config value. |
| **LSP / ISP** | Small ports (`DecisionPort`, `MemoryPort`, `BankingPort`, `FaultInjector`) with interchangeable adapters. |
| **DIP / Hexagonal** | Domain code depends on ports; a composition root wires adapters. |
| **Least privilege** | LLM sees tools, not data; high-risk tools need a token; each module has its own DB role and schema; the backend Space is private. |
| **Fail fast, degrade gracefully** | Timeouts, circuit breakers, fallback controller. |
| **Idempotency** | Sensitive tools take an idempotency key; migrations and seeding are re-runnable. |
| **Modular monolith** | Modules are separate packages that never import each other (enforced by `lint-imports`) and talk over HTTP/MCP, deployed as one process. |

## 7. Repository layout

```
voice-ref/
├── compose.yaml               # local stack: postgres, migrate, backend, web
├── .env.example               # every setting, documented (no secrets)
├── scripts/make-secrets.sh    # ./secrets: generated passwords and keys (ADR-0019)
├── Makefile                   # the commands a contributor runs (CI runs the same)
├── backend/                   # uv workspace; this folder is what the HF Space builds
│   ├── Dockerfile             # one image: start | serve | migrate | seed (+ Laya venv)
│   ├── apps/gateway/          # composition root, health, migrations, launcher, CLI
│   ├── libs/signed_tokens/    # shared kernel: session + confirmation JWTs
│   └── modules/
│       ├── orchestrator/      # LangGraph                → /api
│       ├── banking_api/       # mock bank (schema bank)  → /bank
│       └── mcp_server/        # MCP tools                → /mcp
├── web/                       # Next.js SSR BFF
├── infra/
│   └── kestra/                # Kestra Space + flows     (Phase 3)
├── evals/                     #                          (Phase 4)
├── docs/
│   ├── PLAN.md
│   └── adr/
└── .github/workflows/         # ci.yml now; deploy workflows in Phase 5
```

## 8. Phases

| Phase | Build | Done when |
|---|---|---|
| **0. Skeleton** ✓ | Modular-monolith backend (gateway + 4 module stubs), health checks, per-module roles/schemas, migration runner, seed data, Next.js SSR status page, compose, CI (lint, boundaries, typecheck, tests, image builds), ADRs | `make up` starts everything healthy; CI green |
| **1. Core (text)** ✓ | Banking API, MCP tools, signed tokens, Laya sidecar + decision cascade, LangGraph graph (OTP auth, routing, account agent, card flow with interrupt-based confirmation), launcher, `/chat` with per-turn trace | All three use cases work in text; verified end to end with a scripted OpenAI-compatible model (Groq and Laya to be confirmed on a machine that can reach them) |
| **2. Voice** ✓ | Voice worker (LiveKit Agents, Silero VAD, Groq Whisper, Kokoro), orchestrator as the LLM plugin, spoken one-time codes, `/call` with live transcript and per-stage latency, `latency-probe` | All three use cases work by voice; verified end to end with self-hosted LiveKit, real VAD and TTS, scripted STT/LLM |
| **3. Production traits** | OTel + LangSmith, `/observability`, fault toggles, fallback controller, human handoff, audit log, Kestra (`workflows` profile locally, own HF Space in production), memory (Synap + Postgres adapter), agentgateway sidecar with failover and tool policies (ADR-0017) | Every fault degrades gracefully; latency visible per turn |
| **4. Evaluation** | ~80-case dataset incl. Hindi/Hinglish; intent, tool-choice, task completion, groundedness, sensitive-action compliance; Laya vs Llama; Groq vs Ollama; `/evals` | `make eval` produces a report; nightly Kestra run |
| **5. Ship** | Neon project + bootstrap, backend and Kestra Spaces, web on Cloudflare Workers (OpenNext), keep-alive cron, deploy workflows, `/cost`, `/architecture`, demo script, recording | Public URL up without a laptop; 5-minute demo rehearsed |

## 9. Deployment: all free tiers (ADR-0016)

| Component | Where | Free-tier notes |
|---|---|---|
| Web (Next.js SSR BFF) | Cloudflare Workers via OpenNext | Free plan limits on CPU per request and bundle size; Vercel Hobby is the fallback |
| Backend + voice worker | Hugging Face Space (Docker, 2 vCPU / 16 GB), **private** | Sleeps after ~48 h without traffic; one exposed port (7860) |
| Workflows | Kestra open source in a second HF Space | Same sleep rule; uses its own Neon database |
| Database | Neon Postgres | Scales to zero; first query after idle is slower |
| Media, LLM, STT | LiveKit Cloud, Groq | Free-tier quotas |
| Tracing, memory | LangSmith, Synap | Optional; the system runs without them |
| Keep-alive | Cloudflare Workers cron trigger | Pings both Spaces' `/healthz` |

- **Local (M4, 16 GB)**: `make up` runs Postgres, the backend and the web app in Docker
  (OrbStack or Docker Desktop). Ollama runs natively on macOS for Metal acceleration and
  containers reach it at `host.docker.internal:11434`.
- **Security**: the browser only talks to the Workers BFF and LiveKit. The backend Space
  is private; the BFF calls it with a Hugging Face read token held as a Worker secret.
  Kestra calls back into the backend with HMAC-signed webhooks.
- **Latency**: HF Spaces and Neon (same region) sit in the US next to Groq, where every
  turn makes several sequential model calls; LiveKit Cloud keeps the audio edge near
  users in India. Measured by the `latency-probe` in Phase 2.
- **Trade-off, stated plainly**: $0 buys a system that can sleep. A ~€5–8/month VPS
  running the same compose file is the upgrade path (ADR-0012 records that design).
- **Production for a real Indian bank** would move to an Indian region with in-country
  models to satisfy RBI data-localisation rules: a configuration change, not a code change.

## 10. The five-minute demo

1. "I approached this as an enterprise architecture problem, not a chatbot."
   Business outcomes.
2. Voice: "What's my balance?"
3. Voice: "I don't recognise my last transaction."
4. Voice: "I've lost my card, block it." Confirmation, token, audit, Kestra follow-up.
5. Toggle an MCP failure. Graceful fallback, then handoff with context.
6. `/observability`: trace, Laya decisions and confidence, tool calls, per-stage
   latency, outcome.
7. `/evals` and `/cost`: the numbers.
8. "The objective isn't to show an LLM can talk. It's to show conversational AI
   integrating safely with enterprise systems, operating reliably, and producing
   measurable business outcomes."
