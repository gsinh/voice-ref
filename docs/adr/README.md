# Architecture Decision Records

Each ADR records one decision: the context, what we chose, what we gave up, and the
principle it illustrates. They are short on purpose. When a decision changes, add a new
ADR that supersedes the old one rather than editing history.

| # | Decision | Status |
|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| [0002](0002-monorepo-compose-twelve-factor.md) | Monorepo, Compose profiles, 12-factor config | Accepted |
| [0003](0003-cascaded-voice-pipeline.md) | Cascaded STT → LLM → TTS over speech-to-speech | Accepted |
| [0004](0004-langgraph-orchestration.md) | LangGraph, one graph for text and voice | Accepted |
| [0005](0005-system1-system2-laya-llama.md) | System 1 / System 2: Laya decides, Llama talks | Accepted (latency to validate) |
| [0006](0006-mcp-tool-boundary-guardrails.md) | MCP as the tool boundary; guardrails outside the LLM | Accepted |
| [0007](0007-postgres-single-backing-store.md) | Postgres as the single backing store, schema per service | Accepted |
| [0008](0008-providers-as-configuration.md) | Providers as configuration: Groq default, Ollama fallback | Accepted |
| [0009](0009-kestra-async-workflows.md) | Kestra for async work, off the voice path | Accepted |
| [0010](0010-memory-is-not-system-of-record.md) | Memory is context, never a system of record | Accepted |
| [0011](0011-nextjs-ssr-bff.md) | Next.js SSR as a backend-for-frontend | Accepted |
| [0012](0012-hetzner-eu-cloudflare-tunnel.md) | One Hetzner EU VPS behind Cloudflare Tunnel | Accepted (region to validate) |
| [0013](0013-observability-otel-langsmith.md) | OpenTelemetry plus LangSmith | Accepted |
| [0014](0014-ports-only-where-needed.md) | Ports and adapters only where a second adapter exists | Accepted |

Template: [`template.md`](template.md).
