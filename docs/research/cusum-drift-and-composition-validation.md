# CUSUM Drift Detector & Safety-Floor Composition — Literature Validation

**Scope.** A primary-sourced validation of three decisions for NeonatalGuard's Tier 2 and the
verdict cascade, resolving GitHub issue #11 (blocks engineering issue #4): (a) is **CUSUM** the right
detector for the 6–24 h sepsis **Drift**; (b) what are defensible **tuning parameters** (reference
value *k*, decision interval *h*, target shift, ARL) for a neonatal HRV z-score stream; and (c) does
the literature support the **Safety-Floor composition rules** of ADR-0001 (refine *above* the floor but
never below; asymmetric de-escalation where only the calibrated temporal tier may quiet an alarm down
to — never below — the deterministic floor, and the RAG/LLM tier is escalate-only).

**Builds on:** `detection-methodology.md` §2 (which already establishes CUSUM's provenance and the
*k*/*h*/ARL machinery) and `README.md` (house synthesis + scorecard). This file goes deeper on the
*drift* detector specifically, pins concrete tuned defaults for #4, and adjudicates the composition
rules — separating **literature-backed findings** from **design decisions**.

**Data reality.** 10 preterm infants (PICS), ~450–500 h dual-channel ECG + respiration, **no sepsis
labels**. Tier 1 (deterministic, per-infant, **direction-aware** z-score floor, done in #8) sets the
Safety Floor. Tier 2 = deterministic CUSUM on the z-score stream (#4, ships independently) + a learned
world-model Surprise (#6, separate). CUSUM state persists to `audit.db` per infant. The predictive
signal for sepsis is a **rising trajectory over 6–24 h**, not a single window.

**Date:** 2026-07-12
**Author:** Research agent (change-detection + human-factors)

---

## Bottom line (honest)

| Question | Verdict | One-line |
|---|---|---|
| Is CUSUM the right Drift detector? | **Yes — literature-backed** | Page's cumulative sum is *provably optimal* for detecting small sustained shifts and has a real ICU/quality-monitoring pedigree; it is the standard complement to a Shewhart-style single-window floor (Tier 1). |
| Defensible tuning for a neonatal HRV z-stream? | **Yes — with a caveat** | `k = 0.5`, `h = 4–5` in z-units, targeting a sustained **1 SD** drift, chosen via ARL tables. Because we run a **one-sided** (direction-aware) scheme, in-control ARL₀ is ~2× the textbook two-sided figure. The exact operating point must be **confirmed on the infant's own autocorrelated stream by simulation**, not read blind from an i.i.d. table. |
| Is the 6–24 h lead-time premise real? | **Yes — literature-backed** | Heart-rate characteristics become "increasingly abnormal for up to 24 h" before deterioration; the validated clinical index is explicitly a *fold-increase in risk over the next 24 h*. The signal is a **rise over hours**, exactly what CUSUM integrates. |
| Do the composition rules have literature support? | **They are a DESIGN DECISION** | No paper states the specific rule "refine up but never below a deterministic floor." The *ingredients* are literature-backed — alarm fatigue is real (so we need a de-escalation path), automation bias is real (so only a calibrated component may quiet, and a generative tier never may), and "fail to a safe state" is a classic design principle — but the composition **algebra** is our engineering judgement, not a clinical finding. |

**The single most important honest point:** the CUSUM half of this document rests on **direct primary
sources** (Page 1954; Lorden/Moustakides optimality; NIST/Montgomery ARL tables; Griffin & Moorman 2001).
The composition half rests on **design principles applied to verified human-factors evidence** — we must
not present the cascade rules as though a trial validated them. They are defensible *because* the tension
they resolve (alarm fatigue vs. false-negative safety) is real and cited, not because anyone published the
rule.

---

## Decision evidence table

| Choice | Keep? | Mechanism / rationale | Evidence (PMID/DOI) |
|--------|-------|-----------------------|---------------------|
| **CUSUM (Page) as the Drift detector** | **Yes** | Accumulates deviations from target so *small sustained* shifts that never trip a single-window limit still integrate to threshold; inspired by Wald's SPRT; **minimax-optimal** detection delay for a target shift under a false-alarm constraint. | Page 1954, *Biometrika* 41(1-2):100-115, doi:10.1093/biomet/41.1-2.100; Lorden 1971, *Ann Math Statist* 42(6):1897-1908 (asymptotic minimax); Moustakides 1986, *Ann Statist* 14(4):1379-1387 (exact optimality) |
| **CUSUM *vs* Shewhart / single-threshold (Tier 1)** | **Keep both — complementary** | A 3σ/2σ single-window chart is slow to catch shifts ≤2σ; CUSUM is built for exactly that regime. Pairing Tier 1 (acute single-window floor) with Tier 2 (sub-threshold drift) is the textbook Shewhart-plus-CUSUM design. | NIST/SEMATECH e-Handbook §6.3.2 (itl.nist.gov/div898/handbook/pmc/section3/pmc323.htm); Montgomery, *Intro. to Statistical Quality Control* |
| **CUSUM *vs* EWMA** | **Keep CUSUM (EWMA an acceptable alt)** | EWMA has near-identical ARL for small shifts, but CUSUM is *exactly* optimal, carries explicit cumulative "evidence," and has natural reset/headstart semantics that are easier to persist and audit. | Lucas & Saccucci 1990, *Technometrics* 32(1):1-12, doi:10.1080/00401706.1990.10484583; Roberts 1959, *Technometrics* 1(3):239-250 (EWMA origin) |
| **Reference value `k = 0.5`** (z-units) | **Yes** | `k = δ/2`; `k=0.5` makes the scheme optimal for a **sustained 1 SD (1 z-unit) drift** — the "half the shift" rule. Larger *k* blunts small drifts; smaller *k* invites false alarms. | NIST §6.3.2.3 (itl.nist.gov/div898/handbook/pmc/section3/pmc3231.htm); Montgomery ISQC |
| **Decision interval `h = 4–5`** (z-units), default **h = 5**, tuned to a false-alarm budget | **Yes** | *h* is the alarm threshold on the accumulated sum. **Two-sided** table: `h=4`→ARL₀≈168, `h=5`→ARL₀≈465. **One-sided** (our case): ~2× → `h=4`→ARL₀≈336, `h=5`→ARL₀≈930 in-control samples; ARL₁≈8.4 (h=4) / 10.4 (h=5) samples to flag a 1σ drift. Choose *h* for an acceptable false-alarm rate per infant-day. | NIST §6.3.2.3 (pmc3231.htm, one-sided table: shift 0.5σ→26.6, 1.0σ→8.38 at h=4); Montgomery ISQC (two-sided 168/465) |
| **Target shift `δ = 1 SD` sustained** | **Yes** | A sustained +1 z-unit drift sits **below** Tier 1's single-window YELLOW gate (\|z\|≥2) yet is precisely the multi-hour trajectory Tier 1 misses; it is the smallest shift worth integrating over hours. | Griffin & Moorman 2001, PMID 11134441 (HRC drift over hours, not a single point) |
| **One-sided CUSUM in the pathological direction** | **Yes** | The sepsis phenotype is *directional* — variability falls, decelerations rise. A one-sided scheme in the clinically-meaningful direction matches the direction-aware Tier 1 (#8) and halves the false-alarm rate vs. two-sided. | Griffin & Moorman 2001, PMID 11134441; Kovatchev et al. 2003, PMID 12930915 (sample asymmetry is directional by construction) |
| **6–24 h rising *trajectory* (not single window) as the sepsis signal** | **Yes — the design's core premise** | HRC become "increasingly abnormal for up to 24 h" before abrupt deterioration; the deployed clinical index is a *fold-increase in risk over the next 24 h*; displaying it cut VLBW mortality in an RCT. CUSUM is the tool that turns "a rise over hours" into a decision. | Griffin & Moorman 2001, PMID 11134441; Fairchild & O'Shea 2010, PMID 20813272; Moorman et al. 2011 (RCT), PMID 21864846 |
| **Safety Floor: no tier may fall below Tier-1's deterministic minimum** | **Yes — DESIGN DECISION** | "Fail to a safe (higher-concern) state." A well-established engineering safety principle (fail-safe defaults), applied to encode the FNR=0 promise in one auditable module. *No clinical paper states this rule; the literature is silent on the specific composition.* | Saltzer & Schroeder 1975, *Proc IEEE* 63(9):1278-1308, doi:10.1109/PROC.1975.9939 (fail-safe defaults — **design principle, not clinical evidence**) |
| **Asymmetric de-escalation: only the calibrated Tier 2 may quiet, down to (never below) the floor** | **Yes — DESIGN DECISION** | Alarm fatigue is real and dangerous (desensitisation → missed true alarms), so a de-escalation path must exist; automation bias says the quieting authority must sit with the *calibrated, auditable* component, not an over-trusted or uncalibrated one. Ingredients cited; the rule itself is judgement. | Cvach 2012, PMID 22839984; Drew et al. 2014, PMID 25338067; Parasuraman & Riley 1997, doi:10.1518/001872097778543886; Goddard et al. 2012, PMID 21685142 |
| **RAG / LLM tier is escalate-only (may raise, never lower concern)** | **Yes — DESIGN DECISION** | Generative models hallucinate and are not calibrated to clinical risk; automation bias makes clinicians under-scrutinise machine output. So the LLM may *add* a flag but is never trusted to *suppress* one — mirroring HeRO's FDA adjunct-display posture. | Goddard et al. 2012, PMID 21685142; adversarial-hallucination in clinical LLMs, *Commun Med* 2025, doi:10.1038/s43856-025-01021-3; LLM-CDS field study, *Nat Health* 2026, doi:10.1038/s44360-026-00082-5 |

---

## 1. CUSUM as the Drift detector

### 1.1 Origin and why it fits "Drift"
The cumulative-sum chart is **Page, E. S. (1954), "Continuous inspection schemes," *Biometrika*
41(1-2):100-115, doi:10.1093/biomet/41.1-2.100** (verified, Oxford Academic). Page's scheme accumulates
signed deviations from a target so that a *small, sustained* shift — one a Shewhart chart is slow to catch
— drives the running sum to a decision boundary quickly; it descends from Wald's sequential probability
ratio test. This is a precise match to NeonatalGuard's **Drift** definition: *"no single window trips a
threshold but the cumulative trend is abnormal."*

### 1.2 It is provably the right tool, not just a convention
CUSUM is not merely conventional — it is **optimal**. Lorden (1971) established its **asymptotic minimax
optimality** (it minimises the worst-case expected detection delay subject to a false-alarm constraint),
and **Moustakides (1986)** proved **exact optimality** of Page's CUSUM for that criterion for any
false-alarm level (both corroborated in the change-detection literature searched, e.g. the
Moustakides/Lorden optimality reviews at inria.hal.science/inria-00072047 and projecteuclid). For a system
whose job is *"detect a sustained sub-threshold rise as fast as possible without crying wolf,"* that is the
exact guarantee we want, and it is why a deterministic CUSUM is the defensible, auditable backbone of Tier 2.

### 1.3 Clinical / ICU / SPC pedigree
CUSUM is an established clinical monitoring instrument, not an exotic import (see `detection-methodology.md`
§2.3 for the full list): risk-adjusted CUSUM charts are standard for surgical-performance and learning-curve
monitoring (Steiner et al. 2000, *Biostatistics* 1(4):441-452), and cumulative-change framing is used for
continuous physiological deterioration monitoring. That pedigree is what lets us defend a CUSUM to a
clinician-statistician.

### 1.4 Contrast with EWMA (the smooth cousin)
The exponentially weighted moving average (**Roberts 1959**; properties in **Lucas & Saccucci 1990,
*Technometrics* 32(1):1-12, doi:10.1080/00401706.1990.10484583**) is the usual alternative for small-shift
detection. The verified finding: EWMA's **ARL properties are *similar* to CUSUM's** for small sustained
shifts — so EWMA would also be defensible. We keep **CUSUM** because (i) it is exactly optimal, not merely
comparable; (ii) it exposes an explicit cumulative-evidence statistic that is easy to *explain* in an audit
("evidence has been accumulating for N windows"); and (iii) its reset-to-zero and fast-initial-response
(headstart) semantics map cleanly onto per-infant persisted state. EWMA remains a legitimate fallback if a
smoother response is ever preferred.

> **Mapping to NeonatalGuard.**
> - **SUPPORTS:** a one-sided deterministic CUSUM is the correct, optimality-backed Drift detector and the
>   natural complement to the Shewhart-style Tier-1 floor: Tier 1 catches an acute single-window excursion,
>   CUSUM catches the sub-threshold *trend* Tier 1 is blind to.
> - **Keep CUSUM over EWMA** for auditability and exact optimality; record EWMA as the documented alternative.

---

## 2. Tuning: reference value *k*, decision interval *h*, and the ARL trade-off

Because the monitored stream is already a **per-infant z-score** (unit SD by construction), the CUSUM's σ
*is* one z-unit, which makes the textbook σ-based rules directly usable.

### 2.1 The two knobs and how ARL tables pick them
Standard SPC design (NIST/SEMATECH e-Handbook §6.3.2.3, verified at
`itl.nist.gov/div898/handbook/pmc/section3/pmc3231.htm`; Montgomery, *ISQC*):

- **`k` (reference value / "slack"), in σ units:** set to **half the shift you want to detect**,
  `k = δ/2`. The NIST page states the rule of thumb explicitly — `k = 0.5` targets a **δ = 1σ** shift.
- **`h` (decision interval):** the alarm threshold on the accumulated sum, **`h ≈ 4–5σ`** by the same
  rule of thumb.
- **Selection is via Average Run Length (ARL):** pick `(k,h)` so that ARL is *large* in-control (**ARL₀**,
  few false alarms) and *small* after the shift (**ARL₁**, fast detection). ARL₀ and ARL₁ trade off against
  each other through `h`: raising `h` buys fewer false alarms at the cost of slower detection.

### 2.2 The verified ARL numbers — and the one-sided correction that matters for us
The widely-cited **two-sided** tabular-CUSUM figures at `k = 0.5` are **`h=4` → ARL₀ ≈ 168** and
**`h=5` → ARL₀ ≈ 465** (Montgomery ISQC; corroborated across SPC references). **But NeonatalGuard runs a
*one-sided* CUSUM** (only the pathological direction, matching the direction-aware Tier 1 from #8), and a
one-sided scheme has only **one** boundary to breach, so its in-control ARL₀ is **~2× larger** (it
false-alarms half as often). The NIST handbook page, fetched directly, tabulates for `k = 0.5`:

| Sustained shift (in SD) | ARL, `h=4` | ARL, `h=5` |
|---|---|---|
| 0.00 (in-control, ARL₀) | ~336 | ~930 |
| 0.50 | 26.6 | ~30 |
| 1.00 (ARL₁) | 8.38 | 10.4 |

The **out-of-control cells are identical** to Montgomery's one-sided table (26.6 at 0.5σ, 8.38 at 1σ for
`h=4`) — only the in-control ARL₀ differs by the one-sided-vs-two-sided factor of two (336 ≈ 2×168,
930 = 2×465). **Net:** for our one-sided detector, budget on **ARL₀ ≈ 336 (h=4)** or **≈ 930 (h=5)**
in-control samples between false alarms, and **ARL₁ ≈ 8–10 samples** to flag a sustained 1σ drift.

### 2.3 Translating "samples" into the 6–24 h lead time (the real design lever)
ARL is in **samples**, so the CUSUM's *update cadence* is what converts it into hours — this is the knob to
document. With a HeRO-like ~20–25 min feature window and one CUSUM update per window:

- **h=5, k=0.5:** ARL₁ ≈ 10.4 samples × ~22 min ≈ **~3.8 h** to raise the Drift after a sustained 1σ shift —
  comfortably *inside* the 6–24 h envelope, with headroom to spare. In-control ARL₀ ≈ 930 × 22 min ≈
  **~14 days** between false Drift alarms *per stream* (before multiple-stream inflation).
- **h=4, k=0.5:** ARL₁ ≈ 8.4 samples ≈ **~3.1 h** (faster) but ARL₀ ≈ 336 × 22 min ≈ **~5 days** per stream
  (noisier).

**Recommended default: `h = 5`** — the product's differentiator is *fewer* false alarms (alarm fatigue,
§4), and even at `h=5` the ~3.8 h detection is well within the clinical lead time. Use `h = 4` only if a
future validation shows detection is arriving too late.

### 2.4 The honest caveat — ARL tables assume i.i.d.
The ARL figures above assume **independent** samples. A neonatal HRV z-stream is **autocorrelated**
(overlapping windows, physiologically smooth trends, circadian structure), which **inflates the real
false-alarm rate** relative to the table. Therefore the tuned `(k,h)` must be **confirmed by simulation on
the infants' own streams** (or via a design solver such as the `CUSUMdesign` R package), and the *achieved*
false-alarms-per-infant-day recorded — that empirical number, not the table cell, is the auditable knob a
reviewer will ask for. A per-infant warm-up (Tier-1 baseline must be stable before the CUSUM arms; see
`detection-methodology.md` §4.2) is also required so the z-stream feeding CUSUM is trustworthy.

> **Mapping to NeonatalGuard.**
> - **Concrete tuned starting point:** one-sided CUSUM, `k = 0.5` z-units, `h = 5` z-units, target
>   `δ = 1 SD` sustained, ARL₀ ≈ 930 one-sided samples, ARL₁ ≈ 10 samples.
> - **State `δ` explicitly** (1σ): the `k=δ/2` rule is what makes CUSUM optimal, so the target shift is a
>   documented design input, not an accident.
> - **Do not trust the table blind:** simulate on real autocorrelated data, then persist the chosen `(k,h)`
>   *and* the measured false-alarm rate.

---

## 3. The 6–24 h lead-time basis (why a trajectory, not a window)

This is the premise that justifies building Tier 2 at all, and it is **directly literature-backed**:

- **Griffin, M. P., & Moorman, J. R. (2001), "Toward the early diagnosis of neonatal sepsis and sepsis-like
  illness using novel heart rate analysis," *Pediatrics* 107(1):97-104. PMID 11134441** (verified). Infants
  developing sepsis showed **"increasingly abnormal HRC for up to 24 h preceding abrupt clinical
  deterioration"** — specifically **reduced baseline variability plus transient decelerations** — across 46
  culture-positive and 27 culture-negative episodes. The abnormality is a **rise over hours**, not a single
  aberrant reading. This is the empirical basis for integrating the z-stream over time.
- **Fairchild, K. D., & O'Shea, T. M. (2010), "Heart rate characteristics: physiomarkers for detection of
  late-onset neonatal sepsis," *Clin Perinatol* 37(3):581-598. PMID 20813272** (verified). HRC abnormalities
  "occur early in the course of sepsis, often before clinical signs," and the HRC index is explicitly *"the
  fold increase in risk that a neonate will be diagnosed with sepsis within the next 24 h"* — a **forward-
  looking, hours-scale** quantity.
- **The RCT (verified):** **Moorman, J. R., Carlo, W. A., Kattwinkel, J., et al. (2011), "Mortality
  reduction by heart rate characteristic monitoring in very low birth weight neonates: a randomized trial,"
  *J Pediatr* 159(6):900-906.e1. PMID 21864846. doi:10.1016/j.jpeds.2011.06.044.** N=3003 VLBW infants, 9
  NICUs; displaying the HRC score cut mortality **10.2% → 8.1% (HR 0.78, p=0.04)**, strongest under 1000 g.
  This is why the *trajectory* signal — not a single-window trip — is the clinically validated construct.

> **Note on the task's suggested citation.** The brief offered "the HeRO RCT — Moorman 2011, PMID 21962498
> or similar." **PMID 21962498 is a different article** ("Genomics in Africa: avoiding past pitfalls,"
> *Cell* 2011) and is **not** the HeRO trial. The correct RCT is **PMID 21864846** (verified above); use that.

> **Mapping to NeonatalGuard.**
> - **SUPPORTS the whole Tier-2 premise:** the predictive signal is a multi-hour *rise*, which is exactly
>   what a CUSUM integrates and a single-window Tier-1 gate cannot see.
> - **Caveat we already own:** our score is an *abnormality-departure* signal (self-referenced), not HeRO's
>   *outcome-calibrated risk* — do not conflate a CUSUM Drift alarm with a validated risk score
>   (`detection-methodology.md` §3, README "Do not claim").

---

## 4. Composition / de-escalation rules — a DESIGN DECISION on cited ground

**Direct literature search result: the specific rules of ADR-0001 are not stated in any source.** No
paper says "a monitor's output may be refined upward but never suppressed below a deterministic safety
floor," and none prescribes "only a calibrated model may quiet an alarm while a generative tier is
escalate-only." **The literature is silent on the composition algebra.** We therefore record the cascade
rules as a **design decision** — but one built from **verified, load-bearing ingredients**. Below is the
evidence for each ingredient and why it forces the rule.

### 4.1 Why a de-escalation path must exist at all — alarm fatigue is real and harmful
- **Cvach, M. (2012), "Monitor alarm fatigue: an integrative review," *Biomed Instrum Technol*
  46(4):268-277. PMID 22839984, doi:10.2345/0899-8205-46.4.268** (verified). Alarm fatigue was the
  **#1 medical-device technology hazard of 2012**; desensitisation is driven by high false-alarm rates and
  poor positive predictive value.
- **Drew, B. J., Harris, P., Zègre-Hemsey, J. K., et al. (2014), "Insights into the problem of alarm fatigue
  with physiologic monitor devices…," *PLoS ONE* 9(10):e110274. PMID 25338067** (verified). Over 31 days in
  5 ICUs, **2,558,760 alarms**; of 1,154,201 arrhythmia alarms, **88.8% were false positives**.
- **Joint Commission Sentinel Event Alert #50 (2013), "Medical device alarm safety in hospitals"**
  (verified via search; a Joint Commission bulletin, not a PMID). Of 98 alarm-related events reported
  Jan 2009–Jun 2012, **80 resulted in death**.

**Consequence for the design:** an escalate-only cascade would drown the product's differentiator; a
de-escalation path is *mandatory*. This is the "Specificity" force in ADR-0001, and it is well-cited.

### 4.2 Why only the *calibrated* tier may quiet — automation bias & the direction of trust
- **Parasuraman, R., & Riley, V. (1997), "Humans and automation: use, misuse, disuse, abuse," *Human
  Factors* 39(2):230-253, doi:10.1518/001872097778543886** (verified). Two failure modes bracket our
  problem exactly: **misuse = over-reliance** on automation (monitoring failures, decision bias), and
  **disuse = neglect of automation caused by false alarms**. A cascade must avoid *both* — which is precisely
  why quieting authority is granted (to fight disuse) but *restricted* (to fight misuse).
- **Goddard, K., Roudsari, A., & Wyatt, J. C. (2012), "Automation bias: a systematic review of frequency,
  effect mediators, and mitigators," *JAMIA* 19(1):121-127. PMID 21685142** (verified). Clinicians
  over-accept automated recommendations and fail to catch the *new* errors automation introduces. The
  mitigation implication: the authority to *lower* a safety-critical alarm must sit with the most
  **calibrated and auditable** component (deterministic floor + calibrated Tier 2), never with a component
  whose errors are hard to detect.

**Consequence for the design:** de-escalation is granted to Tier 2 *because* it is calibrated and auditable,
and is bounded to never cross the floor. This is the "asymmetric" half of ADR-0001.

### 4.3 Why the LLM/RAG tier is escalate-only — generative models are neither calibrated nor reliable
- **Adversarial-hallucination assurance analysis, *Commun Med* 2025, doi:10.1038/s43856-025-01021-3**
  (verified via search): clinical LLMs showed **hallucination rates of 50–82.7%** under adversarial
  conditions — an unacceptable basis for *suppressing* a safety alarm.
- **LLM-CDS field study, *Nat Health* 2026, doi:10.1038/s44360-026-00082-5** (verified via search):
  clinicians left LLM output unmodified in **62% of encounters** (automation bias in the wild), and even
  **retrieval-augmentation did not reliably fix** miscalibration — the model can resist retrieved knowledge
  that conflicts with pretraining. A RAG tier is therefore *useful for surfacing missed guideline context*
  (escalation) but *not trustworthy to quiet* (de-escalation).

**Consequence for the design:** the RAG/LLM tier may *raise* concern (add information the models missed) but
**never lower** it — matching HeRO's regulatory posture as an FDA 510(k) **adjunct display**, not a
diagnostic (README).

### 4.4 Why the floor itself cannot be lowered — fail-safe defaults
- **Saltzer, J. H., & Schroeder, M. D. (1975), "The protection of information in computer systems," *Proc
  IEEE* 63(9):1278-1308, doi:10.1109/PROC.1975.9939** (principle verified). Among their eight design
  principles, **fail-safe defaults**: in the absence of an explicit, trusted reason to do otherwise, a system
  should **fail into the safe state**. Applied here, the "safe state" is *higher* concern, so no downstream
  tier may drop a verdict below the deterministic floor. This concentrates the FNR=0 guarantee in one
  testable module — an engineering safety principle, **not** a clinical result.

> **Mapping to NeonatalGuard — and the honest label.**
> - **ADR-0001's rules are a DESIGN DECISION**, correctly grounded: alarm fatigue (§4.1) justifies *having*
>   de-escalation; automation bias (§4.2) justifies *restricting* it to the calibrated tier; LLM
>   unreliability (§4.3) justifies the escalate-only RAG tier; fail-safe defaults (§4.4) justify the
>   un-lowerable floor. The final rule `Verdict = max( merge(Tier2, Tier3 escalations), Safety Floor )` is a
>   faithful encoding of these four verified pressures.
> - **Do not overclaim:** present this to a regulator as *"the language model can raise a flag but never
>   suppress one, and only a calibrated, auditable model can quiet a false alarm — down to, never below, a
>   deterministic floor,"* explicitly as a **safety-engineering design choice informed by human-factors
>   evidence**, not as a validated clinical algorithm.

---

## Confidence & conflicting evidence

- **High confidence (literature-backed):** CUSUM origin and optimality (Page 1954; Lorden 1971; Moustakides
  1986); the `k`/`h`/ARL tuning machinery and the specific ARL cells (NIST §6.3.2.3; Montgomery); the 6–24 h
  trajectory basis and the RCT (Griffin & Moorman 2001, PMID 11134441; Fairchild & O'Shea 2010, PMID
  20813272; Moorman 2011, PMID 21864846). All directly sourced with DOI/PMID.
- **Medium confidence (verified numbers, scheme-dependent interpretation):** the **one-sided vs two-sided
  ARL₀** reconciliation. The out-of-control ARL cells and both in-control values (168/465 two-sided;
  336/930 one-sided) are verified; the *attribution* of the 2× factor to one-sidedness is standard theory
  (one boundary vs two) — but the **real** ARL₀ on an **autocorrelated** neonatal stream will differ and
  **must be simulated**, so treat the table figures as a starting point, not a shipped constant.
- **Design decision, not clinical finding:** the composition rules (§4). The tension they resolve is real and
  cited; the specific rule is not in the literature. Labelled as such throughout.
- **Honest tension #1:** self-referenced CUSUM Drift (departure from own normal) vs. HeRO's outcome-calibrated
  risk. Both are legitimate for *different jobs*; conflating them would overclaim (carried over from
  `detection-methodology.md` §3, README).
- **Honest tension #2:** CUSUM vs EWMA. EWMA is *comparable* (Lucas & Saccucci 1990), so "CUSUM is the only
  option" would be too strong; we choose CUSUM on optimality + auditability, and record EWMA as the
  documented alternative.
- **Weakest-evidence sibling (out of scope here, flagged):** the learned world-model "Surprise" (#6) has
  strong theory but sparse clinical validation; the Safety-Floor architecture is exactly what lets it ship
  as an escalate-above-floor adjunct (`detection-methodology.md` §5).

---

## Concrete defaults for #4

| Parameter | Default | Rationale |
|---|---|---|
| **Detector** | One-sided **tabular (Page) CUSUM** per direction-aware z-stream (pathological side), optionally with a fast-initial-response headstart | Optimal for sustained small shifts; matches Tier-1 direction-awareness (#8); auditable cumulative statistic (Page 1954; Lorden 1971; Moustakides 1986) |
| **Reference value `k`** | **0.5** (z-units) | `k = δ/2`; targets a sustained 1σ drift (NIST §6.3.2.3) |
| **Decision interval `h`** | **5** (z-units) default; `h=4` if detection proves too slow | One-sided ARL₀ ≈ 930 samples in-control, ARL₁ ≈ 10 samples at 1σ; favours specificity for alarm-fatigue reduction (§4.1) |
| **Target shift `δ`** | **1 SD (1 z-unit) sustained** | Sub-Tier-1 (YELLOW = \|z\|≥2) trajectory a single window misses (Griffin & Moorman 2001) |
| **Update cadence** | Tie to the feature-window cadence (~20–25 min HeRO-like → ~3.8 h detection at h=5); **document it** | Cadence is what maps ARL-in-samples to lead-time-in-hours (§2.3) |
| **Operating-point validation** | **Simulate on the infants' own autocorrelated streams**; record achieved false-alarms-per-infant-day; a `CUSUMdesign`-style solver for the i.i.d. anchor | ARL tables assume independence; real streams are autocorrelated (§2.4) |
| **Persistence (`audit.db`, per infant × per stream)** | Store the running one-sided sum `C⁺` (and `C⁻` if any two-sided variant is kept), the last-update timestamp, the reset/headstart state, and the chosen `(k, h, δ)` + measured ARL₀ | CUSUM is stateful; the persisted sum *is* the accumulated evidence; storing `(k,h,δ)` + achieved false-alarm rate makes each Drift verdict reproducible and auditable. Reset `C⁺→0` after a signal (or apply headstart on process restart) |
| **Composition** | Drift feeds Tier 2, which **may de-escalate down to — never below — the Safety Floor**; RAG/LLM **escalate-only**; `Verdict = max( merge(Tier2, Tier3↑), Floor )` | Design decision on cited ground (§4); keep the floor un-lowerable (fail-safe defaults) |

---

## Open questions / unverified

- **[UNVERIFIED — mis-cited in the task brief]** The task's suggested **PMID 21962498** for the HeRO RCT is
  **wrong** — it is a *Cell* genomics article, not the trial. The correct, verified RCT is **PMID 21864846**
  (Moorman 2011, *J Pediatr*). Flagged and corrected in §3.
- **[SCHEME-DEPENDENT]** Exact **ARL₀** for our detector. Verified: two-sided 168/465 and one-sided ~336/~930
  at `k=0.5` (`h=4`/`h=5`). Not verified: the ARL₀ under the **actual autocorrelation** of the neonatal
  z-stream — this must be measured by simulation before shipping a false-alarm claim.
- **[STANDARD BUT NOT RE-FETCHED]** Bibliographic details for **Lorden 1971** (*Ann Math Statist*
  42:1897-1908) and **Moustakides 1986** (*Ann Statist* 14:1379-1387) and **Roberts 1959** (*Technometrics*
  1:239-250) are cited from standard references; the *substantive optimality/EWMA claims* were corroborated
  by search, but the exact page numbers were not re-fetched from the primary PDFs.
- **[RECENT / EVOLVING]** The LLM-reliability citations (*Commun Med* 2025, doi:10.1038/s43856-025-01021-3;
  *Nat Health* 2026, doi:10.1038/s44360-026-00082-5) are recent and were verified via search snippets, not
  full-text read; the *direction* of the evidence (hallucination + automation bias → escalate-only LLM) is
  robust, but treat specific percentages as indicative.
- **[NO PMID — bulletin]** Joint Commission Sentinel Event Alert #50 is an institutional alert, not a
  peer-reviewed article; cited as such.
- **[OPEN — engineering]** Neonatal-specific **warm-up** window count before the CUSUM arms (no published
  standard; see `detection-methodology.md` §4.2) — a design choice, not a validated constant.
- **[OPEN — engineering]** Whether Drift should run on **each clinically-directed feature** separately or on
  a single **multivariate** deviation before the CUSUM (multiple one-sided CUSUMs inflate the aggregate
  false-alarm rate; a multivariate input is the cheaper-to-defend alternative — cf. `detection-methodology.md`
  §1.3 on `max|z|`).

---

## References

**CUSUM / change-detection (the Drift detector)**
1. Page, E. S. (1954). "Continuous inspection schemes." *Biometrika* 41(1-2):100-115.
   doi:10.1093/biomet/41.1-2.100 (CUSUM origin; verified, Oxford Academic).
2. Lorden, G. (1971). "Procedures for reacting to a change in distribution." *Ann Math Statist*
   42(6):1897-1908 (asymptotic minimax optimality of CUSUM).
3. Moustakides, G. V. (1986). "Optimal stopping times for detecting changes in distributions." *Ann Statist*
   14(4):1379-1387 (exact optimality of Page's CUSUM).
4. Lucas, J. M., & Saccucci, M. S. (1990). "Exponentially weighted moving average control schemes:
   properties and enhancements." *Technometrics* 32(1):1-12. doi:10.1080/00401706.1990.10484583 (EWMA ≈
   CUSUM for small shifts; FIR/headstart).
5. Roberts, S. W. (1959). "Control chart tests based on geometric moving averages." *Technometrics*
   1(3):239-250 (EWMA origin).
6. Steiner, S. H., Cook, R. J., Farewell, V. T., Treasure, T. (2000). "Monitoring surgical performance using
   risk-adjusted cumulative sum charts." *Biostatistics* 1(4):441-452 (CUSUM clinical pedigree).

**Tuning (k, h, ARL)**
7. NIST/SEMATECH (current). *e-Handbook of Statistical Methods*, §6.3.2.3 "CUSUM Average Run Length."
   https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc3231.htm (verified: k=0.5 targets 1σ; h≈4–5;
   one-sided ARL table — ARL₀≈336/930, ARL₁≈8.38/10.4). Intro: §6.3.2
   https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc323.htm
8. Montgomery, D. C. *Introduction to Statistical Quality Control* (tabular CUSUM; two-sided ARL₀≈168 at h=4,
   ≈465 at h=5). Design solver: `CUSUMdesign` R package,
   https://cran.r-project.org/web/packages/CUSUMdesign/CUSUMdesign.pdf

**6–24 h lead time (why a trajectory)**
9. Griffin, M. P., & Moorman, J. R. (2001). "Toward the early diagnosis of neonatal sepsis and sepsis-like
   illness using novel heart rate analysis." *Pediatrics* 107(1):97-104. PMID 11134441 (verified: HRC
   "increasingly abnormal for up to 24 h" before deterioration).
10. Fairchild, K. D., & O'Shea, T. M. (2010). "Heart rate characteristics: physiomarkers for detection of
    late-onset neonatal sepsis." *Clin Perinatol* 37(3):581-598. PMID 20813272 (verified: HRC index = fold
    increase in risk over next 24 h).
11. Moorman, J. R., Carlo, W. A., Kattwinkel, J., et al. (2011). "Mortality reduction by heart rate
    characteristic monitoring in very low birth weight neonates: a randomized trial." *J Pediatr*
    159(6):900-906.e1. PMID 21864846. doi:10.1016/j.jpeds.2011.06.044 (verified: N=3003, 10.2%→8.1%,
    HR 0.78, p=0.04). **NB: NOT PMID 21962498, which is an unrelated *Cell* article.**
12. Kovatchev, B. P., Farhy, L. S., Cao, H., Griffin, M. P., Lake, D. E., Moorman, J. R. (2003). "Sample
    asymmetry analysis of heart rate characteristics…" *Pediatr Res* 54(6):892-898. PMID 12930915
    (directional-by-construction deceleration signal).

**Composition / de-escalation (design-decision ingredients)**
13. Cvach, M. (2012). "Monitor alarm fatigue: an integrative review." *Biomed Instrum Technol* 46(4):268-277.
    PMID 22839984. doi:10.2345/0899-8205-46.4.268 (verified).
14. Drew, B. J., Harris, P., Zègre-Hemsey, J. K., et al. (2014). "Insights into the problem of alarm fatigue
    with physiologic monitor devices…" *PLoS ONE* 9(10):e110274. PMID 25338067 (verified: 88.8% of
    arrhythmia alarms false).
15. The Joint Commission (2013). *Sentinel Event Alert #50: Medical device alarm safety in hospitals*
    (verified via search; institutional bulletin — 98 events Jan 2009–Jun 2012, 80 deaths).
16. Parasuraman, R., & Riley, V. (1997). "Humans and automation: use, misuse, disuse, abuse." *Human Factors*
    39(2):230-253. doi:10.1518/001872097778543886 (verified: misuse=over-reliance, disuse=neglect from false
    alarms).
17. Goddard, K., Roudsari, A., & Wyatt, J. C. (2012). "Automation bias: a systematic review of frequency,
    effect mediators, and mitigators." *JAMIA* 19(1):121-127. PMID 21685142. PMC3240751 (verified).
18. Saltzer, J. H., & Schroeder, M. D. (1975). "The protection of information in computer systems." *Proc
    IEEE* 63(9):1278-1308. doi:10.1109/PROC.1975.9939 (fail-safe defaults — design principle).
19. (2025). Adversarial hallucination in clinical LLMs — multi-model assurance analysis. *Commun Med*.
    doi:10.1038/s43856-025-01021-3 (verified via search; hallucination 50–82.7% under adversarial testing).
20. (2026). Safety of an LLM-based clinical decision-support system in primary healthcare. *Nat Health*.
    doi:10.1038/s44360-026-00082-5 (verified via search; automation bias in practice; RAG does not fully fix
    miscalibration).

*Items flagged in "Open questions / unverified" (the mis-cited PMID 21962498; the autocorrelated-stream
ARL₀; un-re-fetched page numbers for Lorden/Moustakides/Roberts; recent LLM percentages; the SEA-50 bulletin)
should be treated with the stated caveats and not cited as settled.*
