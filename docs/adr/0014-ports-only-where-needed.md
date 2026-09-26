# 0014. Ports and adapters only where a second adapter exists

- **Status:** Accepted
- **Date:** 2026-09-26

## Context
Hexagonal architecture says domain code should depend on ports, not concrete
technology. Applied everywhere, it produces wrappers around wrappers.

## Decision
Define our own port only when there is a real second adapter or a real need to fake it
in tests: `DecisionPort` (Laya / LLM), `MemoryPort` (Synap / Postgres), `BankingPort`
(HTTP / in-memory fake), `FaultInjector` (off / configured faults). Wiring happens in one
composition root per service. Everything else uses the library directly.

## Consequences
Real seams where they matter, no ceremony where they don't.

## Principle
**SOLID applied with KISS**: an abstraction must pay for itself.
