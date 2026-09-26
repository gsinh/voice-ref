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
                                CUSTOMER (browser mic)
                                        │ WebRTC
                                        ▼
                               LiveKit Cloud (media edge)
                                        │
┌───────────────────────── Hetzner VPS (docker compose) ─────────────────────────┐
│                                       ▼                                         │
│   voice_agent ── Silero VAD ── STT (Groq Whisper) ── TTS (Kokoro)               │
│        │                                                                        │
│        ▼  same graph as the text path                                           │
│   orchestrator (FastAPI + LangGraph)                                            │
│     auth_gate → memory_recall → decide (Laya: safety, intent, risk)             │
│        │                               │ low confidence                         │
│        │                               └──► Llama fallback (System 2)           │
│        ▼                                                                        │
│     account_agent | card_agent | general_agent   (Llama via Groq / Ollama)      │
│        │                                                                        │
│        │  card_agent: policy → interrupt("confirm?") → Laya yes/no → token      │
│        ▼                                                                        │
│   mcp_server (FastMCP) ──► banking_api (FastAPI) ──► Postgres (mock bank)       │
│                                                                                 │
│   decision (Laya System-1 model, ONNX)          Postgres: checkpoints, metrics, │
│   kestra (async workflows)                                audit, memory         │
│   web (Next.js SSR, BFF)                                                        │
└─────────────────────────────────────────────────────────────────────────────────┘
        ▲ Cloudflare Tunnel + Access (no open ports)
        │
   Outbound only: Groq · LiveKit Cloud · LangSmith · Synap
```

### System 1 / System 2

| | System 1 — **Laya** | System 2 — **Llama** |
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
| System 1 | Laya (ONNX, Hugging Face weights) | `LLMDecision` adapter |
| System 2 | Llama on Groq | Llama on Ollama (native on the Mac: `llama3.2:3b`) |
| Orchestration | LangGraph + Postgres checkpointer | — |
| Tools | MCP (FastMCP, streamable HTTP) + `langchain-mcp-adapters` | — |
| TTS | Kokoro | Piper |
| Memory | Synap | LangGraph `PostgresStore` |
| Workflows | Kestra (self-hosted) | — |
| Tracing | LangSmith + OpenTelemetry | OTel only |
| Backend | FastAPI (Python 3.12, uv) | — |
| Frontend | Next.js (App Router, SSR, BFF) | — |
| Data | Postgres 17 | — |
| Delivery | GitHub Actions → GHCR (multi-arch) → Hetzner | — |
| Edge | Cloudflare Tunnel + Access | — |

## 6. Architecture principles, and where each one appears

| Principle | Where it appears |
|---|---|
| **KISS / YAGNI** | Use LangChain's model abstraction and LiveKit's plugins instead of wrapping them. Three agents, not ten. A compose profile appears only in the phase that needs it. |
| **12-Factor** | Config in env (`pydantic-settings`), backing services attached by URL, stateless processes (state in Postgres), JSON logs to stdout, graceful SIGTERM, same images in dev and prod, one-off admin jobs via `docker compose run`. |
| **SRP** | One job per module: router routes, policy decides, tools act, audit records. |
| **OCP** | New agent = new graph node; new provider = new config value. |
| **LSP / ISP** | Small ports (`DecisionPort`, `MemoryPort`, `BankingPort`, `FaultInjector`) with interchangeable adapters. |
| **DIP / Hexagonal** | Domain code depends on ports; a composition root wires adapters. |
| **Least privilege** | LLM sees tools, not data; high-risk tools need a token; each service has its own DB role. |
| **Fail fast, degrade gracefully** | Timeouts, circuit breakers, fallback controller. |
| **Idempotency** | Sensitive tools take an idempotency key. |

## 7. Repository layout

```
voice-ref/
├── compose.yaml               # profiles grow phase by phase
├── .env.example               # every setting, documented
├── Makefile                   # the commands a contributor runs
├── pyproject.toml             # uv workspace root + shared ruff/mypy/pytest config
├── libs/common/               # shared: settings base, JSON logging, health router
├── services/
│   ├── orchestrator/          # FastAPI + LangGraph
│   ├── mcp_server/            # FastMCP banking tools
│   ├── banking_api/           # mock bank system of record
│   ├── decision/              # Laya System-1 service
│   ├── voice_agent/           # LiveKit worker          (Phase 2)
│   └── web/                   # Next.js SSR
├── infra/
│   ├── postgres/init/         # schemas, roles, seed data
│   └── kestra/flows/          #                        (Phase 3)
├── evals/                     #                        (Phase 4)
├── docs/
│   ├── PLAN.md
│   └── adr/
└── .github/workflows/
```

## 8. Phases

| Phase | Build | Done when |
|---|---|---|
| **0. Skeleton** | Layout, uv workspace, shared lib, service stubs with health checks, Postgres schemas + seed data, Next.js shell, compose `core` profile, CI (lint, typecheck, test, image build), ADRs | `make up` starts everything healthy; CI green |
| **1. Core (text)** | Banking API, MCP tools, Laya decision service, LangGraph graph (auth, routing, 3 agents, interrupt-based confirmation, confirmation token), mock OTP, `/chat` | All three use cases work in text on Groq and on Ollama |
| **2. Voice** | Voice worker (LiveKit Cloud, Silero, Groq Whisper, Kokoro), `/call`, `latency-probe` | All three use cases work by voice; per-stage latency captured |
| **3. Production traits** | OTel + LangSmith, `/observability`, fault toggles, fallback controller, human handoff, audit log, Kestra (`workflows` profile), memory (Synap + Postgres adapter) | Every fault degrades gracefully; latency visible per turn |
| **4. Evaluation** | ~80-case dataset incl. Hindi/Hinglish; intent, tool-choice, task completion, groundedness, sensitive-action compliance; Laya vs Llama; Groq vs Ollama; `/evals` | `make eval` produces a report; nightly Kestra run |
| **5. Ship** | Multi-arch images to GHCR, Hetzner CAX21 (EU), Cloudflare Tunnel + Access, deploy workflow, `/cost`, `/architecture`, demo script, recording | Public URL always on; 5-minute demo rehearsed |

## 9. Deployment

- **Local (M4, 16 GB)**: OrbStack (or Docker Desktop) with ~8 GB for the VM. Ollama
  runs natively on macOS for Metal acceleration; containers reach it at
  `host.docker.internal:11434`. Groq + LiveKit Cloud are the defaults, so the local stack
  stays light.
- **Production**: one Hetzner CAX21 (ARM64, EU — same architecture as the Mac). The same
  compose file, images pulled from GHCR, secrets in a root-only `.env`. Cloudflare Tunnel
  exposes it with no inbound ports; Cloudflare Access gates the live demo.
- **Why EU and not India**: each turn makes several sequential calls to Groq (US/EU),
  but only one audio round trip, and LiveKit Cloud's edge is already near the user.
  Putting the worker near the model APIs wins. Validated by the `latency-probe`
  (ADR-0012).
- **Production for a real Indian bank** would move to an Indian region with in-country
  models to satisfy RBI data-localisation rules. That is a configuration change, not a
  code change.

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
