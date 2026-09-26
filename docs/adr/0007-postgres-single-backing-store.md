# 0007. Postgres as the single backing store, schema per service

- **Status:** Accepted
- **Date:** 2026-09-26

## Context
We need a mock bank database, LangGraph checkpoints, per-turn metrics, an audit log, a
local memory store and a database for Kestra.

## Decision
One **Postgres** instance. Each service gets its **own schema and its own role**
(`bank`, `orchestrator`, …) and can only touch what it owns. Kestra gets its own
database. Schemas, roles and seed data live in `infra/postgres/init/`.

## Alternatives considered
- **SQLite files.** Simple for one process, awkward when several containers share them.
- **A database per service.** Correct at scale, too heavy for one 8 GB VPS.

## Consequences
One thing to back up and monitor. Service boundaries are still enforced by grants, so
splitting into separate databases later is a configuration change.

## Principle
**KISS** for operations, **least privilege** for boundaries.
