# NeonatalGuard — Scientific Evidence Base

*Synthesis written 2026-07-12. Maps the cited literature to our implementation, step by step.*

This folder is the primary-source evidence base for NeonatalGuard's clinical claims. Every
factual assertion below is backed in one of the three companion files, which cite peer-reviewed
papers (PMID/DOI), the ESC/NASPE HRV measurement standard, and the FDA 510(k) record:

| File | What it covers |
|------|----------------|
| [`clinical-evidence-hrv-sepsis.md`](clinical-evidence-hrv-sepsis.md) | Is HRV-for-neonatal-sepsis real science? The HeRO/HRC signature, the physiology, lead time, the RCT, FDA status. |
| [`detection-methodology.md`](detection-methodology.md) | Where our thresholds and detectors come from: 2σ/3σ origins, whether z≥2/z≥3 has clinical backing, CUSUM for Tier 2, and what HeRO *actually* computes. |
| [`hrv-features-neonatal-validity.md`](hrv-features-neonatal-validity.md) | A feature-by-feature audit of all 10 HRV features in neonates specifically. |

### Per-step validation assets (research gates for the Verdict Cascade rebuild)

*Added 2026-07-12 — each resolves a research ticket that gates an engineering ticket (wayfinder map #9) and outputs a decision evidence table (choice → keep/drop → mechanism/direction → PMID/DOI).*

| File | Resolves → unblocks | What it fixes |
|------|--------------------|----------------|
| [`cardiorespiratory-feature-validation.md`](cardiorespiratory-feature-validation.md) | #10 → #3 | Adds SampEn + sample asymmetry + respiration features; retires the crude RR proxies; states the SpO₂ gap. |
| [`cusum-drift-and-composition-validation.md`](cusum-drift-and-composition-validation.md) | #11 → #4 | Fixes CUSUM as the Drift detector with concrete tuning (k=0.5, h=5, δ=1 SD); labels the composition rules a design decision. |
| [`world-model-surprise-validation.md`](world-model-surprise-validation.md) | #12 → #6 | Bounds the world-model Surprise to a gated, escalate-only enhancement on the CUSUM backbone. |

---

## Bottom line

**The premise is real; our current Tier 1 implementation is not yet a faithful version of it.**
HRV-based early detection of neonatal sepsis is a genuine, FDA-cleared, RCT-tested field (HeRO /
heart-rate characteristics monitoring). But the validated system detects a **directional, temporal,
purpose-built** signal — *reduced* variability plus *repetitive decelerations*, rising over hours,
scored by an outcome-calibrated model. Our Tier 1 currently detects a **direction-blind, single-window,
generic-statistics** signal (max |z| ≥ 2/3 over 10 features, several of them weak in neonates). The
architecture is pointed the right way — the real signal lives in the Tier 2 (CUSUM drift) you haven't
built yet — but several cheap changes to Tier 1 would move it from "reasonable prototype" to
"defensible to a clinician."

---

## Is the premise defensible? Yes — with honesty about its limits

- **The signature is confirmed, not folklore:** impending sepsis shows reduced baseline variability
  **plus** transient repetitive decelerations, appearing ~6–24 h before clinical deterioration
  (Griffin & Moorman 2001, PMID 11134441; Fairchild & O'Shea 2010, PMID 20813272). Physiology is sound
  (vagal cholinergic anti-inflammatory pathway; TNF-α depresses HRV).
- **The RCT is real but must be quoted precisely:** N=3003 VLBW infants, 9 NICUs; displaying the HeRO
  score cut mortality 10.2%→8.1% (HR 0.78, 95% CI 0.61–0.99, p=0.04), strongest under 1000 g
  (Moorman et al. 2011, *J Pediatr*, PMID 21864846). **It reduced sepsis-associated mortality, not
  sepsis incidence** — earlier treatment, not prevention.
- **Be ready for the pushback:** a 2023 systematic review rated the evidence **low quality**,
  unreplicated, with an unexplained deafness excess; even in validation, HeRO's real-world PPV was poor
  (~5% of HRC≥2 episodes had bloodstream infection; Coggins 2016). HeRO is FDA **510(k)-cleared as a
  Class II adjunct display** (product code DPS; K021230/K180242) — **decision-support, not a diagnostic**.
  Our pitch should mirror that posture exactly.

---

## Per-step scorecard

Legend: ✅ evidence-supported · ⚠️ weak / needs work · ❌ contradicts the evidence

| Implementation element (as built / planned) | Verdict | Why |
|---|:---:|---|
| **Personalized per-infant baseline** (z vs the infant's own rolling mean/SD) | ✅ | Correct call — neonatal HRV varies so much with gestational/postnatal age that population thresholds detune. |
| **`z ≥ 2` → YELLOW, `z ≥ 3` → RED** cutoffs | ❌ | Pure SPC convention (Shewhart 1931 3σ; Western Electric 2σ). **No neonatal study validates these on HRV.** Not clinical thresholds. |
| **`max|z|` over 10 features** as the combiner | ⚠️ | Inflates false positives: ~37% chance one of 10 healthy features crosses \|z\|≥2. HeRO uses a *fitted* multivariable model, not a max. |
| **Direction discarded** (`abs(z)`) | ❌ | Pathology is *directional*: variability goes **down**, events are **down**-ward decelerations. `max|z|` fires equally on reassuring *high* variability. |
| Feature: **`rmssd`** | ✅ | Best-supported short-term vagal marker in neonates. |
| Feature: **`sdnn`** | ✅ | Validated overall-variability marker — but length-sensitive, needs a fixed window. |
| Feature: **`mean_rr`** (HR level) | ✅ | Legitimate; but see bradycardia proxy below. |
| Feature: **`pnn50`** | ⚠️ | Floor effect in neonates (median ~1.7%) → noisy z-score. pNN20 is the right variant. |
| Feature: **`lf_hf_ratio`** | ❌ | Contested construct (Billman 2013) **and** adult bands misclassify infant respiration. **HeRO deliberately avoids frequency-domain.** Weakest feature — yet can solo-fire RED. |
| Feature: **`rr_ms_min`** | ⚠️ | Single extreme order statistic; artifact-sensitive; ambiguous sepsis direction. Not a validated feature. |
| Features: **`rr_ms_max/25/50/75`** | ⚠️ | Not validated as named features, but conceptually proxy decelerations (`max`) and reduced spread (IQR). Better combined into an asymmetry statistic than fired independently. |
| **Missing: sample entropy + sample asymmetry** | ❌ | These are the *actual* HeRO discriminators (skewness of RR carries the deceleration signal). Tier 1 has neither, so it under-represents the deceleration half of the signature. |
| **Bradycardia proxy** `mean_rr > 600 ms` (HR<100), on the window **mean** | ❌ | Averages out the transient dips that matter; HR<100 is the NRP delivery-room number, not the early-sepsis signal. Early sepsis is usually *tachycardic*. |
| **Tier 1 = instantaneous Safety Floor** | ⚠️ | Role is fine (auditable deterministic minimum), but a single-window detector **fires late** — the predictive signal is a multi-hour *rise*. |
| **Tier 2 = CUSUM drift** (planned) | ✅ | Well-founded (Page 1954) with real clinical pedigree. This is the most defensible part of the roadmap. |
| **Tier 2 = world-model "Surprise"** (planned) | ⚠️ | Principled theory, sparse clinical validation. Keep CUSUM as the auditable backbone; let Surprise only *escalate* above the floor. |
| **Validation = synthetic only** | ❌ | The credibility gap that matters most. Position as triage adjunct + show a real-data validation roadmap. |

---

## The changes that buy the most credibility per unit effort

> **Update (2026-07-12):** **#8 shipped** — Tier 1 (`DeviationAssessor`) is now **direction-aware** and **concordance-gated** (≥2 concordant pathological features for RED), with `lf_hf_ratio`/`rr_ms_min`/`rr_ms_50%` out of the trigger set and `pnn50` demoted to display-only. So recommendations **1–2 below are DONE**; recommendation **3 (persistence)** is now Tier 2's job (#4, CUSUM — see [`cusum-drift-and-composition-validation.md`](cusum-drift-and-composition-validation.md)); recommendations **4–5 (SampEn + sample asymmetry)** are specified for #3 in [`cardiorespiratory-feature-validation.md`](cardiorespiratory-feature-validation.md).

**Do these first — small code, large defensibility gain:**

1. **Restore direction in `DeviationAssessor`.** Use one-sided tests where the evidence is one-sided:
   flag *low* `sdnn`/`rmssd`/`pnn50` (variability collapse) and *high* `rr_ms_max`/high percentiles
   (decelerations); keep `mean_rr` two-sided (baseline HR can move either way). Today `assess()` takes
   `max(abs(z))`, which fires RED on reassuring *high* variability. This is the single biggest
   evidence-alignment win and it's a handful of lines in `src/assessment/deviation.py`.
2. **Stop `lf_hf_ratio` (and `pnn50`) from solo-firing RED.** HeRO omits frequency-domain entirely.
   Cheapest defensible move: drop `lf_hf_ratio` from the threshold set (keep it for display only), and
   switch `pnn50` → pNN20 or de-weight it. This removes the weakest features from the false-alarm floor.
3. **Add a persistence rule before RED (k-of-n windows).** Even 2-of-3 or 3-of-5 both cuts the
   `max|z|` false-positive inflation *and* nudges Tier 1 toward the temporal truth. It's also how the
   2σ warning limit is legitimately used in SPC (never as a single point).

**Higher effort, but where Tier 1's real credibility lives:**

4. **Add the two HeRO discriminators: sample entropy (SampEn) and sample asymmetry** over the RR
   window. These carry the deceleration signal your 10 time-domain features miss. This is what turns
   Tier 1 from "generic anomaly score" into "the validated HRC signature."
5. **Redesign bradycardia detection around transient decelerations**, not window-mean HR<100 — e.g.
   count low-percentile / long-RR excursions within the window (you already compute `rr_ms_max`).

**Framing & roadmap (no code, but load-bearing for the pitch):**

6. **Reframe the thresholds honestly** in the rationale text and the pitch — "|z| ≥ 3 from this infant's
   own baseline," an SPC triage cut, **not** a validated clinical threshold. **Never let our "z > 2" be
   read as HeRO's validated "index > 2"** (which means a *two-fold risk increase* from a fitted model —
   a completely different quantity).
7. **Tier 2 CUSUM: state the auditable knobs** — target shift, reference value `k ≈ 0.5σ`, decision
   interval `h ≈ 4–5σ`, chosen from Average-Run-Length tables. That's what makes it defensible.
8. **Position the product as a decision-support / triage adjunct** with a real-data validation roadmap,
   mirroring HeRO's 510(k) posture — not as a sepsis diagnostic.

---

## What to claim — and not claim — in the pitch

**Safe to claim (backed):**
- Grounded in heart-rate-characteristics monitoring, the one HRV approach with an RCT (N=3003) and FDA
  clearance behind it.
- Per-infant personalized baselining — appropriate for neonates given HRV maturation.
- An architecture that separates an auditable deterministic floor (Tier 1) from a well-founded temporal
  drift detector (Tier 2, CUSUM) and LLM reasoning (Tier 3).

**Do not claim:**
- That `z > 2` / `z > 3` are clinically validated thresholds. (They are statistical conventions.)
- That the system is a validated sepsis *diagnostic*. (HeRO itself is an adjunct; our validation is
  synthetic.)
- Any specific sensitivity/PPV number without our own data behind it.

**Do not conflate:** our `z > 2` (two standard deviations) with HeRO's `HRC index > 2` (two-fold risk).

**Be honest, unprompted:** the RCT reduced mortality, not sepsis incidence; it is unreplicated; a 2023
review rated it low quality; even the validated system has low PPV. This *strengthens* a triage-adjunct
framing and disarms the obvious clinician challenge.

---

## Open / unverified items (flagged by the research agents)

- Exact FDA 510(k) **intended-use sentence** — the summaries are scanned images; not machine-verified.
- Whether **mortality was the pre-specified confirmatory primary endpoint** of the RCT — needs the trial
  protocol (NCT00307333) to adjudicate.
- No published neonatal **baseline "warm-up" standard** — how many windows before a per-infant z-score is
  trustworthy is an open, unspecified parameter (relevant to Tier 1 cold-start).
- A secondary summary's **OR ≈ 7.1 / sens–spec ≈ 53%/79%** for Fairchild 2013 could not be verified in
  the primary article and should not be cited.
