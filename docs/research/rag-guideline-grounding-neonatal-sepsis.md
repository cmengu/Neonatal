# RAG Guideline-Grounding for the Tier 3 Reasoning Tier — Neonatal Sepsis

**Scope.** A primary-sourced adjudication of GitHub issue #5 (the Tier 3 RAG tier of the Verdict Cascade):
*which* neonatal early-/late-onset sepsis guidelines the retrieval corpus should cite, *whether* each
Tier-3 assertion class (concern level, `primary_indicators`, every `APPROVED_ACTIONS` item, and the
`pre_sepsis` autonomic label) is actually guideline-grounded or invented, and *how* that grounding is made
concretely testable as acceptance criteria for #5. Includes a file-by-file audit of the 5 current
un-sourced corpus texts.

**Builds on / cross-links.**
[[clinical-evidence-hrv-sepsis]] (`clinical-evidence-hrv-sepsis.md`) and [[README]] (`README.md`) —
the HeRO / heart-rate-characteristics (HRC) science and the 510(k) *adjunct-not-diagnostic* posture are
established there and are **cross-linked, not re-derived**;
[[cusum-drift-and-composition-validation]] (`cusum-drift-and-composition-validation.md`) §4.3 — *why the
LLM/RAG tier is escalate-only*; [[de-escalation-alarm-fatigue-evidence]]
(`de-escalation-alarm-fatigue-evidence.md`) — the house-style bar this file matches.

**Data reality (unchanged, and it constrains every recommendation below).** NeonatalGuard runs on the PICS
set: 10 preterm infants, ~450–500 h dual-channel **ECG + respiration only** — **no SpO₂, no labs/cultures,
no maternal/intrapartum data, no temperature, no sepsis labels.** It is a decision-support / triage adjunct
(mirroring HeRO's FDA 510(k) posture), **not a sepsis diagnostic.** The central structural finding of this
document falls straight out of that reality: **every authoritative EOS/LOS guideline is built on inputs we
do not have** (maternal/intrapartum risk factors, GBS status, blood culture, CBC, CRP, temperature). Those
guidelines can therefore ground Tier 3's **actions and clinical vocabulary and its "prompt-a-clinician"
framing** — but they can **never** ground the HRV→sepsis *inference itself*. That inference is grounded only
by the HeRO/HRC literature, which is an *adjunct risk-trend display*, not a diagnosis.

**Date:** 2026-07-13
**Author:** Research agent (RAG guideline grounding)

---

## Bottom line (honest)

| Question | Verdict | One-line |
|---|---|---|
| Which guidelines should Tier 3 cite? | **NICE NG195 + AAP/COFN ≤34 6/7 wk (primary); AAP/COFN ≥35 wk, CDC-2010/ACOG-797 GBS, Kaiser EOS-calculator (context only)** | NICE NG195 and the AAP **preterm** report are population-matched and ground the *clinical-indicator vocabulary and the observation/work-up actions*; the others ground *maternal/intrapartum context we cannot compute* and enter only as clinician-facing references. |
| Do the guidelines ground the HRV→sepsis inference? | **No — and this is the load-bearing limit** | NICE/AAP/CDC/ACOG say *nothing* about HRV/HRC (both AAP abstracts are explicit: risk comes from maternal + infant clinical characteristics and delivery circumstances). Only HeRO/Griffin-Moorman ground the HRV signal — as an **adjunct**, not a diagnosis. |
| Is the `pre_sepsis` autonomic label defensible? | **No — overreach; must be renamed in #5** | Neither any guideline **nor even HeRO** calls the HRC pattern "pre-sepsis." The validated construct is *"abnormal heart-rate characteristics"* / *"fold-increase in risk over the next 24 h."* With no labels and no cultures, `pre_sepsis` asserts a diagnostic trajectory the data cannot support. Rename → `abnormal_hrc` / `increased_risk`. |
| Are the `APPROVED_ACTIONS` cadences guideline-specified? | **The *actions* mostly are; three *cadences* are invented** | "Reassess in 2 hours" and "Increase monitoring frequency to every 15 minutes" have **no guideline source** (NICE specifies ≥12 h observation on a newborn early-warning system; neither the 2 h nor the 15 min number appears). "Blood culture and CBC with differential" is a guideline-sanctioned *work-up* but is a **clinician** action our HRV signal cannot itself justify. |
| Can the grounding be validated concretely? | **Yes — as citation-coverage acceptance criteria** | Every corpus chunk carries a source header; every `retrieved_context` chunk resolves to a cited source ID; every `recommended_action` maps to a guideline entry; an audit gate blocks any un-cited clinical claim reaching the alert; corpus-lint strips the fabricated performance numbers. |

**The single most important finding:** two Tier-3 assertions are **not guideline-grounded and must change in
#5** — (1) the **`pre_sepsis`** `autonomic_pattern` label (a diagnostic overreach; rename to an
abnormality/risk label), and (2) the **invented monitoring cadences** ("Reassess in 2 hours",
"every 15 minutes", and the corpus's "blood culture within 1 hour"), which no cited guideline specifies.
Both are the classic failure mode of an un-sourced RAG corpus: fluent, specific, and unattributable.

---

## Decision evidence table (Tier-1 style)

| Claim / assertion | Adopt as citable grounding? | Mechanism / clinical direction | Evidence (PMID/DOI/guideline-ID) |
|---|---|---|---|
| **NICE NG195** (neonatal infection: antibiotics for prevention & treatment) | **ADOPT — primary source** | Grounds the *clinical-indicator vocabulary* (red flags: apnoea, seizures, need for CPR/mechanical ventilation, signs of shock; plus temperature abnormality, feeding difficulty, respiratory distress) and the *observation posture* (monitor vital signs on a **newborn early-warning system**, ≥**12 h** for a single non-red-flag risk factor). Directly relevant to a preterm monitoring adjunct. | NICE **NG195** (pub. 2021-04-20; updated 2026-05-13) — Risk-factors/clinical-indicators & Recommendations chapters |
| **AAP/COFN ≤34 6/7 wk** (Puopolo et al. 2018, preterm report) | **ADOPT — population-matched primary source** | Our infants are preterm; this is the matched guideline. Grounds: empiric antibiotics + blood culture as the EOS work-up, the caution that *prolonged* empiric antibiotics harm preterm infants, and — critically — that preterm EOS risk is driven by **delivery circumstances**, *not* postnatal HRV (bounds what Tier 3 may claim). | **PMID 30455344**; doi:10.1542/peds.2018-2896 (*Pediatrics* 2018;142(6):e20182896) |
| **AAP/COFN ≥35 wk** (Puopolo et al. 2018, term/late-preterm report) | **ADOPT — with population caveat** | Off-population (≥35 wk) but grounds the general EOS logic our actions inherit: **"laboratory tests alone are neither sensitive nor specific"**; risk from maternal + infant clinical characteristics; blood culture + serial physical examination. Use for framing, not as a preterm rule. | **PMID 30455342**; doi:10.1542/peds.2018-2894 (*Pediatrics* 2018;142(6):e20182894) |
| **Kaiser Permanente Neonatal EOS Calculator** (Kuzniewicz/Escobar/Puopolo) | **REJECT as a system input · ADOPT as clinician-facing reference + philosophy** | The calculator needs six **maternal/intrapartum** inputs (baseline EOS incidence, GA, peak intrapartum temp, GBS status, ROM duration, intrapartum-antibiotic timing) — **none of which NeonatalGuard has** — and is validated only ≥34/≥35 wk. We **cannot run it.** Adopt only its *quantitative, antibiotic-sparing philosophy* (aligns with our de-escalation goal) and cite it as the tool a clinician should consult. | **PMID 28241253**; doi:10.1001/jamapediatrics.2016.4678 (JAMA Pediatr 2017); update doi:10.1542/peds.2023-065267 (*Pediatrics* 2024;154(4)) **[VERIFY-PMID]** (update PMID not fetched) |
| **CDC 2010 GBS** + **ACOG Committee Opinion 797 (2020)** | **ADOPT as context only — clinician-facing reference** | GBS is the leading EOS pathogen, but these are **maternal intrapartum-prophylaxis** guidelines whose inputs (GBS colonisation, intrapartum antibiotics) we do not observe. They ground the *GBS-status clinician prompt* and the newborn secondary-prevention context — not any system inference. | CDC MMWR Recomm Rep 2010;**59(RR-10):1–36**, **PMID 21088663**; **ACOG CO 797**, *Obstet Gynecol* 2020;135(2):e51–e72, **PMID 31977795** (correction PMID 32217968) |
| **HeRO / Griffin & Moorman HRC** (the HRV base) | **ADOPT — the *only* source that grounds the HRV signal (cross-link)** | The HRV→sepsis-risk inference is grounded **here and only here**: reduced baseline variability + transient decelerations, rising over 6–24 h, as a *fold-increase in 24-h risk* — an **adjunct display**, not a diagnosis. Everything HRV-specific in the corpus must cite this, not NICE/AAP. | Griffin & Moorman 2001 **PMID 11134441**; Fairchild & O'Shea 2010 **PMID 20813272**; Moorman 2011 RCT **PMID 21864846** — see [[clinical-evidence-hrv-sepsis]] |
| Concern-level **RED / YELLOW / GREEN** semantics | **PARTIAL — triage convention, *not* a diagnostic vocabulary** | It is a traffic-light **triage/early-warning** convention (kin to a newborn early-warning system's escalation tiers, which NICE names), **not** a guideline sepsis-severity grade. Adopt as triage semantics; **do not** let RED read as "sepsis." | NICE NG195 ("newborn early-warning system"); *no* guideline defines RED/YELLOW/GREEN for sepsis |
| **`primary_indicators`** vocabulary | **SPLIT — ground each term to its own source** | HRV terms (low RMSSD/SDNN, decelerations) → HeRO/HRC. Clinical-sign terms (apnoea, temperature instability, feeding intolerance, shock) → NICE NG195. But the system only measures **ECG + respiration**, so temperature/feeding indicators are **clinician prompts, not system assertions.** | HeRO refs above (HRV terms); NICE NG195 (clinical-sign terms) |
| `APPROVED_ACTIONS`: **"Immediate clinical review"** | **ADOPT** | Red-flag findings → urgent senior clinical evaluation is standard NICE/AAP escalation. | NICE NG195; AAP PMID 30455342 |
| `APPROVED_ACTIONS`: **"Blood culture and CBC with differential"** | **ADOPT the action — but flag as a *clinician* action, and drop the "within 1 h"** | Blood culture is the guideline diagnostic standard and CBC/differential the adjunct — **but AAP is explicit that labs alone are insufficient**, and our HRV signal cannot *itself* justify a culture. The corpus's "within 1 hour of identifying this pattern" cadence is **not guideline-specified** → present as a clinician prompt, no invented clock. | AAP PMID 30455342 / 30455344; NICE NG195 (investigations before antibiotics) |
| `APPROVED_ACTIONS`: **"Temperature and perfusion monitoring"** | **ADOPT — as a clinician prompt for inputs we lack** | Temperature abnormality and shock/poor perfusion are NICE indicators — but **we do not measure temperature or perfusion.** This action is legitimately a prompt to *add* a measurement the system cannot make. | NICE NG195 (temperature abnormality; signs of shock) |
| `APPROVED_ACTIONS`: **"Continue routine monitoring"** | **ADOPT** | Directly the NICE posture: monitor vital signs on a newborn early-warning system. | NICE NG195 |
| `APPROVED_ACTIONS`: **"Reassess in 2 hours"** | **REJECT the cadence → soften** | **No cited guideline specifies a 2-hour reassessment.** NICE specifies ≥12 h observation for a single non-red-flag risk factor; AAP describes serial exams over ~24–48 h. The "2 hours" is invented. | *No source* — flag for #5 |
| `APPROVED_ACTIONS`: **"Notify attending neonatologist"** | **ADOPT** | Escalation to the responsible senior clinician is standard. | NICE NG195; AAP |
| `APPROVED_ACTIONS`: **"Increase monitoring frequency to every 15 minutes"** | **REJECT the cadence → soften** | **No cited guideline specifies a 15-minute cadence.** NICE prescribes continued observation (≥12 h) on an early-warning system without a 15-min interval. Invented precision. | *No source* — flag for #5 |
| `APPROVED_ACTIONS`: **"Respiratory support assessment"** | **ADOPT** | Apnoea and need for mechanical ventilation are NICE red flags; respiratory support assessment follows. | NICE NG195 |
| `autonomic_pattern` = **`pre_sepsis`** | **REJECT — overreach; rename** | Neither guidelines nor HeRO name a "pre-sepsis" state; the validated construct is *abnormal HRC / increased 24-h risk*. With no labels/cultures, "pre-sepsis" is an un-supportable diagnostic claim. Rename → `abnormal_hrc` / `increased_risk` / `autonomic_instability`. | HeRO PMID 20813272 (construct is *risk*, not diagnosis); no guideline uses "pre-sepsis" |
| Corpus **performance numbers** (PPV 0.71; sens 78% / spec 82%; ">60% probability"; "OR" figures) | **REJECT — un-sourced/fabricated; remove** | No cited source supports these exact figures on our population; with unlabelled data they are unverifiable. Even validated HeRO showed **poor real-world PPV** (Coggins 2016). | *No source* — remove (see [[clinical-evidence-hrv-sepsis]] §5) |

---

## 1. The guideline set — adopt/reject, and *what class each grounds*

### 1.1 NICE NG195 — ADOPT (primary; grounds vocabulary + observation actions)
**NICE NG195, "Neonatal infection: antibiotics for prevention and treatment"** (published 2021-04-20; last
updated 2026-05-13) is the most *operationally* relevant guideline for this product because, unlike the
intrapartum-focused guidance, it is about **recognition and monitoring** of the already-born baby. Fetched
directly, its Risk-factors/clinical-indicators chapter enumerates **red-flag clinical indicators** — apnoea,
seizures, need for cardiopulmonary resuscitation, need for mechanical ventilation, signs of shock — plus a
longer list of non-red-flag indicators (altered behaviour/responsiveness, feeding difficulties, respiratory
distress, temperature abnormality, jaundice within 24 h, metabolic acidosis). Its monitoring posture is
explicit and quotable: a baby with a single non-red-flag risk factor should have **vital signs and clinical
condition monitored… for at least 12 hours using a newborn early-warning system.**

**What it grounds:** the **`primary_indicators` clinical-sign vocabulary**, the **RED/YELLOW/GREEN triage
framing** (as an early-warning-system analogue, *not* a sepsis grade), and the observation actions
("Continue routine monitoring", "Immediate clinical review", "Respiratory support assessment",
"Notify attending neonatologist"). **What it does not ground:** any HRV inference, and any 2-hour/15-minute
cadence (it specifies a **≥12 h** observation window, not sub-hourly intervals).

### 1.2 AAP/COFN 2018 — ADOPT both reports (the ≤34 6/7 wk one is population-matched)
The AAP Committee on Fetus and Newborn issued **two** 2018 reports. The **preterm** report — *Management of
Neonates Born at ≤34 6/7 Weeks' Gestation…* (**PMID 30455344**, doi:10.1542/peds.2018-2896) — is the
population match for our ≤34-week PICS infants. Its abstract (fetched) is blunt about the current problem
("most preterm infants with very low birth weight are treated empirically with antibiotics… often for
prolonged periods, in the absence of a culture-confirmed infection" and "antibiotic exposures after birth
are associated with multiple subsequent poor outcomes") and locates preterm EOS risk in **delivery
characteristics** — *not* in any postnatal physiological monitor. The **term/late-preterm** report
(**PMID 30455342**, doi:10.1542/peds.2018-2894) supplies the general logic our actions inherit, most usefully
the verified sentence **"Laboratory tests alone are neither sensitive nor specific enough to guide EOS
management decisions."**

**What they ground:** the **"Blood culture and CBC with differential"** work-up (as a *clinician* action,
with the honest caveat that labs alone are insufficient) and the antibiotic-sparing, risk-stratified stance
that aligns with our de-escalation goal. **What they do not ground:** HRV/HRC (neither abstract mentions it),
nor any specific reassessment cadence.

### 1.3 Kaiser EOS Calculator — REJECT as an input, ADOPT as a reference/philosophy
The neonatal EOS calculator (Kuzniewicz et al., **PMID 28241253**, doi:10.1001/jamapediatrics.2016.4678;
2024 update doi:10.1542/peds.2023-065267) is a multivariate model over **six maternal/intrapartum inputs**
(baseline EOS incidence, gestational age, peak intrapartum temperature, GBS status, duration of ruptured
membranes, intrapartum-antibiotic timing) and is validated for **≥34/≥35 weeks**. **NeonatalGuard has none
of those inputs and its infants are largely below the validated range, so the calculator cannot be
computed by the system.** We adopt only (a) its *philosophy* — quantitative risk stratification that safely
cut empiric antibiotics (5.0%→2.6%) and blood cultures (14.5%→4.9%) without missing culture-positive EOS —
as external validation of our alarm-sparing intent, and (b) its status as a **tool a clinician should be
prompted to consult** with the inputs we lack. Any Tier-3 text that implies the system *runs* an EOS-risk
calculation is a fabrication.

### 1.4 CDC 2010 / ACOG 797 GBS — ADOPT as context only
CDC's 2010 revised GBS guidelines (MMWR Recomm Rep 2010;**59(RR-10):1–36**, **PMID 21088663**) and
**ACOG Committee Opinion 797** (2020; *Obstet Gynecol* 135(2):e51–e72, **PMID 31977795**) govern **maternal
intrapartum prophylaxis** and newborn secondary prevention. GBS is the leading EOS pathogen, but the inputs
(colonisation, intrapartum antibiotics) are again maternal and unobserved by us. These enter the corpus only
as the **GBS-status clinician prompt** and background context — never as a system input.

### 1.5 The HRV base — cross-link, do not re-derive
The one body of evidence that actually grounds the physiological signal is the HeRO/HRC literature
(Griffin & Moorman 2001 **PMID 11134441**; Fairchild & O'Shea 2010 **PMID 20813272**; Moorman 2011 RCT
**PMID 21864846**), fully appraised in [[clinical-evidence-hrv-sepsis]]. The decisive property for #5: HeRO
is a **510(k) Class II adjunct display of a *risk trend*, not a sepsis diagnostic** — so any Tier-3 sentence
that upgrades an HRV pattern to a *diagnosis* or that satisfies a *guideline sepsis criterion from HRV alone*
exceeds even the market-leading device's own claims.

---

## 2. Assertion → source mapping (the core deliverable)

| Tier-3 assertion class | Grounding source (or FLAG) | Verdict for #5 |
|---|---|---|
| `concern_level` RED / YELLOW / GREEN | NICE NG195 newborn early-warning-system framing (triage only) | **Keep as triage; add a disclaimer that RED ≠ diagnosed sepsis** |
| `primary_indicators` — HRV terms (low RMSSD/SDNN, decelerations, reduced entropy/asymmetry) | HeRO/HRC (PMID 11134441, 20813272) — cross-link | **Keep; cite HeRO, not NICE/AAP** |
| `primary_indicators` — clinical-sign terms (apnoea, temperature instability, feeding intolerance, shock) | NICE NG195 red flags/indicators | **Keep apnoea (we can derive it); mark temperature/feeding as clinician-prompt only — not measured** |
| Action: Immediate clinical review | NICE NG195; AAP 30455342 | **Grounded — keep** |
| Action: Blood culture and CBC with differential | AAP 30455342/30455344 (work-up) | **Grounded action, but a *clinician* action; DROP the corpus "within 1 hour"** |
| Action: Temperature and perfusion monitoring | NICE NG195 (temperature abnormality; shock) | **Grounded — but frame as prompt for an input we lack** |
| Action: Continue routine monitoring | NICE NG195 | **Grounded — keep** |
| Action: **Reassess in 2 hours** | **NONE** | **FLAG — soften: drop the 2 h number or cite NICE's ≥12 h observation** |
| Action: Notify attending neonatologist | NICE NG195; AAP | **Grounded — keep** |
| Action: **Increase monitoring frequency to every 15 minutes** | **NONE** | **FLAG — soften: "increase monitoring frequency" without the invented interval** |
| Action: Respiratory support assessment | NICE NG195 (apnoea; ventilation) | **Grounded — keep** |
| `autonomic_pattern` = **`pre_sepsis`** | **NONE — not even HeRO** | **FLAG — rename to `abnormal_hrc` / `increased_risk`** |
| `autonomic_pattern` = `bradycardia_reflex` / `normal_variation` / `indeterminate` | HeRO + neonatal bradycardia physiology (see corpus audit §3) | **Defensible as descriptors; keep** |
| Corpus performance numbers (PPV 0.71; 78%/82%; ">60%") | **NONE — fabricated** | **FLAG — remove from corpus (unverifiable on unlabelled data)** |

**Reading of the map.** The *actions* are largely defensible **once reframed as clinician prompts**; the
*cadences* and the *`pre_sepsis` label* and the *performance numbers* are the un-grounded residue. Tier 3's
job is to *retrieve guideline context and escalate*, never to assert a diagnosis or a fabricated statistic.

---

## 3. Corpus audit — are the 5 clinical_texts files traceable? (per-file verdict)

| File | Traceable? | What grounds it / what must change |
|---|---|---|
| `baseline_interpretation.txt` | **Partly — HRV *methodology*, not a sepsis guideline** | The per-infant z-score / burn-in / gestational-age-maturation content is defensible **HRV methodology** and should cite the HRV base ([[clinical-evidence-hrv-sepsis]]), **not** a sepsis guideline. **Soften/remove:** the specific numeric HRV-by-GA ranges (un-cited) and every **LF/HF** claim — LF/HF is the repo-flagged liability that HeRO deliberately avoids ([[README]] scorecard). |
| `bradycardia_patterns.txt` | **Partly — definitions groundable, probabilities fabricated** | Apnoea/bradycardia as red flags → NICE NG195; HR thresholds relate to NRP (but note HR<100 is the *delivery-room* number, not an early-sepsis marker — [[README]]). **Remove:** ">60% probability in <28 weeks", the invented "recurrent = 3+ in 6 h" risk-tier precision, and any RED tier that implies a diagnosis. |
| `hrv_indicators.txt` | **Weak — LF/HF-dependent** | RMSSD/SDNN suppression → HeRO/HRC (keep, cite). **Soften/remove:** the heavy **LF/HF-ratio** dependence (flagged liability) and the un-cited GA-specific numeric ranges. Reframe "pre-sepsis signature" language (see below). |
| `intervention_thresholds.txt` | **Actions yes; cadences + PPV no** | Actions map to NICE/AAP (see §2). **Remove/soften:** "PPV ≈ 0.71", "within 1 hour", "Reassess in 2 hours", "every 15 minutes" — none guideline-sourced. |
| `sepsis_early_warning.txt` | **Lead-time yes; the rest overreaches** | The **12–24 h lead time** is groundable to Griffin & Moorman (PMID 11134441). **Remove/soften:** "pre-sepsis signature", "sensitivity 78% / specificity 82%", the precise "18–24 h before fever" staging, and the LF/HF-dependent tri-feature rule. Rename "pre-sepsis" throughout to *abnormal HRC / increased risk*. |

**Bottom line of the audit:** every file needs a **citation header** and a scrub of **un-sourced
quantitative performance claims** and **LF/HF over-reliance**; two files (`intervention_thresholds`,
`sepsis_early_warning`) additionally carry the invented cadences and the `pre_sepsis` framing that are the
headline fixes for #5.

---

## 4. A concrete, testable validation method (acceptance criteria for #5)

These are written to become CI-checkable gates:

1. **Corpus citation header (lint gate).** Each of the 5 `clinical_texts/*.txt` files must begin with a
   machine-parseable header binding every chunk to a **source ID** (e.g. `NICE-NG195`, `AAP-PRETERM-2018`,
   `HERO-GM-2001`) and a section anchor. *Test:* a corpus-lint fails the build if any chunk lacks a
   resolvable source ID.
2. **No un-sourced quantitative claim (lint gate).** The lint rejects any numeric performance figure
   (PPV/sensitivity/specificity/probability) or any reassessment-interval number not present in a cited
   source. *Test:* regex + allowlist over the corpus; the four fabricated figures (0.71, 78%, 82%, "60%")
   and the invented cadences (2 h, 15 min, "within 1 hour") must be removed or re-cited to pass.
3. **Retrieval traceability (runtime gate).** Every string in `NeonatalAlert.retrieved_context` must resolve
   to a chunk with a valid source ID; an alert that cites a chunk with no source is rejected before persist.
   *Test:* assert each retrieved chunk ID ∈ the source registry.
4. **Action constrained to a guideline-mapped set (runtime gate).** Keep the existing `APPROVED_ACTIONS`
   validator (`enforce_protocol_compliance`) **and** add a static **action→source map** so each approved
   action is backed by a guideline entry; the two flagged cadence actions are rewritten to the
   guideline-sanctioned wording (drop the invented interval). *Test:* every `APPROVED_ACTIONS` item has a
   non-empty source mapping; no shipped action contains an un-sourced time interval.
5. **Citation-coverage of clinical claims (audit gate).** No clinical assertion in `clinical_reasoning` or
   `primary_indicators` may reach the alert without at least one backing `retrieved_context` chunk — the
   "no un-cited clinical claim" gate. *Test:* a self-check step that fails `self_check_passed` when a claimed
   indicator has no supporting retrieved source. (Extends the existing `self_check_passed` field.)
6. **Rename the `pre_sepsis` label (schema gate).** Change `SignalAssessment.autonomic_pattern`'s
   `pre_sepsis` literal to a risk/abnormality term (`abnormal_hrc` or `increased_risk`); every corpus
   reference to "pre-sepsis" is reworded. *Test:* the literal `pre_sepsis` and the substring "pre-sepsis"
   appear nowhere in schema or corpus.
7. **Escalate-only enforcement (carried from #4).** Tier 3 may raise but never lower concern
   ([[cusum-drift-and-composition-validation]] §4.3). *Test:* the composition step asserts
   `verdict ≥ floor` after the RAG tier runs.

---

## 5. Honest residual / limits

- **Un-groundable *from our inputs* (must be framed as clinician prompts, never system assertions):**
  **blood-culture / CBC results; CRP / procalcitonin; temperature; GBS status and all maternal/intrapartum
  EOS-calculator inputs; feeding intolerance; and the sepsis outcome label itself.** Every guideline action
  that consumes one of these (culture/CBC, temperature-and-perfusion monitoring, EOS-calculator risk) is a
  *prompt to a clinician to obtain data the system does not have* — not a recommendation the system can
  justify from HRV + respiration alone.
- **The HRV→sepsis inference is guideline-*orphaned*.** No adopted guideline grounds it; only the HeRO/HRC
  literature does, and only as an *adjunct risk trend*. Tier 3 must therefore separate two citation classes:
  **(a) the physiological signal → HeRO**, and **(b) the recommended action / clinical framing →
  NICE/AAP** — and must never present (a) as satisfying a guideline's sepsis criteria.
- **Unlabelled-data ceiling.** With no sepsis labels we cannot compute PPV/sensitivity/specificity on our
  own cohort; **all corpus performance numbers are therefore unverifiable and must be removed**, not merely
  softened. This is the same ceiling flagged for Tier 1 ([[clinical-evidence-hrv-sepsis]] §5; [[README]]).
- **Decision-support, not diagnostic.** Consistent with HeRO's 510(k) posture, Tier 3's honest output is a
  *retrieved, cited, escalate-only prompt for clinician review*, not a diagnosis. `pre_sepsis` and the
  fabricated cadences are exactly the phrasings that would breach that posture.

---

## Confidence & gaps

- **High confidence (verified against primary sources):** the guideline **identifiers** — NICE NG195 (dates
  from the NICE site); AAP PMIDs **30455342** / **30455344** and DOIs (PubMed); Kuzniewicz 2017
  **PMID 28241253** / DOI (PubMed, incl. the 5.0%→2.6% / 14.5%→4.9% figures); CDC MMWR **59(RR-10)** /
  **PMID 21088663**; ACOG **CO 797** / **PMID 31977795** (search-verified). The structural finding — that
  every guideline's inputs exceed our sensor set — is robust and independently confirmed by both AAP
  abstracts (risk from maternal/infant clinical characteristics + delivery circumstances; no HRV mention).
- **Medium confidence (ID verified, full-text content not directly read):** the AAP publisher pages returned
  **HTTP 403** and ACOG **402**, so the *detailed* recommendation wording (e.g. the ≥35 wk report's three
  named risk-assessment approaches, exact serial-exam cadence) is taken from the PubMed abstracts + widely
  reported summaries, not the article body. The *IDs* are verified; specific *content* claims are flagged
  below.
- **Design-decision, not a clinical finding:** the RED/YELLOW/GREEN → newborn-early-warning-system analogy
  is a *framing* choice; no guideline defines those colours for sepsis. Stated as such.
- **Load-bearing honesty:** the two headline fixes (`pre_sepsis` rename; invented cadences) rest on the
  *absence* of a source — an absence I searched for and did not find in NICE/AAP/CDC/ACOG/HeRO. Absence of
  evidence is the correct basis for "soften/remove" here.

---

### Verification notes (honest flags)

- **[VERIFY-PMID]** Kaiser EOS-calculator **2024 update** (doi:10.1542/peds.2023-065267, *Pediatrics*
  154(4)): the DOI is search-verified but I did **not** fetch its exact PubMed PMID — confirm before quoting
  a PMID for the update. (The 2017 landmark PMID 28241253 / DOI is fully verified.)
- **[VERIFY-CONTENT]** AAP ≥35 wk report (PMID 30455342): the "three risk-assessment approaches"
  (categorical / multivariate-EOS-calculator / serial-physical-exam) framing is from secondary summaries and
  the abstract, **not** the gated (HTTP 403) full text — verify the exact enumeration in the article body
  before quoting it as the guideline's own structure. The verbatim abstract sentence *"Laboratory tests
  alone are neither sensitive nor specific…"* **is** directly verified.
- **[VERIFY-CONTENT]** ACOG CO 797 detail (penicillin dosing, 36–37 wk screening window): the ACOG page
  returned **HTTP 402**; content is from the PubMed/O&G search snippets. IDs (CO 797; PMID 31977795; O&G
  135(2):e51–e72; correction 32217968) are verified; fine-grained clinical detail is not full-text-read.
- **[VERIFY-ID]** CDC MMWR **PMID 21088663** and citation **59(RR-10):1–36** are search-verified against
  PubMed listings, not fetched from the MMWR PDF body.
- **[NO SOURCE — the point]** "Reassess in 2 hours", "Increase monitoring frequency to every 15 minutes",
  "blood culture within 1 hour", PPV 0.71, sensitivity 78% / specificity 82%, ">60% probability": searched
  and **not found** in any adopted guideline. Flagged as un-groundable — the basis for the soften/remove
  recommendations, not an oversight.
- No PMID/DOI in this document was reproduced from memory; every ID above was checked against a live
  PubMed / NICE / publisher listing during this research, with the gated-page caveats noted.

---

## References

**Neonatal infection / EOS guidelines (adopted)**
1. National Institute for Health and Care Excellence. **NG195 — Neonatal infection: antibiotics for
   prevention and treatment.** Published 2021-04-20; updated 2026-05-13.
   https://www.nice.org.uk/guidance/ng195 (verified: red-flag indicators; ≥12 h observation on a newborn
   early-warning system).
2. Puopolo KM, Benitz WE, Zaoutis TE; AAP COFN & COID. **Management of Neonates Born at ≤34 6/7 Weeks'
   Gestation With Suspected or Proven Early-Onset Bacterial Sepsis.** *Pediatrics.* 2018;142(6):e20182896.
   **PMID 30455344.** doi:10.1542/peds.2018-2896 (verified; preterm — antibiotics driven by delivery
   circumstances; harms of prolonged empiric antibiotics).
3. Puopolo KM, Benitz WE, Zaoutis TE; AAP COFN & COID. **Management of Neonates Born at ≥35 0/7 Weeks'
   Gestation With Suspected or Proven Early-Onset Bacterial Sepsis.** *Pediatrics.* 2018;142(6):e20182894.
   **PMID 30455342.** doi:10.1542/peds.2018-2894 (verified; "laboratory tests alone are neither sensitive
   nor specific"; risk from maternal + infant clinical characteristics).

**Risk-stratification tool & GBS context (reference/context only)**
4. Kuzniewicz MW, Puopolo KM, Fischer A, Walsh EM, Li S, Newman TB, Kipnis P, Escobar GJ. **A Quantitative,
   Risk-Based Approach to the Management of Neonatal Early-Onset Sepsis.** *JAMA Pediatr.* 2017;171(4):365–371.
   **PMID 28241253.** doi:10.1001/jamapediatrics.2016.4678 (verified; empiric antibiotics 5.0%→2.6%, blood
   cultures 14.5%→4.9%).
5. Kuzniewicz MW, Escobar GJ, Forquer H, et al. **Update to the Neonatal Early-Onset Sepsis Calculator
   Utilizing a Contemporary Cohort.** *Pediatrics.* 2024;154(4):e2023065267. doi:10.1542/peds.2023-065267
   (DOI verified; **[VERIFY-PMID]**).
6. Verani JR, McGee L, Schrag SJ; CDC. **Prevention of perinatal group B streptococcal disease — revised
   guidelines from CDC, 2010.** *MMWR Recomm Rep.* 2010;59(RR-10):1–36. **PMID 21088663.**
7. American College of Obstetricians and Gynecologists. **Committee Opinion No. 797: Prevention of Group B
   Streptococcal Early-Onset Disease in Newborns.** *Obstet Gynecol.* 2020;135(2):e51–e72. **PMID 31977795**
   (correction: **PMID 32217968**; replaces CO 782, PMID 31241599).

**HRV / HeRO base (cross-linked, not re-derived — see [[clinical-evidence-hrv-sepsis]])**
8. Griffin MP, Moorman JR. *Pediatrics.* 2001;107(1):97–104. **PMID 11134441.**
9. Fairchild KD, O'Shea TM. *Clin Perinatol.* 2010;37(3):581–598. **PMID 20813272.**
10. Moorman JR, Carlo WA, Kattwinkel J, et al. *J Pediatr.* 2011;159(6):900–906.e1. **PMID 21864846.**
    doi:10.1016/j.jpeds.2011.06.044.
11. Coggins SA, et al. *Arch Dis Child Fetal Neonatal Ed.* 2016;101(4):F329–332. **PMID 26518312**
    (poor real-world PPV — why fabricated corpus performance numbers must be removed).
