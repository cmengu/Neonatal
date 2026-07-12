# Clinical Evidence Base for Heart-Rate-Variability (HRV) Monitoring to Detect Neonatal Sepsis

*Scope: a primary-source, deliberately non-promotional appraisal of the clinical evidence that HRV / heart-rate-characteristics (HRC) monitoring detects impending late-onset neonatal sepsis, mapped to the NeonatalGuard Tier 1 design.*
*Date: 2026-07-12*

---

## Bottom line

The core physiology is real and reasonably well understood: systemic infection depresses beat-to-beat heart-rate variability and superimposes transient decelerations, mediated by the vagal cholinergic anti-inflammatory pathway and pro-inflammatory cytokines (Fairchild & O'Shea 2010, Clin Perinatol, PMID 20813272). The abnormal signature that precedes clinical sepsis is well characterised and consistent across the founding studies — **reduced baseline variability PLUS transient repetitive decelerations** — and it emerges up to ~24 h before overt deterioration (Griffin & Moorman 2001, Pediatrics, PMID 11134441). One adequately powered RCT (the HeRO trial, N=3003) showed a real but modest mortality benefit from displaying the HRC index (10.2%→8.1%; HR 0.78), concentrated in <1000 g infants (Moorman et al. 2011, J Pediatr, PMID 21864846). Crucially, the trial did **not** reduce the incidence of sepsis — the benefit is attributed to earlier treatment of sepsis that still occurred (Fairchild et al. 2013, Pediatr Res, PMID 23942558). The evidence is thinner than the marketing implies: a 2023 systematic review rated the single RCT's quality as **low**, found the mortality signal concentrated implausibly in a low-lethality organism (coagulase-negative staphylococci), flagged an unexplained excess of deafness in the monitored arm, and recommended a new international RCT before adoption as standard of care (Koppens et al. 2023, Neonatology, PMID 37379804). Real-world use has under-performed the validation studies — in a 2384-infant cohort, elevated HRC scores had low positive predictive value for bloodstream infection because respiratory deterioration and surgery also raise the score (Coggins et al. 2016, Arch Dis Child Fetal Neonatal Ed, PMID 26518312). The direction of the abnormality (variability **down**, decelerations = downward HR excursions) and its temporal, drifting evolution are central to the validated signal — two properties that the current NeonatalGuard Tier 1 design (absolute |z|, stateless) does not preserve.

---

## 1. Physiological basis linking sepsis / systemic inflammation to HRV changes

**Autonomic / vagal mechanism.** Sepsis and its systemic inflammatory response depress heart-rate variability by dysregulating autonomic (chiefly vagal) control of the sinoatrial node; the same process produces transient decelerations attributed to intermittent vagal firing during systemic inflammation (Fairchild & O'Shea 2010, Clin Perinatol 37(3):581-598, PMID 20813272, DOI 10.1016/j.clp.2010.06.002).

**Cholinergic anti-inflammatory pathway.** Vagal efferent signalling releases acetylcholine, which binds macrophage receptors and dampens production of pro-inflammatory cytokines (tumour necrosis factor, interleukin-1β); the decelerations of impending sepsis are proposed to be pathogen-induced vagus-nerve firing as part of this protective cholinergic anti-inflammatory reflex (Fairchild 2013, Curr Opin Pediatr 25(2):172-179, PMID 23407184, DOI 10.1097/MOP.0b013e32835e8fe6).

**Cytokine–HRV coupling.** An inverse correlation has been shown between HRV and pro-inflammatory cytokine production in sepsis; experimentally, TNF-α alone is sufficient to depress HRV, and dexamethasone (suppressing cytokines) resolves the abnormal HRV — establishing a mechanistic, not merely correlational, link (Fairchild & O'Shea 2010, Clin Perinatol, PMID 20813272).

> **Mapping to NeonatalGuard.** SUPPORTS the premise: there is a genuine biological pathway by which infection perturbs HRV, so monitoring HRV features is scientifically justified. It does **not** by itself justify any particular feature set or thresholding scheme — see §2–§3.

---

## 2. The specific abnormal signature that precedes sepsis

**The claim is confirmed, not refuted.** The founding study defined the signature as **reduced baseline variability together with short-lived (transient) decelerations of heart rate** occurring before abrupt clinical deterioration (Griffin & Moorman 2001, Pediatrics 107(1):97-104, PMID 11134441, DOI 10.1542/peds.107.1.97). The review literature restates it identically: "decreased HRV but also transient, repetitive heart-rate decelerations coinciding with or preceding clinical signs of sepsis" — i.e. *decreased variability with multiple superimposed transient decelerations* (Fairchild & O'Shea 2010, Clin Perinatol, PMID 20813272). So yes — (a) reduced baseline variability **plus** (b) transient decelerations **is** the actual HRC signature.

**What the validated algorithm actually computes.** The HRC index (the "HeRO score") is the output of a logistic-regression model over three features predicting acute clinical deterioration in the next 24 h (Fairchild & O'Shea 2010, Clin Perinatol, PMID 20813272):
1. **Standard deviation** of RR intervals — the low-variability component.
2. **Sample asymmetry** — a *directional* measure that is <1 when the histogram has a tail toward decelerations; this is what specifically detects the transient decelerations.
3. **Sample entropy** — signal irregularity, which *falls* before sepsis.

The original discriminator in Griffin & Moorman 2001 was the distribution's **third moment (skewness)**: +0.59 ± 0.10 in sepsis and +0.51 ± 0.12 in sepsis-like illness versus −0.10 ± 0.13 in controls over the 6 h before deterioration (Griffin & Moorman 2001, Pediatrics, PMID 11134441). Skewness/asymmetry — not symmetric spread — carried the signal. A recent editorial reiterates that HR **skewness and kurtosis** (not just mean and SD) are the informative moments around sepsis onset (Sullivan & Fairchild 2025, Pediatr Res 97(1):35-37, PMID 39242935, DOI 10.1038/s41390-024-03548-y).

> **Mapping to NeonatalGuard.**
> - **PARTIAL SUPPORT** for the "reduced variability" half: SDNN, RMSSD and pnn50 directly capture the low-variability component the evidence requires (Griffin & Moorman 2001, PMID 11134441).
> - **DIVERGES on the deceleration half.** The validated signal is carried by *asymmetry/skewness* (sample asymmetry, 3rd moment) and *sample entropy* (Fairchild & O'Shea 2010, PMID 20813272; Griffin & Moorman 2001, PMID 11134441). NeonatalGuard's 10 features include **no skewness/asymmetry feature and no entropy feature.** The RR percentile features (min / 25 / 50 / 75 / max) capture the *tails* of the distribution but a symmetric per-feature z-score does not encode the left/right asymmetry that distinguishes a decelerating infant from a merely noisy one. Recommend adding (i) an RR/HR skewness or sample-asymmetry feature and (ii) a sample-entropy feature; these are the two most sepsis-specific elements and both are currently missing.

---

## 3. Direction of change (does variability go DOWN?)

**Yes — the pathological direction is unambiguous and it matters.** In impending sepsis, variability **decreases** (fewer small accelerations/decelerations, lower SD/entropy) and the transient events are **decelerations** — downward excursions of heart rate (equivalently, upward/longer RR-interval excursions) (Griffin & Moorman 2001, Pediatrics, PMID 11134441; Fairchild & O'Shea 2010, Clin Perinatol, PMID 20813272). The validated algorithm encodes this direction explicitly: **sample asymmetry** is a signed/directional statistic (<1 for a deceleration tail), and **sample entropy decreases** (not "changes") before deterioration (Fairchild & O'Shea 2010, PMID 20813272). Direction is therefore part of the signal, not incidental.

A 2025 editorial adds an important nuance that *cuts against direction-blind schemes*: depressed HRV can occur with or without a change in mean HR, and healthy infants can show tachycardia with normal HRV — so magnitude alone, stripped of direction and context, is a weak discriminator (Sullivan & Fairchild 2025, Pediatr Res, PMID 39242935).

> **Mapping to NeonatalGuard — this is the single most important divergence.**
> - **DIVERGES.** Tier 1 takes `max |z|` and discards sign. For the variability features (SDNN, RMSSD, pnn50) the evidence says **low = pathological**; a symmetric |z| would fire equally on a *high* variability outlier, which is generally reassuring/normal, not septic (Fairchild & O'Shea 2010, PMID 20813272). This inflates false positives and dilutes the specific low-variability signature.
> - **Nuance (partly defensible):** for `mean_rr` the direction is genuinely bidirectional — sepsis can present with baseline tachycardia *and* with transient bradycardic decelerations — so a two-sided test on mean HR is not unreasonable (Sullivan & Fairchild 2025, PMID 39242935). The problem is applying the *same* direction-blind rule to the variability features, where direction is known.
> - **Recommendation:** make the variability features (SDNN, RMSSD, pnn50, sample entropy if added) one-sided (flag only low), and reserve two-sided testing for mean-level features where the literature is genuinely ambiguous.

---

## 4. Lead time before clinical diagnosis

Abnormal HRC appear **up to ~24 hours** before abrupt clinical deterioration, with statistically significant changes already measurable in the **6-hour** window preceding the event (Griffin & Moorman 2001, Pediatrics, PMID 11134441). The HRC index is explicitly calibrated as the fold-increase in risk of a sepsis-like deterioration **in the next 24 h**, and in illustrative cases rises over roughly the preceding 12 h from baseline (~0.5) to a ~4-fold risk before laboratory confirmation (Fairchild & O'Shea 2010, Clin Perinatol, PMID 20813272; Fairchild 2013, Curr Opin Pediatr, PMID 23407184). Net: a practical actionable lead time on the order of **6–24 h**.

> **Mapping to NeonatalGuard.**
> - **DIVERGES for a stateless Tier 1.** The predictive value comes from a signal that *rises over hours* — a trajectory, not a single abnormal reading (Fairchild & O'Shea 2010, PMID 20813272; Griffin & Moorman 2001, PMID 11134441). An instantaneous, memoryless z-score can catch a single deviant window but cannot see the drift that is the actual early-warning signal, so it will tend to fire late (near deterioration) rather than early.
> - **SUPPORTS the planned Tier 2.** CUSUM "drift" detection over 6–24 h is exactly the right instrument for a slowly rising risk trajectory, and the learned "surprise" term maps conceptually onto the validated *sample-entropy* metric. The evidence argues Tier 2 is not a nicety but the part that captures the clinically validated behaviour; Tier 1 alone under-uses the signal.

---

## 5. What the RCT showed — and what it did NOT

**The trial (HeRO RCT).** Individually randomised, two-arm (HRC display vs masked), **3003 very-low-birth-weight infants across 9 NICUs** (Moorman et al. 2011, J Pediatr 159(6):900-906.e1, PMID 21864846, DOI 10.1016/j.jpeds.2011.06.044).

| Outcome | Result | Source |
|---|---|---|
| All-cause mortality, display vs masked | 8.1% vs 10.2% | Moorman 2011, PMID 21864846 |
| Hazard ratio (95% CI), p | **0.78 (0.61–0.99), p=0.04** | Moorman 2011, PMID 21864846 |
| Number needed to monitor | 48 | Moorman 2011, PMID 21864846 |
| Subgroup <1000 g, HR (95% CI), p | **0.74 (0.57–0.95), p=0.02**; NNM 23 | Moorman 2011, PMID 21864846 |
| Days alive & ventilator-free (of 120) | 95.9 vs 93.6, **p=0.08 (NS)** | Moorman 2011, PMID 21864846 |
| Other secondary outcomes | No significant differences | Moorman 2011, PMID 21864846 |
| **Sepsis incidence** | **No reduction** (see below) | Fairchild 2013, PMID 23942558 |

**What it did NOT show.** HRC monitoring did **not reduce the incidence of late-onset septicaemia.** In the pre-specified secondary analysis, the 974 septicaemia episodes were split essentially evenly between arms (486 in 348 infants displayed vs 488 in 352 masked); what differed was **mortality within 30 days of sepsis: 11.8% (display) vs 19.6% (masked), RR 0.61 (95% CI 0.43–0.87), p<0.01** — interpreted as earlier detection and treatment of sepsis that still occurred, **not prevention** (Fairchild et al. 2013, Pediatr Res 74(5):570-575, PMID 23942558, DOI 10.1038/pr.2013.136). Displaying the score also carried costs: roughly **10% more blood cultures and ~5% more antibiotic-days** (Fairchild 2013, Curr Opin Pediatr, PMID 23407184; Koppens et al. 2023, Neonatology, PMID 37379804).

**Independent critical appraisal (the honest part).** A 2023 systematic review (15 reports: 3 from the single RCT + 12 from 8 cohort studies, ~8230 infants) reached notably guarded conclusions (Koppens et al. 2023, Neonatology 120(5):548-557, PMID 37379804, DOI 10.1159/000531118):
- The RCT's methodological quality was rated **LOW** — performance/detection bias unavoidable (open-label), no correction for multiple comparisons, selective outcome reporting not excludable.
- Absolute mortality reduction was only **~2.1% (95% CI 0.01–4.14)**; the reviewers state the benefit "should be interpreted with caution given the methodological weaknesses, the uncertainty of clinical relevance, and the concerns on generalizability."
- The mortality benefit was concentrated in **coagulase-negative staphylococcal** sepsis — an organism with intrinsically *low* mortality — which the reviewers flag as biologically hard to explain.
- An **unexplained excess of deafness** appeared in the monitored arm (4.4% vs 0.5%).
- Recommendation: **conduct a new international RCT before adopting HRC monitoring as standard of care.**

A contemporaneous peer-reviewed editorial accompanying the trial framed the result cautiously ("HeRO or villain?") rather than as settled practice (Groves & Edwards 2011, J Pediatr 159(6):885-886, PMID 21982302, DOI 10.1016/j.jpeds.2011.08.049; editorial, no abstract).

**Real-world performance gap.** In a 30-month single-centre cohort (127,673 HRC scores, 2384 infants), elevated HRC had **limited ability to detect bloodstream infection**: only ~5% of infants with HRC ≥2 and ~9% with HRC ≥5 actually had BSI, because respiratory deterioration and surgery also raise the score — i.e. low specificity/PPV in practice, contrasting with validation-study AUROCs of 0.78–0.90 (Coggins et al. 2016, Arch Dis Child Fetal Neonatal Ed 101(4):F329-332, PMID 26518312, DOI 10.1136/archdischild-2015-309210; AUROC range per Koppens et al. 2023, PMID 37379804).

> **Mapping to NeonatalGuard.**
> - **Calibration DIVERGES.** HeRO maps HRC to an *outcome-calibrated* fold-increase in 24-h sepsis risk (Fairchild & O'Shea 2010, PMID 20813272). NeonatalGuard's |z|≥2→YELLOW / |z|≥3→RED are generic statistical cut-points with unknown sensitivity/specificity/PPV against sepsis. Given that even the validated, calibrated HeRO score showed poor real-world PPV (Coggins et al. 2016, PMID 26518312), an uncalibrated z-threshold should be *expected* to over-alarm. Treat Tier 1 output as a screening/triage prior, not a probability, and validate thresholds against labelled outcomes before making any diagnostic claim.
> - **Honest framing for the pitch:** the strongest defensible claim is "early *detection* enabling earlier treatment," not "sepsis prevention," and the mortality evidence is one modest, low-quality-rated RCT that has not been replicated (Fairchild 2013, PMID 23942558; Koppens 2023, PMID 37379804).

---

## 6. Regulatory & clinical-adoption status of HeRO

**Regulatory (authoritative, via openFDA 510(k) database, api.fda.gov):** The HeRO monitor has been cleared through the FDA **510(k) (substantial-equivalence)** pathway multiple times, all under product code **DPS**:

| K-number | Device name | Applicant | Decision date | Decision |
|---|---|---|---|---|
| **K021230** | HERO | Medical Decision Networks (predecessor name) | **2003-05-09** | Substantially Equivalent |
| K081473 | HERO, Version 2.0 | Medical Predictive Science Corp. | 2008-06-27 | Substantially Equivalent |
| K111601 | HERO | Medical Predictive Science Corp. | 2011-07-08 | Substantially Equivalent |
| K180242 | HeRO Symphony / ES / solo / duet | Medical Predictive Science Corporation | 2018-02-28 | Substantially Equivalent |

Source: FDA openFDA 510(k) API (`api.fda.gov/device/510k`), records for applicant "Medical Predictive Science" and device "HeRO"; original 2003 clearance under predecessor company "Medical Decision Networks." Product-code **DPS** resolves to **"Electrocardiograph," device class II, 21 CFR 870.2340, cardiovascular** (FDA openFDA classification API, `api.fda.gov/device/classification`). FDA record pages: `https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfPMN/pmn.cfm?ID=K021230` (and K081473, K111601, K180242).

**What that clearance means (honest reading).** HeRO is regulated as a **Class II electrocardiograph/ECG-analysis device cleared by substantial equivalence — not as a PMA-approved "sepsis diagnostic."** The device *displays* the HRC index (a fold-increase in near-term risk) as an **adjunct** to clinical judgement; it is not authorised to diagnose sepsis or to direct treatment on its own (intended-use framing per Fairchild & O'Shea 2010, PMID 20813272; Fairchild 2013, PMID 23407184). This is the standard, honest caveat: 510(k) clearance certifies substantial equivalence to a predicate ECG monitor, not demonstrated clinical efficacy for a sepsis-diagnosis claim.

**Clinical adoption.** HeRO is commercially available and is frequently described as the first FDA-cleared predictive-monitoring tool in the NICU (Fairchild 2013, Curr Opin Pediatr, PMID 23407184). However, adoption is not universal and independent reviewers explicitly declined to endorse it as standard of care pending a new confirmatory RCT (Koppens et al. 2023, Neonatology, PMID 37379804).

> **Mapping to NeonatalGuard.** A product pitched to clinicians should mirror this regulatory posture: position NeonatalGuard as **decision support / an adjunct risk-trend display**, not a diagnostic. Claiming diagnostic performance without an outcome-validated, calibrated score and prospective evidence would over-reach beyond even what the market-leading, decades-old HeRO device claims.

---

## Confidence & conflicting evidence

**High confidence (verified against primary sources):**
- The physiological mechanism, the signature (low variability + transient decelerations), the downward direction, and the ~6–24 h lead time are consistent across the founding paper and reviews (Griffin & Moorman 2001, PMID 11134441; Fairchild & O'Shea 2010, PMID 20813272).
- Exact RCT numbers (N=3003, 9 NICUs, HR 0.78 [0.61–0.99] p=0.04, <1000 g HR 0.74 [0.57–0.95] p=0.02) verified from the PubMed record (Moorman 2011, PMID 21864846) and corroborated by the systematic review (Koppens 2023, PMID 37379804).
- FDA clearances (K-numbers, dates, applicant, product code DPS = Class II electrocardiograph) taken directly from the structured openFDA API — authoritative.

**Conflicting / contested evidence (surfaced deliberately):**
- **Efficacy vs. quality.** The RCT is positive for mortality, but the only systematic review rates its quality **low** and calls for a new RCT; the mortality mechanism (benefit concentrated in low-lethality CoNS; unexplained deafness excess) is not fully explained (Koppens 2023, PMID 37379804). The RCT authors attribute mortality reduction to earlier treatment (Fairchild 2013, PMID 23942558).
- **Validation vs. real world.** Cohort AUROCs of 0.78–0.90 (Koppens 2023, PMID 37379804) contrast sharply with poor real-world PPV/specificity (Coggins 2016, PMID 26518312). Both are true; the discrepancy is driven by non-sepsis causes of abnormal HRC (respiratory events, surgery).
- **Whether mortality was the pre-specified confirmatory primary endpoint.** The systematic review states mortality "was not the primary outcome" and that no multiple-testing correction was applied (Koppens 2023, PMID 37379804), whereas the trial is titled and headlined around mortality reduction (Moorman 2011, PMID 21864846). I did not obtain the full trial protocol/methods to adjudicate this precisely — **unverified; needs confirmation from the trial's Methods/registration (ClinicalTrials.gov NCT00307333).**

**Could not fully verify:**
- **Exact FDA intended-use wording.** The 510(k) *summary* PDFs (K081473, K111601) are scanned images with no machine-extractable text, so the verbatim intended-use sentence is **unverified — needs manual/OCR read of the FDA summary**. The product-code classification (Class II electrocardiograph) and clearance dates are authoritative from openFDA; the "adjunct / fold-increase in risk" framing is taken from peer-reviewed reviews, not from the cleared label text itself.
- **One citation-mapping caveat.** The PMC identifier `PMC10989716` resolved (via the fetch tool) to the Fairchild 2013 *Curr Opin Pediatr* content despite a PMC number that looks too recent for a 2013 article; I have therefore cited that source by its stable **PMID 23407184 / DOI 10.1097/MOP.0b013e32835e8fe6**, which are correct, rather than by the PMC URL. If quoting that source, re-confirm via PubMed.
- No fabricated numbers appear in this document. Where a figure is approximate (e.g., Coggins PPV percentages) it is labelled as such.

**Net honesty statement for the pitch:** HRV/HRC monitoring for neonatal sepsis rests on solid physiology, a clear and reproducible early-warning signature, and one positive-but-modest, unreplicated, low-quality-rated RCT that reduced *mortality* (not sepsis incidence) mainly in the smallest infants, with documented real-world specificity problems. It is a credible **early-warning adjunct**, not a validated diagnostic — and NeonatalGuard's Tier 1 currently diverges from the validated signal in three fixable ways: it discards direction, omits the asymmetry/skewness and entropy features that carry the deceleration signal, and is stateless rather than trend-aware.

---

## References

1. Griffin MP, Moorman JR. **Toward the early diagnosis of neonatal sepsis and sepsis-like illness using novel heart rate analysis.** *Pediatrics.* 2001 Jan;107(1):97-104. PMID: 11134441. DOI: 10.1542/peds.107.1.97. https://pubmed.ncbi.nlm.nih.gov/11134441/

2. Moorman JR, Carlo WA, Kattwinkel J, Schelonka RL, Porcelli PJ, Navarrete CT, et al. **Mortality reduction by heart rate characteristic monitoring in very low birth weight neonates: a randomized trial.** *J Pediatr.* 2011 Dec;159(6):900-906.e1. PMID: 21864846. DOI: 10.1016/j.jpeds.2011.06.044. https://pubmed.ncbi.nlm.nih.gov/21864846/

3. Fairchild KD, O'Shea TM. **Heart rate characteristics: physiomarkers for detection of late-onset neonatal sepsis.** *Clin Perinatol.* 2010 Sep;37(3):581-598. PMID: 20813272. DOI: 10.1016/j.clp.2010.06.002. https://pmc.ncbi.nlm.nih.gov/articles/PMC2933427/

4. Fairchild KD. **Predictive monitoring for early detection of sepsis in neonatal ICU patients.** *Curr Opin Pediatr.* 2013 Apr;25(2):172-179. PMID: 23407184. DOI: 10.1097/MOP.0b013e32835e8fe6. https://pubmed.ncbi.nlm.nih.gov/23407184/

5. Fairchild KD, Schelonka RL, Kaufman DA, Carlo WA, Kattwinkel J, Porcelli PJ, et al. **Septicemia mortality reduction in neonates in a heart rate characteristics monitoring trial.** *Pediatr Res.* 2013 Nov;74(5):570-575. PMID: 23942558. DOI: 10.1038/pr.2013.136. https://pmc.ncbi.nlm.nih.gov/articles/PMC4026205/

6. Koppens HJ, Onland W, Visser DH, van Kaam AH, Groenendaal F, et al. **Heart Rate Characteristics Monitoring for Late-Onset Sepsis in Preterm Infants: A Systematic Review.** *Neonatology.* 2023;120(5):548-557. PMID: 37379804. DOI: 10.1159/000531118. https://pmc.ncbi.nlm.nih.gov/articles/PMC10614451/

7. Coggins SA, Weitkamp JH, Grunwald L, Stark AR, Reese J, Walsh W, Wynn JL. **Heart rate characteristic index monitoring for bloodstream infection in an NICU: a 3-year experience.** *Arch Dis Child Fetal Neonatal Ed.* 2016 Jul;101(4):F329-332. PMID: 26518312. DOI: 10.1136/archdischild-2015-309210. https://pubmed.ncbi.nlm.nih.gov/26518312/

8. Sullivan BA, Fairchild KD. **Heart rate analysis in neonatal sepsis: a complex equation.** *Pediatr Res.* 2025 Jan;97(1):35-37 (Epub 2024 Sep 6). PMID: 39242935. DOI: 10.1038/s41390-024-03548-y. https://pubmed.ncbi.nlm.nih.gov/39242935/

9. Groves AM, Edwards AD. **Heart rate characteristic monitoring — HeRO or villain?** (editorial) *J Pediatr.* 2011 Dec;159(6):885-886. PMID: 21982302. DOI: 10.1016/j.jpeds.2011.08.049. https://pubmed.ncbi.nlm.nih.gov/21982302/

10. U.S. FDA 510(k) Premarket Notification database (via openFDA, `api.fda.gov/device/510k` and `api.fda.gov/device/classification`). HeRO clearances: **K021230** (2003-05-09, applicant Medical Decision Networks), **K081473** (2008-06-27), **K111601** (2011-07-08), **K180242** (2018-02-28); all product code **DPS = Electrocardiograph, Class II, 21 CFR 870.2340**. FDA record page pattern: https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfPMN/pmn.cfm?ID=K021230

11. HeRO RCT registration (for protocol/primary-endpoint verification — see Confidence section): ClinicalTrials.gov **NCT00307333**, "Impact of Heart Rate Characteristics Monitoring in Neonates." https://clinicaltrials.gov/study/NCT00307333
