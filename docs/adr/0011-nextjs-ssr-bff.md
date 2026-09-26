# 0011. Next.js SSR as a backend-for-frontend

- **Status:** Accepted
- **Date:** 2026-09-26

## Context
The UI needs a voice call page, a chat page, live observability, fault toggles, eval
results and a cost calculator. It must not expose backend topology or secrets.

## Decision
- **Next.js App Router with SSR**, `output: 'standalone'`, running as a container next to
  the backend.
- The Next.js server is a **backend-for-frontend (BFF)**. The browser talks only to
  Next.js (and to LiveKit for audio). Next.js holds the session cookie (httpOnly), mints
  LiveKit tokens, and calls the orchestrator server-to-server.
- Rendering per route: static for architecture and ADRs, periodically revalidated for
  evals and cost, dynamic SSR plus streaming for observability. Mic and WebRTC live in
  client components.
- Code stays portable: standard Next.js APIs only, so it could move to Cloudflare Workers
  (OpenNext) later.

## Consequences
Secrets and internal URLs never reach the browser. Server Components keep the client
bundle small. One more Node process to run.

## Principle
**Least privilege** at the edge, and the right rendering strategy for each page.
