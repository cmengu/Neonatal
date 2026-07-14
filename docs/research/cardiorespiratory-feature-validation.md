# Validation of Issue #3's Feature Set: Sample Entropy, Sample Asymmetry, and Respiration-Derived Cardiorespiratory Features

**Scope:** A primary-source appraisal of the features that engineering issue **#3** will compute — **sample entropy (SampEn)**, **sample asymmetry**, and **respiration-derived cardiorespiratory** features — and an explicit, feature-by-feature statement of what should **replace** the crude RR-tail proxies that issue **#8** left in place. This resolves research issue **#10** and unblocks **#3**. It builds directly on the three companion files in this folder (`hrv-features-neonatal-validity.md`, `clinical-evidence-hrv-sepsis.md`, `README.md`) and does not restate their per-feature verdicts except where the #8→#3 boundary requires it.

**Date:** 2026-07-12
**Prepared for:** Clinical/engineering handoff — written to be defensible feature-by-feature, with a primary-source citation (PMID/DOI) on every substantive claim and explicit **[UNVERIFIED]** flags where a value could not be confirmed against the primary text.

**Data reality being designed for:** PICS cohort — **10 preterm infants**, ~**450–500 h** of **dual-channel ECG + respiration**, **no SpO₂**, **no sepsis labels**. That is ~45 h/infant, ample for the ~20–25-min moving windows and per-infant baselines these features require, but it forecloses any SpO₂-derived feature and any supervised threshold tuning.

**What #8 shipped (the boundary to resolve).** The Tier-1 deterministic floor was made direction-aware and reduced to these triggers: `sdnn`/`rmssd` (**low-only**), `rr_ms_max`/`rr_ms_75%` (**high-only**, as crude "deceleration-tail" proxies), and `mean_rr` (**two-sided**). It removed `lf_hf_ratio`, `rr_ms_min`, `rr_ms_50%` from the trigger set and demoted `pnn50` to display-only. The computed columns are exactly: `mean_rr, sdnn, rmssd, pnn50, lf_hf_ratio, rr_ms_min, rr_ms_max, rr_ms_25%, rr_ms_50%, rr_ms_75%` (there is **no** `pnn20`). **#3's job:** replace the crude RR-tail proxies with the *actual* validated HeRO discriminators (SampEn + sample asymmetry) and add respiration-derived features.

---

## Bottom line

- **Add sample entropy (SampEn) as a low-only trigger.** SampEn is the neonatally-validated measure of signal *irregularity/non-Gaussianity*; it **falls** in the days before sepsis (Lake 2002, PMID 12185014) and is one of the three features the FDA-cleared HeRO monitor actually computes (Moorman 2011, PMID 22026974). It is preferred over classical time/frequency HRV because it is robust to the non-stationarity, spikes, and short records that defeat spectral analysis (Richman & Moorman 2000, PMID 10843903). Defensible neonatal defaults: **m = 3, r = 0.2 × SD (relax upward for short/noisy windows), N ≈ 4096 RR intervals (~20–25 min moving window)**.
- **Add sample asymmetry as a high-only trigger — this is the real replacement for `rr_ms_max`/`rr_ms_75%`.** Sample asymmetry separately quantifies accelerations (R1) and decelerations (R2) from the *shape of the RR histogram* and **rises** before sepsis/SIRS (from ~3.3 to ~4.2 over 3–4 days, steepest in the last 24 h), driven mainly by **reduced accelerations** with **increased decelerations** (Kovatchev 2003, PMID 12930915; Moorman 2011, PMID 22026974). This is the whole-histogram deceleration-burden statistic that a single order-statistic (`rr_ms_max`) only crudely gestures at.
- **Add respiration-derived features from the respiration channel (not SpO₂).** In preterm infants, **apnea**, **periodic breathing**, and **respiratory instability** all **increase** in the 1–2 days before late-onset sepsis (Pre-Vent, J Pediatr 2024, PMID 38570031; Joshi 2019, PMID 31295130), and these are derivable from **chest-impedance / respiration waveforms alone** (Vergales 2014, PMID 23592319; Mohr 2015, PMID 26012526; Patel 2016, PMID 27002984). The apnea/periodic-breathing → **bradycardia** link is the classic apnea-bradycardia physiology of prematurity.
- **The SpO₂ boundary is hard.** The single strongest cardiorespiratory predictor in ventilated infants — prolonged **intermittent hypoxemia (IH)** — requires SpO₂ and therefore **cannot be computed on PICS data** (Pre-Vent, PMID 38570031). #3 should build the ECG + respiration features and record IH as an explicit gap.
- **Retire the crude RR proxies as triggers.** `rr_ms_max` and `rr_ms_75%` **fold into sample asymmetry (R2) + SD**; `rr_ms_25%` folds into the R1/spread side; `rr_ms_50%` stays retired (redundant with `mean_rr`); `rr_ms_min` folds into R1 (accelerations). None of the five raw RR quantiles is an established, named, neonatally-validated feature — sample asymmetry is the validated construct they were proxying (Kovatchev 2003, PMID 12930915).

---

## Decision evidence table

Directions are stated for the **RR-interval** domain (a *deceleration* = a longer RR / slower beat). "Trigger?" states the recommended Tier-1 disposition **for #3**; the "(#8: …)" note records the status #8 left the feature in, so the boundary is explicit.

| Feature / choice | Keep as trigger? | Pathological direction / mechanism | Evidence (PMID/DOI) |
|------------------|------------------|------------------------------------|---------------------|
| **Sample entropy (SampEn)** | **ADD — new, low-only** (#8: not computed) | **Falls** before sepsis. Measures conditional regularity/irregularity (non-Gaussianity) of the RR series; infection-driven loss of complex autonomic modulation lowers entropy hours-to-days ahead. Robust to non-stationarity/spikes that break spectral HRV. | Lake 2002, PMID 12185014, DOI 10.1152/ajpregu.00069.2002; Richman & Moorman 2000, PMID 10843903, DOI 10.1152/ajpheart.2000.278.6.H2039; Moorman 2011, PMID 22026974, DOI 10.1088/0967-3334/32/11/S08 |
| **Sample asymmetry** (R2/R1 of RR histogram) | **ADD — new, high-only** (#8: not computed) | **Rises** before sepsis/SIRS (~3.3→4.2 over 3–4 d; steepest last 24 h), **mainly from fewer accelerations (R1↓) plus more/bigger decelerations (R2↑)** — i.e. the "reduced variability *with* transient decelerations" signature quantified from histogram shape. Its precursor, RR **skewness**, was +0.59 (sepsis) vs −0.10 (controls). | Kovatchev 2003, PMID 12930915, DOI 10.1203/01.PDR.0000088074.97781.4F; Moorman 2011, PMID 22026974; Griffin & Moorman 2001, PMID 11134441, DOI 10.1542/peds.107.1.97 |
| **Respiratory-rate variability / respiratory instability** (from respiration channel) | **ADD — new, high-only** (#8: not computed) | **Increases** — respiration becomes more unstable (irregular breath-to-breath intervals) in the hours before late-onset sepsis. Derivable from the respiration waveform; **no SpO₂ needed**. | Joshi 2019, PMID 31295130, DOI 10.1109/JBHI.2019.2927463; Pre-Vent J Pediatr 2024, PMID 38570031, DOI 10.1016/j.jpeds.2024.114042 |
| **Apnea burden** (pauses ≥ ~15–20 s from chest impedance/respiration) | **ADD — new, high-only** (#8: not computed) | **Increases** in the 1–2 d before sepsis. Central apnea is detectable from the respiration/chest-impedance signal (validated automated detectors); apnea → **bradycardia** is the classic apnea-of-prematurity coupling. | Pre-Vent J Pediatr 2024, PMID 38570031; Vergales 2014, PMID 23592319, DOI 10.1055/s-0033-1343769; Fairchild 2016 (part 1, central apnea), PMID 26959485, DOI 10.1038/pr.2016.43 |
| **Periodic-breathing burden (%PB)** (wavelet transform of respiration) | **ADD — new, high-only / escalation** (#8: not computed) | **Increases** — a >2-fold rise in %PB over the infant's baseline preceded diagnosis in ~1/3–1/2 of septicemia/NEC cases; quantified from chest impedance via a wavelet method. Noisier/less specific → best as escalation or with persistence, not a lone RED. | Mohr 2015, PMID 26012526, DOI 10.1088/0967-3334/36/7/1415; Patel 2016 (part 2, periodic breathing), PMID 27002984, DOI 10.1038/pr.2016.58; Pre-Vent J Pediatr 2024, PMID 38570031 |
| **Bradycardia / transient-deceleration event count** (from ECG/RR, not window-mean) | **ADD / REFRAME — high-only** (replaces the `mean_rr>600 ms` bradycardia *role*) | **Increases** — counting transient long-RR (deceleration) excursions captures the validated signal that a *window mean* averages away; bradycardia events rise before sepsis. Complements sample asymmetry (R2). | Pre-Vent J Pediatr 2024, PMID 38570031; Griffin & Moorman 2001, PMID 11134441; Sullivan & Fairchild 2024/25, PMID 39242935, DOI 10.1038/s41390-024-03548-y |
| **Intermittent hypoxemia (IH) / desaturation depth-duration** | **CANNOT COMPUTE — no SpO₂ in PICS** (record as a gap) | Prolonged IH was the strongest cardiorespiratory predictor in *ventilated* extremely-preterm infants — but it is an **SpO₂** feature and PICS has no SpO₂. Do not fabricate a proxy. | Pre-Vent J Pediatr 2024, PMID 38570031 |
| `rr_ms_max` (window max RR) | **REPLACE → fold into sample asymmetry (R2)** (#8: kept high-only) | Was the crude "deepest single deceleration" proxy. The validated construct is deceleration **burden across the whole histogram** (R2), not one artifact-prone extreme. Retire as trigger once sample asymmetry ships; may keep for display/artifact QC. | Kovatchev 2003, PMID 12930915; Moorman 2011, PMID 22026974 |
| `rr_ms_75%` (75th pct RR) | **REPLACE → fold into sample asymmetry (R2) + SD** (#8: kept high-only) | Proxied "deceleration tail + reduced spread." Both halves are now carried explicitly by sample asymmetry (deceleration side) and SDNN (spread). Retire as an independent trigger. | Kovatchev 2003, PMID 12930915; Moorman 2011, PMID 22026974 |
| `rr_ms_25%` (25th pct RR) | **FOLD into R1 (acceleration side) — display only** (#8: already not a trigger) | Part of the robust-spread / acceleration information now encoded by sample asymmetry (R1) and SD. Not a standalone trigger. | Kovatchev 2003, PMID 12930915 |
| `rr_ms_50%` (median RR) | **RETIRE — redundant with `mean_rr`** (#8: already removed) | Median RR ≈ inverse of median HR, duplicating `mean_rr`. Keep for display only. | Task Force 1996, PMID 8737210; Moorman 2011, PMID 22026974 |
| `rr_ms_min` (window min RR) | **FOLD into R1 (accelerations) / retire** (#8: already removed) | Single fastest beat; artifact-sensitive and directionally ambiguous alone. The *acceleration* information it gestured at is captured cleanly by R1 of sample asymmetry. | Kovatchev 2003, PMID 12930915; Moorman 2011, PMID 22026974 |
| `sdnn` (SD of NN) | **KEEP — low-only** (#8: trigger) | **Falls** — the "reduced variability" half of the signature; SD is literally one of HeRO's three features. Length-dependent → fixed window mandatory. | Moorman 2011, PMID 22026974; Griffin 2003, PMID 12646726; Task Force 1996, PMID 8737210 |
| `rmssd` (RMS successive diff) | **KEEP — low-only** (#8: trigger) | **Falls** — best-supported short-term vagal marker in neonates; loss of beat-to-beat variability. | Patural 2022, DOI 10.3389/fped.2022.860145; Griffin 2003, PMID 12646726 |
| `mean_rr` (mean RR / HR level) | **KEEP — two-sided** (#8: trigger) | Bidirectional: sustained **tachycardia** (RR↓) *plus* transient **decelerations** (RR↑). Two-sided is defensible for the *level*; the transient signal is better carried by sample asymmetry + event counts. | Sullivan & Fairchild 2024/25, PMID 39242935; Griffin & Moorman 2001, PMID 11134441 |
| `lf_hf_ratio` | **KEEP OUT — display only** (#8: removed) | HeRO deliberately uses **no** frequency-domain measures (non-stationarity, respiratory-rate dependence, cardiac aliasing, unequal sampling); adult bands also misclassify infant respiration. SampEn is the nonlinear feature that replaces its intended role. | Moorman 2011, PMID 22026974; Billman 2013, DOI 10.3389/fphys.2013.00026 |
| `pnn50` | **DISPLAY ONLY; consider `pnn20`** (#8: demoted) | Floor effect in neonates (term median ~1.7%). Not part of #3's core scope, but if any pNN is ever re-triggered it must be `pnn20`. | Oliveira 2019, PMID 31440164; Mietus 2002 |

---

## Sample entropy (SampEn)

### Why entropy, and why *sample* entropy

Classical HRV splits into time-domain (SD, RMSSD) and frequency-domain (LF/HF) measures. Both are poorly suited to the neonatal sepsis signal: the frequency-domain assumes a **stationary, periodic, equally-sampled** signal, none of which holds for neonatal heart rate (Moorman 2011, PMID 22026974), and the time-domain SD/RMSSD capture *amount* of variability but not its **temporal structure/regularity**. Entropy measures the latter — how *predictable* the RR series is — which is exactly what a failing autonomic system loses.

**Approximate entropy (ApEn)** (Pincus) was the first such measure but is **biased** and inconsistent on the short, noisy records typical of bedside monitoring because it counts self-matches. **Sample entropy (SampEn)** was introduced specifically to remove that bias: it is "largely independent of record length and displays relative consistency under conditions where ApEn does not," and it "agreed with theory much more closely than ApEn over a broad range of conditions" (Richman & Moorman 2000, PMID 10843903, DOI 10.1152/ajpheart.2000.278.6.H2039). SampEn is defined as **the negative natural logarithm of the conditional probability that two subseries (templates) of length *m* that match within tolerance *r* also match at the next point** — computed *without* self-matches.

**Neonatal validation.** Lake, Richman, Griffin & Moorman applied SampEn directly to neonatal RR data (89 NICU admissions, 21 sepsis episodes) and showed that **entropy falls before the clinical signs of neonatal sepsis**; that paper is also where the questions of "optimal selection of *m* and *r*" and tolerance of missing data were worked out for this exact application (Lake 2002, PMID 12185014, DOI 10.1152/ajpregu.00069.2002). SampEn is one of the **three** heart-rate characteristics the FDA-cleared HeRO monitor computes — "sample entropy tells us the degree of non-Gaussianity" — alongside SD and sample asymmetry (Moorman 2011, PMID 22026974).

### Concrete parameters #3 needs (embedding dimension m, tolerance r, window length N)

| Parameter | Defensible neonatal default | Basis |
|---|---|---|
| **m** (embedding/template length) | **3** for neonatal RR (general SampEn default is **2**) | m = 3 is the value reported for the Lake 2002 neonatal analysis; m = 2 is the general reference default (Richman & Moorman 2000, PMID 10843903; PhysioNet `sampen` reference implementation). Moorman 2011 (PMID 22026974): parameters should be "relaxed enough — that is, *m* short enough and *r* large enough." |
| **r** (tolerance) | **0.2 × SD** of the detrended RR series; **relax upward (≈0.2–0.3)** for short/noisy neonatal windows | 0.2 × SD is the standard convention (Richman & Moorman 2000, PMID 10843903; PhysioNet `sampen`). For short, spiky neonatal records a **larger r** improves consistency, and r should ideally be tuned to maximize discrimination rather than left fixed (Lake 2002, PMID 12185014; Moorman 2011, PMID 22026974). |
| **N** (window length) | **≈ 4096 RR intervals ≈ 20–25 min** moving window | The HeRO operational window analyzes sets of ~4096 intervals (~20–25 min at neonatal HR); slide per the existing Tier-1 cadence (Moorman 2011, PMID 22026974). |
| **Preprocessing (required)** | Reject artifact intervals (e.g. >20% from the local mean of the prior ~15 beats, or |ΔRR| > 5×SD of the last ~512 differences); detrend by subtracting a moving-average baseline **before** computing r and entropy | Entropy "inevitably falls in any record with spikes," so artifact rejection is not optional — a missed/ectopic beat masquerades as structure and corrupts SampEn (Lake 2002, PMID 12185014; HeRO methods per Moorman 2011, PMID 22026974). |
| **Cold-start** | Require ≥ ~1 full window (and ideally a short warm-up of several windows) before trusting the per-infant z-score | No published neonatal baseline-warmup standard exists (see `README.md` open item); a SampEn z against a near-empty baseline is unstable. |

**Direction / trigger.** SampEn **falls** before sepsis → wire it as a **low-only** trigger, exactly parallel to how #8 made `sdnn`/`rmssd` low-only. This is the correct nonlinear replacement for the role `lf_hf_ratio` was wrongly given.

**Feasibility on PICS.** A 20–25-min window over ~45 h/infant yields >100 windows per infant — more than enough for a stable per-infant SampEn baseline.

---

## Sample asymmetry

### What it is, and why it beats raw RR quantiles

Sample asymmetry analysis (SAA) quantifies **the shape of the RR-interval histogram**, separating the contribution of **accelerations (R1)** from **decelerations (R2)**. Concretely, R1 and R2 are computed from deviations **below** and **above** the median respectively: on the RR series, values *above* the median are **long RR / decelerations (R2)** and values *below* are **short RR / accelerations (R1)** (Moorman 2011, PMID 22026974). "Unlike other measures of heart rate variability, SAA allows separate quantification of the contribution of accelerations and decelerations" (Kovatchev 2003, PMID 12930915) — which is precisely the property the symmetric per-feature z-scores of the RR quantiles cannot provide.

**Direction of change in sepsis.** Sample asymmetry **rises**: in the 3–4 days before sepsis and SIRS it increased "from a baseline value of 3.3 (SD 1.6) to 4.2 (SD 2.3), p = 0.02," with the steepest climb in the last 24 h, and the change was "mainly due to fewer accelerations than to decelerations" (Kovatchev 2003, PMID 12930915, DOI 10.1203/01.PDR.0000088074.97781.4F). Healthy vs sepsis infants differed at p = 0.002. HeRO describes the same abnormal pattern mechanistically as **reduced R1 (few or no accelerations) with increased R2 (more and bigger decelerations)** (Moorman 2011, PMID 22026974). The original discriminator was the distribution's **skewness** (third moment): **+0.59 ± 0.10** in sepsis vs **−0.10 ± 0.13** in controls over the 6 h before deterioration (Griffin & Moorman 2001, PMID 11134441); sample asymmetry is the refined, separately-quantified successor to that skewness signal.

**The HeRO connection — "reduced variability WITH transient decelerations."** This is the single most-validated neonatal-sepsis phenomenon, and it is a *joint* pattern: **low** SD/SampEn (reduced variability) **together with** a **rising** sample asymmetry (transient decelerations). #8's `rr_ms_max`/`rr_ms_75%` triggers were an attempt to catch the deceleration half with a single order statistic; sample asymmetry catches it properly, over the whole histogram, and is far less artifact-fragile than one extreme value.

**Direction / trigger.** Sample asymmetry **rises** → wire it as a **high-only** trigger. This is the direct, evidence-grounded replacement for the `rr_ms_max`/`rr_ms_75%` "deceleration-tail" proxies.

**Sign-convention caveat (must be pinned down by #3).** The primary sources compute asymmetry on **RR intervals** with the R2/R1 (deceleration-weighted) definition, for which the value **rises** toward decelerations (Kovatchev 2003, PMID 12930915; Moorman 2011, PMID 22026974). A widely-cited secondary review instead states sample asymmetry is "<1 when the histogram has a tail toward decelerations" (Fairchild & O'Shea 2010, PMID 20813272, as quoted in `clinical-evidence-hrv-sepsis.md`) — a *different normalization* (and possibly the HR rather than RR domain), where the value would **fall**. These are the same physiology with opposite signs. **#3 must fix (a) HR vs RR domain and (b) the R2/R1 vs R1/R2 (or normalized) definition so the direction-aware trigger points the right way.** Recommended: compute on RR with the Kovatchev R2/R1 convention → **high-only**.

---

## Respiration-derived cardiorespiratory features

The PICS data's **respiration channel** (dual-channel ECG + respiration) is an under-used signal that carries independent, validated early-sepsis information — and crucially, the validated features below are derived from the **respiration/chest-impedance waveform, not SpO₂**.

### What is validated in neonates, and the apnea → bradycardia link

- **Apnea (central).** Central apnea is reliably detected from the **chest-impedance waveform** by validated automated algorithms that filter cardiac and motion artifact; the classic clinical event is the **apnea–bradycardia–desaturation (ABD)** triad, i.e. an apneic pause followed by **bradycardia** (Vergales 2014, PMID 23592319, DOI 10.1055/s-0033-1343769; Fairchild 2016 part 1, PMID 26959485, DOI 10.1038/pr.2016.43). Apnea and bradycardia are physiologically coupled in the preterm infant, so the respiration channel and the ECG carry correlated deterioration signals.
- **Periodic breathing (PB).** Regular cycles of short apneic pauses and breaths, quantified as **%time-in-PB** via a **wavelet transform of the chest-impedance signal** (Mohr 2015, PMID 26012526, DOI 10.1088/0967-3334/36/7/1415). A **>2-fold increase in %PB over the infant's own baseline** in the day before diagnosis preceded a substantial fraction of septicemia and NEC cases (Patel 2016 part 2, PMID 27002984, DOI 10.1038/pr.2016.58).
- **Respiratory instability / respiratory-rate variability.** Breathing becomes **more unstable** (irregular breath-to-breath intervals) before late-onset sepsis; a multi-feature model over HRV + respiratory + motion features found "increased respiratory instability" and "increased propensity toward pathological heart-rate decelerations" in the hours before clinical suspicion (Joshi 2019, PMID 31295130, DOI 10.1109/JBHI.2019.2927463).
- **Direct sepsis evidence (Pre-Vent).** In 719 extremely-preterm infants (47,512 patient-days), for infants **not** on a ventilator, **apnea, periodic breathing, and bradycardia events increased in the 1–2 days before sepsis diagnosis**; a multivariable cardiorespiratory model reached **AUC 0.783** (Pre-Vent, J Pediatr 2024;271:114042, PMID 38570031, DOI 10.1016/j.jpeds.2024.114042).

### The SpO₂ boundary — explicit

**PICS has ECG + respiration but NO SpO₂.** Therefore #3 **can** compute, from the respiration waveform + ECG:
- respiratory rate and **respiratory-rate variability / instability**;
- **apnea burden** (count/total duration of pauses ≥ ~15–20 s);
- **periodic-breathing burden** (%PB via wavelet);
- **bradycardia / transient-deceleration event counts** (from RR).

#3 **cannot** compute (and must record as an explicit gap, not proxy):
- **intermittent hypoxemia (IH)** depth/duration and desaturation-based ABD confirmation — these need **SpO₂**, and IH was the *strongest* cardiorespiratory predictor in ventilated infants in Pre-Vent (PMID 38570031). A recent multi-NICU "cardiorespiratory early-warning" model likewise leans on SpO₂ (PMID 36593281) and is therefore only partially reproducible on PICS.

**Direction / trigger.** All computable respiration features move **up** before sepsis → wire as **high-only** triggers. Given they are noisier and less specific than the HRV core, `%PB` in particular is best used as an **escalation** signal or gated behind a persistence (k-of-n) rule rather than allowed to solo-fire RED — consistent with the persistence recommendation in `README.md`.

---

## Disposition of the existing RR proxies (explicit boundary vs #8)

| Proxy | #8 status | #3 disposition | Rationale |
|---|---|---|---|
| `rr_ms_max` | **Kept** as high-only "deceleration-tail" trigger | **Replace → fold into sample asymmetry (R2).** Retire as trigger; may keep for display/artifact QC. | A single extreme is fragile (a dropped beat looks like a huge deceleration); R2 measures deceleration *burden* over the whole histogram (Kovatchev 2003, PMID 12930915). |
| `rr_ms_75%` | **Kept** as high-only trigger | **Replace → fold into sample asymmetry (R2) + SDNN.** Retire as independent trigger. | Its two roles (deceleration tail + reduced spread) are now carried explicitly by asymmetry and SD (Moorman 2011, PMID 22026974). |
| `rr_ms_25%` | Display-only (not a trigger) | **Fold into R1 / robust-spread; remains display-only.** | Acceleration-side/spread information subsumed by sample asymmetry R1 and SD (Kovatchev 2003, PMID 12930915). |
| `rr_ms_50%` (median) | **Removed** from triggers | **Stay retired** (display-only). | Redundant with `mean_rr` (Task Force 1996, PMID 8737210). |
| `rr_ms_min` | **Removed** from triggers | **Fold into R1 (accelerations) / stay retired.** | Directionally ambiguous and artifact-prone alone; R1 captures the acceleration signal properly (Kovatchev 2003, PMID 12930915). |

**Net:** the "deceleration-tail" intent that #8 encoded with `rr_ms_max`/`rr_ms_75%` is fully absorbed by **sample asymmetry (R2)**; the "reduced-spread" intent is already covered by `sdnn` (kept) and now **SampEn**; the acceleration/central-tendency quantiles retire or become display-only. No raw RR quantile survives as a Tier-1 trigger after #3.

---

## Boundary vs #8 / handoff to #3

**#8 left in place** (direction-aware Tier-1 floor): `sdnn`/`rmssd` low-only, `mean_rr` two-sided, and — as *interim crude proxies* — `rr_ms_max`/`rr_ms_75%` high-only.

**#3 should:**
1. **Keep** `sdnn`, `rmssd` (low-only) and `mean_rr` (two-sided) unchanged — these are the validated "reduced variability" + HR-level core.
2. **Add `sampen`** (low-only) with **m = 3, r = 0.2×SD (relax upward for short/noisy windows), N ≈ 4096 RR intervals (~20–25 min)**, mandatory artifact rejection + detrend before computing r/entropy.
3. **Add `sample_asymmetry`** (high-only), computed on **RR** with the R2/R1 (deceleration-weighted) convention so it **rises** toward the pathological state; pin the sign convention explicitly.
4. **Add respiration features** (high-only) from the respiration channel: `resp_rate_variability` / respiratory instability, `apnea_burden` (pauses ≥ ~15–20 s), `periodic_breathing_pct` (wavelet %PB, best as escalation/persistence), and a `bradycardia_event_count` reframing of the transient-deceleration signal.
5. **Retire the crude RR proxies as triggers:** drop `rr_ms_max` and `rr_ms_75%` from the trigger set once sample asymmetry is live; `rr_ms_25%/50%/min` remain display-only (or dropped). Their intent is now carried by sample asymmetry + SD + SampEn.
6. **Do not build any SpO₂ feature** (no SpO₂ in PICS); record **intermittent hypoxemia** as a known, unreproducible gap.

This turns Tier-1 from a generic-statistics anomaly detector into a faithful, direction-aware encoding of the validated HeRO signature — **low SD + low SampEn (reduced variability) with a rising sample asymmetry and rising respiratory instability (transient decelerations + immature breathing)** — using only the ECG + respiration that PICS actually provides.

---

## Open questions / unverified

- **[UNVERIFIED]** *Exact r and N used in Lake 2002.* The neonatal primary (Lake 2002, PMID 12185014) full text is paywalled (HTTP 403); **m = 3** is attributed to it via secondary sources and the abstract confirms it addressed "optimal selection of m and r," but the **exact r value and record length N used in that paper were not machine-verified from the primary text.** The recommended defaults above therefore lean on Richman & Moorman 2000 (PMID 10843903) + the PhysioNet `sampen` reference implementation (m = 2, r = 0.2×SD) and the HeRO operational window (Moorman 2011, PMID 22026974).
- **[UNVERIFIED]** *HeRO preprocessing constants (N ≈ 4096 ≈ 20–25 min; 20%/5-SD outlier filter; ~201-point moving-average detrend).* These were read from the HeRO methods description / summaries around Moorman 2011 (PMID 22026974) and the associated method patent, not from a direct fetch of the primary methods PDF; the ~4096-interval window is consistent across sources, but the exact filter constants should be re-confirmed against the primary before hard-coding.
- **[UNVERIFIED]** *Sample-asymmetry sign convention.* Kovatchev 2003 (PMID 12930915) and Moorman 2011 (PMID 22026974) give a value that **rises** toward decelerations on RR; a secondary review states a "<1" (falling) convention. The *physiology* is unambiguous (reduced accelerations + increased decelerations); the *numeric sign* depends on domain (HR vs RR) and normalization and **must be fixed empirically in #3** before it drives a direction-aware trigger.
- **[UNVERIFIED]** *Richman & Moorman 2000 in-text default values.* The paper's abstract (PMID 10843903) confirms SampEn's reduced bias but does **not** state the m/r defaults; the m = 2, r = 0.2×SD figures come from the PhysioNet reference implementation by the same authors, not the paper's abstract text.
- **[UNVERIFIED]** *Fairchild 2016 part 1 (central apnea) page range and Pre-Vent 2024 author list.* PMID 26959485 and PMID 38570031 (with DOIs) are verified; exact page numbers for part 1 and the full Pre-Vent author list were not independently confirmed and are omitted rather than guessed.
- **[UNVERIFIED]** *Cardiorespiratory-signature multi-NICU model (PMID 36593281).* Cited only as corroboration that combined cardiorespiratory features predict LOS; its DOI and exact feature list were not verified, and it uses **SpO₂**, so it is only partially reproducible on PICS.
- **Open (design):** optimal apnea-pause threshold for PICS (≥10 s with brady/desat per Vergales 2014 vs ≥20 s per Pre-Vent) and the %PB wavelet cutoff both depend on the respiration channel's sampling rate and quality, which should be checked against the actual PICS recordings.
- **Open (design):** with **no sepsis labels** in PICS, none of these directions/thresholds can be *tuned* on this data — they are transferred from the cited cohorts and must be validated later; per-infant baselining + persistence is the safest interim posture.

---

## References

1. **Richman JS, Moorman JR.** Physiological time-series analysis using approximate entropy and sample entropy. *Am J Physiol Heart Circ Physiol.* 2000;278(6):H2039–H2049. PMID: 10843903. DOI: 10.1152/ajpheart.2000.278.6.H2039.
2. **Lake DE, Richman JS, Griffin MP, Moorman JR.** Sample entropy analysis of neonatal heart rate variability. *Am J Physiol Regul Integr Comp Physiol.* 2002;283(3):R789–R797. PMID: 12185014. DOI: 10.1152/ajpregu.00069.2002.
3. **Moorman JR, Delos JB, Flower AA, Cao H, Kovatchev BP, Richman JS, Lake DE.** Cardiovascular oscillations at the bedside: early diagnosis of neonatal sepsis using heart rate characteristics monitoring. *Physiol Meas.* 2011;32(11):1821–1832. PMID: 22026974. DOI: 10.1088/0967-3334/32/11/S08. (PMC4898648)
4. **Kovatchev BP, Farhy LS, Cao H, Griffin MP, Lake DE, Moorman JR.** Sample asymmetry analysis of heart rate characteristics with application to neonatal sepsis and systemic inflammatory response syndrome. *Pediatr Res.* 2003;54(6):892–898. PMID: 12930915. DOI: 10.1203/01.PDR.0000088074.97781.4F.
5. **Griffin MP, Moorman JR.** Toward the early diagnosis of neonatal sepsis and sepsis-like illness using novel heart rate analysis. *Pediatrics.* 2001;107(1):97–104. PMID: 11134441. DOI: 10.1542/peds.107.1.97.
6. **Griffin MP, O'Shea TM, Bissonette EA, Harrell FE Jr, Lake DE, Moorman JR.** Abnormal heart rate characteristics preceding neonatal sepsis and sepsis-like illness. *Pediatr Res.* 2003;53(6):920–926. PMID: 12646726.
7. **Vergales BD, Paget-Brown AO, Lee H, et al.** Accurate automated apnea analysis in preterm infants. *Am J Perinatol.* 2014;31(2):157–162. PMID: 23592319. DOI: 10.1055/s-0033-1343769.
8. **Mohr MA, Fairchild KD, Patel M, Sinkin RA, Clark MT, Moorman JR, Lake DE, Kattwinkel J, Delos JB.** Quantification of periodic breathing in premature infants. *Physiol Meas.* 2015;36(7):1415–1427. PMID: 26012526. DOI: 10.1088/0967-3334/36/7/1415.
9. **Patel M, Mohr M, Lake D, Delos J, Moorman JR, Sinkin RA, Kattwinkel J, Fairchild K.** Clinical associations with immature breathing in preterm infants: part 2—periodic breathing. *Pediatr Res.* 2016;80(1):28–34. PMID: 27002984. DOI: 10.1038/pr.2016.58.
10. **Fairchild K, Mohr M, Paget-Brown A, Tabacaru C, Lake D, Delos J, Moorman JR, Kattwinkel J.** Clinical associations of immature breathing in preterm infants: part 1—central apnea. *Pediatr Res.* 2016;80(1). PMID: 26959485. DOI: 10.1038/pr.2016.43. (page range not independently verified)
11. **Pre-Vent study.** Apnea, Intermittent Hypoxemia, and Bradycardia Events Predict Late-Onset Sepsis in Infants Born Extremely Preterm. *J Pediatr.* 2024;271:114042. PMID: 38570031. DOI: 10.1016/j.jpeds.2024.114042. (ClinicalTrials.gov NCT03174301; author list not independently verified)
12. **Joshi R, Kommers D, Oosterwijk L, Feijs L, van Pul C, Andriessen P.** Predicting neonatal sepsis using features of heart rate variability, respiratory characteristics, and ECG-derived estimates of infant motion. *IEEE J Biomed Health Inform.* 2020;24(3):681–692. PMID: 31295130. DOI: 10.1109/JBHI.2019.2927463.
13. **Sullivan BA, Fairchild KD.** Heart rate analysis in neonatal sepsis: a complex equation. *Pediatr Res.* 2025;97(1):35–37 (Epub 2024). PMID: 39242935. DOI: 10.1038/s41390-024-03548-y.
14. **Fairchild KD, O'Shea TM.** Heart rate characteristics: physiomarkers for detection of late-onset neonatal sepsis. *Clin Perinatol.* 2010;37(3):581–598. PMID: 20813272. DOI: 10.1016/j.clp.2010.06.002.
15. **Task Force of the ESC/NASPE.** Heart rate variability: standards of measurement, physiological interpretation, and clinical use. *Circulation.* 1996;93(5):1043–1065. PMID: 8737210. DOI: 10.1161/01.CIR.93.5.1043.
16. **PhysioNet.** Sample Entropy (`sampen`) reference implementation and documentation (default m = 2, r = 0.2). https://physionet.org/physiotools/sampen/ (software reference for the standard SampEn defaults).
17. *(corroboration only, not verified in full)* Cardiorespiratory signature of neonatal sepsis: development and validation of prediction models in 3 NICUs. PMID: 36593281. (uses SpO₂; only partially reproducible on PICS)

*Citation-precision note (house style): every PMID/DOI above was checked against a primary or authoritative index (PubMed/journal/PhysioNet) during this review. Where an element (exact r/N in Lake 2002, HeRO preprocessing constants, a page range, an author list, one DOI) could not be machine-verified from the primary text, it is flagged **[UNVERIFIED]** in the Open questions section and the value is omitted or qualified rather than guessed. No PMID, DOI, or numeric value in this document was fabricated.*
