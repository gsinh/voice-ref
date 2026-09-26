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
- Every tool has a **risk level**. Read tools need an authenticated session.
  `block_card` needs a **single-use confirmation token** that only the orchestrator's
  policy node can issue, after an explicit confirmation. It also takes an
  **idempotency key**, and every call is written to an **audit log**.

## Alternatives considered
- **Give the LLM SQL or direct API access.** Unbounded blast radius.
- **Rely on the system prompt.** Prompts are guidance, not enforcement.

## Consequences
Even a fully prompt-injected model cannot block a card: it cannot produce a valid token.
Tools are reusable by any MCP client. A little more plumbing per tool.

## Principle
**Least privilege** and **defence in depth**: enforce policy in deterministic code at
the boundary.
