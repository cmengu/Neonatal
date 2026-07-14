# Detection Methodology — Statistical Defensibility Review

**Scope.** An honest, primary-sourced audit of the statistical methods behind NeonatalGuard's
detection tiers, for the clinical pitch. Question under review: *are our specific thresholds and
methods scientifically defensible, and where are they validated vs. mere convention?*

**Implementation under review.**
- **Tier 1 (Deviation, live in code):** personalized z-scores of 10 time-domain HRV features vs. the
  infant's own rolling baseline; `max|z|` mapped to concern — `|z|>=2 -> YELLOW`, `|z|>=3 -> RED`;
  **direction discarded** (uses `abs`); instantaneous/stateless; acts as the deterministic **Safety Floor**.
  (Source: `src/assessment/deviation.py`, features `src/features/constants.py`.)
- **Tier 2 (planned):** deterministic **CUSUM** "Drift" detector + a learned **world-model** "Surprise" signal.

**Date:** 2026-07-12
**Author:** Research agent (statistical methodology)

---

## Bottom line (honest)

| Choice | Status | One-line verdict |
|---|---|---|
| 3-sigma as the "hard" limit | **Reasonable convention, not clinical** | Shewhart's 3σ was chosen as "an acceptable economic value," justified by "empirical evidence that it works" — an engineering default, never derived from neonatal physiology. |
| 2-sigma as the "warning" limit | **Reasonable convention, not clinical** | Comes from the Western Electric zone rules (1956), another SPC convention for factory charts. |
| `|z|>=2 / |z|>=3` on HRV features as a *sepsis* threshold | **Not clinically validated (weak)** | No neonatal study validates fixed per-feature sigma cut-offs for sepsis. The validated system (HeRO) does something materially different (below). Our cut-offs are generic statistics, not clinical evidence. |
| `max|z|` over 10 correlated features | **Weak (false-positive inflation)** | Taking the max of 10 tests inflates the alarm rate well above the nominal per-feature 5%/0.3%. A multivariate statistic or a persistence rule is more defensible. |
| Discarding direction (two-sided `abs`) | **Weak / clinically questionable** | The pathological direction is *reduced* variability + *decelerations*. Firing RED on an *increase* in variability is a likely false alarm. HeRO is directional. |
| Per-infant baseline (vs. population norm) | **Directionally supported** | "Change from a patient's own baseline" is a recognised monitoring principle, but neonatal HRV is strongly non-stationary (matures with age, circadian), so the baseline must adapt. |
| CUSUM for Tier-2 drift | **Well-founded** | Page (1954) is the canonical change-detector; CUSUM has real clinical pedigree (surgical/quality monitoring). Good choice — if tuned via ARL. |
| Learned world-model "Surprise" | **Promising but largely unproven** | The idea (predictive-coding "surprise") is principled, but validated *unsupervised* deterioration detectors are sparse; deployed systems are overwhelmingly *supervised*. |

**The single most important honest point for the pitch:** the number "2" in the validated neonatal
literature (HeRO/HRC index > 2) means a **two-fold increase in *risk*** from a logistic-regression model
trained against real sepsis outcomes — **not** two standard deviations of an HRV feature. Our `z>=2` and
the clinical `HRC index > 2` are different quantities. We should not imply our sigma thresholds inherit
HeRO's clinical validation; they do not.

---

## 1. Z-score / sigma thresholds

### 1.1 Origin of the 3-sigma rule (Shewhart)
The control chart and the 3-sigma limit come from **Walter A. Shewhart, *Economic Control of Quality of
Manufactured Product*, Van Nostrand, 1931** (preceded by Shewhart, *Bell System Technical Journal* 9(2):364-389,
1930, doi:10.1002/j.1538-7305.1930.tb00373.x). The 3σ multiplier was **not** mathematically derived:
Shewhart set limits at 3σ because 3.0 "seems to be an acceptable economic value," justified by "empirical
evidence that it works" — i.e., an economic trade-off between false alarms and missed shifts, not a
distributional or clinical argument (summarised at SPC for Excel, *Three Sigma Limits and Control Charts*,
https://www.spcforexcel.com/knowledge/control-chart-basics/three-sigma-limits-control-charts/; Wikipedia,
*Walter A. Shewhart*, https://en.wikipedia.org/wiki/Walter_A._Shewhart). Under a Normal model, 3σ corresponds
to a ~0.27% two-sided false-alarm rate per point, which is the actual meaning of our RED gate under
Gaussian assumptions.

### 1.2 The 2-sigma "warning" limit (Western Electric rules)
The 2σ "warning" concept is from the **Western Electric Company, *Statistical Quality Control Handbook*,
1st ed., 1956** (AT&T/Western Electric, Indianapolis). It divides the chart into 1σ/2σ/3σ zones and adds
"runs" rules — e.g., *2 of 3 consecutive points beyond 2σ on the same side*, *4 of 5 beyond 1σ* — to catch
smaller sustained shifts the bare 3σ line misses (Wikipedia, *Western Electric rules*,
https://en.wikipedia.org/wiki/Western_Electric_rules). Note two facts relevant to us: (a) the WE rules use
2σ **in combination with persistence** (2-of-3, runs), never a single point at 2σ as an action limit; and
(b) applying multiple such rules inflates the false-alarm rate (the classic figure is ~1 alarm per ~91.75
points when all four rules run together).

### 1.3 Is there ANY clinical/neonatal literature using `|z|>=2` or `|z|>=3` on HRV features for sepsis?
**Searched honestly; answer: no direct validation found.** The neonatal-sepsis HRV literature does not
threshold individual HRV features at a fixed number of standard deviations. Instead it:
- computes a small set of *purpose-built* heart-rate-characteristic (HRC) metrics, and
- combines them in a **multivariable logistic regression** whose output is a **fold-increase in risk**,
  reported as the "HRC index"/HeRO score (Griffin et al., *Pediatrics* 2005; Moorman et al., *Physiol Meas*
  2011 — see §3).

Where a "2" appears clinically, it is a **risk** cut, not a sigma cut: an *HRC index > 2* means ≥2× the
average risk of sepsis, and a rise in the HRC index is associated with late-onset neonatal sepsis
(Fairchild, K. D. (2013), "Predictive monitoring for early detection of sepsis in neonatal ICU patients,"
*Curr Opin Pediatr* 25(2):172-179, doi:10.1097/MOP.0b013e32835e8fe6, PMID 23407184). *(A secondary search
summary reported specific figures of OR ≈ 7.1 (95% CI 2.6-19.0) and sensitivity/specificity ≈ 53%/79% for
HRC index > 2; I could not confirm those exact numbers in the primary article and mark them **unverified**.)*
**So our z=2/z=3 cut-offs carry generic SPC provenance, not neonatal clinical validation.**

> **Mapping to NeonatalGuard.**
> - **DIVERGES** from the validated clinical method: HeRO does not use per-feature sigma thresholds. Our
>   `z>=2/z>=3` are Shewhart/Western-Electric conventions transplanted onto physiology.
> - **Defensible reframing:** present Tier 1 honestly as a *deterministic SPC-style Safety Floor* (a
>   generic abnormality gate), not as a validated sepsis detector. That is an accurate and still-valuable claim.
> - **DIVERGES (multiple comparisons):** `max|z|` over 10 features is 10 simultaneous 2σ tests. Under
>   independent Gaussians the chance that *at least one* exceeds |z|>=2 is `1-(0.9545)^10 ≈ 37%`, and for
>   |z|>=3 it is `1-(0.9973)^10 ≈ 2.7%` — far above the per-feature 4.6%/0.27%. The 10 HRV features are
>   also strongly correlated (e.g., `sdnn`, `rmssd`, `rr_ms_*` percentiles), so the true rate sits somewhere
>   between the per-feature and the independent-max figures, but it is *above* nominal. **Defensible fixes:**
>   (a) a single multivariate distance (Mahalanobis / Hotelling T²) instead of `max|z|`; (b) a Bonferroni/
>   Šidák-adjusted per-feature limit if features are kept separate; or (c) a **persistence** requirement
>   (fire only if the limit is breached in *k of the last n* windows) — exactly the Western-Electric-runs
>   / CUSUM idea, and the cheapest robust upgrade.
> - **DIVERGES (direction):** discarding sign means an infant whose SDNN/RMSSD/entropy *rises* can trip RED,
>   which is not the sepsis phenotype (reduced variability + decelerations). **Defensible fix:** make the
>   gate one-sided per feature in the clinically meaningful direction (low SDNN/RMSSD/pNN50/entropy; and
>   deceleration-side asymmetry), or at minimum weight the pathological direction.

---

## 2. CUSUM and related change-detection (planned Tier-2 "Drift")

### 2.1 CUSUM origin
**Page, E. S. (1954). "Continuous inspection schemes." *Biometrika* 41(1-2):100-115.
doi:10.1093/biomet/41.1-2.100.** This is the canonical origin of the cumulative-sum chart. Page's scheme
accumulates deviations from a target so that small, sustained shifts (which a Shewhart chart is slow to
catch) trigger quickly; it was inspired by Wald's sequential probability ratio test
(https://www.scienceopen.com/document?vid=224e2c81-6327-4838-b2e9-78a006610245). CUSUM is provably optimal
(minimises average detection delay for a target shift size) — the right tool for *slow drift*, which is
precisely NeonatalGuard's Tier-2 "Drift" definition ("no single window trips a threshold but the cumulative
trend is abnormal").

### 2.2 Tuning parameters that matter: reference value *k* and decision interval *h*
Standard SPC guidance (NIST/SEMATECH *e-Handbook of Statistical Methods* §6.3.2.3,
https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc3231.htm; Montgomery, *Introduction to Statistical
Quality Control*):
- **k (reference value / "slack"):** set to **half the shift you want to detect**, in σ units:
  `k = δ/2` where δ is the target shift (a common default is `k = 0.5σ` to detect a 1σ shift). Larger k =
  less sensitive to small drifts.
- **h (decision interval):** the alarm threshold on the accumulated sum, typically **h ≈ 4-5σ**.
- **Selection is via Average Run Length (ARL):** choose (k,h) so ARL is *large* when in-control (few false
  alarms) and *small* after the shift (fast detection). The textbook pair `k=0.5, h=4` gives in-control
  ARL₀ ≈ 168; `h=5` gives ARL₀ ≈ 465 (NIST handbook, ibid.). Tables/solvers (e.g., the `CUSUMdesign` R
  package, https://cran.r-project.org/web/packages/CUSUMdesign/CUSUMdesign.pdf) map (k,h) ↔ ARL.

### 2.3 Clinical pedigree of CUSUM / EWMA
CUSUM is not exotic in medicine — it is an established audit and monitoring tool:
- **Surgical performance / quality monitoring:** risk-adjusted CUSUM charts are a standard method for
  monitoring surgical outcomes and learning curves (Steiner et al., "Monitoring surgical performance using
  risk-adjusted cumulative sum charts," *Biostatistics* 2000;1(4):441-452,
  https://www.researchgate.net/publication/10601019; broad review of surgical CUSUM at PMID 23359307).
- **Continuous physiological deterioration:** CUSUM/累积-change framing is used for vital-sign
  deterioration monitoring (e.g., review of continuous vital-sign monitoring, PMC9310747,
  https://pmc.ncbi.nlm.nih.gov/articles/PMC9310747/).
- **EWMA (the smooth cousin of CUSUM):** used for real-time change detection in longitudinal clinical/
  behavioral data (tutorial: PMC10248291, https://pmc.ncbi.nlm.nih.gov/articles/PMC10248291/) and for
  risk-adjusted hospital-indicator monitoring (Cook et al., PMID 21209145). EWMA with smoothing λ is
  roughly interchangeable with CUSUM for slow drift; either is defensible for Tier 2.

> **Mapping to NeonatalGuard.**
> - **SUPPORTS:** a deterministic CUSUM (or EWMA) "Drift" detector is a well-founded, decades-validated
>   choice for slow deterioration, and complements Tier 1: Tier 1 catches acute single-window abnormality,
>   CUSUM catches sub-threshold sustained trend. This is the standard Shewhart-plus-CUSUM pairing.
> - **Defensible parameter starting point:** run a one-sided CUSUM per clinically-directed feature (or on
>   the multivariate deviation), `k ≈ 0.5σ` (detect ~1σ sustained drift), `h ≈ 4-5σ`, then tune h to hit a
>   target in-control ARL that matches an acceptable false-alarm-per-infant-hour budget. Document the ARL
>   you pick — that is the honest, auditable knob, and it is the number a clinician-statistician will ask for.
> - **Note:** the "half the shift" rule (`k=δ/2`) is what makes CUSUM optimal; state your target δ explicitly.

---

## 3. What the validated HeRO system actually computes (vs. our z-scores)

HeRO = "Heart Rate Observation." The definitive method paper is **Moorman, J. R., Delos, J. B., Flower, A. A.,
Cao, H., Kovatchev, B. P., Richman, J. S., Lake, D. E. (2011). "Cardiovascular oscillations at the bedside:
early diagnosis of neonatal sepsis using heart rate characteristics monitoring." *Physiological Measurement*
32(11):1821-1832. doi:10.1088/0967-3334/32/11/S08. PMID 22026974.**

### 3.1 The three HRC metrics (note: not our 10 time-domain features)
HeRO analyses windows of **4096 RR intervals (~20-25 min)**, filters outliers (>20% from the local mean),
and normalises by the SD, then computes three complementary shape/complexity metrics of the RR histogram
(Moorman et al. 2011, *Physiol Meas*):
1. **Standard deviation of RR** — "the width of the histogram" (reduced variability).
2. **Sample entropy (SampEn)** — a complexity/"non-Gaussianity" measure (see §3.2).
3. **Sample asymmetry** — separates *decelerations* from *accelerations* (see §3.3).

These target the specific sepsis phenotype: **reduced baseline variability + transient decelerations**. Our
10 features (`mean_rr, sdnn, rmssd, pnn50, lf_hf_ratio, rr_ms_min/max/25/50/75%`) capture *variability and
distribution spread* but **do not include sample entropy or sample asymmetry**, the two nonlinear metrics
that give HeRO its deceleration sensitivity.

### 3.2 Sample entropy — why used for neonates over classical HRV
- Foundational: **Richman, J. S., Moorman, J. R. (2000). "Physiological time-series analysis using
  approximate entropy and sample entropy." *Am J Physiol Heart Circ Physiol* 278(6):H2039-H2049.
  doi:10.1152/ajpheart.2000.278.6.H2039.** SampEn is the negative log conditional probability that two
  sequences similar within tolerance `r` for `m` points remain similar at the next point; it corrects a
  bias in Pincus's approximate entropy (ApEn) by **excluding self-matches**, making it more consistent on
  the short, noisy records typical of clinical data.
- Neonatal specialisation: **Lake, D. E., Richman, J. S., Griffin, M. P., Moorman, J. R. (2002). "Sample
  entropy analysis of neonatal heart rate variability." *Am J Physiol Regul Integr Comp Physiol*
  283(3):R789-R797. doi:10.1152/ajpregu.00069.2002. PMID 12185014.** Key results: SampEn is preferred over
  ApEn (less bias) and over classical time/frequency HRV because it is stable on short neonatal records; and
  crucially **"entropy falls before clinical signs of neonatal sepsis."** An important subtlety they flag:
  the entropy fall is driven partly by *spikes* (decelerations) rather than by regularity per se — so the
  metric works, but naive interpretation is a trap, and they explicitly "addressed the fundamental issues of
  optimal selection of m and r." *(Exact neonatal m/r values are not in the abstract I could access —
  marked **unverified**; the paper's contribution is that m and r must be chosen deliberately, not defaulted.)*

Why this matters for us: classical time-domain features (what we use) can miss the deceleration/complexity
signature that SampEn was specifically engineered to catch in neonates.

### 3.3 Sample asymmetry — how it captures decelerations
**Kovatchev, B. P., Farhy, L. S., Cao, H., Griffin, M. P., Lake, D. E., Moorman, J. R. (2003). "Sample
asymmetry analysis of heart rate characteristics with application to neonatal sepsis and systemic
inflammatory response syndrome." *Pediatr Res* 54(6):892-898. doi (Nature: pr2003513),
https://www.nature.com/articles/pr2003513. PMID 12930915.** Sample asymmetry (SAA) quantifies the *shape* of
the RR-interval histogram by separately accumulating deviations **below** the median (`R1`, acceleration
side) and **above** the median (`R2`, deceleration side); the asymmetry ratio rises when decelerations
increase and/or accelerations decrease. Reported finding: asymmetry rose over the 3-4 days before sepsis/SIRS,
steepest in the final 24 h (from baseline 3.3 ± 1.6 to 4.2 ± 2.3, p=0.02), and the pre-sepsis change was
driven **more by fewer accelerations than by more decelerations**. The point: SAA is *directional by
construction* — the opposite of our direction-discarding `abs(z)`.

### 3.4 How HeRO combines metrics into a risk score
The metrics feed a **multivariable logistic regression** trained against **real sepsis outcomes**; the output
is the **HRC index / HeRO score = the fold-increase in the probability of a sepsis-like clinical
deterioration in the next 24 h** (Griffin, M. P., Lake, D. E., Bissonette, E. A., Harrell, F. E. Jr, O'Shea,
T. M., Moorman, J. R. (2005), "Heart rate characteristics: novel physiomarkers to predict neonatal infection
and death," *Pediatrics* 116(5):1070-1074, PMID 16402612; model development in Griffin, M. P., O'Shea, T. M.,
Bissonette, E. A., et al. (2003), "Abnormal heart rate characteristics preceding neonatal sepsis and
sepsis-like illness," *Pediatr Res* 53(6):920-926, PMID 12646726, doi:10.1203/01.PDR.0000064904.05313.D2).
Later work added nearest-neighbour terms (Xiao, Griffin, Lake, Moorman, 2010, *Med Decis Making*,
doi:10.1177/0272989X09337791). The score is thus **outcome-calibrated and population-referenced**, not
self-referenced to the infant's own rolling mean.

**Clinical validation of the score:** the display of the HeRO score reduced all-cause mortality in a **9-NICU
RCT of ~3000 VLBW infants** by a relative ~22% (8.1% vs 10.2% mortality, p=0.04; NNT ≈ 48) — **Moorman, J. R.,
Carlo, W. A., Kattwinkel, J., et al. (2011). "Mortality reduction by heart rate characteristic monitoring in
very low birth weight neonates: a randomized trial." *J Pediatr* 159(6):900-906.e1. PMID 21864846.
doi:10.1016/j.jpeds.2011.06.044.** This RCT is the reason HeRO — and *its specific method* — can claim clinical
validation. Our z-score method shares the *input domain* (HRV) but not the *method* and not the *validation*.

> **Mapping to NeonatalGuard.**
> - **DIVERGES (features):** we omit the two nonlinear metrics (sample entropy, sample asymmetry) that carry
>   HeRO's deceleration/complexity sensitivity. **Concrete adoption:** add SampEn (Richman-Moorman
>   definition, deliberate m/r) and a deceleration-side sample-asymmetry feature to the 10-feature set; both
>   are cheap to compute on the same RR windows.
> - **DIVERGES (combination):** HeRO uses a regression fit to outcomes; we use `max|z|`. A regression (or any
>   calibrated combiner) turns "how abnormal" into "how much risk," which is what a clinician reads. If we
>   cannot train on labelled sepsis, we should at least (a) use a multivariate statistic rather than the max,
>   and (b) be explicit that our score is an *abnormality* score, not a *risk* score.
> - **DIVERGES (reference):** HeRO is population/outcome-referenced; we are self-referenced. Self-referencing
>   is legitimate for a "departure from own normal" signal (Tier 2's whole premise) but is *not* equivalent
>   to HeRO's risk calibration — do not present it as such.
> - **SUPPORTS (window logic):** HeRO's ~20-25 min windows and outlier filtering are a good template for our
>   feature windows; adopting a comparable window + artifact filter would strengthen comparability.

---

## 4. Personalized baselines

### 4.1 Per-patient baseline vs. population norms
The principle that **"a change from the patient's own baseline is often more informative than a single
population-referenced reading"** is standard clinical-monitoring doctrine (e.g., vital-sign assessment
guidance emphasising comparison to the patient's established baseline; general monitoring reviews). It is
also implicit in trend-based early-warning logic. So a per-infant baseline is *directionally supported* as a
sensitisation strategy. **However**, note the tension with §3: HeRO — the validated neonatal system —
deliberately went **population/outcome-referenced**, because it needed the score to map to absolute sepsis
*risk*. The defensible synthesis: use the per-infant baseline for the *"departure from own normal"* signal
(Tiers 1-2), and treat population/outcome calibration as a separate, missing ingredient we should be honest
about not yet having.

### 4.2 Baseline estimation / "warm-up" — how much data before a z-score is trustworthy?
There is **no neonatal-specific published standard** for "warm-up before a per-infant z-score is stable"
(marked **unverified** — none found). Two defensible anchors from primary literature:
- **Window length for the features themselves:** short-term HRV metrics stabilise at surprisingly short
  windows — near-perfect agreement with reference by ~120 s for both SDNN and RMSSD, with **RMSSD less
  sensitive to duration than SDNN** (Munoz et al., "Validity of (Ultra-)Short Recordings for HRV
  Measurements," *PLoS ONE* 2015;10(9):e0138921, https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0138921;
  ultra-short review, Pecchia/Shaffer et al., *Front Neurosci*/PMC7710683,
  https://pmc.ncbi.nlm.nih.gov/articles/PMC7710683/). Implication: `sdnn` needs longer, cleaner windows than
  `rmssd`; a per-feature warm-up is more honest than one global number.
- **Statistical stability of the baseline SD:** the standard error of an estimated SD is ≈ `σ/√(2(n-1))`
  for `n` independent windows, so a z-score's *denominator* is only ~10-15% uncertain after ~n≈25-50
  independent baseline windows and stays materially noisy below ~n≈10. Early z-scores are therefore
  over-confident (a small, unstable baseline SD makes `|z|` spuriously large). **Defensible fix:** suppress
  or widen Tier-1 gates until the baseline has accumulated a minimum window count, and/or use a robust
  scale (MAD) that is less sensitive to early outliers. *(This SE formula is standard sampling theory;
  the specific n we should require is a design choice, not a validated constant — mark as our judgement.)*

### 4.3 Non-stationarity of neonatal HRV (the real hazard for a fixed baseline)
Neonatal HRV is strongly non-stationary, which directly threatens any *fixed* baseline:
- **Maturational drift:** HRV increases with gestational/postmenstrual age as the autonomic nervous system
  matures; SampEn rises measurably from ~32 to ~36 weeks PMA (autonomic-maturation studies: ProMote,
  *PLoS ONE*, https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0339681; Bonneau et al.,
  *Acta Paediatrica* 2025, https://onlinelibrary.wiley.com/doi/10.1111/apa.70462). A baseline learned in
  week 1 is mis-calibrated by week 3 on maturation alone.
- **Circadian structure:** circadian amplitude in preterm infants grows with both postnatal and
  postmenstrual age (Circadian-rhythm-development study, *ScienceDirect* S0378378224001531,
  https://www.sciencedirect.com/science/article/abs/pii/S0378378224001531). A same-infant z-score can drift
  purely on time-of-day.

> **Mapping to NeonatalGuard.**
> - **SUPPORTS (concept):** per-infant baselining is a legitimate, literature-backed sensitiser.
> - **DIVERGES / risk (execution):** a **rolling** baseline is essential — a fixed early baseline will be
>   detuned by maturation and circadian drift within days. **Defensible fixes:** (a) use an *adaptive*
>   rolling baseline (EWMA of mean/SD) with a window long enough to smooth circadian cycles but short enough
>   to track maturation; (b) enforce a **minimum warm-up window count** before Tier-1 gates arm; (c) prefer
>   robust location/scale (median/MAD) to blunt early-outlier contamination; (d) consider conditioning the
>   baseline on time-of-day if circadian drift proves material.

---

## 5. Novelty / anomaly detection ("world model" / "Surprise") precedent

### 5.1 The concept is principled
"Surprise" as *departure from a learned generative model of normal dynamics* is well-grounded in the
predictive-coding / free-energy framework — **Friston, K. (2010). "The free-energy principle: a unified brain
theory?" *Nat Rev Neurosci* 11(2):127-138. doi:10.1038/nrn2787** — where an agent minimises the "surprise"
(negative log-evidence) of inputs under an internal model. This is a sound theoretical basis for a
world-model "Surprise" signal: rising surprise = the infant's dynamics no longer fit its own learned normal.

### 5.2 But validated *unsupervised* deterioration detection is sparse
The clinical evidence base for *learned normal-dynamics / novelty* detectors in patient monitoring is thin
and mostly **not** the "surprise/world-model" formulation:
- Deployed and trial-validated systems are almost all **supervised** predictors trained on labelled
  outcomes (HeRO itself; recent wearable deep-learning deterioration models, e.g., *Nat Commun* 2025,
  https://www.nature.com/articles/s41467-025-65219-8, predict alerts up to ~17 h ahead but are trained on
  alert/outcome labels).
- Genuinely *unsupervised* physiological anomaly work exists but is mostly **artifact detection** or
  method papers rather than validated deterioration alarms (e.g., VAE + isolation-forest artifact detection
  on ICU vitals, arXiv:2312.05959; unsupervised time-series novelty methods, PMC10864956). A notable
  neonatal exception using data-driven signature discovery (not a world model) is **highly-comparative
  time-series analysis of fatal neonatal illness** (Sullivan/Moorman group, PMC8764068,
  https://pmc.ncbi.nlm.nih.gov/articles/PMC8764068/), which is closer in spirit but still supervised on
  outcomes.

> **Mapping to NeonatalGuard.**
> - **DIVERGES / weakest-evidence tier:** a learned "Surprise" detector has strong *theory* (Friston) but
>   little *clinical validation* as a standalone deterioration alarm. Be explicit that this is the research
>   frontier, not settled practice.
> - **Defensible posture:** keep the **deterministic CUSUM** as the auditable Tier-2 backbone (validated
>   change-detection math), and treat the world-model Surprise as an *adjunct that can only escalate above
>   the Safety Floor*, never a sole trigger — which is exactly what the CONTEXT.md Safety-Floor design
>   already enforces. That architecture is the honest, defensible way to ship an unproven learned signal.

---

## Confidence & conflicting evidence

- **High confidence:** SPC provenance of 3σ/2σ (Shewhart 1931; Western Electric 1956); CUSUM origin and
  tuning (Page 1954; NIST handbook); the HeRO metric set, its logistic-regression "fold-increase-in-risk"
  output, and its RCT mortality result (Moorman 2011 *Physiol Meas* and *J Pediatr*; Griffin 2003/2005;
  Kovatchev 2003; Lake 2002; Richman-Moorman 2000). These are directly sourced with DOIs/PMIDs.
- **Medium confidence:** the *exact* deployed HeRO coefficients and the neonatal SampEn m/r values are not
  fully public in the sources accessed (the *Physiol Meas* review describes the method but not shipping
  coefficients; the Lake 2002 abstract states m/r were optimised but does not print the numbers). Treat
  specific numeric internals as **unverified**.
- **Honest tension #1:** per-infant baseline (§4) vs. HeRO's population/outcome reference (§3). Both are
  defensible for *different jobs* — "departure from own normal" vs. "absolute risk." The literature does not
  say a self-referenced HRV z-score predicts sepsis; conflating the two would overclaim.
- **Honest tension #2:** the multiple-comparison inflation of `max|z|` (§1.3) vs. the appeal of a simple max.
  The max is transparent and cheap but statistically loose; a multivariate statistic or persistence rule is
  more defensible without much added complexity.
- **Weakest evidence:** learned world-model "Surprise" for deterioration (§5) — strong theory, sparse
  clinical validation.
- **Not found (so stated plainly):** any peer-reviewed neonatal study validating `|z|>=2` or `|z|>=3` on
  individual HRV features as a sepsis threshold; any published neonatal "warm-up" standard for per-infant
  z-score stability. Absence-of-evidence, not evidence-of-absence — but we should not imply validation we
  could not find.

---

## References

**Statistical process control (thresholds & change-detection)**
1. Shewhart, W. A. (1931). *Economic Control of Quality of Manufactured Product.* Van Nostrand, New York.
   (3σ as "acceptable economic value"; control-chart origin.) Background: SPC for Excel,
   https://www.spcforexcel.com/knowledge/control-chart-basics/three-sigma-limits-control-charts/ ;
   https://en.wikipedia.org/wiki/Walter_A._Shewhart
2. Shewhart, W. A. (1930). "Economic quality control of manufactured product." *Bell System Technical
   Journal* 9(2):364-389. doi:10.1002/j.1538-7305.1930.tb00373.x
3. Western Electric Company (1956). *Statistical Quality Control Handbook*, 1st ed. AT&T/Western Electric,
   Indianapolis. (2σ warning / zone & runs rules.) Summary: https://en.wikipedia.org/wiki/Western_Electric_rules
4. Page, E. S. (1954). "Continuous inspection schemes." *Biometrika* 41(1-2):100-115.
   doi:10.1093/biomet/41.1-2.100 (CUSUM origin).
5. NIST/SEMATECH (current). *e-Handbook of Statistical Methods*, §6.3.2.3 "CUSUM Average Run Length."
   https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc3231.htm (k, h, ARL selection).
6. Steiner, S. H., Cook, R. J., Farewell, V. T., Treasure, T. (2000). "Monitoring surgical performance using
   risk-adjusted cumulative sum charts." *Biostatistics* 1(4):441-452.
   https://www.researchgate.net/publication/10601019 (CUSUM clinical pedigree).
7. Cook, D. A., et al. (2011). Risk-adjusted EWMA charts for hospital indicators. PMID 21209145. EWMA
   real-time change-detection tutorial: PMC10248291, https://pmc.ncbi.nlm.nih.gov/articles/PMC10248291/

**HeRO / heart-rate-characteristics method (the validated neonatal system)**
8. Richman, J. S., Moorman, J. R. (2000). "Physiological time-series analysis using approximate entropy and
   sample entropy." *Am J Physiol Heart Circ Physiol* 278(6):H2039-H2049.
   doi:10.1152/ajpheart.2000.278.6.H2039 (SampEn foundational).
9. Lake, D. E., Richman, J. S., Griffin, M. P., Moorman, J. R. (2002). "Sample entropy analysis of neonatal
   heart rate variability." *Am J Physiol Regul Integr Comp Physiol* 283(3):R789-R797.
   doi:10.1152/ajpregu.00069.2002. PMID 12185014.
10. Kovatchev, B. P., Farhy, L. S., Cao, H., Griffin, M. P., Lake, D. E., Moorman, J. R. (2003). "Sample
    asymmetry analysis of heart rate characteristics with application to neonatal sepsis and systemic
    inflammatory response syndrome." *Pediatr Res* 54(6):892-898. PMID 12930915.
    https://www.nature.com/articles/pr2003513
11. Griffin, M. P., O'Shea, T. M., Bissonette, E. A., et al. (2003). "Abnormal heart rate characteristics
    preceding neonatal sepsis and sepsis-like illness." *Pediatr Res* 53(6):920-926. PMID 12646726.
    doi:10.1203/01.PDR.0000064904.05313.D2 (logistic-regression HRC model development).
12. Griffin, M. P., Lake, D. E., Bissonette, E. A., Harrell, F. E. Jr, O'Shea, T. M., Moorman, J. R. (2005).
    "Heart rate characteristics: novel physiomarkers to predict neonatal infection and death." *Pediatrics*
    116(5):1070-1074. PMID 16402612.
13. Moorman, J. R., Delos, J. B., Flower, A. A., Cao, H., Kovatchev, B. P., Richman, J. S., Lake, D. E.
    (2011). "Cardiovascular oscillations at the bedside: early diagnosis of neonatal sepsis using heart rate
    characteristics monitoring." *Physiol Meas* 32(11):1821-1832. doi:10.1088/0967-3334/32/11/S08.
    PMID 22026974 (definitive method review: SD + SampEn + sample asymmetry; 4096-interval windows).
14. Moorman, J. R., Carlo, W. A., Kattwinkel, J., et al. (2011). "Mortality reduction by heart rate
    characteristic monitoring in very low birth weight neonates: a randomized trial." *J Pediatr*
    159(6):900-906.e1. PMID 21864846. doi:10.1016/j.jpeds.2011.06.044 (the RCT: ~22% relative mortality
    reduction, NNT≈48).
15. Xiao, Y., Griffin, M. P., Lake, D. E., Moorman, J. R. (2010). "Nearest-neighbor and logistic regression
    analyses of clinical and heart rate characteristics in the early diagnosis of neonatal sepsis." *Med
    Decis Making*. doi:10.1177/0272989X09337791.
16. Fairchild, K. D. (2013). "Predictive monitoring for early detection of sepsis in neonatal ICU patients."
    *Curr Opin Pediatr* 25(2):172-179. doi:10.1097/MOP.0b013e32835e8fe6. PMID 23407184. PMC10989716,
    https://pmc.ncbi.nlm.nih.gov/articles/PMC10989716/ (review confirming HRC-index rise ↔ late-onset
    sepsis; specific OR/sens-spec figures **not** found in this primary text — see §1.3).

**Personalized baselines & neonatal HRV non-stationarity**
17. Munoz, M. L., et al. (2015). "Validity of (Ultra-)Short Recordings for Heart Rate Variability
    Measurements." *PLoS ONE* 10(9):e0138921.
    https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0138921 (SDNN/RMSSD window stability).
18. Shaffer, F., et al. (2020). "A Critical Review of Ultra-Short-Term Heart Rate Variability Norms
    Research." *Front Neurosci*. PMC7710683, https://pmc.ncbi.nlm.nih.gov/articles/PMC7710683/
19. ProMote study. "Autonomic nervous system maturation in preterm neonates: correlation with gestational
    and postmenstrual age." *PLoS ONE*.
    https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0339681 (HRV/SampEn maturation).
20. Bonneau, et al. (2025). "Early Maturation of Heart Rate Variability in Very Preterm Infants…" *Acta
    Paediatrica.* https://onlinelibrary.wiley.com/doi/10.1111/apa.70462
21. "Circadian rhythm development in preterm infants: postnatal vs postmenstrual age." *ScienceDirect*
    S0378378224001531. https://www.sciencedirect.com/science/article/abs/pii/S0378378224001531

**Novelty / world-model / "surprise"**
22. Friston, K. (2010). "The free-energy principle: a unified brain theory?" *Nat Rev Neurosci* 11(2):127-138.
    doi:10.1038/nrn2787. https://www.nature.com/articles/nrn2787
23. (2025). Clinical wearable deep-learning in-hospital deterioration prediction. *Nat Commun.*
    https://www.nature.com/articles/s41467-025-65219-8 (supervised, not world-model — context).
24. Sullivan/Moorman group. "Discovery of signatures of fatal neonatal illness in vital signs using highly
    comparative time-series analysis." PMC8764068, https://pmc.ncbi.nlm.nih.gov/articles/PMC8764068/

*Items marked "unverified" in the text (deployed HeRO coefficients; neonatal SampEn m/r numbers; any
neonatal per-feature sigma sepsis threshold; a published z-score warm-up standard) could not be confirmed
from primary sources accessed on 2026-07-12 and should not be cited as established.*
