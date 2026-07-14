# ADR-0001 — Verdict composition: the safety floor and asymmetric de-escalation

**Status:** Accepted (2026-07-12)

## Context

The Verdict Cascade merges three Assessments (Tier 1 Deviation, Tier 2 Temporal, Tier 3
RAG) into one Verdict. Two forces pull against each other:

- **Safety** — a critical concern level must never be talked down, or we lose the FNR=0
  guarantee that is the system's core clinical promise.
- **Specificity** — the product's differentiator is *reducing* false alarms (alarm
  fatigue). Something must be allowed to quiet a noisy alert, or the differentiator dies.

A single "escalate-only" or "free merge" rule cannot satisfy both. And the three tiers do
not warrant equal trust: Tier 1 is deterministic, Tier 2 is a calibrated model, Tier 3 is
an LLM.

## Decision

Composition is governed by a **Safety Floor** plus **asymmetric, per-tier de-escalation
authority**:

1. **Safety Floor** — Tier 1's deterministic hard rules compute a minimum concern level.
   No tier may produce a Verdict below it. This is the FNR=0 guarantee, in one place.
2. **Tier 2 (world model)** — *may de-escalate* down to (never below) the floor, and may
   escalate. This is where false-alarm reduction lives, because it is calibrated and
   auditable.
3. **Tier 3 (RAG / LLM)** — *escalate-only*. It may raise concern if guideline context
   reveals something the models missed, but may never lower it. An LLM is never trusted to
   talk clinical concern down.

Final verdict = `max( merge(Tier2, Tier3 escalations), Safety Floor )`.

## Consequences

- The FNR=0 claim becomes a property of one module (the floor), testable in isolation,
  rather than an emergent accident across five scattered checks.
- False-alarm reduction is possible but *only* through the calibrated Tier 2 — a defensible
  story for a regulator: "the language model can raise a flag but never suppress one."
- Tier 3 remains a full Assessor (it emits a level, satisfying the uniform currency) yet
  is constrained to one direction — the constraint lives in the cascade, not the tier.

## Alternatives considered

- **Escalate-only for all tiers** — simplest safety story, but kills false-alarm reduction.
- **Free confidence-weighted merge + clamp** — flexible but unauditable; a poor fit for a
  medical device where every verdict must be explainable.
- **Let RAG de-escalate too** — maximally capable, but admits the automation-bias failure
  mode the product explicitly manages.
