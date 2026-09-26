# 0012. One Hetzner EU VPS behind Cloudflare Tunnel

- **Status:** Superseded by [0016](0016-free-tier-deployment.md): the owner chose a $0 deployment.
  Kept as the documented upgrade path if always-on without sleeping becomes a requirement.
- **Date:** 2026-09-26

## Context
The demo must be always on and must not depend on a laptop. Budget: minimal. Users
are in India; model APIs (Groq) are mainly in the US and Europe.

## Decision
- One **Hetzner CAX21** (4 ARM vCPU, 8 GB) in **Helsinki or Falkenstein**, running the
  same compose file with images pulled from GHCR.
- **Cloudflare Tunnel** for ingress (no inbound ports open), **Cloudflare Access** to gate
  the live demo.
- LiveKit Cloud carries audio from an edge near the user.

## Why EU and not India
Each turn makes several sequential Groq calls (STT, one or two LLM calls) but only one
audio round trip, and LiveKit Cloud's edge is already close to the user. Placing the
worker near the model APIs wins. An Indian VPS would add India↔US latency to every
model call and costs several times more.

## Alternatives considered
- **Free platforms (Hugging Face Spaces, Neon, Workers).** $0 but services sleep,
  cold starts hurt voice latency, and Kestra doesn't fit.
- **Oracle Always Free.** Declined.
- **Cloud credits.** Temporary.

## Consequences
About €5–8/month for a truly always-on system with dev/prod parity. ARM64 matches the M4
Mac. For a real Indian bank, RBI data localisation would move the deployment and the
models to an Indian region: a configuration change, not a code change.

## Principle
**Measure, then place**: put compute next to the calls it makes most often.
