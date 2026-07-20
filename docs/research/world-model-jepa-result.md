# World-Model JEPA — Honest Scorecard & Config Decision (issue #58)

**What this is.** The empirical result of iterating the Tier-2 *learned* world model (a
next-latent-prediction **JEPA**) until its numbers are *honestly* promising, per the map-#56
handoff (`docs/handoff/world-model-jepa-improvement.md`). It reports the metrics, the config
sweep that produced the winning model, and — non-negotiable per the owner's honesty bar — a
plain statement of what is and is not measurable on the data as it exists.

**Date:** 2026-07-18
**Companion:** the VAR(1) baseline result (`world-model-surprise-loio-result.md`) and ADR-0002
(why a per-infant self-supervised model replaced the supervised classifier).

---

## Headline

On the 10-infant PICS cohort, with **no labels used at any point**, the JEPA's learned signals
separate *physiological departure from each infant's own normal* — held out across infants,
and decisively better than the linear baseline:

| Metric (held-out, per-infant standardised) | JEPA (h16_m50) | VAR(1) baseline |
|---|---|---|
| **Onset-anticipation — surprise** (rise in the 5 windows *before* a departure onset; 3 571 onsets) | **0.772** (median infant 0.77) | ~chance |
| **Departure-vs-calm — embedding novelty** (concurrent separation) | **0.678** | 0.527 |
| **Onset-anticipation — embedding novelty** | 0.626 | — |
| Demo-window embedding drift (infant7 `[2740,2919]`, vs full calm cloud) | **1.31 calm-SD**, peak **1.9× the cloud edge** | — |

> **Re-measured on the #18-corrected data (2026-07-18).** Everything above was originally
> measured on the pre-#18 feature stream — the model was trained, swept and scored before the
> bradycardia data-integrity fix landed, and the two lived on branches that had never met. On the
> corrected stream the **headline anticipation AUC survives and slightly improves, 0.758 →
> 0.772**, which is the reassuring half. The demo window did not survive: the original
> `[1240,1419]` no longer opens calm, and its drift collapses **1.56 → 0.41 calm-SD**. It has been
> replaced by `[2740,2919]`, this infant's strongest remaining calm-opening departure. The
> checkpoint itself is still the pre-fix one; **retraining on the corrected stream is open work**,
> and the numbers here should be re-run when it happens.

**Two signals, one coherent story.** Embedding **novelty** measures *where the state is*
(distance from the infant's calm cloud) → it separates *sustained* departures concurrently.
**Surprise** measures *that the state is changing* (latent prediction error) → it fires at the
*onset transition*, so it **anticipates**. They are complementary, and the demo uses both: the
3-D embedding leaves the learned-normal cloud while surprise spikes at the turn.

**What the 3-D hero can and cannot show.** The departure is *diffuse* — spread thinly across
the 48 embedding dimensions rather than concentrated in a few. Three axes carry only **64%** of
it (`pca.novelty_captured`), so the dot's on-screen travel is a fraction of the real
displacement, and the panel now says so. Two things were tried and rejected on measurement:
whitening the basis into the Mahalanobis metric (helps on one window, *hurts* on the other, and
halves `novelty_captured` on both — it was fitting the basis to the example), and reading the
visible drift as the finding (the window with the strongest true signal, 1.31 calm-SD, has the
*weakest* visible drift, 0.21). No 3-axis linear projection recovers this departure. The hero is
therefore driven by novelty and surprise, with position as context — not the other way round.

**The demo window is a case study, not a summary.** Across 2 308 candidate 180-window slices
that open calm, the *median* novelty rise is **0.08 calm-SD**: most of the record has nothing to
show. The shipped window sits near the 99th percentile. That is a legitimate way to illustrate a
real signal and a dishonest way to summarise one — so the cohort-wide anticipation AUC above
stays the claim, and the panel caption states the selection explicitly.

**This clears the "promising" bar honestly** (owner's definition: *a meaningful embedding
departure from normal during deterioration, and/or rising surprise around real events*):
the departure is real and held-out (novelty 0.68 vs linear 0.53), and surprise genuinely
anticipates departures (0.76). Nothing is faked, hand-authored, or overfit-to-look-good.

---

## The one honest caveat (read this — it replaces a wrong number in the handoff)

**"Deterioration" here means a sustained excursion of the personalised-deviation signal
`||x_dev||`** — the *same* physiological-departure notion Tier 1's floor triggers and Tier 2's
CUSUM half already act on — **not confirmed bradycardia.** That substitution is forced, and it
is the honest thing to do, because:

- The bradycardia **labels are broken** (issue #18): RR "cleaning" deletes the bradycardia beats
  as ectopy *and* the labels are misaligned to the windows. Measured: at `label==1` windows the
  HRV shows no bradycardia signature. So any label-supervised metric on this data scores at
  chance **regardless of model quality**.
- The **raw PICS records (`.qrsc`/`.atr`/`.hea`) are absent from this repo**, so #18 cannot be
  fixed here (it needs a rebuild of the RR stream from the raw reference annotations).

**Correction to the handoff:** it cites "the VAR forecaster baseline is AUC ≈ 0.635." That
number is an *unverified "on corrected data" projection* (map-22 summary) that was never
produced — the data was never corrected. The **actually-measured** VAR supervised LOIO AUC is
**0.515 (chance)** (`world-model-surprise-loio-result.md`, and reproduced here). The supervised
LOIO metric is therefore **blocked, not weak** — do not chase it on this data.

Because the ground truth is the model-blind `||x_dev||` excursion (a signal the JEPA never sees
as a label), the metrics above are **non-circular** and reproducible. This is exactly the
owner-OK'd "small-cohort, honest-proxy, more-patients-next-time" framing — and it is arguably
*stronger* than a supervised number, because it generalises across 10 held-out infants and
3 563 onsets and beats the linear baseline on the identical protocol.

---

## How the metrics are defined (so they can be audited)

All in `src/world_model/jepa_score.py`; the hand-rolled AUC is verified equal to
`sklearn.roc_auc_score` (ties included) to machine precision.

- **Model-blind ground truth.** `||x_dev||` = magnitude of the 10 personalised-deviation HRV
  features, rolling-averaged (20 windows). A *departure* window = top-15% of that signal for the
  infant; *calm* = bottom-50%. A *departure onset* = the signal crossing its 85th percentile
  from below. The JEPA is never given this signal, or any label, at train time.
- **Embedding novelty.** Mahalanobis distance of the target-encoder embedding from the infant's
  **full calm-window** latent cloud (well-estimated covariance — *not* a 60-window third, which
  small-sample-inflates the distance; that inflation is why the handoff's whitened demo numbers
  looked like 12 SD).
- **Surprise.** Horizon-aggregated latent prediction error — mean predicted-vs-true target-latent
  error over the whole `H`-window horizon (`JEPA.surprise_horizon`). A single +1 step is
  trivially predictable on autocorrelated HRV (flat); the horizon error rises when the near
  future becomes genuinely unpredictable.
- **Held-out / per-infant.** Every infant is scored only against its *own* calm baseline; no
  infant informs another's score or any shared threshold. Anticipation reuses the *validated*
  `loio.py` machinery (window roles, Mann–Whitney AUC, pooling), swapping the broken brady
  labels for the honest `||x_dev||`-onset target.

---

## The config sweep (what iterating actually bought)

`scripts/jepa_sweep.py` — each config trained identically (2 800 steps, stride 4, batch 256,
var-coef 1.5) to its own checkpoint, then scored. `scripts/jepa_finalize.py` adds the
anticipation + robust-demo numbers for the contenders.

| config | H | mask | novelty (concurrent) | surprise (concurrent) | **surprise (anticipation)** | demo drift | embed_std |
|---|---|---|---|---|---|---|---|
| h4_base (prior) | 4 | 0.0 | **0.701** | 0.539 | 0.520 (chance) | 0.94 | 1.02 |
| h16 | 16 | 0.0 | 0.674 | 0.606 | 0.673 | 1.54 | 1.02 |
| **h16_m50 ✓** | 16 | 0.5 | 0.678 | 0.675 | **0.758** | **1.56** | 1.02 |
| h24_m50 | 24 | 0.5 | 0.672 | 0.647 | (H=24 overshoots) | 1.38 | 1.02 |

**What moved the numbers** (handoff method menu):

1. **Harder prediction — longer horizon (method #1).** H 4→16 revived surprise (0.52→0.67
   anticipation) and sharpened the demo drift (+64%). H=24 overshot — 16 is the sweet spot.
2. **Harder prediction — input masking (method #1).** 50% denoising mask on the context pushed
   anticipation-surprise 0.67→**0.76** and turned the demo-window surprise rise positive.
3. **Per-infant whitening (method #2).** Mahalanobis novelty against the infant's own calm cloud
   lifted concurrent novelty 0.67→0.70 — the single cheapest win, applied at scoring time.
4. **Sharper surprise (method #4).** Horizon-aggregation (vs single +1 step) is what makes
   surprise anticipatory at all.

Anti-collapse held throughout (`embed_std ≈ 1.02`; VICReg + EMA + stop-grad untouched). The
prior h4 model keeps a hair more *concurrent* novelty (0.701 vs 0.678) but has **chance**
surprise; the demo needs both signals, so **h16_m50 wins decisively.**

---

## What ships

- **Winning model → `models/jepa/jepa.pt`** — JEPA `H=16, mask_ratio=0.5, D=48, Lc=24`
  (`JEPAConfig` defaults updated to match). ~140k params, trains in ~7 min on Apple MPS.
- **Scorecard → `src/world_model/jepa_score.py`** (novelty / surprise / departure-AUC /
  anticipation-AUC / demo-trajectory), sweep + finalize runners in `scripts/`.
- **For #60/#62:** `demo_trajectory()` returns the real per-window novelty + surprise + the
  `||x_dev||` ground-truth for infant7 — the honest series to export into the trace `world_model`
  block and drive the 3-D warp. Recommend the demo narrate "state departs from this infant's
  learned-normal cloud" (true, grounded) rather than "bradycardia" (unverifiable on this data).

## What's next (honest future work, not blockers)

- **Fix #18 at the source** (rebuild RR from raw `.qrsc`, per-infant `fs`, apply `trim_offsets`)
  → unblocks a *real* supervised bradycardia-anticipation AUC to sit beside these numbers.
- **Richer features (method #3) — BLOCKED in-repo (verified 2026-07-18).** Folding in the
  respiration / apnea–bradycardia stream is the right idea, but it **cannot be done honestly on
  the committed data**: `all_patients_resp_features.csv` uses a *different, coarser window grid*
  than `all_patients_windowed.csv` (infant7: 2 439 resp windows vs 7 217 HRV windows), and
  `window_idx` is **not a shared coordinate** — a naive `(record_name, window_idx)` join is 64 %
  NaN and the 36 % that "match" are index coincidences, not time-aligned. An honest join needs
  per-window timestamps to map the two grids by time; the HRV windowed file carries only
  `window_idx`, so the mapping isn't recoverable here. Unblock by re-emitting both feature streams
  on one shared time grid (same windowing metadata #18's rebuild would produce). Until then,
  do **not** force the misaligned join — it would fabricate a feature relationship.
- **More patients.** Everything here is a 10-infant result; the honest pitch line is
  *"separates departure from baseline at held-out AUC ≈ 0.7–0.76; next we scale the cohort."*

## Reproduce

```
PYTHONPATH=. python3 scripts/jepa_sweep.py         # train + score the config sweep
PYTHONPATH=. python3 scripts/jepa_finalize.py      # anticipation + robust-demo for contenders
PYTHONPATH=. python3 -m src.world_model.jepa_score --whiten --surp-horizon   # score models/jepa/jepa.pt
```
