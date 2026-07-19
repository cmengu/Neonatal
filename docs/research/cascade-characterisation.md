# Cascade characterisation — what the watcher can see, and how often it cries wolf

**Issues:** #83 (harness), #84 (Tier 2 operating point) · **Spec:** #82, decisions D10, D11
**Regenerate:** `PYTHONPATH=. python scripts/characterise_cascade.py` → `results/cascade_characterisation.json`
**Code:** `src/characterisation/harness.py` · **Tests:** `tests/test_characterisation_harness.py`

---

## What this document may and may not be used for

Every number here comes from **synthetic data**. It characterises the *detector* — Tier 1's
floor and Tier 2's CUSUM — and says nothing whatever about any infant, about sepsis, or
about clinical performance.

That separation is the acceptance condition of #83, and it has published precedent in this
exact niche. Montazeri Ghahjaverestan et al. (2021) characterised an apnea-bradycardia
detector on simulated data (Se 96.67%, Sp 98.98%), then validated the clinical claim on
real preterm ECG (Se 94.87%, Sp 96.52%, mean delay 0.73 s). Reviewers accepted it because
simulation characterised the detector and real data characterised the claim, and the paper
never conflated the two.

**Supports:** "the watcher detects a sustained departure of magnitude δ within N windows at
X false alarms per patient-day."
**Never supports:** anything about sepsis, or about a real infant.

### Two limits to state before any number is quoted

1. **The stream is z-scores, not RR intervals.** Departures are injected into the
   per-infant z-score stream the cascade consumes, one stage after feature extraction. This
   is deliberate: Tier 1's `z_trigger` and Tier 2's `(k, h)` are both defined in z-units, so
   a departure specified in z-units is specified in the detector's own units. The cost is
   that this measures the detector, **not** the feature pipeline — it cannot tell you what
   RMSSD drop in milliseconds produces a 1 SD z-shift. Quote these results in z-units only.
2. **In-control windows are i.i.d.; real ones are not.** A real neonatal z-stream is
   autocorrelated, which inflates the true false-alarm rate above an i.i.d. simulation.
   **Every ARL₀ and false-alarm figure below is an optimistic bound.** Read the ordering
   across `(k, h)`, not the absolute level. `src/assessment/cusum.py` has flagged this as
   pending since the research gate (§2.4); this document is that simulation, and it does not
   discharge the need to confirm on the real stream.

Window cadence: a Tier-1 window advances 25 beats; at ~140 bpm that is **10.7 s**, so one
patient-day ≈ 8,064 windows.

---

## The finding that explains everything else

`composite_deviation` — the scalar the CUSUM accumulates — is a **rectified** statistic.
`pathological_magnitude` returns `max(0, ·)`: a feature deviating the *reassuring* way
contributes 0, not a negative. So under pure noise the composite does not average to zero.

Measured over 4,000 in-control windows: **mean composite = 0.474**.
Analytic, for N(0,1) with four one-sided features and one two-sided (`mean_rr`):

    (4 · E[z⁺] + E|z|) / 5  =  (4 · 0.399 + 0.798) / 5  =  0.479

Measurement and theory agree. **This is the number `k` has to clear.**

The textbook rule that produced the current setting — *k = half the shift you want to
detect, so k = 0.5 for a sustained 1 SD shift* — assumes the CUSUM's input is **zero-mean
under control** and that it sees the **full** shift. Neither holds here:

- the input has an in-control mean of **0.474**, not 0;
- a departure moves 3 of the 5 direction-aware features, and the composite is their *mean*,
  so a nominal 1.0 SD departure presents to the CUSUM as **0.886** (ratio 0.89), and a
  2.0 SD departure as 1.442 (ratio 0.72).

So `k = 0.5` sits **0.026 above the noise floor**. The accumulator is very nearly an
unbiased random walk, and it wanders up to `h` on noise alone. That is not a typo-level
error — the value is defensible arithmetic from a rule that does not apply to this input.

---

## Measured operating characteristic

Sustained 1.0 SD departure in `sdnn`/`rmssd`/`sampen`. ARL₀ from in-control runs of 20,000
windows (~2.5 patient-days each), 40 runs per cell — 800,000 in-control windows per cell.

| k | h | ARL₀ (windows) | false alarms / patient-day | detection | median delay |
|---|---|---|---|---|---|
| 0.25 | 5.0 | 23 | **347** | 0% — always fires before onset | — |
| 0.50 | 3.0 | 463 | 17.4 | 85.0% | 6 win / 64 s |
| 0.50 | 4.0 | 886 | 9.1 | 98.3% | 8 win / 86 s |
| **0.50** | **5.0** | **1,700** | **4.7** | **99.2%** | **10 win / 107 s** ← current |
| 0.50 | 6.0 | 2,899 | 2.8 | 99.2% | 13 win / 139 s |
| **0.60** | **4.0** | **> 800,000** | **0.00** | **100%** | **14 win / 150 s** ← candidate |
| 0.60 | 5.0 | > 800,000 | 0.00 | 100% | 17 win / 182 s |
| 0.68 | 4.0 | > 800,000 | 0.00 | 100% | 19 win / 204 s |
| 0.75 | 5.0 | > 800,000 | 0.00 | 100% | 36 win / 380 s |
| 1.00 | 5.0 | > 800,000 | 0.00 | **6.7%** | 1,677 win / 5.0 h |

Every cell is measured at the same run length. An earlier draft of this table mixed
3,000-window and 20,000-window runs and produced a non-monotonic row — ARL₀ appearing to
*fall* between h=5 and h=6, which is impossible. The cause was censoring: at 3,000 windows
a large fraction of high-h runs never fire, and dropping them biases ARL₀ downward. Runs
that never fire are now counted, and `censored_fraction` is reported alongside every figure.

Three regimes, and the boundary is the 0.474 noise floor:

- **k < 0.474** — the accumulator drifts upward on noise. k=0.25 gives ARL₀ = 23 windows,
  i.e. **344 false alarms per patient-day**. Unusable.
- **k ≈ 0.474** — marginal. This is where k=0.5 sits, and 4.7 false alarms/day follows.
- **k > 0.474 with margin** — mean-reverting. At k=0.60 the drift is −0.126, roughly five
  times more negative, and ARL₀ grows so fast that **zero false signals occurred in 800,000
  in-control windows**.
- **k > the departure composite** — detection all but fails. k=1.0 exceeds the 0.886 that a
  1 SD departure produces, so the accumulator has negative drift even *during* the
  departure and only reaches h on a lucky excursion: 6.7% detection at a median 5 hours.
  That row is the arithmetic working exactly as it should.

There is also a cheaper option on the same curve: **k=0.5, h=6.0** keeps the current k and
buys 4.7 → 2.8 false alarms/day for 32 s of delay. It is strictly worse than the k=0.60
candidate (2.8 vs 0.00 alarms/day for 11 s less delay), but it is the smaller change, and
worth naming rather than leaving implicit.

### What raising k costs

The gain is not free, and the cost falls entirely on **small** departures.

| δ (SD) | k=0.5, h=5.0 (current) | k=0.6, h=4.0 (candidate) | cost |
|---|---|---|---|
| 0.25 | 99.2% · 61 win / **654 s** | 95.0% · 849 win / **9,096 s** | **14× slower** |
| 0.50 | 99.2% · 24 win / 257 s | 100% · 56 win / 595 s | 2.3× |
| 0.75 | 99.2% · 16 win / 171 s | 100% · 22 win / 241 s | 1.4× |
| 1.00 | 99.2% · 10 win / 107 s | 100% · 14 win / 150 s | 1.4× |
| 1.50 | 99.2% · 6 win / 64 s | 100% · 7 win / 75 s | 1.2× |
| 2.00 | 99.2% · 4 win / 43 s | 100% · 4 win / 43 s | none |

The δ=0.25 row is the one to argue about. Note what it is: a departure an **eighth** the
size Tier 1 needs to fire at all (`z_trigger = 2.0`), well inside the normal variation of
an infant's own baseline. Detecting it 2.5 hours later, rather than 11 minutes later, is
the price of removing every measured false alarm.

For δ ≥ 0.75 the candidate costs **≤ 43 s** of extra delay and removes ~4.7 false alarms per
patient-day. For δ = 0.25 it costs **2.5 hours instead of 11 minutes** — a real loss, on a
departure well inside normal variation, an eighth of the size Tier 1 needs to fire at all.

### On the "sensitivity floor"

There is no useful unqualified sensitivity floor for this detector, and that is a property
of CUSUMs rather than a gap in the measurement. A CUSUM integrates, so for a *sustained*
departure the detection probability tends to 1 for any δ > 0 given unbounded time —
measured here as **99.2% at every δ from 0.25 to 2.0 SD** when 500 windows were available.
An unqualified floor would always read ≈ 0 and mean nothing.

The honest form is a joint statement: **this magnitude, within this long, at this
false-alarm rate.** `sensitivity_floor()` therefore requires a time budget as a mandatory
argument.

### Tier 1, separately

Tier 1 is memoryless. With 5 trigger-capable features under i.i.d. noise, P(some feature
clears z=2.0 in its pathological direction) ≈ 11% per window, so a single-feature YELLOW
appears within a handful of windows on a stream containing no departure at all. Measured:
the composed cascade fires at window 4 on a stream where Tier 2 alone never fires.

This is the design working, not failing — it is exactly why a single-feature floor is
**SOFT** and why Tier 2 is the only tier permitted to quiet it (ADR-0003). But it means
**Tier 1's alarm rate is dominated by multiplicity, and any alarm-burden claim must be made
about the composed cascade, never about Tier 2's ARL₀ alone.**

---

## Recommendation for #84 — and what is not being decided here

**Move `k` from 0.50 to 0.60, and `h` from 5.0 to 4.0.** On the measured curve this is
better on every axis that was measured except small-departure latency:

- false alarms **4.7/day → 0** (none in 800,000 in-control windows)
- detection of a 1 SD departure **99.2% → 100%**
- median delay **107 s → 150 s** — 43 s slower
- and the i.i.d. caveat makes this *more* urgent, not less: 4.7/day is an optimistic bound,
  so the real current rate is worse than measured, while k=0.60 has ~800,000 windows of
  headroom to absorb autocorrelation.

**The default has not been changed in code.** Two reasons, and both are judgement calls a
reviewer should be able to overturn:

1. The 0.25 SD row is a genuine clinical trade-off — whether an eighth-of-threshold drift is
   worth catching 2.5 hours late, or at all, is a question about what the system is *for*,
   and it is not answerable from simulation.
2. Alarm thresholds on a device analogue are not a parameter to change silently as a side
   effect of building a harness.

`CusumThresholds` is already injectable, so adopting this is a one-line change with no
rewrite: `TemporalAssessor(thresholds=CusumThresholds(k=0.6, h=4.0))`.

**What #84 asked for is settled either way:** the operating point is no longer inherited. It
now sits on a measured curve, with the reason the original justification does not hold
written down — the "half the shift" rule assumes a zero-mean input, and this input has an
in-control mean of 0.474.

## Still open

- **Confirm on the real stream.** Everything here is i.i.d. The autocorrelated-stream
  measurement that `cusum.py` §2.4 has always asked for still has not been done, and it is
  the one that fixes the absolute level rather than the ordering.
- **Persist the audit fields.** `cusum.py` notes that state deliberately does not yet carry
  `(k, h, δ)` + measured ARL₀. Now that ARL₀ is measured, those fields can be populated.
- **Characterise the composed cascade's alarm burden**, not just Tier 2's — see the Tier 1
  multiplicity note above.
- **Feature-pipeline sensitivity** — what departure in milliseconds produces a 1 SD z-shift
  — is out of scope here by construction and belongs with the D2 quantisation work.

## References

- Page, E.S. (1954). Continuous inspection schemes. *Biometrika* 41(1–2):100–115.
- Montazeri Ghahjaverestan, N. et al. (2021) — apnea-bradycardia detector characterised on
  simulated data, claim validated on real preterm ECG.
- `docs/research/cusum-drift-and-composition-validation.md` — research gate #11, the source
  of the original `k = 0.5`, `h = 5` defaults.
