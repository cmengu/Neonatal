# De-escalation & Alarm Fatigue — Evidence for the Two-Level Safety Floor (ADR-0003)

**Scope.** A primary-sourced evidence asset that gives *more weight* to one specific design decision:
ADR-0003's **two-level Safety Floor with asymmetric de-escalation**. Concretely, it fortifies the claim
that **letting a warmed-up, settled, *calibrated deterministic* detector (Tier 2 CUSUM) quiet a transient
single-parameter warning (a SOFT single-feature YELLOW) down to GREEN — with guaranteed deterministic
re-escalation if the excursion persists — is a defensible, evidence-grounded alarm-fatigue reduction, NOT
an over-reach.** RED (concordant, ≥2 features) is never quietable; the LLM/RAG tier (Tier 3) is
escalate-only.

**Builds on:** `cusum-drift-and-composition-validation.md` **§4** (the composition/de-escalation
ingredients — alarm fatigue, automation bias, fail-safe defaults — are established there and *not*
restated). This file **extends** §4 in three directions §4 did not cover:
1. **neonatal/NICU-specific** alarm-burden and desensitisation evidence, and the empirical link that
   *reducing* non-actionable alarms **improves** response to real ones;
2. **the key precedent** — physiological monitors already suppress transient single-parameter excursions
   with **annunciation delays / persistence requirements**, which is the direct analogue of "quiet a
   transient YELLOW until it persists"; and
3. the **directional (omission-vs-commission) asymmetry** of automation bias, which is *why* suppression
   authority must stay with a calibrated/auditable/deterministic component and never with an LLM.

**Data reality (unchanged).** 10 preterm infants (PICS), ~450–500 h dual-channel ECG + respiration,
**no sepsis labels**. This asset changes no numbers; it strengthens a design rationale. It is a
**DESIGN-DECISION** document built on verified human-factors and neonatal-monitoring evidence — no paper
validates NeonatalGuard's exact rule.

**Date:** 2026-07-13
**Author:** Research agent (alarm human-factors + neonatal monitoring)

---

## Bottom line (honest)

| Question | Verdict | One-line |
|---|---|---|
| Is transient-single-parameter alarm burden real and harmful **in the NICU specifically**? | **Yes — literature-backed** | Non-actionable alarms dominate NICU monitoring (SpO2 especially); desensitisation measurably **slows nurse response to the next alarm**, and reducing non-actionable alarms **speeds** response to true ones. |
| Is "quiet a transient single-parameter excursion until it persists" **standard monitoring practice**? | **Yes — literature-backed, and this is the strongest point** | Annunciation **delays / persistence requirements** are an established, evidence-backed alarm-reduction method — including **neonatal SpO2 delay** studies — endorsed by AAMI / Joint Commission alarm-management guidance. Our Tier-2 quiet-until-persist is the same mechanism, made deterministic and auditable. |
| Is assisted **suppression** more hazardous than assisted **escalation**? | **Yes — directionally supported** | Automation bias splits into **omission** (miss what the aid didn't flag) and **commission** (wrongly follow the aid) errors; suppression sits on the harder-to-catch **omission** side — which is *why* the quieting authority must be calibrated, auditable, deterministic, and re-triggering, never an LLM. |
| Does our exact rule have a validating study? | **No — it remains a DESIGN DECISION** | The *ingredients* are cited and load-bearing; the *composition* (two-level floor, quiet-to-GREEN-then-re-escalate) is engineering judgement. The honest residual is the **empirical false-quiet rate** (how often a quieted YELLOW preceded a genuine event, and the delay it added), which needs real outcome data we do not have. |

**The single most important honest point:** the strongest fortification is **§2 (annunciation delays /
persistence)**. It reframes the two-level floor not as a novel liberty but as **the deterministic,
per-infant, re-escalating version of a technique physiological monitors already ship** (SpO2 alarm delays,
averaging windows). We de-risk that precedent further by (a) restricting the quiet to a *single-feature*
YELLOW (never RED, never ≥2 concordant features), (b) requiring the detector to be **warmed-up, low-drift,
and not-recently-alarmed**, and (c) guaranteeing **deterministic re-escalation** if the excursion persists.

---

## Decision evidence table

| Claim / ingredient | Supports de-escalation? | Mechanism / rationale | Evidence (PMID/DOI) |
|---|---|---|---|
| NICU alarms are overwhelmingly **non-actionable**, SpO2 the worst offender | **Yes — motivates a quiet path** | Desensitisation is driven by a flood of low-PPV single-parameter alerts; a single-feature transient YELLOW is exactly this class. | Sendelbach & Funk 2013, PMID 24153215; Drew 2014, PMID 25338067 (both — 72–99% / 88.8% false); NICU QI: McCauley 2021 (98% of yellow self-resolving SpO2 alarms needed no action), doi:10.1097/pq9.0000000000000386 |
| Desensitisation **measurably delays** response to the *next* alarm | **Yes — the harm is real & quantified** | Response time rises with the count of preceding non-actionable alarms → true alarms are answered later (patient harm). | Bonafide et al. 2015, PMID 25873486 (PICU median response 1.6 → 16.0 min as non-actionable exposure rises); Joshi et al. 2017, doi:10.1371/journal.pone.0184567 (NICU: only 26% of critical alarms answered within 90 s) |
| **Reducing** non-actionable alarms **improves** response to true alarms | **Yes — direct causal-direction evidence** | The de-escalation goal isn't just "fewer beeps" — cutting nuisance alarms *restores* responsiveness to genuine ones. | Stiglich et al. 2024 (NICU before/after), PMID 37339673 (non-actionable 69%→43%; median response 35 s → 12 s) |
| **Annunciation delay / persistence** before a single-parameter alarm sounds *is standard practice* | **YES — the key precedent** | Monitors already suppress transient single-parameter excursions until they persist; a short delay removes self-resolving events without hiding sustained ones. | Görges et al. 2009, PMID 19372334 (14 s delay → 50% fewer false alarms; 19 s → 67%); **neonatal** McClure/Fairchild 2016, PMID 27834782 (15 s SpO2 delay → 67% fewer alarms, sensitivity preserved); McCauley 2021 NICU QI (delay 10→20 s, 64% fewer, no harm) |
| Guidance bodies **recommend** delays / threshold & default adjustment | **Yes — endorsed, not fringe** | AAMI / Joint Commission NPSG alarm-management guidance explicitly lists delays and default/threshold tuning as sanctioned reductions. | Joint Commission NPSG.06.01.01 / SEA #50 (2013); AAMI alarm-management guidance (institutional — no PMID) |
| A **sustained trend**, not a single reading, is the actionable signal | **Yes — quieting a lone reading is principled** | SPC/change-detection: single points are noisy; the decision-worthy event is persistence/accumulation — exactly what Tier-2 CUSUM integrates. | Page 1954, doi:10.1093/biomet/41.1-2.100; Griffin & Moorman 2001, PMID 11134441 (see cusum doc §1, §3) |
| Automation-assisted **suppression** is more hazardous than assisted **escalation** | **Yes — bounds *who* may quiet** | Omission errors (miss what the aid didn't flag) are driven by vigilance decrement and are harder to catch than commission errors; suppression = the omission side. | Skitka, Mosier & Burdick 1999, doi:10.1006/ijhc.1999.0252; Goddard et al. 2012, PMID 21685142; Parasuraman & Riley 1997, doi:10.1518/001872097778543886; Lyell & Coiera 2017, doi:10.1093/jamia/ocw105 |
| Keep a **calibrated / auditable / deterministic** component (not an LLM) in the suppression loop | **Yes — mitigates the omission hazard** | A deterministic, warmed-up, low-drift, re-triggering rule makes the suppression inspectable and self-correcting — the opposite of an uncalibrated generative quiet. | Lyell & Coiera 2017, doi:10.1093/jamia/ocw105; Goddard 2012, PMID 21685142; (LLM unreliability — cusum doc §4.3) |
| A bounded quiet with a **guaranteed re-trigger** is a **fail-safe** pattern | **Yes — framing** | Suppression that reverts to the safe (higher-concern) state on persistence is fail-safe-defaults applied in time. | Saltzer & Schroeder 1975, doi:10.1109/PROC.1975.9939 (see cusum doc §4.4) |

---

## 1. Alarm fatigue — strength of evidence, extended to the neonate

`cusum-drift-and-composition-validation.md` §4.1 already establishes the *general* case (Cvach 2012, PMID
22839984; Drew 2014, PMID 25338067; Joint Commission SEA #50). This section adds three things §4.1 did not:
NICU-specificity, a **quantified desensitisation→delay** link, and **direction-of-effect** evidence.

**Non-actionable single-parameter alarms dominate — and dominate *most* in the NICU.** Sendelbach & Funk's
review puts the false-alarm fraction at **72–99%** and names the mechanism precisely: sensory overload →
**desensitisation → missed alarms**, with patient deaths attributed (Sendelbach & Funk 2013, PMID
24153215; AACN 2014 National Patient Safety Goal). In the NICU the dominant nuisance channel is **SpO2**:
the Mayo Level IV NICU quality-improvement project found **98% of "yellow self-resolving" SpO2 alarms
required no clinical intervention** (McCauley et al. 2021, doi:10.1097/pq9.0000000000000386). That is
exactly the population a *single-feature transient YELLOW* falls into.

**The harm is not "annoyance" — it is measured slower response to the *next* alarm.** Bonafide et al.
directly observed pediatric nurses and found response time **rose monotonically with the number of
preceding non-actionable alarms**: PICU median **1.6 min** (0–29 prior non-actionable alarms) → **6.3 min**
(30–79) → **16.0 min** (80+), log-rank *P*<0.001 (Bonafide et al. 2015, PMID 25873486, doi:10.1002/jhm.2331).
In the NICU itself, nurses answered **only 26% of critical alarms within 90 s** (median 55 s), and were
*slower* to chronically-ill infants — i.e. desensitisation is already operating at the bedside (Joshi et
al. 2017, doi:10.1371/journal.pone.0184567).

**The load-bearing new evidence: reducing non-actionable alarms *improves* response to real ones.** A NICU
before/after study of an alarm-management program cut non-actionable alarms **69% → 43%** and, in the same
window, dropped **median response time from 35 s → 12 s** (both *P*=0.001) (Stiglich et al. 2024, PMID
37339673, doi:10.1055/a-2113-8364). This closes the causal loop §4.1 left open: quieting nuisance alarms is
not a cosmetic trade against safety — it *restores* responsiveness to genuine deterioration.

> **Mapping to NeonatalGuard.** A single-feature transient YELLOW is precisely the low-PPV, self-resolving,
> often-SpO2-adjacent alarm class that *drives* desensitisation. Quieting it is therefore not a safety
> concession but a **direct lever on the harm** (delayed response to the RED that matters). This is the
> "Specificity" force of ADR-0003, now with **neonatal, quantified, direction-of-effect** support — a
> strict extension of §4.1, not a restatement.

---

## 2. THE KEY PRECEDENT — annunciation delays / persistence before a single-parameter alarm

**This is the most important section: it legitimises the two-level floor as *standard monitoring practice*,
not novelty.** Physiological monitors do not annunciate every threshold crossing instantly; they routinely
**suppress transient single-parameter excursions using annunciation delays, persistence requirements, and
averaging windows**, sounding only when the excursion *persists*. That is the exact behaviour of a Tier-2
quiet-until-persist rule — the difference is that ours is deterministic, per-infant, and re-escalating.

**The ICU classic.** Görges, Markewitz & Westenskow instrumented a medical ICU (up to **94% of alarms
false**; clinicians **ignored 41%**) and showed a short annunciation delay is a clean lever: a **14-second
delay removed 50% of false alarms; a 19-second delay removed 67%**, because most were self-resolving
transients (Görges et al. 2009, *Anesth Analg* 108(5):1546–1552, PMID 19372334).

**The neonatal analogue — same mechanism, same channel as our nuisance class.** McClure & Fairchild
analysed preterm SpO2 streams and found that **adding a 15-second alarm delay to 2-second averaging cut
SpO2 alarms by 67% while preserving sensitivity to genuine aberrant-oxygenation events** — and, crucially,
that simply *lengthening the averaging window* (the naïve alternative) **masks real events** (McClure,
Young Jang & Fairchild 2016, *J Neonatal Perinatal Med* 9(4):357–362, PMID 27834782,
doi:10.3233/NPM-16162). The contrast matters for us: a delay/persistence rule that *reverts* is safer than
a smoothing rule that *hides* — which is exactly why our quiet is **time-bounded with guaranteed
re-escalation**, not a permanent suppression. A Level IV NICU QI project then implemented this in practice
(low-limit alarm **delay 10→20 s**, limit widening), cutting yellow self-resolving SpO2 alarms **64%** (14→5
per patient-hour) **with no adverse safety outcomes and stable time-in-target-range** (McCauley et al. 2021,
doi:10.1097/pq9.0000000000000386).

**It is endorsed, not fringe.** AAMI alarm-management guidance and the Joint Commission National Patient
Safety Goal on clinical alarms (NPSG.06.01.01; SEA #50, 2013) explicitly sanction **alarm delays and
default/threshold adjustment** as first-line, evidence-based reductions of non-actionable alarms
(institutional guidance — no PMID).

**The underlying statistical principle.** A single window is a noisy sample; the decision-worthy event is
*persistence / accumulation*, not one reading. This is the SPC/change-detection basis already established in
the CUSUM document (Page 1954, doi:10.1093/biomet/41.1-2.100; Griffin & Moorman 2001, PMID 11134441 — the
sepsis signal is a *rise over hours*, not a single point; see cusum doc §1 & §3). A transient one-feature
YELLOW is the single noisy reading; the actionable object is whether it *persists* — which is precisely what
Tier-2 CUSUM measures.

> **Mapping to NeonatalGuard.** Tier-2's authority to quiet a SOFT single-feature YELLOW is the
> **deterministic, per-infant, calibrated, re-escalating** form of the annunciation-delay/persistence
> technique that monitors already use and guidelines already endorse. We are *stricter* than the shipped
> precedent on three axes: (i) it only touches a **single-feature** YELLOW — never RED, never ≥2 concordant
> features (which stay a HARD floor); (ii) it fires only when the detector is **warmed-up, low accumulated
> drift, and not-recently-alarmed** (a fixed-time monitor delay has none of these gates); and (iii) if the
> excursion persists, the deterministic CUSUM **re-escalates on its own**. On this axis the design is *more*
> conservative than standard practice, not less.

---

## 3. Automation-bias asymmetry — why suppression authority must be calibrated & deterministic

`cusum` §4.2 established that automation bias exists (Parasuraman & Riley 1997,
doi:10.1518/001872097778543886; Goddard et al. 2012, PMID 21685142) and therefore quieting must sit with a
calibrated component. This section adds the **directional** argument the brief asks for: *why suppression is
specifically more dangerous than escalation*, and why that argument points at a deterministic (not LLM)
quieter.

**Automation bias has two error modes, and they are not symmetric.** Skitka, Mosier & Burdick separate
**commission errors** (wrongly *following* an automated recommendation despite contra-indications) from
**omission errors** (failing to notice/act on a real event *because the aid did not flag it*), and show they
have different psychological drivers — commission from over-trust + failure to cross-check, **omission from a
vigilance decrement** (Skitka, Mosier & Burdick 1999, *Int J Hum-Comput Stud* 51(5):991–1006,
doi:10.1006/ijhc.1999.0252). This maps cleanly onto our cascade:

- An **escalation** aid (Tier 3 adds a flag) can, at worst, cause a **commission** error — a clinician acts
  on a false positive. That error is **verifiable at the bedside** and self-limiting (they look, they see
  nothing, they move on).
- A **suppression** aid (something quiets an alarm) can cause an **omission** error — the clinician **never
  looks**, because they were never prompted. Omission errors are driven by the vigilance decrement, are the
  *harder-to-catch* failure, and are compounded by the very desensitisation of §1.

**So suppression is intrinsically the higher-hazard direction of automation assistance** — which is exactly
why ADR-0003 (a) forbids *any* suppression below the HARD floor, and (b) permits the SOFT-YELLOW quiet
**only** through a component engineered to blunt the omission hazard. Lyell & Coiera's systematic review
adds the mitigator: automation bias worsens with cognitive load and with **verification complexity** — the
harder the automated judgement is to check, the more the human defers (Lyell & Coiera 2017, *JAMIA*
24(2):423–431, doi:10.1093/jamia/ocw105). A **deterministic, calibrated, auditable** CUSUM with explicit
warmed-up / low-drift / not-recently-alarmed gates has **low verification complexity** — a reviewer can
inspect the accumulated evidence and the gate states — and it **self-corrects** (guaranteed re-escalation).
An LLM quieter would be the worst case on every axis: uncalibrated, high verification complexity,
hallucination-prone (cusum doc §4.3) — hence Tier 3 is **escalate-only**.

> **Mapping to NeonatalGuard.** The omission/commission asymmetry is the human-factors justification for the
> whole *shape* of the cascade: escalation is the low-hazard direction (allow it broadly, even from the LLM),
> suppression is the high-hazard direction (allow it narrowly, only from a calibrated deterministic detector,
> only above the floor, only with a re-trigger). Directional trust is *earned by verifiability and
> self-correction*, which the CUSUM has and the LLM does not.

---

## 4. Fail-safe / self-correction framing (brief)

A bounded suppression that **reverts to the safe state on persistence** is **fail-safe defaults applied in
the time domain**. Saltzer & Schroeder's principle — absent an explicit, trusted reason to do otherwise, a
system should **fail into the safe (here: higher-concern) state** — is already cited in cusum doc §4.4 for
the un-lowerable floor (Saltzer & Schroeder 1975, doi:10.1109/PROC.1975.9939). The connection worth naming
here: our quiet is *not* an open-ended trust extension. It is a **provisional** suppression whose default,
on any persistence of the excursion, is to re-arm — the deterministic re-escalation guarantee. That makes
the SOFT-YELLOW quiet a **self-correcting** operation, not a bet: the failure mode of a wrong quiet is a
*bounded added delay* (until the next CUSUM update crosses threshold), not a silent permanent miss.

> **Mapping to NeonatalGuard.** "Quiet, but fail back to concern if it persists" is the fail-safe pattern.
> The residual risk it leaves is *delay*, not *omission* — and that residual is precisely what §5 says we
> cannot yet quantify.

---

## Confidence & gaps

- **High confidence (literature-backed, primary-sourced):**
  - NICU/ICU non-actionable alarm burden and the desensitisation → **delayed response** harm (Sendelbach &
    Funk 2013, PMID 24153215; Bonafide 2015, PMID 25873486; Joshi 2017, doi:10.1371/journal.pone.0184567).
  - **Reducing** non-actionable alarms **improves** true-alarm response (Stiglich 2024, PMID 37339673).
  - **Annunciation delay / persistence is standard, effective, guideline-endorsed practice**, including
    **neonatal SpO2** (Görges 2009, PMID 19372334; McClure/Fairchild 2016, PMID 27834782; McCauley 2021,
    doi:10.1097/pq9.0000000000000386). *This is the strongest leg of the argument.*
  - Automation bias splits into omission/commission with omission the harder-to-catch mode (Skitka 1999,
    doi:10.1006/ijhc.1999.0252; Lyell & Coiera 2017, doi:10.1093/jamia/ocw105; Goddard 2012, PMID 21685142).

- **This remains a DESIGN DECISION — no paper validates our exact rule.** Every source above validates an
  *ingredient* (fatigue is harmful; delays work; suppression is the risky direction; fail-safe reversion is
  sound). **None** validates the specific composition "a warmed-up low-drift not-recently-alarmed CUSUM may
  quiet a single-feature YELLOW to GREEN, RED never quietable, re-escalate on persistence." The precedent
  studies use **fixed-time** delays on a raw parameter; ours substitutes a **calibrated stateful detector**
  with gates — a defensible generalisation, but a generalisation, and the burden of proof is ours.

- **The honest residual — the empirical false-quiet rate.** The one number that would settle this is: *how
  often did a quieted single-feature YELLOW precede a genuine event, and how much detection delay did the
  quiet add before deterministic re-escalation?* That requires **labelled outcome data we do not have** (10
  infants, no sepsis labels). Until then, the quiet's safety rests on (a) its narrow scope (single feature,
  above floor only), (b) its gates, and (c) the guaranteed re-trigger bounding the worst case to *delay,
  not omission* — an argument, not a measurement.

- **Directional-generalisation caveat.** The delay evidence is strongest for **SpO2/oxygenation**; our
  quiet applies to single-feature HRV/cardiorespiratory YELLOWs. The *principle* (transient single-parameter
  excursions are largely self-resolving) transfers, but the *quantitative* 67%/64% reductions are
  channel-specific and should not be quoted as if they were our own measured numbers.

- **Institutional (non-PMID) sources.** Joint Commission NPSG / SEA #50 and AAMI alarm-management guidance
  are institutional documents, not peer-reviewed trials — cited as endorsement of the *practice*, not as
  experimental evidence.

---

## References

**Alarm fatigue — neonatal/ICU burden & the desensitisation→delay harm** (extends cusum doc §4.1)
1. Sendelbach, S., & Funk, M. (2013). "Alarm fatigue: a patient safety concern." *AACN Adv Crit Care*
   24(4):378–386. **PMID 24153215.** doi:10.1097/NCI.0b013e3182a903f9 (verified; 72–99% false;
   desensitisation → missed alarms).
2. Bonafide, C. P., Lin, R., Zander, M., et al. (2015). "Association between exposure to nonactionable
   physiologic monitor alarms and response time in a children's hospital." *J Hosp Med* 10(6):345–351.
   **PMID 25873486.** doi:10.1002/jhm.2331 (verified; PICU median response 1.6 → 16.0 min as non-actionable
   exposure rises; *P*<0.001).
3. Joshi, R., et al. (2017). "The heuristics of nurse responsiveness to critical patient monitor and
   ventilator alarms in a private room neonatal intensive care unit." *PLOS ONE* 12(10):e0184567.
   doi:10.1371/journal.pone.0184567 (verified; NICU — only 26% of critical alarms answered within 90 s,
   median 55 s).
4. Stiglich, Y. F., Dik, P. H. B., Segura, M. S., & Mariani, G. L. (2024). "The Alarm Fatigue Challenge in
   the Neonatal Intensive Care Unit: A 'before' and 'after' Study." *Am J Perinatol* 41(S 01):e2348–e2355.
   **PMID 37339673.** doi:10.1055/a-2113-8364 (verified; NICU — non-actionable alarms 69%→43%; median
   response 35 s → 12 s; *P*=0.001).

**The key precedent — annunciation delays / persistence** (new; §2)
5. Görges, M., Markewitz, B. A., & Westenskow, D. R. (2009). "Improving alarm performance in the medical
   intensive care unit using delays and clinical context." *Anesth Analg* 108(5):1546–1552.
   **PMID 19372334** (verified; 14 s delay → 50% fewer false alarms; 19 s → 67%; up to 94% of alarms false;
   41% ignored).
6. McClure, C., Young Jang, S., & Fairchild, K. (2016). "Alarms, oxygen saturations, and SpO2 averaging time
   in the NICU." *J Neonatal Perinatal Med* 9(4):357–362. **PMID 27834782.** doi:10.3233/NPM-16162
   (verified; **neonatal** — 15 s alarm delay on 2 s averaging → 67% fewer SpO2 alarms, sensitivity
   preserved; longer averaging *masks* events).
7. McCauley, K. E., Schroeder, A. A., DeBoth, T. K., et al. (2021). "Reducing Alarm Burden in a Level IV
   Neonatal Intensive Care Unit." *Pediatr Qual Saf* 6(2):e386. doi:10.1097/pq9.0000000000000386
   (verified via PMC10990340; NICU QI — low-limit alarm delay 10→20 s + limit widening → yellow
   self-resolving SpO2 alarms 14→5/patient-hour, 64%↓, no adverse safety outcomes; 98% needed no action.
   *Exact PMID cross-check advised — see note.*).
8. The Joint Commission (2013). *Sentinel Event Alert #50: Medical device alarm safety in hospitals*; and
   National Patient Safety Goal NPSG.06.01.01 on clinical alarm management (institutional — no PMID; endorses
   delays and default/threshold adjustment).
9. AAMI Foundation. Alarm-management guidance / toolkit ("Ten Ideas for Safe Alarm Management," AAMI
   *Biomed Instrum Technol* practice guidance, e.g. doi:10.2345/0899-8205-51.2.109) (institutional guidance
   — endorses delays and default-setting review).

**Automation-bias asymmetry** (extends cusum doc §4.2)
10. Skitka, L. J., Mosier, K. L., & Burdick, M. (1999). "Does automation bias decision-making?" *Int J
    Hum-Comput Stud* 51(5):991–1006. doi:10.1006/ijhc.1999.0252 (verified; omission vs commission errors;
    omission = vigilance-decrement-driven, harder to catch).
11. Lyell, D., & Coiera, E. (2017). "Automation bias and verification complexity: a systematic review."
    *JAMIA* 24(2):423–431. doi:10.1093/jamia/ocw105 (verified; automation bias worsens with cognitive load
    and verification complexity → favour low-verification-complexity, auditable, deterministic quieter).
12. Goddard, K., Roudsari, A., & Wyatt, J. C. (2012). "Automation bias: a systematic review of frequency,
    effect mediators, and mitigators." *JAMIA* 19(1):121–127. **PMID 21685142.** PMC3240751 (verified; carried
    from cusum doc §4.2).
13. Parasuraman, R., & Riley, V. (1997). "Humans and automation: use, misuse, disuse, abuse." *Human Factors*
    39(2):230–253. doi:10.1518/001872097778543886 (verified; misuse=over-reliance, disuse=neglect from false
    alarms; carried from cusum doc §4.2).

**Fail-safe framing & SPC principle** (carried; §4, §2)
14. Saltzer, J. H., & Schroeder, M. D. (1975). "The protection of information in computer systems." *Proc
    IEEE* 63(9):1278–1308. doi:10.1109/PROC.1975.9939 (fail-safe defaults — design principle; carried from
    cusum doc §4.4).
15. Page, E. S. (1954). "Continuous inspection schemes." *Biometrika* 41(1-2):100–115.
    doi:10.1093/biomet/41.1-2.100 (sustained accumulation, not a single point, is the actionable signal;
    carried from cusum doc §1).
16. Griffin, M. P., & Moorman, J. R. (2001). "Toward the early diagnosis of neonatal sepsis… using novel
    heart rate analysis." *Pediatrics* 107(1):97–104. **PMID 11134441** (the sepsis signal is a *rise over
    hours*, not a single reading; carried from cusum doc §3).

**Carried, already-verified in cusum doc §4.1 (not re-fetched here):** Cvach 2012, PMID 22839984;
Drew et al. 2014, PMID 25338067.

---

### Verification notes (honest flags)

- **All new PMIDs/DOIs above were verified** against PubMed / publisher / PMC pages during this research
  (refs 1–6, 10–12). No PMID was reused from memory.
- **[VERIFY-PMID]** Ref 7 (McCauley 2021, *Pediatr Qual Saf*) citation was resolved from **PMC10990340**;
  journal/authors/DOI (doi:10.1097/pq9.0000000000000386) are consistent, but the exact PubMed PMID returned
  by the fetch (38571516) sat oddly against the 2021 volume — **confirm the PMID directly in PubMed before
  quoting it**; the *findings* (delay 10→20 s, 64%↓, no harm) are from the article body and are reliable.
- **[NO PMID — institutional]** Refs 8–9 (Joint Commission, AAMI) are institutional documents, cited as
  endorsement of the *practice* of alarm delays / threshold adjustment, not as experimental evidence.
- **Channel caveat** (repeated for safety): the 67% / 64% delay-reduction figures are **SpO2/oxygenation**
  results; treat them as *precedent for the mechanism*, not as NeonatalGuard's own measured HRV numbers.
- **[UNVERIFIED — none load-bearing]** No claim in this document rests on an unverified source; the only
  flagged item is the *exact PMID* of ref 7 (finding-independent).
