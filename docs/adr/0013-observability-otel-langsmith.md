# 0013. Observability: OpenTelemetry plus LangSmith

- **Status:** Accepted
- **Date:** 2026-09-26

## Context
We must show where every millisecond of a turn goes, which tools were called, what
the models decided, token usage, errors and retries.

## Decision
- **OpenTelemetry** spans for every stage (VAD end, STT, decision, LLM, tool, TTS first
  audio), exported over OTLP to an endpoint set by env (no self-hosted collector on the
  free tier).
- **LangSmith** for LLM-level traces and eval experiments (free developer tier,
  optional: with no key, OTel only).
- A compact **per-turn metrics row** in Postgres feeds the in-app `/observability`
  page, so the demo does not depend on an external tool.

## Consequences
Vendor-neutral telemetry with a best-of-breed LLM view on top. Two places to look, which
the observability page unifies by linking trace IDs.

## Principle
**You can't improve what you don't measure**: instrument before optimising.
