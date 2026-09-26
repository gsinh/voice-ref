# 0002. Monorepo, Docker Compose profiles, 12-factor configuration

- **Status:** Accepted
- **Date:** 2026-09-26

## Context
A backend (orchestrator, MCP server, banking API, decision service, voice worker), a web
app, Postgres and Kestra must run the same way on an M4 Mac and in production, built and
operated by one person.

## Decision
- One repository. The backend is a **uv workspace** (`backend/`) whose modules deploy as
  one process (ADR-0015); the web app lives in `web/`.
- One `compose.yaml` for local development. Core services always start; optional ones
  (`workflows`, `voice`) join behind profiles in the phase that needs them.
- **12-factor** configuration: every setting comes from the environment through
  `pydantic-settings`; `.env.example` documents all of them. Services are stateless,
  log JSON to stdout, and shut down cleanly on SIGTERM.

## Alternatives considered
- **Repo per service.** Realistic for large teams, pure overhead for one person.
- **Kubernetes locally.** Teaches Kubernetes, not the architecture. Compose maps cleanly
  to Kubernetes later if needed.

## Consequences
Dev/prod parity: the backend image that runs locally is the image the HF Space builds;
only environment variables differ (ADR-0016).

## Principle
**12-factor** (config, backing services, processes, disposability, dev/prod parity,
logs) and **KISS**.
