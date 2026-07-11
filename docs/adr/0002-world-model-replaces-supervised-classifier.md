# ADR-0002 — The world model replaces the supervised classifier as Tier 2

**Status:** Accepted (2026-07-12)

## Context

The original architecture derived every verdict from an ONNX gradient-boosted classifier
trained on PICS bradycardia-onset labels. On held-out infants that classifier scores
at-random (AUC-PR ≈ 0.018 vs. a 0.018 base rate; AUC-ROC ≈ 0.48). The cause is structural,
not a bug: 10 infants and ~595 positive windows at a 0.4% base rate cannot support a
supervised model, and any attempt to force one will overfit these particular infants.

A per-infant, self-supervised **world model** (Tier 2 — World Model) sidesteps this: it
trains on the continuous stream (~4M beats), validates against the bradycardia events
*without training on them*, and — because it is fit per infant — has no population weights
that could overfit the cohort.

## Decision

The per-infant world model becomes Tier 2. The supervised ONNX classifier and its
`risk_score` are retired. Tier 1 becomes a new, pure deterministic **Deviation** layer
(the [[Safety Floor]] source), which does not exist in the current code — today the learned
classifier, not deviation math, drives the verdict.

## Consequences

- The dead supervised path (`train_classifier.py`, `export_onnx.py`, the ONNX serving in
  `runner.py`) is removed or repurposed. The ONNX contract test loses its subject.
- The "deterministic <15 ms edge inference" property the pitch leans on now rests on the
  cheap per-infant model (Kalman/VAR) instead of ONNX — survivable, but the claim's
  basis changes and must be restated honestly.
- Validation shifts from window-level AUC-PR to whether **surprise** rises before the
  `.atr` bradycardia events under leave-one-infant-out. This is the honest viability test.
- We commit to the data-bounded ceiling (10 infants, no SpO₂) as the limit, and stop
  trying to rescue a supervised approach the data cannot support.

## Alternatives considered

- **Keep both models in Tier 2** — more signal if the supervised path recovers any, but
  added complexity for a path we expect to stay weak.
- **Retrain the classifier, defer the world model** — lower risk, reuses infrastructure,
  but bets on the supervised approach this ADR rejects.
