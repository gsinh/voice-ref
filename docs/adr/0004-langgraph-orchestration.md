# 0004. LangGraph for orchestration, one graph for text and voice

- **Status:** Accepted
- **Date:** 2026-09-26

## Context
The orchestrator must route intents, hold conversation and auth state, pause for human
confirmation, survive process restarts, and hand off to a human with context.

## Decision
Use **LangGraph**:
- A supervisor graph: `auth_gate → memory_recall → decide → {account, card, general}
  agent → respond`, with `fallback` reachable from every node.
- `interrupt()` for high-risk confirmation (human-in-the-loop).
- The **Postgres checkpointer** for state, keyed by conversation ID.
- The graph is a plain Python package. FastAPI exposes it for text (`/chat`). The voice
  worker calls the same graph. Neither transport leaks into the graph.

## Alternatives considered
- **Hand-written state machine.** Simpler to start, but we would re-implement
  persistence, interrupts and tracing.
- **Fully autonomous multi-agent frameworks.** Harder to reason about and to guard.
  We want explicit edges.

## Consequences
Explicit, inspectable control flow. State survives restarts and handoffs. LangSmith
tracing comes almost for free. We take a dependency on the LangChain ecosystem, which we
limit to the orchestrator service.

## Principle
**SRP / OCP**: each node has one job, and a new agent is a new node, not an edit to
existing ones.
