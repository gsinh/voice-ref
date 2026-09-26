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
apps/gateway/        composition root: mounts modules, health, migrations, launcher, CLI
libs/
  signed_tokens/     shared kernel: session + confirmation JWTs (issuer and verifier agree)
modules/
  orchestrator/      LangGraph conversation graph             → /api
  banking_api/       mock bank system of record (schema bank) → /bank
  mcp_server/        MCP tools, the LLM's only way to data    → /mcp
```

Sidecars, on localhost inside the same container (started by `gateway start`):
- `laya-serve` on :8100: System 1 decisions (installed in its own virtualenv, /opt/laya)
- agentgateway on :15000 (Phase 3)

Rules, enforced by `uv run lint-imports`:
- modules never import each other; they talk over HTTP/MCP even in-process
- modules never import the gateway; only the gateway knows every module
- shared libs import nothing of ours

Each module that stores data owns one Postgres schema, logs in as its own role, and ships
its own migrations.

## Commands

```bash
uv sync --all-packages                 # install
uv run python -m gateway serve         # HTTP server alone on :7860
uv run python -m gateway start         # launcher: server + SIDECARS (container default)
uv run python -m gateway migrate seed  # apply migrations, reset demo data
uv run ruff check . && uv run mypy apps libs modules && uv run lint-imports
```

## Tests

Unit tests run anywhere. Integration and end-to-end tests need a bootstrapped and
migrated Postgres, and are skipped otherwise:

```bash
export TEST_DATABASE_URL=postgresql://postgres:<pw>@localhost:5432/voiceref
export TEST_BANK_DATABASE_URL=postgresql://bank_api:<pw>@localhost:5432/voiceref
export TEST_ORCHESTRATOR_DATABASE_URL=postgresql://orchestrator:<pw>@localhost:5432/voiceref
uv run pytest
```

`apps/gateway/tests/test_chat_e2e.py` runs the whole text path over real HTTP with only
the LLM replaced by a scripted OpenAI-compatible endpoint.
