# ADR-0003 — Two-level Safety Floor: a quietable SOFT floor with guaranteed deterministic re-escalation

**Status:** Accepted (2026-07-13)

**Extends:** [ADR-0001](0001-verdict-composition-and-safety-floor.md) (verdict composition + Safety Floor).
**Evidence:** [`docs/research/de-escalation-alarm-fatigue-evidence.md`](../research/de-escalation-alarm-fatigue-evidence.md)
(neonatal alarm-fatigue + annunciation-delay precedent + automation-bias asymmetry), which builds on
[`cusum-drift-and-composition-validation.md`](../research/cusum-drift-and-composition-validation.md) §4.

## Context

ADR-0001 settled the *shape* of composition — a single deterministic Safety Floor that nothing may cross,
Tier 2 may quiet down to (never below) it, Tier 3 is escalate-only. It left one thing unresolved: the floor
is a **single** level, so the only alarm Tier 2 can ever quiet is one that Tier 1 raised *above* the floor.
But Tier 1 (the #8 direction-aware, concordance-gated Deviation layer) sets the floor **at** the level it
detects. A lone single-feature YELLOW *is* the floor, so under ADR-0001 it is un-quietable — exactly the
transient, low-PPV, self-resolving alarm class that drives alarm fatigue. The product's differentiator
(quieting nuisance alarms) therefore cannot touch its single largest source.

Two forces still pull against each other, now at finer grain:

- **Safety** — a concordant, multi-feature, or critical signal must never be talked down (the FNR=0 promise).
- **Specificity** — a *transient single-feature* YELLOW is the dominant nuisance class; if nothing may quiet
  it, alarm fatigue — which measurably *delays* nurse response to the next, real alarm — is left intact.

The evidence asset resolves how far the quiet may safely reach. Its load-bearing findings:

1. **Precedent, and it is neonatal.** Physiological monitors already suppress transient single-parameter
   excursions with **annunciation delays / persistence requirements** — including preterm SpO₂, where a 15 s
   delay cut alarms 67 % with sensitivity preserved (McClure & Fairchild 2016, PMID 27834782). This reframes
   a quietable floor as *standard monitoring practice made deterministic and per-infant*, not a novel liberty.
2. **The harm is quantified.** Nurse response time rises monotonically with preceding non-actionable alarms
   (PICU median 1.6 → 16 min, Bonafide 2015, PMID 25873486); and cutting non-actionable NICU alarms *restored*
   response to true ones (35 s → 12 s, Stiglich 2024, PMID 37339673). Quieting nuisance alarms is a **direct
   lever on the harm**, not a trade against safety.
3. **Suppression is the hazardous direction.** Automation bias splits into commission (verifiable at the
   bedside) and **omission** (the clinician never looks — vigilance-decrement-driven, harder to catch). A
   quieter sits on the omission side, so the authority to quiet must stay with a **calibrated, auditable,
   deterministic, self-correcting** component (Tier 2 CUSUM) — never the LLM (Skitka 1999; Lyell & Coiera 2017).

## Decision

Split the single Safety Floor into **two levels**, and grant Tier 2 a **gated, self-correcting** authority to
quiet the lower one.

1. **HARD floor — un-quietable.** RED, and any concordant (≥2 direction-agreeing features) Tier 1 signal,
   compute a minimum concern level that **no tier may lower, ever**. This is the unchanged FNR=0 guarantee of
   ADR-0001, now named explicitly as the *hard* floor.

2. **SOFT floor — a transient single-feature YELLOW.** A YELLOW raised by exactly **one** feature, with no
   concordance, is a *quietable* floor. Tier 2 may de-escalate it to GREEN **only** when the deterministic
   CUSUM Drift detector is, at that window, all of:
   - **warmed-up** (enough per-infant history to be calibrated, not cold-start);
   - **low accumulated drift** (`C⁺` well below the CUSUM threshold `h` — no building trend); and
   - **not-recently-alarmed** (no Tier 2 signal in the recent guard window).

3. **Guaranteed deterministic re-escalation.** A SOFT quiet is **provisional**, never permanent. If the
   excursion persists, the deterministic CUSUM accumulates and **re-escalates on its own** on a later window —
   no LLM, no learned tier, in the loop. The worst case of a wrong quiet is therefore a **bounded added delay**
   (until the next CUSUM crossing), not a silent omission. This is fail-safe-defaults applied in the time
   domain (Saltzer & Schroeder 1975): absent a trusted reason to stay quiet, revert to the higher-concern state.

4. **Tier 3 (RAG/LLM) stays escalate-only** — unchanged from ADR-0001. The LLM may raise concern; it has **no**
   part in any quiet, at either floor. Directional trust is earned by verifiability and self-correction, which
   the CUSUM has and the LLM does not.

Composition becomes:

```
hard_floor = deviation.hard_level        # RED or ≥2 concordant — un-quietable
soft_floor = deviation.soft_level        # single-feature YELLOW — quietable to GREEN by a gated Tier 2
effective_floor = hard_floor  if not (single-feature YELLOW and CUSUM warmed-up & low-drift & not-recently-alarmed)
                  else GREEN            # the SOFT quiet
verdict = max( merge(Tier2, Tier3 escalations), effective_floor )
```

RED and concordant signals collapse `soft_floor` into `hard_floor` (nothing to quiet). The only behavioural
change from ADR-0001 is the narrow, gated, self-reverting quiet of a **lone** transient YELLOW.

## Consequences

- The differentiator finally reaches its largest target: the transient single-feature YELLOW — the class the
  neonatal literature identifies as the dominant, ~98 %-self-resolving nuisance alarm — is now quietable,
  where before it was pinned at the floor.
- The safety story stays a one-module property and gets *stronger*, not weaker: the HARD floor is still
  un-lowerable and testable in isolation; the SOFT quiet is bounded by three inspectable gates **and** a
  guaranteed re-trigger, so its failure mode is provably *delay, not omission*.
- The de-escalation algebra that #4 deferred and #5 was holding now has a written contract with evidentiary
  weight — it graduates into its own engineering ticket, gated (green) by this evidence asset, rather than
  living as a comment in `cascade.py`.
- Tier 1 must expose the floor as **two** levels (hard vs. soft), not one — the concordance/direction
  machinery from #8 already computes the distinction; the cascade just needs to consume both.
- The regulator-facing line sharpens: *"the language model can raise a flag but never suppress one; only a
  calibrated, auditable, self-correcting detector may quiet a single transient reading, and only until it
  persists."*

## The honest residual (named, not hidden)

No paper validates this **exact** rule. Every ingredient is primary-sourced — fatigue is harmful; delays
work; suppression is the risky direction; fail-safe reversion is sound — but the *composition* (a warmed-up,
low-drift, not-recently-alarmed CUSUM may quiet a single-feature YELLOW to GREEN, re-escalating on
persistence) is engineering judgement. The one number that would settle it — the **empirical false-quiet
rate** (how often a quieted YELLOW preceded a genuine event, and the delay the quiet added) — is
**unmeasurable on our unlabelled 10-infant PICS set**. Until real outcome data exists, the argument rests on
narrow scope (single feature, above the HARD floor only) + the three gates + the guaranteed re-escalation
bounding the worst case to delay. The precedent studies also used **fixed-time** delays on a **raw**
parameter (mostly SpO₂); ours substitutes a **calibrated stateful detector** with gates over HRV — a
defensible generalisation, but a generalisation, and the burden of proof is ours.

> **Citation flag:** McCauley et al. 2021 (*Pediatr Qual Saf*) is carried in the evidence asset with a
> **[VERIFY-PMID]** note (the fetched PMID sat oddly against the 2021 volume). Its *findings* are reliable
> from the article body; the exact PMID is to be confirmed or the citation dropped before it is quoted as
> settled. This ADR does not lean on it as load-bearing — McClure/Fairchild 2016 and Stiglich 2024 carry
> the neonatal precedent independently.

## Alternatives considered

- **Keep the single floor (ADR-0001 as-is)** — simplest, but leaves the largest nuisance-alarm class
  un-quietable, so the alarm-fatigue differentiator never engages its main target.
- **Quiet with a fixed-time annunciation delay on the raw feature** (the literal precedent) — well-validated,
  but throws away personalisation and the auditable CUSUM state; a fixed delay has none of the warmed-up /
  low-drift / not-recently-alarmed gates, and reverts by a dumb timer rather than by evidence accumulation.
- **Let a longer averaging window smooth the transient** — the naïve alternative the neonatal evidence
  explicitly warns against: longer averaging *masks* real events (McClure/Fairchild 2016). A quiet that
  *reverts on persistence* is safer than a smooth that *hides*.
- **Allow Tier 3 to quiet the SOFT floor too** — maximally capable, but puts suppression authority on the
  omission-hazard side with an uncalibrated, high-verification-complexity generative component. Rejected.
- **A permanent (non-reverting) quiet of the SOFT YELLOW** — simpler control flow, but converts a bounded
  *delay* into a possible silent *omission*, forfeiting the fail-safe property that is the whole safety case.
