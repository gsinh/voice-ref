# 0010. Memory is context, never a system of record

- **Status:** Accepted
- **Date:** 2026-09-26

## Context
Remembering a customer across calls ("are you calling about yesterday's ₹1,999 charge?")
improves experience. But a bank cannot answer balance questions from a memory store,
and sending PII to a third party raises data-residency questions (RBI).

## Decision
- A `MemoryPort` with two adapters: **Synap** (managed, when `SYNAP_API_KEY` is set) and
  **LangGraph `PostgresStore`** (local).
- Memory holds **context only**. Facts (balances, card status, transactions) always come
  from the banking API via MCP.
- **Redact PII** before writing. Memory is scoped per customer and supports `forget()`.
- **Recall once** after authentication; **write asynchronously** in Kestra after the
  call. Memory adds no per-turn latency.

## Consequences
Personalisation without correctness risk. The data-residency discussion becomes an
explicit, configurable choice.

## Principle
**Single source of truth.** Caches and memories inform; systems of record decide.
