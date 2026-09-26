# 0006. MCP as the tool boundary; guardrails enforced outside the LLM

- **Status:** Accepted
- **Date:** 2026-09-26

## Context
The agent must read balances and transactions and, rarely, take a sensitive action
(block a card). A prompt can be manipulated. The model must not be the last line of
defence.

## Decision
- The LLM reaches enterprise systems only through an **MCP server** exposing six tools:
  `get_customer`, `get_account_balance`, `get_recent_transactions`,
  `get_transaction_details`, `get_card_status`, `block_card`.
- The MCP server calls the banking API. It never holds database credentials for the bank
  schema itself.
- **Identity never comes from the model.** Every MCP call carries a short-lived
  **session token** (a JWT the orchestrator mints per turn after the one-time code);
  tools read the customer from it, and **no tool takes a customer id argument**. A
  prompt-injected "show me CUST-1002's balance" has nothing to act on.
- `block_card` also needs a **confirmation token**: a JWT bound to this customer, this
  action and this card, issued by deterministic graph code only after an explicit
  confirmation. Its unique id is the bank's **idempotency key**, so replaying it can
  never block twice.
- **The LLM is never given `block_card`.** It only gets the three read-only account
  tools; the card flow calls `block_card` itself, and replies with a fixed template.
- Both token types live in one shared kernel (`libs/signed_tokens`), so issuer and
  verifier cannot drift apart. Every call is recorded in the turn trace (Phase 3 adds a
  persistent audit log).

## Alternatives considered
- **Give the LLM SQL or direct API access.** Unbounded blast radius.
- **Rely on the system prompt.** Prompts are guidance, not enforcement.

## Consequences
Even a fully prompt-injected model cannot block a card: it cannot produce a valid token.
Tools are reusable by any MCP client. A little more plumbing per tool.

## Principle
**Least privilege** and **defence in depth**: enforce policy in deterministic code at
the boundary.
