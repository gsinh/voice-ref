# 0017. agentgateway for LLM and MCP traffic, as an in-container sidecar

- **Status:** Accepted (introduced in Phase 3)
- **Date:** 2026-09-26

## Context
Every LLM call and tool call needs the same cross-cutting controls: authentication and
authorisation, rate limits and budgets, provider failover (free tiers rate-limit), and
telemetry. Implemented inside the agent, these controls get repeated, mixed with business
logic, and bypassed by any new caller (e.g. the voice worker).

## Decision
- Route all agent → LLM and agent → MCP traffic through **agentgateway** (open source,
  Apache-2.0, Linux Foundation): one OpenAI-compatible LLM endpoint with failover
  (Groq 70B → Groq 8B → Cloudflare Workers AI), per-tool authorisation and rate limits on
  MCP, OTel spans for every call.
- It runs as a **sidecar process inside the backend container**, bound to
  `127.0.0.1:15000`. The same image runs locally and on the Hugging Face Space; a small
  launcher starts the gateway, agentgateway and (Phase 2) the voice worker, and exits if
  any one dies so the platform restarts the container cleanly.
- The orchestrator only knows two URLs from the environment (`LLM_BASE_URL`,
  `MCP_URL`). Phase 1 points them straight at the providers; Phase 3 points them at
  agentgateway. Adding the gateway is a configuration change.
- Guardrails become three independent layers: the gateway (which caller may use which
  tool, how often), the MCP server (single-use confirmation token), and the bank module
  (its own database role).

## Alternatives considered
- **A separate Space for the gateway.** Every hot-path call would cross the internet
  (tens of ms), and it is one more service to keep awake and authenticate.
- **Cloudflare Workers.** agentgateway is a native binary; Workers run JS/WASM only.
- **Controls in the agent code.** Repeated per caller, mixed with business logic.

## Consequences
Centralised security, cost control and failover; the "AI gateway" pattern. One more
process and one more config file. The processes share fate: if agentgateway dies, the
container restarts, which is correct because the backend is useless without it.

## Principle
**Separation of concerns** at the infrastructure level: cross-cutting policy belongs
in a gateway, not in every agent.
