# 0005. System 1 / System 2: Laya decides, Llama talks

- **Status:** Accepted (latency on CPU to be validated in Phase 1)
- **Date:** 2026-09-26

## Context
Most per-turn decisions are small and bounded: which intent? did the customer confirm?
is this risky? is this frustrated? Using a generative LLM for these adds hundreds of
milliseconds and cost to every turn, and returns free text we must then parse.

## Decision
- **System 1: Laya**, an open-source (Apache-2.0) non-autoregressive decision model.
  It scores a fixed set of options and returns a typed answer (choice, score, yes/no)
  with calibrated confidence. Weights come from Hugging Face and run with ONNX Runtime in
  the `decision` service.
- **System 2: Llama** (Groq or Ollama) for reasoning, tool use and natural replies.
- A **confidence-gated cascade**: act on Laya above a threshold, escalate to Llama below
  it, ask a clarifying question if both are unsure. Thresholds are env config.
- Behind a `DecisionPort` with two adapters: `LayaDecision` and `LLMDecision`, which is
  both the fallback and the evaluation baseline.

## Alternatives considered
- **LLM for everything.** Simplest, slowest, most expensive, least predictable.
- **Train our own classifier.** More work, worse multilingual coverage, and no
  calibrated confidence out of the box.

## Consequences
- Lower latency and cost on the hot path; typed, bounded outputs for guardrails.
- Laya cannot invent an option, but it can pick the wrong one. Evals measure this and the
  cascade covers it.
- One more service and model to operate. CPU latency must be measured, not assumed.

## Principle
Use the **smallest tool that does the job**, and make uncertainty explicit so the
system can act on it.
