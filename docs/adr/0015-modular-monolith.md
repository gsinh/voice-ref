# 0015. Modular monolith: independent modules, one process

- **Status:** Accepted
- **Date:** 2026-09-26

## Context
The free-tier host (a Hugging Face Space, ADR-0016) runs one container with one exposed
port. We still want clear boundaries between the orchestrator, the MCP tools, the bank
system of record and the decision model, because those boundaries are the architecture.

## Decision
- **Modules** (`backend/modules/*`) are separate packages, each with its own settings,
  router, schema and migrations.
- **The gateway** (`backend/apps/gateway`) is the composition root. It is the only code
  that knows every module; it mounts them under `/api`, `/bank` and `/mcp`, runs the
  `migrate` and `seed` admin commands, and launches sidecars.
- **Shared kernels** (`backend/libs/*`) hold the few contracts two modules must agree on
  exactly, e.g. `signed_tokens` (issued by the orchestrator, verified by MCP). They
  depend on nothing of ours.
- Boundaries are **enforced**, not hoped for: `lint-imports` fails CI if a module
  imports another module or the gateway, or a shared lib imports anything of ours.
- Modules talk over their real protocols even in-process: the orchestrator uses MCP,
  MCP calls the bank over HTTP (loopback, ~1 ms).
- Heavy or foreign runtimes run as **localhost sidecars** in the same container, not as
  modules: Laya (PyTorch) now, agentgateway (Rust) in Phase 3.

Phase 1 removed the planned `decision` module: Laya ships its own HTTP server, so a
module wrapping it would only have been a pass-through. The orchestrator's
`DecisionPort` calls the sidecar directly. (KISS: a module has to earn its place.)

MCP is pinned to SDK 1.x for now: `langchain-mcp-adapters` does not support 2.x yet.
The wire protocol is the same, so upgrading is a version bump.
- Local and production use the **same layout**, so there is one topology to reason about.

## Alternatives considered
- **Microservices (one container each).** What the first skeleton did. Realistic, but a
  free Space cannot host it, and it multiplies deploys and cold starts.
- **One undivided package.** Simplest, but boundaries erode silently.

## Consequences
One deploy, one image, no network between modules except loopback. Splitting a module
out later is a deployment change: point its URL setting somewhere else. Shared process
means shared failure: a crash in one module restarts all of them.

## Principle
**Separate logical architecture from physical deployment.** Boundaries belong in the
code; how many processes run them is a deployment decision.
