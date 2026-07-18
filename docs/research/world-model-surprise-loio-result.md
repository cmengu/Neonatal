# World-Model Surprise — LOIO Spike Result (issue #6)

**What this is.** The empirical result of the issue #6 spike: build a per-infant
forecaster, compute a per-window **Surprise** signal, and test — leave-one-infant-out —
whether Surprise rises in the lead window before the annotated bradycardia events. This is
the "concrete number and plot" the ticket asks for, and the wiring decision that follows.

**Companion research gate:** [`world-model-surprise-validation.md`](world-model-surprise-validation.md)
(gate #12, green) — the evidence case for *why* Surprise belongs in Tier 2 and under what
guardrails. This document is the *engineering result* of acting on it.

**Date:** 2026-07-14

---

## Headline

> **⚠️ SUPERSEDED — the 0.515 headline below was measured on the confounded data. Issue #18
> is now resolved and the harness re-run on corrected data gives a different verdict. See the
> UPDATE block immediately below; the original text is retained for the record.**

### UPDATE (2026-07-15, issue #18 resolved) — valid re-run on corrected data

The two data-integrity defects flagged in §"The confound" (bradycardia scrubbed by the
global-median RR filter; event labels misaligned by a hardcoded 500 Hz + missing trim offset)
are fixed: RR is rebuilt from the `.qrsc` reference peaks with a physiological band that keeps
bradycardia, and `.atr` onsets are aligned to windows via carried raw-sample beat positions
(per-infant fs, no cumsum drift). At the labelled event windows `mean_rr` is now clearly
elevated over baseline (e.g. infant1 485 ms vs 389 ms; infant2 565 ms vs 462 ms) and each
infant's labelled-window count equals its `.atr` onset count — the signal the old pipeline
destroyed is present again.

**Valid pooled LOIO AUC (lead vs baseline) = 0.635.** Per-infant AUCs span **0.567–0.637**
(mean 0.614, median 0.617) — **every** infant scores above chance under leave-one-infant-out,
on 621 events / 3,105 lead vs 115,157 baseline windows. 322/621 events show a pre-onset
Surprise rise (median lead 1 window ≈ 10 s). Features and protocol are unchanged from the
original run (`mean_rr_dev, sdnn_dev, rmssd_dev, rr_ms_max_dev, rr_ms_75%_dev`; lead=5,
guard=30) — the *only* variable changed is the data-integrity fix.

**Revised reading:** Surprise carries **real but modest** lead-time signal once the target is
intact. The original "at-chance ⇒ not wired" verdict was an artifact of the confound, not a
property of Surprise. Whether 0.635 clears the gate's wiring bar (and under what CUSUM-adjunct
guardrails) is a decision for the #6/gate owner — this document only re-establishes the
*valid number*. Re-run artifacts: `data/processed/world_model_loio_results.json`,
`docs/research/assets/world-model-surprise-loio.png` (branch `feat/onnx-cutover`).

*Caveat:* the re-run reproduces the original **10-feature (pre-#13) schema** that this result
and `FORECAST_FEATURES` both use; issue #13's `sampen`/`sample_asymmetry` are excluded (they
are unused by the harness and never ran on the cohort — `_sampen` over the 4096-beat window
costs ~6.9 s/window ≈ 30 h/infant, a separate performance defect).

---

<sub>Original headline (confounded data — superseded):</sub>

**Pooled LOIO AUC (lead-window vs baseline) = 0.515** — indistinguishable from chance
(0.500). Per-infant AUCs span 0.47–0.53; mean 0.50.

**Decision (per the gate's own decoupling rule): Surprise is NOT wired into Tier 2.
Tier 2 stays CUSUM-only.** The research gate is explicit — *"CUSUM ships regardless…
Surprise is a gated adjunct… wired in only if it leads events under LOIO; else record the
finding and Tier 2 stays CUSUM-only."* Surprise did not lead events, so it is recorded here
and not wired. CUSUM (the deterministic Tier 2 backbone from #4) is unaffected.

**But this AUC is _inconclusive_, not a clean refutation of Surprise.** The spike uncovered
two upstream data-integrity defects that remove and mislabel the bradycardia target *before*
any tier sees it. On the data as processed there is essentially nothing to anticipate, so a
chance AUC is the expected result *regardless of whether Surprise works*. See §"The confound".

---

## What was built (landed, tested, ready to re-run)

- **`src/world_model/forecaster.py`** — `PerInfantForecaster`. A per-infant **VAR(1)** fit by
  OLS on the infant's own personalised-deviation stream (no shared population weights — the
  gate's hard requirement, and the ADR-0002 fix for label scarcity). Surprise is the
  closed-form Gaussian **NLL of the one-step-ahead innovation**,
  `½(eᵀΣ⁻¹e + log|2πΣ|)` — the auditable Mahalanobis form the gate mandates ("start linear",
  Kalman/VAR before any neural model). Two-sided by construction (gate §4.3).
- **`src/world_model/loio.py`** — the LOIO evaluation core: window-role labelling
  (lead / baseline / excluded-guard), a dependency-free Mann–Whitney AUC, per-event lead-time,
  peri-event trace, and per-infant → pooled summarisation. Standardises each infant's Surprise
  to its *own* baseline so no infant informs another's score.
- **`scripts/run_world_model_loio.py`** — runs the spike on the 10-infant cohort, prints the
  table + headline, and writes the plot + `data/processed/world_model_loio_results.json`.
- **Tests:** `tests/test_world_model_forecaster.py` (6) + `tests/test_world_model_loio.py` (8).
  The harness is validated on synthetic streams with *planted* lead-window rises — it recovers
  them at **AUC > 0.9**. So a ~0.5 on real data is a statement about the data, not the harness.

Feature vector: the `_dev` (personalised z-score) form of the five physiologically-meaningful
HRV features #8 kept as floor triggers (`mean_rr, sdnn, rmssd, rr_ms_max, rr_ms_75%`).

**Plot:** [`assets/world-model-surprise-loio.png`](assets/world-model-surprise-loio.png) —
peri-event mean Surprise (flat through the lead window — no anticipatory rise) + per-infant AUC.

---

## The confound — why the number is uninterpretable on the current data

Diagnostics run during the spike (all reproducible from the raw PICS records):

### 1. The bradycardia target is scrubbed out of the feature stream (upstream, `run_nb02_real.py`)

RR "cleaning" uses a **global-median ectopic band**:

```python
rolling_median = np.median(rr_ms)          # NB: global median of the whole record, not rolling
mask = np.abs(rr_ms - rolling_median) / rolling_median < ectopic_threshold
rr_clean = rr_ms[mask]
```

A bradycardia is exactly a large, sustained jump above the local rate (RR leaps from ~400 ms
to >600 ms — a ~50% deviation), so it is **deleted as an ectopic beat**. Consequence, measured:

- In every infant's `rr_clean`, **the maximum RR interval is 436–558 ms** (HR 108–138 bpm).
  **No interval anywhere exceeds ~560 ms** — i.e. bradycardia (RR > 600 ms / HR < 100, the PICS
  criterion) is **entirely absent** from the processed stream.
- In the **raw** `.qrsc` reference-QRS annotations the events are present: infant1 has 0.25% of
  beats at RR > 600 ms and 77 `.atr` `[` bradycardia marks — the target exists; the pipeline
  removes it.

### 2. The event labels are misaligned to the windows (upstream, `run_nb04.py`)

`align_labels_to_windows` hardcodes `FS_ECG = 500`, but **infant1 and infant5 are 250 Hz**
(confirmed from the `.hea` headers), so their beat-time reconstruction is off by 2×. It also
never subtracts the **`trim_offsets`** (infant4 = 14 000, infant5 = 364 000, infant7 = 15 000
samples) that were stripped from the front of the signal before RR extraction — so the `.atr`
sample indices (raw space) are compared against cumulative beat positions (trimmed space).

Measured consequence: at `label == 1` windows the HRV shows **no bradycardia signature** —
`mean_rr ≈ 388 ms` (identical to baseline), **0%** of "event" windows have `mean_rr > 550 ms`.
The labelled windows are not the event windows.

### Why this matters beyond #6

Every event-aligned evaluation on this processed data inherits both defects. In particular,
**ADR-0002's finding that the supervised ONNX classifier "scored at-random" (AUC-PR ≈ base
rate) was measured against these same scrubbed features and misaligned labels** — its
conclusion should be revisited once the data is corrected. (This does not change ADR-0002's
*architectural* call — per-infant self-supervision is still the right response to label
scarcity — but the specific "at-random" number is not trustworthy evidence.)

---

## Acceptance criteria — disposition

| AC | Status |
|----|--------|
| Per-infant forecaster produces a Surprise signal from the feature stream | ✅ `forecaster.py`, tested |
| Surprise evaluated LOIO, aligned to bradycardia events → number + plot | ✅ number (0.515) + plot produced; **inconclusive** — target scrubbed/mislabeled upstream |
| Forecaster fit per infant, no shared population weights | ✅ by construction; tested |
| If Surprise leads events → wire into Tier 2; else record finding, Tier 2 stays CUSUM-only | ✅ **did not lead → NOT wired; Tier 2 = CUSUM-only** (this document is the recorded finding) |

**Net:** the engineering deliverable is complete and the safe default holds (Tier 2 ships on
CUSUM alone, exactly as the gate requires when Surprise fails its gate). The Surprise *viability
verdict* is **deferred, not decided** — the harness is ready to re-run and give a real answer
the moment the RR-cleaning + label-alignment defects are fixed at the source.

---

## Follow-up

A blocking data-integrity ticket is filed for the two upstream defects (RR-cleaning removes
bradycardia; NB04 label mis-alignment). Fixing it — rebuild the RR stream from the raw `.qrsc`
reference annotations with a physiological band that preserves bradycardia, use per-infant `fs`,
and apply `trim_offsets` — unblocks a *valid* re-run of this exact harness and a re-measurement
of ADR-0002. That work sits in the real-data / empirical-validation workstream (the map's
literature-grounding destination deliberately does **not** turn on our-data empirical checks),
so it is tracked as its own effort rather than gating the cascade design.
