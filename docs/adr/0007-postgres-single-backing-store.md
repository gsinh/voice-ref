# 0007. Postgres as the single backing store, schema per service

- **Status:** Accepted
- **Date:** 2026-09-26

## Context
We need a mock bank database, LangGraph checkpoints, per-turn metrics, an audit log, a
local memory store and a database for Kestra.

## Decision
One **Postgres**: a container locally, **Neon** (free tier) in production. Each module
gets its **own schema and its own login role** (`bank`, `orchestrator`, …) and can only
touch what it owns. Kestra gets its own database.

- `python -m gateway bootstrap` is the only admin step: it creates (or rotates) each
  module's login and schema, sending Postgres SCRAM verifiers, never passwords
  (ADR-0019).
- Each module ships its own forward-only SQL migrations and runs them **as its own
  role** (`python -m gateway migrate`), so it can never alter another module's schema.
- Demo data is a separate, idempotent `seed` command that can be re-run at any time.

## Alternatives considered
- **SQLite files.** Simple for one process, but a Space's disk is not persistent.
- **A database per module.** Correct at scale, more than the free tier needs.
- **Alembic.** Solid, but assumes SQLAlchemy models; plain SQL files plus a ~60-line
  runner are enough and easier to read.

## Consequences
One thing to back up and monitor. Service boundaries are still enforced by grants, so
splitting into separate databases later is a configuration change.

## Principle
**KISS** for operations, **least privilege** for boundaries.
