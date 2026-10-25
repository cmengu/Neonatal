# Viability Brief — NeonatalGuard (MGC 2026 pitch appendix)

*The "does this survive past a demo?" appendix. Three questions a probing judge, clinician, or
investor will ask once the demo lands — **Is this legal to deploy? Does the edge story hold up on
real hardware? Isn't the bedside already saturated with monitors?** — each answered from primary
sources and defensible line-by-line. Every claim here traces to one of three companion research
assets, which carry the full citations.*

**Date:** 2026-07-15 · **Map:** [Wayfinder #22](https://github.com/cmengu/Neonatal/issues/22) ·
**Ticket:** [#36](https://github.com/cmengu/Neonatal/issues/36) (Viability strand, synthesis)

**Companion assets (full citations live here):**
- [`hsa-samd-classification-pathway.md`](hsa-samd-classification-pathway.md) — regulatory class + route
- [`edge-deployment-feasibility.md`](edge-deployment-feasibility.md) — where the model actually runs
- [`sg-neonatal-monitoring-landscape.md`](sg-neonatal-monitoring-landscape.md) — what we complement

---

## The one-paragraph version

NeonatalGuard survives past the demo on all three axes. **Regulatorily**, it is a Class C Software
as a Medical Device under Singapore's HSA — a known, walkable path (MEDICS registration + a lawful
pre-registration NICU pilot under a clinical-trials notification), not a wall. **Technically**, the
honest edge story is a hybrid: the deterministic safety-floor runs on the bedside microcontroller
always-on, and the learned intelligence runs on a small nearby gateway — each half backed by
first-party hardware numbers, and we explicitly refuse the false claim that a large model runs on
the chip. **Commercially**, the NICU bedside is saturated with hardware, but none of it is what we
are: we complement the monitors and the one predictive incumbent (HeRO) by adding the reasoning
layer above them, on the telemetry they already produce, anchored to KKH's documented VLBW
late-onset-sepsis population. The through-line: we win by being narrower and more honest than a
marketing claim, not broader.

---

## 1. Regulatory viability — is this legal to deploy, and how hard is the path?

**Verdict: Class C SaMD (plausible range B–C). A defined, walkable path — pilot-legal before full
registration.** Full analysis: [`hsa-samd-classification-pathway.md`](hsa-samd-classification-pathway.md).

- **It is a medical device (SaMD), not an exempt CDSS.** It analyses real-time patient telemetry and
  generates *new* patient-specific escalation verdicts, so it fails both HSA "Non-MD CDSS" exemptions
  — the display-only carve-out (which explicitly excludes real-time patient monitoring) and the
  guideline-echo carve-out (our verdict is *computed* from the infant's own signals, not read off a
  guideline) [GL-07 §3].
- **Most defensible class: C.** On HSA's SaMD matrix, an escalation verdict is *drive clinical
  management* used in a *critical* setting for a *fragile* population (neonates) → Class C [GL-07 §2
  table, p.12]. Doubly anchored by GN-13 Rule 10(i), which puts *continuous surveillance of vital
  physiological processes in intensive care* in Class C ("monitors/alarms for intensive care; apnoea
  monitors"). HSA's own worked example — software that risk-stratifies vital signs for a cardiac event
  at the ED — is classified Class C; we are the neonatal analogue.
- **The lever between B and C is the written intended-use claim.** Claimed as *inform* only, it could
  be Class B; but an "escalation verdict" honestly reads as *drive*, so B would likely be challenged.
  **Plan for C.** Class D is not reachable for this product type.
- **The path is walkable, not a wall.** Register through **MEDICS**; as a novel device the default is
  the Full evaluation route (~220 working days, ~S$6,250), which drops to faster/cheaper Abridged or
  Expedited routes if we hold a prior reference-agency (e.g. FDA/EU) clearance. A **dealer's licence +
  ISO 13485 QMS** are required regardless.
- **We can pilot lawfully before registration.** A pre-commercial NICU pilot is legal as an
  IRB/HBRA-governed clinical trial with a **Clinical Research Materials (CRM) notification** to HSA
  covering the unregistered device — the compliant route to generating our own clinical evidence.
- **AI-specific standing rules (GL-04-R4):** dataset provenance, bias-checked local-population
  validation, clinical association independent of training data, human-in-the-loop workflow (which is
  also what holds us at *drive*, not *diagnose*), and drift monitoring. Practical steer: **ship a
  *locked* model first** — continuous-learning models carry a heavier submission burden.

> **Corrects the main pitch.** The pitch body currently targets **Class B**; the defensible planning
> class is **C**. This is not a weakness to hide — Class C is the honest read of an escalation tool,
> the path is well-defined, and claiming B risks an HSA challenge that reads worse than planning for C
> from the start. Recommend the pitch's regulatory paragraph move to "Class C (decision-support,
> physician-in-the-loop), plausibly B if scoped to inform-only."

## 2. Technical viability — does the "runs on the edge" claim hold on real hardware?

**Verdict: yes, as a hybrid — deterministic floor on the microcontroller, learned intelligence on a
nearby gateway.** Full analysis: [`edge-deployment-feasibility.md`](edge-deployment-feasibility.md).

- **What runs *on* the bedside MCU: the deterministic Tier-1 safety-floor — not a neural net.** Rolling
  per-infant z-scores (Welford, O(1) state) + a CUSUM drift detector (O(1) state) over ~10–12 HRV
  features is a few hundred bytes to single-digit KB of state, no matrix multiply — against **512 KB
  SRAM** on an ESP32-S3. It fits with ~1000× headroom and runs **always-on, WiFi-independent**: a
  dropped network degrades to "local deterministic alarms still fire," not "monitoring offline." This
  is the strongest *true* on-device claim, and it is the clinically load-bearing one.
- **What runs on the gateway: the learned tiers (Tier-2 world-model, Tier-3 guideline-grounded LLM).**
  A 1B-parameter model at 4-bit needs **~0.5–1 GB of RAM** — comfortable on a **Raspberry Pi 5 (up to
  16 GB)** or **NVIDIA Jetson Orin Nano (8 GB, 40–67 TOPS)**, both at the bedside, no cloud round-trip.
  Pi vs Jetson is a cost/latency/power tradeoff, not a feasibility question.
- **The number to have ready for the probe:** a 1B-param 4-bit model is **~1000× larger than the
  ESP32's SRAM**. Stating this *first, unprompted* is what makes the hybrid read as honest engineering.
- **Streaming is trivial:** vitals are ~KB/s; the ESP32's Wi-Fi/BLE-5 radio carries that with orders of
  magnitude of margin. Streaming only computed features/verdicts also keeps patient data local.
- **The refusal is the credibility:** we never claim a large/LLM model runs on the microcontroller. It
  can't (off by ~1000×), and it doesn't need to.

> **Corrects the main pitch.** Two stale phrasings to tighten: (a) the pitch's "deterministic **ONNX**
> safety gate" — the ONNX classifier was **retired** (map #7); the on-device floor is the deterministic
> Tier-1 deviation math, which is a *stronger* claim (auditable, no learned weights). (b) "edge
> deployment / inference under 15 ms" should be scoped to the **gateway** (Pi/Jetson) for the learned
> tiers, with the **MCU** hosting only the deterministic floor — the current wording blurs the two and
> invites the "does the model run on the chip?" gotcha. The honest hybrid answer is more defensible
> than the ambiguous "runs on the edge."

## 3. Commercial viability — isn't the NICU bedside already saturated?

**Verdict: yes — with hardware and one predictive score, neither of which is what we are. We
complement, not compete.** Full analysis: [`sg-neonatal-monitoring-landscape.md`](sg-neonatal-monitoring-landscape.md).

- **Layer 1 — the bedside monitor** (Philips IntelliVue, Dräger Infinity, GE CARESCAPE) is universal
  and continuous, but its alerting is *stateless threshold crossing* — the exact alarm-fatigue regime
  we sit above. It is a sensor + display, not a reasoner. We consume its output; we don't replace it.
- **Layer 2 — the predictive overlay** is essentially one incumbent: **HeRO** (MPSC), FDA-cleared,
  RCT-backed, which reads ECG and emits a single opaque **HRC index**. Its evidence is real but narrow
  and contested (one low-rated RCT; mortality benefit concentrated in <1000 g infants; no reduction in
  sepsis *incidence*; poor real-world PPV — respiratory events and surgery also raise the score).
- **The gap we fill sits above both:** HeRO gives a *number* over one signal, stateless w.r.t. drift
  and un-cited; the monitor gives *threshold alarms*. Neither gives a **tiered, drift-aware, cited
  verdict** a clinician can read, interrogate, and escalate from. NeonatalGuard is a *reasoning*
  overlay, not a rival *scoring* overlay — on the telemetry these devices already produce, so **no new
  bedside hardware**.
- **KKH is the anchor.** Singapore's largest NICU (~40% of national births); its own 11-year cohort —
  1,740 VLBW infants, 9.7% late-onset sepsis, 16% of those died (Goh et al. 2022) — is exactly the
  population HeRO targets and our Tier-1 HRV signature is validated against. KKH is *already* building
  an Early Sepsis Recognition tool — the demand signal for the niche we occupy.
- **Deployability precedent:** HeRO Solo (single-patient, low-infrastructure, marketed outside the US)
  shows a per-cot overlay is a viable market form — the same shape we can take.

> **Reinforces the main pitch.** The pitch's "closes the gap HeRO leaves with per-infant baselines" is
> correct and now fully cited; this section adds the honest appraisal of HeRO's evidence (so we're not
> caught overstating a competitor's weakness) and the KKH population/demand anchor.

---

## Consolidated adversarial Q&A

**"Is this even legal to sell in Singapore?"** Not until registered — and we're explicit it's a Class C
SaMD requiring MEDICS registration + ISO 13485. But we can *pilot* lawfully before that, as an
IRB-approved clinical trial with an HSA CRM notification. The path is defined, not speculative. (§1)

**"You said Class B in the pitch — which is it?"** Class C is the defensible planning class; B is only
reachable if we scope the claim to inform-only, which an escalation verdict doesn't honestly support.
We plan for C. Saying B and being pushed to C later is the worse outcome. (§1)

**"Does the AI run on that little ESP32 chip?"** No — and we lead with that. The ESP32 has ~512 KB of
RAM; a billion-param model needs ~0.5–1 GB, about 1000× more. What runs on the MCU is the deterministic
safety-floor math (z-scores + CUSUM), a few KB of state. The learned model runs on a Pi/Jetson gateway.
(§2)

**"Then why put anything on the MCU?"** Because the safety floor must survive a network outage. Local
+ deterministic means a dropped link degrades to "local alarms still fire," not "monitoring offline" —
and it's O(1) per sample, so there's no reason not to. (§2)

**"The bedside is full of monitors and HeRO already exists — what's left?"** The reasoning layer. The
monitors give threshold alarms; HeRO gives one opaque number over one signal with poor real-world PPV.
Neither gives a tiered, drift-aware, cited verdict a clinician can interrogate. We ride the telemetry
they already produce — no new hardware, not a rival score. (§3)

**"What would you never claim?"** That a large model runs on the microcontroller (it can't), that we're
a new sensor (we're not), or that HeRO doesn't work (it does — narrowly). Each refusal is where the
credibility comes from. (§1–3)

---

## Open items carried from the source assets

- **IMDRF N12 PDF** not directly fetched; its framework is quoted via GL-04/GL-07 which reproduce it —
  Class-C conclusion unaffected. (regulatory asset §2.4)
- **HBRA/DSRB exact obligations** and **GN-15 clause-level** route wording taken from HSA pages, not
  page-by-page from the source PDFs; the route *structure, timelines and fees* are from primary HSA
  pages and reliable. (regulatory asset §5)
- **Our Tier-2/Tier-3 model sizes are not yet fixed** — the recommended hybrid claim is robust either
  way (it only asserts the *deterministic* Tier-1 runs on-device and the *LLM* runs on the gateway). If
  the linear world-model turns out <250 KB, that's an *additional* on-device option, not a change to the
  claim. (edge asset, open items)

---

## Sources

All primary citations (HSA guidance documents, Espressif/NVIDIA/Raspberry Pi datasheets, and the
neonatal-monitoring literature incl. PMIDs/DOIs) live in the three companion assets linked at the top
of this brief. This appendix synthesizes and cross-references them; it does not restate the full
citation lists.
