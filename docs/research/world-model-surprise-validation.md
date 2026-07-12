# World-Model "Surprise" — Validation Evidence for the Weakest-Evidence Tier

**Scope.** An honest, primary-sourced audit of the evidence for a learned **novelty / "Surprise"**
signal (predictive-coding / world-model prediction error) as a detector of **physiological
deterioration in neonates**. This extends [`detection-methodology.md`](detection-methodology.md) §5
("Novelty / anomaly detection precedent") — the tier that same review rates **weakest-evidence** — and
answers the gating question for engineering issue #6: *is a per-infant "Surprise" signal defensible in
Tier 2, and under exactly what guardrails?*

**Question under review.** Not "is predictive coding elegant?" (it is) but: *is there peer-reviewed
evidence that a learned model of an infant's own normal dynamics, flagging departures as "surprise,"
detects deterioration — and how far can that be pushed before it overclaims?*

**Implementation being evidence-checked.**
- **Tier 2 backbone (issue #4, ships regardless):** a deterministic **CUSUM** "Drift" detector — the
  auditable change-detector (Page 1954), already scored **well-founded** in the methodology review.
- **Tier 2 enhancement (issue #6, under review here):** a per-infant, self-supervised **world model**.
  **Surprise** = prediction error / negative log-likelihood (NLL) of the next window under the *infant's
  own* fitted model. Fit **per infant**, **start linear** (Kalman / VAR) before any neural model. Gated
  on its own **leave-one-infant-out (LOIO)** viability test: *does Surprise rise in the lead window
  before the annotated `.atr` bradycardia events?*

**Data reality (the binding constraint).** 10 preterm infants (PICS), ~450–500 h dual-channel ECG +
respiration, **no sepsis labels**. The retired supervised ONNX classifier scored **at-random** on
held-out infants (AUC-PR ≈ 0.018 vs. 0.018 base rate; ADR-0002). Any method proposed here must survive
*that* reality: no population labels, 10 subjects, high overfitting risk.

**Date:** 2026-07-12
**Author:** Research agent (world-model / novelty-detection evidence)

---

## Bottom line (honest)

**Surprise belongs in Tier 2 — but only as a gated, escalate-only *enhancement* riding on top of the
deterministic CUSUM backbone, never as a standalone trigger and never as a risk score.** The *theory* is
strong and the *data-fit* argument (self-supervised, per-infant, no labels) is exactly right for a
10-infant cohort. The *clinical validation* of learned novelty detection as a deployed deterioration
alarm is **sparse**, and for **neonates specifically it is essentially absent** — the honest, valuable
negative finding of this review. What rescues it from "untethered" is (a) a genuine neonatal precedent
for a *per-infant generative model anticipating events with lead time* (Gee et al. 2016, on bradycardia,
same 10-infant cohort size), and (b) a clean information-theoretic bridge to the **validated** HeRO
entropy evidence: sample entropy is the model-free ancestor of Surprise.

| Claim about Surprise | Honest status |
|---|---|
| Predictive-coding "surprise" is a principled basis for a novelty signal | **Strong theory** — but a motivating analogy, not clinical proof (Friston 2010; Rao & Ballard 1999). |
| One-class / novelty modeling is the *right* tool given no labels + 10 infants | **Well-founded** — this is the textbook use-case for novelty detection (Pimentel 2014). |
| Unsupervised novelty detection is validated for patient deterioration | **Weak / sparse** — the one real deployed example is adult (Visensia/BioSign), and its real-world evidence is *limited* (NICE MIB36). Deployed EWS are overwhelmingly supervised. |
| A per-infant generative model anticipates *neonatal* events with lead time | **One good precedent** — Gee 2016 (point-process HR model, ~116 s before bradycardia, 10 infants) — but it targets **bradycardia, not sepsis**, and is a single group. |
| Surprise is tethered to validated physiology (not free-floating) | **Yes, via entropy** — SampEn falls before neonatal sepsis (Lake 2002); loss of complexity marks deterioration broadly (Lipsitz & Goldberger 1992). |
| Surprise may safely *lower* a verdict / act alone / report absolute risk | **No — do not do this** — automation-bias omission risk (Goddard 2012) + 10-infant overfitting/contamination + no labels to calibrate risk. |

**The single most important honest point:** a learned per-infant model can be *wrong in the most
dangerous direction* — it can learn a subtly deteriorating infant's dynamics **as** normal (training-window
contamination) and then fail to be surprised exactly when it should be. That single failure mode dictates
the entire guardrail: **Surprise may only escalate above the deterministic floor; it may never lower it,
and CUSUM ships regardless of whether Surprise ever passes its LOIO gate.**

---

## Decision evidence table

| Approach / claim | Adopt? | Rationale | Evidence (PMID/DOI) |
|------------------|--------|-----------|---------------------|
| Free-energy / predictive-coding "surprise" as the *conceptual* basis for a per-infant novelty signal | **Yes — as motivating framework only** | Principled account of an agent minimising the surprise (negative log-evidence) of inputs under an internal model; rising surprise = dynamics no longer fit learned normal. Honest caveat: a neuroscience *analogy*, not clinical evidence. | Friston 2010, DOI 10.1038/nrn2787; Rao & Ballard 1999, DOI 10.1038/4580 |
| Formal definition: Surprise = surprisal = **negative log-likelihood** of the next window under the infant's own model | **Yes** | Gives a precise, computable target (per-window NLL / prediction error), not a hand-wave. Surprisal = self-information = −log p(x) is standard information theory. | Shannon 1948, *Bell Syst Tech J* 27:379-423; Friston 2010, DOI 10.1038/nrn2787 |
| **One-class / novelty modeling** given no sepsis labels + 10 infants | **Yes** | Novelty detection is *defined* as the tool for when abnormal data are too scarce to model explicitly — precisely our situation. Sidesteps the label scarcity that sank the supervised classifier. | Pimentel, Clifton, Clifton & Tarassenko 2014, *Signal Processing* 99:215-249 |
| Unsupervised novelty detection as a **deployed deterioration alarm** | **Adopt only as a gated adjunct** | The one genuine deployed example (Visensia/BioSign) models population "normality" and flags departures — but its real-world evidence is explicitly *limited*, and it is adult, population- (not self-) referenced. Do not present as settled practice. | Tarassenko, Hann & Young 2006, PMID 16707529; Hravnak et al. 2008, PMID 18574087; Hravnak et al. 2011, PMID 20935559; NICE MIB36 (2015) |
| A **per-infant generative model** anticipating neonatal events with lead time | **Yes — strongest precedent** | Gee 2016: per-infant point-process (lognormal RR) model; instantaneous variance rises ~80 s before, and forecasts severe bradycardia ~116 s before onset, in the **same 10-infant cohort size**. This is a per-infant world model anticipating an event — the exact shape of issue #6. Caveat: targets **bradycardia, not sepsis**; single group; AUC 0.79 / FPR 0.15. | Gee, Barbieri, Paydarfar & Indic 2016, PMID 27898379, DOI 10.1109/TBME.2016.2632746 |
| Surprise is **tethered to a validated metric** (sample entropy is its model-free ancestor) | **Yes — the honest bridge** | SampEn = −log conditional probability that similar sequences stay similar = a model-free surprisal. "Entropy falls before clinical signs of neonatal sepsis" (validated). Loss of complexity marks deterioration broadly. So Surprise generalises an already-validated idea. | Lake, Richman, Griffin & Moorman 2002, PMID 12185014; Richman & Moorman 2000, DOI 10.1152/ajpheart.2000.278.6.H2039; Lipsitz & Goldberger 1992, PMID 1482430 |
| **Escalate-only** guardrail: Surprise may raise but **never lower** the verdict below the floor | **Yes — mandatory** | Automation bias → omission errors: clinicians miss real deterioration when an automated cue falsely reassures. A learned, possibly-overfit per-infant model must never be allowed to *reduce* concern. | Goddard, Roudsari & Wyatt 2012, PMID 21685142 |
| **CUSUM (#4) ships regardless** as the auditable Tier-2 backbone | **Yes — mandatory** | Deterministic, inspectable, tunable via ARL, decades of clinical pedigree — the opposite of a black-box per-infant model. Surprise is an adjunct *on top of* it, gated on LOIO. | Page 1954, DOI 10.1093/biomet/41.1-2.100 (full pedigree in methodology review §2) |
| **Start linear** (Kalman / VAR) before any neural world model | **Yes** | On 10 infants a high-capacity model will memorise; a linear per-infant predictor is inspectable, cheap, and its NLL is a clean surprisal. Escalate to neural only if the linear LOIO test is promising. | Pimentel 2014 (model-complexity vs. data); in-repo ADR-0002 (supervised overfit at-random) |
| Surprise as a **standalone trigger / sole verdict** | **No** | The retired supervised path already showed what "trust the learned model alone" buys on this data: random performance on held-out infants. Compounded by automation-bias risk. | In-repo ADR-0002 (AUC-PR ≈ 0.018); Goddard 2012, PMID 21685142 |
| Surprise as an **absolute risk score** ("this = X% sepsis probability") | **No** | With no sepsis labels and 10 infants there is nothing to calibrate an absolute risk against. Surprise is an *abnormality* signal, not a *risk* signal — the same honesty line the review draws for Tier-1 z-scores vs. HeRO's fitted risk. | Contrast HeRO's outcome-calibrated model, Griffin et al. 2005, PMID 16402612 (see methodology §3.4) |

---

## 1. Theoretical basis — what "Surprise" formally is, and its honest status

### 1.1 The free-energy / predictive-coding account
The world-model framing descends from **predictive coding** — feedback carries *predictions* of lower-level
activity, feedforward carries the *residual prediction errors* (**Rao, R. P. N. & Ballard, D. H. (1999).
"Predictive coding in the visual cortex…" *Nat Neurosci* 2(1):79-87. doi:10.1038/4580**) — and from the
**free-energy principle**, in which an agent minimises the **surprise** (negative log-evidence) of its
sensory inputs under an internal generative model (**Friston, K. (2010). "The free-energy principle: a
unified brain theory?" *Nat Rev Neurosci* 11(2):127-138. doi:10.1038/nrn2787**). Mapped to NeonatalGuard:
the infant's own fitted model *is* the generative model; a window that fits it poorly is *surprising*;
rising surprise = the infant's dynamics have departed from their learned normal.

### 1.2 A precise, computable definition (not a metaphor)
Formally, **surprisal** is Shannon self-information, the negative log-probability of an outcome
(**Shannon, C. E. (1948). "A mathematical theory of communication." *Bell System Technical Journal*
27:379-423, 623-656**). For a per-infant generative model with parameters θ_i fitted on infant *i*'s own
history, the operational Surprise of the next window *x_t* is its **negative log-likelihood**:

> `Surprise_i(t) = −log p(x_t | x_<t , θ_i)`  ≡  per-window prediction error / negative log-evidence.

For a **linear** model (Kalman filter / VAR) this is available in closed form as the normalised innovation
(the standardised one-step-ahead residual): a Mahalanobis distance of the prediction error under the
model's predicted covariance. That is the honest first implementation — no neural network required — and
it makes "Surprise" an auditable number, not a black box.

> **Mapping to NeonatalGuard.**
> - **SUPPORTS (theory):** Friston/Rao-Ballard give a principled, quantitatively precise target (per-window
>   NLL). Starting with a Kalman/VAR innovation keeps that target inspectable and cheap — right for 10 infants.
> - **DIVERGES / honesty:** the free-energy principle is a *theory of brains*, not clinical evidence that
>   surprise predicts neonatal deterioration. It motivates the signal; it does **not** validate it. State
>   this plainly in the pitch — do not let "grounded in the free-energy principle" read as clinical proof.

---

## 2. Validated use in patient deterioration — searched honestly, mostly negative

### 2.1 Novelty detection *is* the correct tool for our data — that much is well-founded
"Novelty detection… is typically used when the quantity of available 'abnormal' data is insufficient to
construct explicit models for non-normal classes" — a model of *normal* is built, and departures are
flagged (**Pimentel, M. A. F., Clifton, D. A., Clifton, L. & Tarassenko, L. (2014). "A review of novelty
detection." *Signal Processing* 99:215-249**). This is a near-exact description of NeonatalGuard's bind:
595 positive windows at a 0.4% base rate across 10 infants cannot support a supervised model (ADR-0002),
so modelling each infant's *normal* and scoring departures is the methodologically appropriate move. So
the *choice of paradigm* is defensible.

### 2.2 But a *deployed, validated* unsupervised deterioration alarm is essentially one system — and it is adult
The clearest real-world instance of the novelty-detection paradigm for patient deterioration is the Oxford
group's **BioSign / Visensia**: a probabilistic model of *normal* multi-parameter vital signs (HR, BP,
SpO₂, respiration, temperature) learned from a patient population, generating a single "Patient Status /
Safety Index" and alerting when a patient departs from normality (**Tarassenko, L., Hann, A. & Young, D.
(2006). "Integrated monitoring and analysis for early warning of patient deterioration." *Br J Anaesth*
97(1):64-68. PMID 16707529**). Independent evaluation in step-down units (Hravnak et al., University of
Pittsburgh) linked the Visensia index to clinically-adjudicated cardiorespiratory instability and used it
to characterise instability incidence and monitoring impact (**Hravnak et al. 2008, PMID 18574087**;
**Hravnak et al. 2011, *Crit Care Med* 39(1):65-72, PMID 20935559**).

Two honesty flags, both material:
1. **It is population-referenced, not per-infant self-referenced.** Visensia learns "normal" from a
   *population* and is a *supervised-adjacent* calibration exercise; NeonatalGuard's Surprise learns normal
   from *one infant's own* stream. Visensia validates the *paradigm* (model-of-normal → flag departures),
   not our specific self-supervised, per-subject variant.
2. **Its real-world evidence is limited.** NICE's Medtech innovation briefing concluded the evidence base
   for Visensia is limited in quantity/quality (**NICE MIB36, 2015**). This is not a system with an
   HeRO-style RCT behind it. Do not borrow strength it does not have.

### 2.3 Everything else deployed for deterioration is supervised
Consistent with methodology §5: the trial-validated and commercial neonatal system (HeRO) is a
**supervised** logistic-regression fold-risk model; recent neonatal-sepsis ML (e.g., XGBoost on 865
infants, ~69–81% sensitivity) and apnea/bradycardia predictors are **supervised** on labelled events. No
search returned a **validated unsupervised/self-supervised neonatal deterioration-warning system**.

> **Mapping to NeonatalGuard.**
> - **SUPPORTS (paradigm):** novelty detection is the right family for a no-label, 10-infant cohort
>   (Pimentel 2014), and it *has* been fielded for adult deterioration (Visensia).
> - **DIVERGES / weakest-evidence tier (state plainly):** there is **no validated neonatal unsupervised
>   deterioration alarm** in the literature, and the one adult exemplar has only *limited* evidence. This
>   is absence-of-strong-evidence, not proof it cannot work — but Surprise must therefore ship *gated and
>   subordinate*, not as a validated detector.

---

## 3. The neonatal precedent that actually matters — Gee et al. 2016

The closest thing to a proof-of-concept for issue #6 is not a "surprise" paper at all, but a per-infant
**generative model of heart rate that anticipates neonatal events with lead time**:

**Gee, A. H., Barbieri, R., Paydarfar, D. & Indic, P. (2016). "Predicting Bradycardia in Preterm Infants
Using Point Process Analysis of Heart Rate." *IEEE Trans Biomed Eng.* PMID 27898379.
doi:10.1109/TBME.2016.2632746.** Key facts, and why each matters here:
- **Per-infant generative model.** A point-process model with a **lognormal** inter-beat-interval
  distribution, yielding instantaneous mean *M(t)* and variance *V(t)* — a fitted model of the infant's
  own HR dynamics, exactly the object issue #6 proposes (start-linear).
- **Model state shifts *before* the event.** "The average instantaneous variance increases ~80 s prior to
  severe bradycardia"; the algorithm forecasts bradycardia **~116 s** before onset (range 39–179 s). A
  departure in the model's own fit precedes the clinical event — the operational content of "Surprise rises
  in the lead window."
- **Same cohort scale.** **10 preterm infants**, **444 bradycardia events**, AUC **0.79**, FPR **0.15**.
  This is direct evidence that a per-infant model on a 10-infant PICS-scale cohort can carry real lead-time
  signal — precisely the LOIO viability question for issue #6.

Honesty flags: (a) it targets **bradycardia**, the same `.atr` event we validate against — **not sepsis**;
(b) it is a **single group's** work, not deployed or independently replicated; (c) it uses variance/point-
process statistics, not a full NLL "surprise," so it is a *cousin* of the proposed signal, not the identical
method; (d) AUC 0.79 with FPR 0.15 is useful-but-imperfect, not a solved problem.

> **Mapping to NeonatalGuard.**
> - **SUPPORTS (strongest available):** a per-infant generative model *does* anticipate the exact event class
>   (bradycardia) we hold out for validation, at our exact cohort scale, with clinically-meaningful lead time.
>   This is why issue #6's LOIO gate (does Surprise rise before `.atr` bradycardias?) is a *reasonable* bet,
>   not a shot in the dark.
> - **DIVERGES / scope discipline:** bradycardia-anticipation ≠ sepsis-detection. Gee 2016 licenses the claim
>   "a per-infant model can anticipate neonatal bradycardia events"; it does **not** license "Surprise detects
>   sepsis." Keep those claims separate. The bradycardia LOIO test is a *viability proxy*, not a sepsis result.

---

## 4. The link to Drift — Surprise is a learned analogue of sample entropy

The charge against Surprise is that it is untethered novelty. It is not — and the tether is
information-theoretic, running straight back to the **validated** HeRO evidence base.

### 4.1 Sample entropy is the model-free ancestor of Surprise
SampEn is defined as the **negative log conditional probability** that two sequences similar within
tolerance *r* for *m* points remain similar at the next point (**Richman, J. S. & Moorman, J. R. (2000).
*Am J Physiol Heart Circ Physiol* 278(6):H2039-H2049. doi:10.1152/ajpheart.2000.278.6.H2039**). That *is*
a surprisal: "how unpredictable is the next sample given the recent past." SampEn does it **model-free**
(pattern-counting); world-model Surprise does the same job with a **fitted per-infant generative model**
(NLL). They are two points on one continuum — predictability of the next sample — with Surprise the learned
generalisation.

### 4.2 The predictability signature already moves before neonatal deterioration (validated)
- **Neonatal sepsis:** "entropy falls before clinical signs of neonatal sepsis" (**Lake, D. E., Richman,
  J. S., Griffin, M. P. & Moorman, J. R. (2002). "Sample entropy analysis of neonatal heart rate
  variability." *Am J Physiol Regul Integr Comp Physiol* 283(3):R789-R797. PMID 12185014**). The
  predictability structure of the RR series shifts *ahead of* clinical signs — the validated core of HeRO.
- **General principle:** loss of physiologic complexity accompanies illness and reduced adaptive capacity
  (**Lipsitz, L. A. & Goldberger, A. L. (1992). "Loss of 'complexity' and aging…" *JAMA* 267(13):1806-1809.
  PMID 1482430**). "Deterioration changes signal predictability" is a broad, established idea, not a
  NeonatalGuard invention.

### 4.3 The honest direction caveat (do not paper over it)
The *direction* of the predictability shift is **event- and timescale-specific**, and the two neonatal
precedents point opposite ways at first glance:
- Before **sepsis** (slow), SampEn **falls** (signal more regular) — Lake 2002.
- Before **bradycardia** (acute), point-process variance **rises** — Gee 2016.

These are not contradictory: they are different targets, and Lake 2002 itself flags that the entropy fall
is driven partly by deceleration *spikes* (the very events that precede bradycardia). The resolution is the
reason the *learned* signal is worth having: **Surprise is NLL against the infant's own normal, so it rises
for departure in *either* direction** — a signal that becomes anomalously *regular* is still surprising to a
model that learned what that infant's normal irregularity looks like. (Note the contrast with the Tier-1
`abs(z)` critique in methodology §1.3: two-sidedness is *defensible here* because the reference is a learned
model of normal, not a raw magnitude.) But this is exactly why the **direction of Surprise must be validated
per-target, empirically, by the LOIO test** — not assumed.

> **Mapping to NeonatalGuard.**
> - **SUPPORTS:** Surprise inherits legitimacy from SampEn — same information-theoretic quantity
>   (predictability of the next sample), and the validated neonatal literature already shows that quantity
>   moves before deterioration (Lake 2002). Surprise is *not* untethered novelty.
> - **DIVERGES / must-verify:** the *sign and lead time* of Surprise for our `.atr` bradycardia target are an
>   empirical question. Gee 2016 predicts a *rise* ~80–116 s ahead; the LOIO test must confirm that on our
>   own data before Surprise influences any verdict. Report the observed lead-time distribution, as Gee did.

---

## 5. Guardrails — the evidence-based case for escalate-only + CUSUM backbone

### 5.1 Escalate-only: a learned model may raise concern, never lower it
The dominant risk of an automated cue is **omission error** — clinicians failing to catch the automation's
error, i.e., under-reacting when the system falsely reassures. The systematic review of automation bias
across 74 studies documents both omission and commission errors and the over-trust that drives them
(**Goddard, K., Roudsari, A. & Wyatt, J. C. (2012). "Automation bias: a systematic review of frequency,
effect mediators, and mitigators." *JAMIA* 19(1):121-127. PMID 21685142**). Applied here: if a per-infant
Surprise model — possibly overfit, possibly contaminated — were permitted to *lower* a verdict below the
deterministic floor, a low-surprise reading could quietly cancel a real Tier-1/CUSUM concern, producing
exactly the omission error automation bias predicts. Therefore Surprise is **strictly additive**: it may
escalate YELLOW→RED, never de-escalate below the floor. This is the same Safety-Floor doctrine CONTEXT.md
already encodes, now with an automation-bias citation behind it.

### 5.2 The specific 10-infant failure mode: training-window contamination
Self-supervised per-infant fitting sidesteps *population* overfitting (no shared weights to overfit the
cohort — ADR-0002's rationale). But it introduces a distinct hazard: if an infant's training window already
contains sub-clinical deterioration, the model learns the abnormal pattern **as** normal, and Surprise stays
low precisely when it should spike — a **false reassurance**. There are no sepsis labels and only 10 infants
to detect or correct this. This hazard is a second, independent argument for **escalate-only** (a
falsely-low Surprise then simply does nothing, rather than cancelling the floor) and for **starting linear**
(a low-capacity model contaminates less catastrophically and its innovations are inspectable).

### 5.3 CUSUM is the auditable backbone that ships regardless
CUSUM (**Page 1954, doi:10.1093/biomet/41.1-2.100**) is deterministic, ARL-tunable, and clinically
pedigreed (methodology §2) — everything a learned per-infant model is not. HeRO itself ships as an FDA
510(k) Class II **adjunct display**, not a diagnostic (README synthesis); the defensible posture for an
*unproven learned signal* is stricter still. So the architecture is: **CUSUM (#4) is the Tier-2 signal that
ships**; **Surprise (#6) is an enhancement gated on passing its LOIO viability test**, and even then only
escalates. If Surprise never passes LOIO, Tier 2 still ships — unchanged — on CUSUM. That decoupling is the
honest, regulator-shaped way to field a research-frontier signal.

> **Mapping to NeonatalGuard.**
> - **SUPPORTS:** escalate-only + deterministic backbone is not defensive hand-waving — it is the direct
>   mitigation for the two documented risks (automation-bias omission; small-cohort/contamination overfit).
> - **DIVERGES from any "let the model decide" framing:** the retired supervised path is the cautionary tale
>   (random on held-out infants, ADR-0002). Surprise gets *less* trust than that model had, not more, until
>   its own LOIO evidence exists.

---

## Confidence & conflicting evidence

- **High confidence:** the *theoretical* basis (Friston 2010; Rao & Ballard 1999; Shannon 1948) and that
  novelty detection is the appropriate paradigm for a no-label, 10-infant cohort (Pimentel 2014). The
  neonatal per-infant precedent (Gee 2016) and its numbers (10 infants, ~116 s lead, AUC 0.79) are directly
  sourced. The entropy tether (Richman-Moorman 2000; Lake 2002) and the automation-bias basis for
  escalate-only (Goddard 2012) are directly sourced.
- **Medium confidence:** that Visensia/BioSign is the *best* deployed exemplar of unsupervised deterioration
  detection — it is the clearest one found, but it is population-referenced and its real-world evidence is
  *limited* (NICE MIB36); do not over-read it.
- **Honest tension #1 (direction):** SampEn *falls* before sepsis (Lake 2002) but point-process variance
  *rises* before bradycardia (Gee 2016). Reconciled in §4.3 (different targets; learned NLL is two-sided),
  but the sign/lead-time of *our* Surprise on *our* `.atr` events is unproven and must be measured, not assumed.
- **Honest tension #2 (paradigm vs. instance):** the paradigm (model-of-normal → flag departures) is
  well-founded and fielded; the *specific* self-supervised, per-infant, sepsis-oriented instance we propose is
  **not** independently validated. We inherit the paradigm's credibility, not a clinical result.
- **Weakest evidence (stated plainly):** there is **no validated neonatal unsupervised/self-supervised
  deterioration-warning system** in the literature searched. This is the honest core finding. It does not
  forbid the approach; it *mandates* the guardrails (gated, escalate-only, CUSUM-backed).
- **Not found (so stated):** any peer-reviewed system that (a) is unsupervised/self-supervised, (b) is
  neonatal, and (c) has validated deterioration-*warning* performance. Absence of evidence, not evidence of
  absence — but we must not imply a validation we could not find.

---

## Verdict — does Surprise belong in Tier 2, and under what guardrails?

**Yes — conditionally, and subordinately.** Surprise belongs in Tier 2 as a **gated, escalate-only
enhancement** to the deterministic CUSUM backbone, justified by strong theory (Friston; Rao-Ballard;
Pimentel's novelty-detection paradigm being the correct tool for a no-label 10-infant cohort) and by one
solid neonatal precedent (Gee 2016: a per-infant generative model anticipating bradycardia at our cohort
scale). It does **not** belong there as a validated detector, a standalone trigger, or a risk score — the
clinical evidence for unsupervised deterioration detection is sparse and, for neonates specifically, absent.

**The guardrails are not optional — they are the reason it is defensible to ship at all:**
1. **Escalate-only.** Surprise may raise the verdict above the deterministic floor; it may **never** lower it
   (automation-bias omission risk — Goddard 2012; contamination false-reassurance risk).
2. **CUSUM (#4) ships regardless.** The auditable, ARL-tunable change-detector (Page 1954) is the Tier-2
   backbone; Surprise is an adjunct on top of it. If Surprise never passes its gate, Tier 2 still ships.
3. **Gated on LOIO viability.** Surprise influences no verdict until it demonstrably rises in the lead window
   before held-out `.atr` bradycardia events (the Gee-2016-shaped test), with its lead-time distribution
   reported.
4. **Start linear.** Kalman/VAR innovation (a closed-form NLL) before any neural model — inspectable, cheap,
   contamination-resistant on 10 infants.
5. **Abnormality, not risk.** With no labels and 10 infants, Surprise is a *departure-from-own-normal* signal,
   never an absolute sepsis probability — the same honesty line drawn for Tier-1 z-scores vs. HeRO's fitted risk.
6. **Bradycardia viability ≠ sepsis validation.** Passing the LOIO bradycardia test licenses "the per-infant
   model carries lead-time signal," not "Surprise detects sepsis." Keep the claims separate in the pitch.

---

## Open questions / unverified

- **DOI strings not individually re-fetched this session** were taken from standard bibliographic records;
  the *anchor identifier* verified by direct lookup on 2026-07-12 is given for each. Specifically verified
  this session by search/fetch: Rao & Ballard **doi:10.1038/4580**; Pimentel 2014 *Signal Processing*
  **99:215-249**; Tarassenko **PMID 16707529** (*BJA* 97(1):64-68); Hravnak **PMID 18574087** and **PMID
  20935559** (*Crit Care Med* 39(1):65-72); Gee **PMID 27898379 / doi:10.1109/TBME.2016.2632746**; Goddard
  **PMID 21685142** (*JAMIA* 19(1):121-127); Lipsitz & Goldberger **PMID 1482430** (*JAMA* 267(13):1806-1809).
  Friston 2010 (**doi:10.1038/nrn2787**), Richman & Moorman 2000, Lake 2002 (**PMID 12185014**) and Page 1954
  are carried from the companion `detection-methodology.md` (verified there 2026-07-12), not re-fetched here.
- **Exact Hravnak 2008 vol/pages** (*Arch Intern Med*) were not machine-confirmed beyond PMID 18574087; cite
  by PMID. The NICE Visensia briefing is **MIB36 (2015)**; the precise "limited evidence" wording should be
  quoted from the primary NICE page before use in the pitch. Marked **[UNVERIFIED — exact wording]**.
- **No validated neonatal unsupervised/self-supervised deterioration system** was found. If one exists, it
  eluded this search; treat the negative finding as current-best, not exhaustive. Marked
  **[UNVERIFIED — absence]** (a bounded literature search, not a systematic review).
- **Gee 2016 uses point-process variance, not an NLL "surprise."** The equivalence to our per-window NLL is a
  reasoned analogy (both are per-infant model-fit departures), not a claim the two metrics are identical.
- **The sign and lead time of Surprise on our `.atr` bradycardia events are unmeasured.** Gee 2016 predicts a
  *rise* ~80–116 s ahead; our LOIO test must confirm direction, magnitude, and lead-time on our own data
  before Surprise is wired into any verdict. This is the deliverable of issue #6, not an assumption of this review.

---

## References

**Theoretical basis (predictive coding / free-energy / information theory)**
1. Friston, K. (2010). "The free-energy principle: a unified brain theory?" *Nat Rev Neurosci* 11(2):127-138.
   doi:10.1038/nrn2787. (Surprise = negative log-evidence minimised under an internal model.)
2. Rao, R. P. N. & Ballard, D. H. (1999). "Predictive coding in the visual cortex: a functional interpretation
   of some extra-classical receptive-field effects." *Nat Neurosci* 2(1):79-87. doi:10.1038/4580. (Feedforward
   = prediction error; feedback = prediction.)
3. Shannon, C. E. (1948). "A mathematical theory of communication." *Bell System Technical Journal*
   27:379-423, 623-656. (Surprisal / self-information = −log p.)

**Novelty detection — paradigm and deployed patient-deterioration use**
4. Pimentel, M. A. F., Clifton, D. A., Clifton, L. & Tarassenko, L. (2014). "A review of novelty detection."
   *Signal Processing* 99:215-249. (Novelty detection = model-of-normal, for when abnormal data are scarce.)
5. Tarassenko, L., Hann, A. & Young, D. (2006). "Integrated monitoring and analysis for early warning of
   patient deterioration." *Br J Anaesth* 97(1):64-68. PMID 16707529. (BioSign/Visensia — probabilistic model
   of normal vital signs, flags departures.)
6. Hravnak, M., et al. (2008). "Defining the incidence of cardiorespiratory instability in patients in
   step-down units using an electronic integrated monitoring system." *Arch Intern Med.* PMID 18574087.
7. Hravnak, M., et al. (2011). "Cardiorespiratory instability before and after implementing an integrated
   monitoring system." *Crit Care Med* 39(1):65-72. PMID 20935559.
8. NICE (2015). Medtech innovation briefing **MIB36**, "Visensia for early detection of deteriorating vital
   signs in adults in hospital." (Evidence base judged *limited*.)

**Neonatal per-infant generative-model precedent**
9. Gee, A. H., Barbieri, R., Paydarfar, D. & Indic, P. (2016). "Predicting Bradycardia in Preterm Infants Using
   Point Process Analysis of Heart Rate." *IEEE Trans Biomed Eng.* PMID 27898379. doi:10.1109/TBME.2016.2632746.
   (Per-infant lognormal RR point-process model; variance rises ~80 s before, forecast ~116 s before severe
   bradycardia; 10 infants, 444 events, AUC 0.79, FPR 0.15.)

**The entropy tether (Surprise ↔ validated predictability signature)**
10. Richman, J. S. & Moorman, J. R. (2000). "Physiological time-series analysis using approximate entropy and
    sample entropy." *Am J Physiol Heart Circ Physiol* 278(6):H2039-H2049. doi:10.1152/ajpheart.2000.278.6.H2039.
    (SampEn = −log conditional probability of continued similarity.)
11. Lake, D. E., Richman, J. S., Griffin, M. P. & Moorman, J. R. (2002). "Sample entropy analysis of neonatal
    heart rate variability." *Am J Physiol Regul Integr Comp Physiol* 283(3):R789-R797. PMID 12185014. ("Entropy
    falls before clinical signs of neonatal sepsis.")
12. Lipsitz, L. A. & Goldberger, A. L. (1992). "Loss of 'complexity' and aging. Potential applications of
    fractals and chaos theory to senescence." *JAMA* 267(13):1806-1809. PMID 1482430. (Loss of physiologic
    complexity accompanies illness / reduced adaptive capacity.)

**Guardrails (automation bias; auditable backbone)**
13. Goddard, K., Roudsari, A. & Wyatt, J. C. (2012). "Automation bias: a systematic review of frequency, effect
    mediators, and mitigators." *JAMIA* 19(1):121-127. PMID 21685142. (Omission/commission errors from
    over-trust in automated cues — basis for escalate-only.)
14. Page, E. S. (1954). "Continuous inspection schemes." *Biometrika* 41(1-2):100-115.
    doi:10.1093/biomet/41.1-2.100. (CUSUM — the auditable Tier-2 backbone; full pedigree in methodology §2.)

**In-repo evidence (cited, not external)**
15. ADR-0002, "The world model replaces the supervised classifier as Tier 2" (2026-07-12). (Supervised ONNX
    classifier scored at-random on held-out infants, AUC-PR ≈ 0.018; per-infant self-supervised model as the
    label-scarcity-robust alternative.)
16. `detection-methodology.md` §2 (CUSUM), §3 (HeRO/entropy/asymmetry), §5 (novelty precedent) and README
    synthesis (HeRO 510(k) adjunct posture) — the companion evidence base this review extends.

*Items explicitly flagged in-text as **[UNVERIFIED]** (the exact NICE MIB36 wording; the absence of any
validated neonatal unsupervised deterioration system; exact Hravnak 2008 vol/pages) could not be fully
confirmed from primary sources on 2026-07-12 and should not be cited as established.*
