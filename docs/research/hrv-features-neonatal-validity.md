# Scientific Validity of NeonatalGuard's 10 HRV Features in Neonates

**Scope:** Feature-by-feature appraisal of whether each heart-rate-variability (HRV) feature used by NeonatalGuard's Tier-1 detector is scientifically valid **specifically in neonates** (term and preterm), using primary sources only (peer-reviewed papers with DOI/PMID and the ESC/NASPE measurement standard). For each feature: (1) definition/physiology per the ESC/NASPE standard, (2) neonatal validation and normal ranges, (3) expected direction of change in impending sepsis/illness, (4) known limitations in infants. Plus focused sub-questions (LF/HF critique, neonatal frequency bands, bradycardia thresholds, RR quantiles) and an evidence-strength table.

**Date:** 2026-07-12
**Prepared for:** Clinical pitch — written to be rigorous and to flag weak/contested features honestly.

**Implementation context being assessed:** Tier-1 takes the **max |z|** across these 10 features versus the infant's own rolling baseline; **|z| ≥ 2 → YELLOW, |z| ≥ 3 → RED**. Because it is a max over co-equal features, *any single* feature — including a weak or contested one — can independently drive a RED alert. That makes per-feature validity a safety-relevant question, not an academic one.

---

## Bottom line

- **Strong, defensible in neonates:** `rmssd` (best-supported short-term vagal marker), `sdnn` (validated overall-variability marker, with caveats), and heart-rate level via `mean_rr` (HR is the central axis of the validated HeRO signal — but see the "mean vs. transient" caveat).
- **Weak / contested — should NOT carry co-equal RED-triggering authority:**
  - `lf_hf_ratio` — contested as a construct in general (Billman 2013) **and** doubly broken in neonates because the adult HF band (0.15–0.4 Hz) does not contain the infant respiratory peak (~0.7–1.3+ Hz; neonatal HF is defined up to ~2 Hz). The clinically validated HeRO system **deliberately does not use frequency-domain LF/HF at all** (Moorman 2011).
  - `pnn50` — severe **floor effect** in neonates (term median ≈ 1.7%); fast neonatal HR rarely produces >50 ms beat-to-beat jumps, so it clusters near zero and discriminates poorly. `pNN20` is the neonatally-appropriate variant.
  - `rr_ms_min` — a single extreme order-statistic; artifact/ectopy-sensitive, non-robust, ambiguous sepsis direction, and not an established named neonatal HRV feature.
- **Moderate / conceptually-aligned but not individually validated:** the RR-distribution quantiles `rr_ms_max`, `rr_ms_25%`, `rr_ms_50%`, `rr_ms_75%`. These are **not** established named features in the neonatal HRV literature, but they *plausibly proxy* constructs that ARE validated: high percentiles (`max`, `75%`) proxy **decelerations** (the hallmark HeRO sepsis signal), the inter-quartile spread (`75%`−`25%`) proxies **reduced variability**, and the median (`50%`) is largely redundant with `mean_rr`. The validated construct is histogram *shape* (sample asymmetry), which raw quantiles only partially capture.
- **Design point in NeonatalGuard's favor:** using each infant as its **own baseline** (per-infant z-score) is the right call, because neonatal HRV varies enormously with gestational and postnatal age; a fixed population normal range would be inappropriate. This does not, however, fix feature-level validity or the max-over-co-equal-features problem.
- **Does HeRO avoid LF/HF? YES — confirmed and explicit.** Moorman et al. (2011) state they use standard deviation, sample asymmetry, and sample entropy, and "have not employed frequency-domain measures in our current bedside monitors," citing four specific problems with spectral analysis of neonatal heart rate (non-stationarity, respiratory-rate dependence, cardiac aliasing, unequal sampling).

---

## Per-feature assessment

Throughout, "Task Force 1996" = the ESC/NASPE standard (Circulation 1996;93:1043–1065 / Eur Heart J 1996;17:354–381, PMID 8737210), which defines every time- and frequency-domain metric below and the adult frequency bands.

### 1. `mean_rr` (mean RR / NN interval)

1. **Definition/physiology.** The average of normal-to-normal (NN) inter-beat intervals; the reciprocal of mean heart rate (Task Force 1996). It reflects the net set-point of heart rate — the balance of intrinsic sinoatrial rate plus tonic sympathetic (rate-raising) and parasympathetic/vagal (rate-lowering) input.
2. **Neonatal validation / normal range.** Well-established. Healthy term newborns in the first 6 h have median HR ≈ 122 bpm (mean RR ≈ 490 ms) over 5-min ECG segments (Oliveira 2019). Normal neonatal HR is typically ~120–160 bpm (mean RR ~375–500 ms); preterm infants run faster with higher baseline HR (Sullivan & Fairchild 2024; Patural 2022).
3. **Sepsis direction.** The **dominant** early change is **tachycardia** → mean RR **down**. However, the validated HeRO signature is *reduced baseline variability punctuated by transient decelerations* (brief mean-RR upswings) that occur hours-to-days before clinical sepsis (Griffin 2003; Moorman 2011; Sullivan & Fairchild 2024). So the informative content is bidirectional: sustained tachycardia (RR down) **plus** transient decelerations (RR spikes up).
4. **Limitations in infants.** (a) A *window mean* smooths over exactly the **transient decelerations** that carry the validated signal — so `mean_rr` alone is a coarse proxy for the HeRO deceleration phenomenon. (b) NeonatalGuard's stated bradycardia proxy `mean_rr > 600 ms` (mean HR < 100 bpm) equals the **Neonatal Resuscitation Program** delivery-room bradycardia number, but a *sustained* mean HR < 100 is more typical of apnea-of-prematurity spells or late/terminal deterioration than of early sepsis, whose onset is usually tachycardic (see bradycardia sub-question). **Verdict: HR is clinically central (moderate–strong), but a windowed mean is a blunt instrument for the transient-deceleration signal.**

### 2. `sdnn` (standard deviation of NN intervals)

1. **Definition/physiology.** The standard deviation of all NN intervals over the analysis window; because variance is mathematically the total power, SDNN reflects **all** cyclic components contributing to variability — i.e., *overall* HRV, not a specific autonomic branch (Task Force 1996).
2. **Neonatal validation / normal range.** Validated and widely used; increases with gestational age and postnatal maturation as autonomic control develops (Patural 2022). Healthy term newborns: SDNN median ≈ 27.5 ms over 5-min segments (Oliveira 2019). Preterm infants are far lower (single-digit-to-low-double-digit ms in very preterm cohorts) and rise with maturation (Patural 2022).
3. **Sepsis direction.** **Down** — reduced overall variability is the core abnormality detected by HeRO's SD-of-RR term (Griffin 2003; Moorman 2011). Caveat: in an endotoxemia model, the fall in HRV was statistically *attributable almost entirely to the rise in HR*, not to an independent variability collapse (Sullivan & Fairchild 2024).
4. **Limitations in infants.** **Length-dependence:** the Task Force explicitly warns that total variance — and therefore SDNN — grows with the length of the recording, so SDNN values from different recording durations are not comparable and must be computed over standardized windows (Task Force 1996). SDNN is also HR-confounded and sensitive to artifact/ectopy. **Verdict: strong construct, moderate in practice — valid only with fixed windows and per-infant baselining (both of which NeonatalGuard's design supports).**

### 3. `rmssd` (root mean square of successive differences)

1. **Definition/physiology.** The square root of the mean of squared differences between successive NN intervals; a **short-term, beat-to-beat** measure that primarily indexes **parasympathetic (vagal)** modulation (Task Force 1996; Patural 2022).
2. **Neonatal validation / normal range.** The best-supported short-term vagal marker in neonates; rMSSD and pNN50 "represent the rapid changes associated with the parasympathetic activity," and vagal indices rise with gestational age (Patural 2022). Healthy term newborns: RMSSD median ≈ 18.3 ms over 5-min segments (Oliveira 2019); preterm values are lower and increase with maturation.
3. **Sepsis direction.** **Down** — loss of beat-to-beat vagal variability accompanies the reduced-variability HRC pattern (Griffin 2003; Moorman 2011).
4. **Limitations in infants.** Still partly HR-confounded (Sullivan & Fairchild 2024); transient decelerations can momentarily inflate successive-difference terms; sensitive to ectopy/artifact at the beat-to-beat scale. **Verdict: strong — the most defensible short-term vagal metric to keep.**

### 4. `pnn50` (proportion of successive NN differences > 50 ms)

1. **Definition/physiology.** NN50 = count of successive NN interval pairs differing by > 50 ms; pNN50 = NN50 ÷ total NN count. Like RMSSD it indexes short-term **vagal** activity and correlates strongly with RMSSD (Task Force 1996; Patural 2022).
2. **Neonatal validation / normal range.** Here the metric largely **fails in neonates due to a floor effect.** Healthy term newborns have pNN50 median ≈ **1.7%** versus pNN20 median ≈ **14.8%** (Oliveira 2019). Because neonatal HR is fast and beat-to-beat variability is small, successive intervals rarely differ by the full 50 ms threshold, so pNN50 clusters near zero and loses discriminative power; lower thresholds (pNN20) separate groups far better (Mietus 2002; Oliveira 2019).
3. **Sepsis direction.** In principle **down** (less vagal variability), but near the floor there is little dynamic range left to move, so sensitivity is poor.
4. **Limitations in infants.** The 50 ms threshold is an adult convention that is inappropriate for neonatal heart rates; near-zero baseline → low signal-to-noise and unreliable z-scores (a tiny absolute change can produce a large spurious z when the baseline SD is ~0). **Verdict: weak in neonates — floor effect. Prefer pNN20, or drop from the co-equal RED set.**

### 5. `lf_hf_ratio` (low-frequency / high-frequency power ratio)

1. **Definition/physiology.** Ratio of LF power (adult band 0.04–0.15 Hz) to HF power (adult band 0.15–0.4 Hz), historically promoted as an index of "sympatho-vagal balance," with HF taken as vagal/respiratory and LF as mixed (Task Force 1996).
2. **Neonatal validation.** **Doubly problematic.** (a) As a *construct* it is contested even in adults — see the Billman 2013 critique in the sub-questions below. (b) In *neonates* the adult band boundaries are wrong: the infant respiratory/ventilatory peak sits well above the adult HF ceiling of 0.4 Hz, so neonatal HF is defined much wider — "high frequencies (HF) of 0.15 to **2 Hz** in newborns correspond to the ventilatory component under the exclusive control of the parasympathetic system" (Patural 2022). With adult bands, genuine respiratory (vagal) power leaks out of the HF window, corrupting both numerator and denominator. Notably, the clinically validated HeRO system **does not use frequency-domain LF/HF at all** (Moorman 2011), and a normative neonatal study explicitly de-emphasized LF/HF "due to ongoing controversies regarding interpretation" (Oliveira 2019).
3. **Sepsis direction.** **Uncertain / not cleanly interpretable** in neonates; reported changes are inconsistent and confounded (Billman 2013; Sullivan & Fairchild 2024).
4. **Limitations in infants.** Adult bands misclassify infant respiration; ratio is non-stationary and mathematically unstable (same value from opposite physiology); no neonatal outcome validation as a threshold feature. **Verdict: weak/contested — this feature having co-equal power to fire a RED alert is the single biggest scientific liability in the Tier-1 design.**

### 6. `rr_ms_min` (minimum RR in window)

1. **Definition/physiology.** The shortest NN interval in the window — i.e., the single fastest beat / deepest acceleration. **Not** an ESC/NASPE-defined HRV metric; it is a raw order statistic of the RR distribution.
2. **Neonatal validation.** Not an established named feature in the neonatal HRV literature. The *related* validated construct is **accelerations** (the "R1" term of sample asymmetry), but HeRO quantifies these from the whole-histogram shape, not from a single extreme value (Kovatchev 2003; Moorman 2011).
3. **Sepsis direction.** **Ambiguous.** Tachycardia would push the minimum RR down, but the abnormal HRC pattern includes *reduced accelerations* (R1 down), which would truncate the fast tail and push the minimum RR **up**. The two effects oppose each other.
4. **Limitations in infants.** A single extreme value is maximally sensitive to artifact, motion, and ectopic beats; non-robust; low test-retest reliability; redundant with HR-level information. **Verdict: weak / no neonatal validation as a named feature — noise-prone and directionally ambiguous.**

### 7. `rr_ms_max` (maximum RR in window)

1. **Definition/physiology.** The longest NN interval in the window — the single slowest beat / deepest **deceleration**. A raw order statistic, not an ESC/NASPE metric.
2. **Neonatal validation.** The raw maximum is not itself a named feature, **but it points at the single most validated neonatal-sepsis phenomenon: transient decelerations.** Reduced variability *with transient decelerations* is the hallmark HRC pattern preceding sepsis (Griffin 2003; Kovatchev 2003; Moorman 2011).
3. **Sepsis direction.** **Up** — more and deeper decelerations raise the window maximum. This is the quantile most directly aligned with the validated signal.
4. **Limitations in infants.** A single extreme is artifact-sensitive (a missed beat looks like a huge deceleration); the *validated* approach measures **deceleration burden across the whole histogram** (sample asymmetry / "R2"), not one outlier. A robust high-percentile (e.g., the 95th/99th) or an explicit deceleration detector would be sounder than the raw max. **Verdict: moderate — conceptually proxies the validated deceleration signal, but the raw estimator is fragile.**

### 8–10. `rr_ms_25%`, `rr_ms_50%` (median), `rr_ms_75%` (RR distribution quartiles)

1. **Definition/physiology.** Order statistics of the RR distribution: the median (50th percentile) is a robust central-tendency estimate (≈ inverse of median HR); the 25th/75th percentiles bound the central half, and the **inter-quartile range (75%−25%)** is a robust, outlier-resistant measure of spread. None are ESC/NASPE-defined, though percentiles are discussed as intuitive distribution descriptors in the HeRC literature (Moorman 2011).
2. **Neonatal validation.** These specific quartile features are **not** validated named HRV metrics in neonates. However, HeRO's foundational method **is** a shape-of-the-RR-histogram approach — sample asymmetry quantifies how decelerations/accelerations distort the histogram, and the authors explicitly note that non-parametric percentiles "can provide more intuitive information" about such distributions (Kovatchev 2003; Moorman 2011). So the quartiles are *in the family* of validated ideas without being individually validated.
3. **Sepsis direction.** Median → **down** with tachycardia (largely redundant with `mean_rr`); IQR (75%−25%) → **down** with reduced variability (a robust proxy for the SDNN/RMSSD signal); 75th percentile → **up** if the deceleration tail thickens.
4. **Limitations in infants.** Individually redundant/overlapping (median ≈ mean_rr; IQR ≈ robust SDNN), and — crucially — the validated construct is histogram **asymmetry** (the *difference* between how the upper and lower tails deviate from center), which no single quartile captures; you need the *combination* (e.g., asymmetry of 75% vs 25% about the median) to approximate sample asymmetry. As raw co-equal z-score features they add correlated, partially-redundant triggers. **Verdict: median weak/redundant; IQR a reasonable robust-spread proxy; 75% a reasonable deceleration proxy — but none individually neonatally validated, and they should ideally be combined into an asymmetry statistic rather than fired independently.**

---

## Focused sub-questions

### A. The LF/HF ratio does not cleanly measure sympatho-vagal balance — and is worse in neonates

**General critique (Billman 2013, Front Physiol 4:26, DOI 10.3389/fphys.2013.00026):** The claim that LF/HF indexes cardiac sympatho-vagal balance "has been disproven." Specifically:
- **LF is not a pure sympathetic marker.** Cholinergic blockade / parasympathectomy reduces LF power by ~50%, so LF is a *mixture* of sympathetic and parasympathetic (and other) influences; direct muscle-sympathetic-nerve recordings do not correlate with LF power in healthy subjects or heart-failure patients. In one preparation, combined β-blockade plus parasympathetic denervation *raised* LF/HF (1.1 → 8.4), the opposite of the "sympathetic dominance" interpretation.
- **HF is confounded by respiration**, independent of autonomic tone (rate and tidal volume both shift HF); most human studies did not control respiration.
- **Sympathetic and parasympathetic effects are non-linear and non-reciprocal**, so a change in the ratio cannot be mapped to a change in "balance."
- **The ratio is mathematically ambiguous:** identical LF/HF values arise from opposite physiological states (change the numerator, the denominator, or both), so "spurious values for LF/HF can result as a consequence of the mathematical manipulations."

**Additional neonatal problem — the bands are wrong for infants.** The adult HF band is 0.15–0.4 Hz (Task Force 1996). Infant respiration is far faster: newborn/preterm respiratory rates of ~40–80 breaths/min correspond to ~0.7–1.3+ Hz, i.e., **above** the adult HF ceiling. Accordingly, neonatal HRV work defines HF up to ~2 Hz — "high frequencies (HF) of 0.15 to 2 Hz in newborns correspond to the ventilatory component" (Patural 2022); more broadly, the standard adult LF/HF classification "do[es] not apply in the infant case," and no consensus infant band scheme yet exists. Using adult bands therefore pushes real respiratory (vagal) power out of the HF window and into/above the boundary, corrupting the ratio in a direction that is hard to predict.

**Does the validated HeRO system use LF/HF? No — confirmed explicitly.** Moorman et al. (2011, Physiol Meas 32(11):1821–1832, PMID 22026974) use three **time-domain** measures — standard deviation (histogram width), sample asymmetry (deceleration/acceleration imbalance), and sample entropy (non-Gaussianity) — and state: *"We have not employed frequency-domain measures in our current bedside monitors,"* citing four fundamental problems with spectral analysis of neonatal HR: non-stationarity, respiratory-rate dependence, cardiac aliasing, and unequal sampling intervals. A neonatal normative study likewise de-emphasized LF/HF "due to ongoing controversies regarding interpretation" (Oliveira 2019).

**Implication for NeonatalGuard:** treating `lf_hf_ratio` as a co-equal threshold feature that can independently fire a RED alert is not supported by the neonatal evidence and diverges from the one HRV monitor with a mortality-reduction RCT (HeRO). Recommend demoting or removing it, or at minimum recomputing HF with neonatally-appropriate bands and never letting it solo-trigger.

### B. RMSSD & pNN50 as short-term (vagal) markers — which is more reliable in neonates?

Both are Task Force-defined vagal indices and are strongly correlated (Task Force 1996; Patural 2022). In neonates, **RMSSD is the more reliable of the two.** pNN50 suffers a **floor effect**: fast neonatal HR and low absolute variability mean successive intervals seldom differ by >50 ms, so term-newborn pNN50 medians are ~1.7% versus ~14.8% for pNN20 (Oliveira 2019), and lower pNN thresholds discriminate better (Mietus 2002). RMSSD retains dynamic range and is the standard short-term vagal marker used in neonatal maturation studies (Patural 2022). **Keep RMSSD; treat pNN50 as weak (or replace with pNN20).**

### C. SDNN and recording length

The Task Force 1996 standard is explicit that SDNN is **length-dependent**: because SDNN equals the square root of total variance, and total variance rises as longer recordings capture more slow cyclic components, SDNN computed over 24 h is systematically larger than over 5 min, and **SDNN values from recordings of different durations must not be compared.** The standard therefore fixes two canonical windows — ~5-min "short-term" and ~24-h "long-term." For NeonatalGuard this means SDNN (and, to a lesser degree, all variance-based features) is only meaningful if the analysis window is held **constant** and baselining is per-infant — both of which the design appears to do.

### D. `mean_rr` and neonatal bradycardia thresholds

There is **no single universal neonatal bradycardia threshold**; the number depends on the clinical frame:
- **Neonatal Resuscitation Program (NRP):** bradycardia = HR **< 100 bpm** (the delivery-room resuscitation trigger). NeonatalGuard's `mean_rr > 600 ms` (mean HR < 100 bpm) proxy matches *this* number.
- **PALS / general infant physiology:** bradycardia is often taken as **< 80 bpm** (some use < 60 bpm for symptomatic bradycardia); "severe" neonatal bradycardia is frequently defined **< 80 bpm** and "mild" as 80–100 bpm.
- **Apnea-of-prematurity spells** are commonly defined by HR **< 80 bpm** for ≥ ~10 s, or a **≥ 33% drop** from baseline with desaturation — and one detection study using a flat < 80 bpm rule reported a **64% false-alarm rate**, underscoring that a fixed cutoff is a blunt tool (Cardiovascular/bradycardia-detection literature: PMC8131388; delivery-room HR review PMC10528538).

Two honest caveats for the proxy: (1) **HR < 100 is the resuscitation number, not the NICU norm** — healthy neonatal HR is ~120–160, so a *sustained* mean HR < 100 is genuinely bradycardic, but it is more characteristic of **apnea-bradycardia of prematurity** or late/terminal deterioration than of early sepsis, whose onset is usually **tachycardic**. (2) A *window mean* crossing 600 ms captures **sustained** bradycardia, whereas the validated early-sepsis signal is **transient decelerations** superimposed on a tachycardic baseline (Griffin 2003; Moorman 2011; Sullivan & Fairchild 2024). So `mean_rr` is relevant to apnea-bradycardia monitoring but is not, by itself, the early-sepsis discriminator.

### E. RR-distribution quantiles (min/max/25/50/75) — are order statistics used in neonatal HRC?

**Directly as raw min/max/quartile features: no — these are not established, named, neonatally-validated HRV metrics.** But the *idea* is adjacent to validated work:
- HeRO's **sample asymmetry** (Kovatchev 2003; Griffin 2003; Moorman 2011) is precisely a *shape-of-the-RR-histogram* statistic: it separates the contribution of **decelerations** (bigger/more → increased "R2") from **accelerations** (fewer → decreased "R1"), and the authors note that non-parametric **percentiles** are an intuitive way to describe such distributions (Moorman 2011). The abnormal, pre-sepsis histogram is *asymmetric* — a long deceleration tail with a truncated acceleration side (Kovatchev 2003).
- Mapping to NeonatalGuard's features: **`rr_ms_max` and `rr_ms_75%` plausibly proxy the deceleration tail** (the validated signal, expected **up** in sepsis); the **IQR (`75%`−`25%`) proxies reduced spread/variability** (expected **down**); **`rr_ms_50%` is largely redundant with `mean_rr`**; and **`rr_ms_min` is the noisiest and least interpretable** (deep accelerations, artifact).

**Honest assessment:** the quantile *family* is defensible as a rough, robust re-encoding of "central rate + spread + deceleration tail," and the deceleration-tail piece aligns with the single best-validated neonatal-sepsis phenomenon. But (a) none of these five features is individually validated in neonates, (b) they are mutually correlated and correlated with `mean_rr`/`sdnn`, and (c) the validated construct is *asymmetry* (a relationship between the tails), which no single quantile captures — so firing each quartile independently as a co-equal z-score is weaker than combining them into an explicit asymmetry/deceleration statistic à la HeRO.

---

## Summary table

| Feature | Neonatally validated? | Expected sepsis direction | Key caveat |
|---|---|---|---|
| `mean_rr` | **Moderate–strong** (HR is central to validated HeRO signal) | Mean **down** (tachycardia) + transient **up**-spikes (decelerations) | Window mean blurs the transient decelerations that carry the signal; `>600 ms` = NRP resuscitation threshold, not early-sepsis-specific |
| `sdnn` | **Strong construct / moderate in practice** | **Down** (reduced overall variability) | Length-dependent (Task Force 1996) — fixed window mandatory; HR-confounded; artifact-sensitive |
| `rmssd` | **Strong** (best short-term vagal marker) | **Down** | Still partly HR-confounded; beat-to-beat → ectopy/artifact sensitive |
| `pnn50` | **Weak** (floor effect) | Down in principle, poor sensitivity | Term median ~1.7% → clusters near zero; use pNN20 instead |
| `lf_hf_ratio` | **Weak / contested** | Uncertain / not interpretable | Construct disputed (Billman 2013); adult bands miss infant respiration (HF to ~2 Hz); HeRO deliberately avoids it |
| `rr_ms_min` | **None** as a named feature | **Ambiguous** (tachycardia ↓ vs reduced accelerations ↑) | Single extreme → artifact/ectopy-sensitive, non-robust |
| `rr_ms_max` | **Moderate** (proxies validated decelerations) | **Up** | Raw max is fragile; validated method uses whole-histogram deceleration burden, not one outlier |
| `rr_ms_25%` | **Weak–moderate** (part of robust spread) | **Up** (toward median) / contributes to ↓ IQR | Redundant; only meaningful combined into IQR/asymmetry |
| `rr_ms_50%` (median) | **Weak** (redundant) | **Down** (tachycardia) | Largely duplicates `mean_rr` |
| `rr_ms_75%` | **Moderate** (proxies deceleration tail + spread) | **Up** (deceleration tail) / ↓ IQR | Not individually validated; best combined into an asymmetry statistic |

Legend: strong = direct neonatal peer-reviewed validation; moderate = conceptually aligned with validated constructs but not validated as this exact feature; weak = validated construct that performs poorly in neonates, or redundant; none = no neonatal validation as a named feature.

---

## Confidence & conflicting evidence

- **High confidence:** ESC/NASPE definitions and adult bands; SDNN length-dependence; the pNN50 neonatal floor effect (direct empirical numbers, Oliveira 2019 + Mietus 2002); that HeRO uses time-domain/nonlinear measures and explicitly avoids LF/HF (Moorman 2011); that reduced variability + transient decelerations precede neonatal sepsis (Griffin 2003; Kovatchev 2003; Moorman 2011); and that adult HF bands do not fit infant respiration (Patural 2022).
- **Genuine conflict / open questions:**
  - **Is the HRV drop in sepsis independent of heart rate?** Sullivan & Fairchild (2024) report that in an endotoxemia model the HRV decline was statistically *entirely attributable to the HR rise*, questioning whether SDNN/RMSSD add information beyond HR — an argument to weight `mean_rr` heavily and to use HR-robust measures (e.g., entropy) rather than to stack many correlated variability features.
  - **Direction ambiguity** for `rr_ms_min` and `lf_hf_ratio` is real, not just uncertainty on our part — the physiology pushes both ways.
  - **No consensus neonatal frequency-band scheme** exists (Patural 2022), so any spectral feature is method-dependent.
  - **Normative ranges vary enormously with gestational and postnatal age** (Patural 2022; Oliveira 2019), which is exactly why NeonatalGuard's **per-infant baseline** approach is appropriate — but it also means a z-score computed against a noisy or near-floor baseline (notably pNN50) can be numerically unstable and produce spurious large |z|.
- **Design-level flag for the pitch:** because Tier-1 is a **max over co-equal features**, the *weakest* feature sets the false-alarm floor. The evidence supports keeping `rmssd`, `sdnn`, and HR/`mean_rr` as primary; demoting or removing `lf_hf_ratio` and `pnn50`; treating `rr_ms_min` as noise; and, ideally, replacing the independent quartile triggers with a single HeRO-style **deceleration / sample-asymmetry** statistic that the literature actually validates.

---

## References

1. **Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology.** Heart rate variability: standards of measurement, physiological interpretation, and clinical use. *Circulation.* 1996;93(5):1043–1065 (also *Eur Heart J.* 1996;17(3):354–381). PMID: 8737210. DOI: 10.1161/01.CIR.93.5.1043. https://pubmed.ncbi.nlm.nih.gov/8737210/
2. **Billman GE.** The LF/HF ratio does not accurately measure cardiac sympatho-vagal balance. *Front Physiol.* 2013;4:26. DOI: 10.3389/fphys.2013.00026. PMC3576706. https://pmc.ncbi.nlm.nih.gov/articles/PMC3576706/
3. **Moorman JR, Delos JB, Flower AA, Cao H, Kovatchev BP, Richman JS, Lake DE.** Cardiovascular oscillations at the bedside: early diagnosis of neonatal sepsis using heart rate characteristics monitoring. *Physiol Meas.* 2011;32(11):1821–1832. PMID: 22026974. DOI: 10.1088/0967-3334/32/11/S08. https://pmc.ncbi.nlm.nih.gov/articles/PMC4898648/
4. **Griffin MP, O'Shea TM, Bissonette EA, Harrell FE Jr, Lake DE, Moorman JR.** Abnormal heart rate characteristics preceding neonatal sepsis and sepsis-like illness. *Pediatr Res.* 2003;53(6):920–926. PMID: 12646726. https://pubmed.ncbi.nlm.nih.gov/12646726/
5. **Kovatchev BP, Farhy LS, Cao H, Griffin MP, Lake DE, Moorman JR.** Sample asymmetry analysis of heart rate characteristics with application to neonatal sepsis and systemic inflammatory response syndrome. *Pediatr Res.* 2003. https://www.nature.com/articles/pr2003513
6. **Griffin MP, Moorman JR.** Toward the early diagnosis of neonatal sepsis and sepsis-like illness using novel heart rate analysis. *Pediatrics.* 2001;107(1):97–104. PMID: 11134441. https://pubmed.ncbi.nlm.nih.gov/11134441/
7. **Sullivan BA, Fairchild KD.** Heart rate analysis in neonatal sepsis: a complex equation. *Pediatr Res.* 2024. PMID: 39242935. DOI: 10.1038/s41390-024-03548-y. https://pmc.ncbi.nlm.nih.gov/articles/PMC11798831/
8. **Patural H, Franco P, Pichot V, Giraud A.** Heart rate variability analysis to evaluate autonomic nervous system maturation in neonates: an expert opinion. *Front Pediatr.* 2022;10:860145. DOI: 10.3389/fped.2022.860145. https://www.frontiersin.org/journals/pediatrics/articles/10.3389/fped.2022.860145/full
9. **Oliveira V, von Rosenberg W, Montaldo P, et al.** Early postnatal heart rate variability in healthy newborn infants. *Front Physiol.* 2019;10:922. PMID: 31440164. DOI: 10.3389/fphys.2019.00922. https://pmc.ncbi.nlm.nih.gov/articles/PMC6692663/
10. **Mietus JE, Peng CK, Henry I, Goldsmith RL, Goldberger AL.** The pNNx files: re-examining a widely used heart rate variability measure. *Heart.* 2002;88(4):378–380. PMC1767394. https://pmc.ncbi.nlm.nih.gov/articles/PMC1767394/
11. **Lake DE, Richman JS, Griffin MP, Moorman JR.** Sample entropy analysis of neonatal heart rate variability. *Am J Physiol Regul Integr Comp Physiol.* 2002;283(3):R789–R797. DOI: 10.1152/ajpregu.00069.2002. https://journals.physiology.org/doi/full/10.1152/ajpregu.00069.2002
12. **Longin E, Gerstner T, Schaible T, Lenz T, König S.** Short-term heart rate variability in healthy neonates: normative data and physiological observations. *Early Hum Dev.* 2005;81(8):663–671. (Neonatal normative reference; cited via Patural 2022.)
13. **Early bradycardia detection and therapeutic interventions in preterm infant monitoring.** *Sci Rep.* 2021. PMC8131388. https://pmc.ncbi.nlm.nih.gov/articles/PMC8131388/ (bradycardia thresholds and false-alarm rates)
14. **Significance of neonatal heart rate in the delivery room — a review.** PMC10528538. https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10528538/ (NRP HR < 100 bpm bradycardia framing)

*Note on citation precision: where an exact page range, PMID, or DOI was not independently verified from a primary page (items 5, 12, 13, 14), the verified elements (authors/title/journal/year and a stable URL) are given and the unverified elements omitted rather than guessed. No citation, value, or normal range in this document was fabricated; features with no neonatal validation are stated as such.*
