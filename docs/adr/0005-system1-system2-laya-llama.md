# 0005. System 1 / System 2: Laya decides, Llama talks

- **Status:** Accepted. Revised in Phase 1 with what we learned about Laya.
- **Date:** 2026-09-26

## Context
Most per-turn decisions are small and bounded: which intent? did the customer confirm?
which card? Using a generative LLM for these adds hundreds of milliseconds and cost to
every turn, and returns free text we must then parse and trust.

## Decision
- **System 1: Laya** (`laya` on PyPI, Apache-2.0, Convai). It is a non-autoregressive
  decision model that scores a fixed set of options and returns a typed answer with a
  calibrated confidence.
- **System 2: Llama** (Groq or Ollama) for reasoning, tool use and natural replies.
- The orchestrator reaches System 1 through `DecisionPort`, over one wire format,
  `POST /v1/systemone`. Two services speak it:
  - **Laya's own server (`laya-serve`)** as a localhost sidecar in the backend container,
    installed in its own virtualenv (`/opt/laya`) so PyTorch never enters the app's
    dependency tree. On a Mac it can run natively on the Apple GPU instead.
  - **Hosted Jev** (TypeSafe), whose API Laya's server was built to match. Switching is
    a change of `SYSTEM1_URL` and `SYSTEM1_API_KEY`.
- A **confidence-gated cascade**: act on System 1 above a threshold (0.85 for intent,
  0.9 for confirmation); otherwise ask the LLM as a constrained choice; if that fails
  too, return "unsure" and let the graph take the safe path (clarify, or don't act).

## What we learned in Phase 1
From Laya's own documentation ("Honest limits"), which shaped the design:
- **Latency is 33 ms on a T4 GPU, but 193–464 ms on CPU.** Our free Space is CPU-only, so
  the speed win over a hosted LLM is smaller than the headline suggests. We must measure.
- **Zero-shot accuracy is modest.** Laya describes itself as "a fast base to specialise,
  not a zero-shot decision engine". Fine-tuning on our own examples is the Phase 4 lever.
- **Boolean-looking labels mislead it.** So the confirmation question uses semantic labels
  (`confirm` / `decline`), not `yes` / `no`, and not Laya's `noul` type.
- **An LLM fallback always picks something.** It has no calibrated "unsure", so the card
  question carries an explicit `unspecified` option, and the graph only acts on a card
  the customer actually named.

## Alternatives considered
- **LLM for everything.** Simplest, slowest, most expensive, least predictable.
- **Laya's ONNX export in-process.** Still pulls PyTorch in as a dependency; a sidecar
  keeps the app light and the model swappable.
- **Train our own classifier.** More work, worse multilingual coverage, no calibration.

## Consequences
- Bounded, typed decisions with an explicit confidence on the hot path; the trace shows
  who decided (Laya or LLM) and how sure it was.
- The cascade makes System 1 optional: if the sidecar is down, decisions fall back to
  the LLM and the status page says so.
- Phase 4 compares Laya, Jev and Llama on the same labelled dataset (accuracy, p50/p95
  latency, cost), and decides the thresholds from data.

## Principle
Use the **smallest tool that does the job**, make uncertainty explicit, and let the
system act on it.
