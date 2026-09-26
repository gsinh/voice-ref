---
# Hugging Face Space metadata: this directory is deployed as a Docker Space as-is.
title: voice-ref backend
emoji: 🏦
colorFrom: indigo
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# voice-ref backend

The backend is a **modular monolith** (ADR-0015): independent modules deployed as one
process.

```
apps/gateway/        composition root: mounts modules, health, migrate/seed commands
modules/
  orchestrator/      LangGraph conversation graph             → /api
  banking_api/       mock bank system of record (schema bank) → /bank
  mcp_server/        MCP tools, the LLM's only way to data    → /mcp
  decision/          Laya System-1 decisions                  → /decide
```

Rules, enforced by `uv run lint-imports`:
- modules never import each other; they talk over HTTP/MCP even in-process
- modules never import the gateway; only the gateway knows every module

Each module that stores data owns one Postgres schema, logs in as its own role, and ships
its own migrations.

## Commands

```bash
uv sync --all-packages                 # install
uv run python -m gateway               # serve on :7860
uv run python -m gateway migrate seed  # apply migrations, reset demo data
uv run pytest                          # tests (set TEST_DATABASE_URL for integration tests)
uv run ruff check . && uv run mypy apps modules && uv run lint-imports
```
