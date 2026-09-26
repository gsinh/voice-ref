# 0002. Monorepo, Docker Compose profiles, 12-factor configuration

- **Status:** Accepted
- **Date:** 2026-09-26

## Context
Six services (orchestrator, MCP server, banking API, decision service, voice worker,
web) plus Postgres and Kestra must run the same way on an M4 Mac and on a production VPS,
by one person.

## Decision
- One repository. Python services share a **uv workspace** and a small `libs/common`
  package (settings base, JSON logging, health endpoints).
- One `compose.yaml`. **Profiles** select what runs: `core` now; `voice`, `workflows`,
  `local-ai` are added in the phase that needs them.
- **12-factor** configuration: every setting comes from the environment through
  `pydantic-settings`; `.env.example` documents all of them. Services are stateless,
  log JSON to stdout, and shut down cleanly on SIGTERM.

## Alternatives considered
- **Repo per service.** Realistic for large teams, pure overhead for one person.
- **Kubernetes locally.** Teaches Kubernetes, not the architecture. Compose maps cleanly
  to Kubernetes later if needed.

## Consequences
Dev/prod parity: production runs the same images and the same compose file with a
different `.env`. A shared lib creates coupling, so it stays deliberately tiny:
infrastructure helpers only, no domain code.

## Principle
**12-factor** (config, backing services, processes, disposability, dev/prod parity,
logs) and **KISS**.
