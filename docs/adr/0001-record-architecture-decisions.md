# 0001. Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-09-26

## Context
This project exists to demonstrate architectural judgement, not only working code. A
reviewer (or interviewer) should be able to see *why* each choice was made and what it
cost.

## Decision
Record every significant decision as a short ADR in `docs/adr/`, using
[`template.md`](template.md). Superseded ADRs stay in place and link to their replacement.

## Alternatives considered
- **A single long design doc.** Harder to review, and it hides when and why decisions
  changed.
- **Comments in code.** Good for local reasoning, bad for cross-cutting decisions.

## Consequences
Small writing overhead per decision. In exchange, the ADRs double as interview talking
points.

## Principle
Make the reasoning as reviewable as the code.
