# 0016. Free-tier deployment: HF Spaces, Neon, Cloudflare Workers

- **Status:** Accepted. Supersedes [0012](0012-hetzner-eu-cloudflare-tunnel.md).
- **Date:** 2026-09-26

## Context
The demo must be reachable without the owner's laptop, at no cost. Nothing free offers a
single server large enough for the whole stack, so it must be spread across free tiers.

## Decision
| Component | Host |
|---|---|
| Web (Next.js SSR BFF) | Cloudflare Workers via OpenNext |
| Backend (modular monolith) + voice worker | Hugging Face Space (Docker), **private** |
| Kestra (open source) | A second Hugging Face Space |
| Postgres | Neon, same US region as the Spaces |
| Media / LLM / STT | LiveKit Cloud / Groq |
| Keep-alive | Cloudflare Workers cron trigger pinging both Spaces |

- The `backend/` folder is exactly what the Space builds: its `Dockerfile` runs as uid 1000
  on port 7860, and its `README.md` carries the Space metadata.
- The BFF holds a Hugging Face read token (Worker secret) to call the private Space. The
  browser never sees it. Kestra and the backend sign webhooks to each other with HMAC.
- Deploys: GitHub Actions pushes `backend/` to the Space's git repo and deploys `web/`
  with `wrangler`. Migrations run as a one-off job before the Space update.

## Alternatives considered
- **One small VPS (ADR-0012).** Simplest and never sleeps, but costs ~€5–8/month.
- **Oracle Always Free.** Declined by the owner.
- **Serverless containers (Cloud Run, Render free).** Scale to zero and reload models on
  every cold start; the voice worker needs a long-running process.

## Consequences
- $0, with the backend placed next to Groq (US) and audio handled at LiveKit's edge.
- **Spaces sleep** after ~48 h without traffic and take about a minute to wake; the
  keep-alive cron reduces but does not remove this. Scheduled Kestra flows are best-effort.
- 2 vCPU per Space: Laya and Kokoro latency must be measured, not assumed.
- Neon scales to zero, so the first query after idle is slower.
- Workers' free-plan CPU and bundle limits may force the fallback to Vercel Hobby.
- More moving parts than one VPS: five free dashboards instead of one.

## Principle
**Make trade-offs explicit.** $0 is a legitimate requirement; the ADR records exactly
what it costs in reliability, and the upgrade path.
