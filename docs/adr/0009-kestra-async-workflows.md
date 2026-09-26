# 0009. Kestra for async workflows, off the voice path

- **Status:** Accepted
- **Date:** 2026-09-26

## Context
Blocking a card should feel instant to the customer, but a real bank then has to order
a replacement, notify the customer, update the case and audit it. These steps are slow,
must retry, and must not be lost. The same holds for post-call analytics, human
handoff cases, nightly evals and backups.

## Decision
The voice turn does the minimum synchronously and emits an event. **Kestra** (self-hosted,
`workflows` profile) runs durable flows triggered by webhook or schedule:
`lost_card_followup`, `post_call_processing`, `human_handoff`, `nightly_evals`,
`db_backup`. Webhooks are signed with a shared secret.

## Alternatives considered
- **Background tasks in the API process.** Lost on restart, no retries, no visibility.
- **Celery / queue workers.** Fine, but we'd build scheduling, UI and retries ourselves.

## Consequences
Clear sync/async split, retries and a UI for free. Kestra is JVM-based (~1.5 GB RAM),
so it gets its own profile and a heap cap.

## Principle
Keep the **hot path minimal**; make slow work **durable and observable**.
