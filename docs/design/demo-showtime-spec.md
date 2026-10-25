# NeonatalGuard — Showtime Demo Spec

**Wayfinder ticket:** [#57](https://github.com/cmengu/Neonatal/issues/57) · **Map:** [#56](https://github.com/cmengu/Neonatal/issues/56)
**Status:** 🟢 APPROVED 2026-07-18 — #57 closed. Frontier is now ② (train JEPA, #58) + ⑤ (immersive shell, #61).

> **How to read this.** `[LOCKED]` = grilled and decided. `[PROPOSED]` = my recommendation — redline freely. The whole point of this doc is to give every downstream ticket one shared source of truth before any code.

---

## 1. Locked decisions (the context every ticket inherits)

From the map (#56), grilled 2026-07-17:
1. Map carries execution; **this spec + the ticket trajectory are approved before any code**.
2. Build **on** the existing trace + ward architecture; elevate **every** element to wow (an ensemble, not one hero + supporting cast).
3. **Real spine, cinematic presentation** — real JEPA + real recorded window drive every panel; **no fabricated clinical/accuracy numbers on screen**.
4. JEPA = real trained model **and** a real Assessor in the cascade seam (Tier 2's learned half, **observational** `may_quiet=false`); the demo reads its real embeddings from the recorded window.
5. Tier 3 reasoning = **recorded-real, cinematically animated** retrieval.

Grilled for this spec (2026-07-17/18):
- **[LOCKED] Scenario** — `infant7 [1240,1419]` (~180 windows ≈ 90 min). Winner of a dataset-wide hunt for the cleanest calm→sustained-elevation arc (baseline deviation ~0.9 → sustained ~1.6). **Fallback:** the proven `infant7 [113,292]` (already recorded, real HARD RED + CUSUM crossing). **#58's acceptance test is the real check** — if the JEPA embedding doesn't visibly leave the normal cloud on `[1240,1419]`, revert to the fallback.
  - *Honest note carried into the pitch:* bradycardia labels in this dataset are isolated single windows (data-integrity artifact, issue #18), so "sustained deterioration" means the real **deviation trend + CUSUM accumulation + JEPA surprise**, not a labelled multi-window episode. That is what's on screen; we never claim more.
- **[LOCKED] Visual direction** — **Clinical-noir** (dark cinematic): near-black canvas, neon-accented data, the 3-D embedding glowing in a black void, mission-control feel.

---

## 2. The demo narrative — beat sheet `[PROPOSED]`

~75 s spine, **auto-play with free scrub afterward** (see §5). One continuous take, no scene cuts that break the "one pipeline, one infant, one clock" feeling.

| t (s) | Beat | What's on screen |
|---|---|---|
| 0–8 | **The ward** | Dark NICU grid, ~12 beds calm (GREEN), **infant7 pulsing RED**. Reads: "many babies, one turning." |
| 8–12 | **Drill-in** | Camera pushes into infant7; the immersive view assembles around a single timeline. |
| 12–52 | **The pipeline, on the shared clock** | Playhead sweeps the 90-min window. Data-in streams; **Tier 1** deviations climb to band-exit; **Tier 2** CUSUM `C⁺` accumulates toward its crossing; the **3-D embedding** drifts out of the normal cloud as Surprise rises; **Tier 3** agents light up and pull citations. Everything moves together. |
| 52–68 | **The verdict** | The cascade merges the three Assessments → **RED**; the **Safety Floor** visibly holds (nothing crossed it); Escalate. |
| 68+ | **Explore** | Free scrub — drag the timeline, every panel + the 3-D move in lockstep. This is the "let me show you any moment" mode for Q&A. |

---

## 3. Visual system — Clinical-noir `[PROPOSED]`

- **Canvas:** near-black `#080b12`, panel surfaces `#0e1420` at ~70% with subtle blur (translucent HUD).
- **Tier accents (one hue each, so the eye tracks a tier across panels):** Tier 1 = cyan/sky, Tier 2 = violet, Tier 3 = amber, Verdict = the concern color. **Concern levels** keep their clinical mapping: GREEN `#22c55e`, YELLOW `#eab308`, RED `#ef4444`.
- **Accessibility:** all text/data ≥ WCAG AA on the dark ground; color never the *only* signal (shape/label too). Applies `/dataviz` palette discipline in ⑦.
- **Type:** a clean grotesk for UI; monospace for numbers/telemetry.
- **Motion:** 60 fps, `easeInOut`, tasteful glow/bloom on the embedding only; everything else restrained (motion earns its place — no gratuitous particles).

---

## 4. Layout — 3-D hero + orbiting HUD `[PROPOSED — key redline #1]`

Full-viewport, single screen (the "dropdown fills the whole page"):
- **Center/right:** the **3-D embedding** as the hero, full-bleed depth.
- **Left rail:** the tier stack — data-in, Tier 1, Tier 2 CUSUM — as translucent panels.
- **Right rail:** the **agent-reasoning theater**.
- **Bottom:** the **shared timeline scrubber** + phase chips (normal / onset / sustained) + verdict readout.

Everything on one clock; nothing is a separate route or modal. *Alternative if you'd rather:* a composed **dashboard grid** where the 3-D is the largest cell but tiers/agents are co-equal framed panels (more legible, slightly less "wow"). **This is the main thing to redline.**

---

## 5. Shared clock + interaction `[PROPOSED]`

- One **playhead index** `0 ≤ P < n` off the #30 time grid drives every series **and** the 3-D marker together.
- **Scrub** (drag), **play/pause**, **phase-jump** (click a phase chip → jump the playhead).
- **Demo-mode** auto-plays the §2 beat sheet with choreographed timing; any interaction drops into free-scrub.

---

## 6. Panel-by-panel wow `[PROPOSED]`

- **Data-in** — HR / RR streams with the normal-band overlay; a glow + marker at band-exit.
- **Tier 1 (Deviation)** — per-feature z-score small-multiples with **labelled axes + legend** (no cram); concordant features highlighted; the persistent **Safety-Floor track** underneath.
- **Tier 2 (CUSUM drift)** — the `C⁺` trajectory climbing to the threshold `h`, a burst at the **crossing index**, and the **quiet-gate table** (why `may_quiet` = ✗).
- **Tier 3 (agents)** — streamed reasoning token-by-token; **animated retrieval** (supervisor → signal/brady/clinical/protocol handover; "reach into NICE NG195 → pull the passage" card reveal); the **escalate-only** rule shown as a structural beat; the self-check pass.
- **3-D embedding (hero)** — §7.

---

## 7. The 3-D embedding hero `[PROPOSED]`

- **Space:** `PCA(embedding) → 3-D`, the basis **fitted on the *normal* phase only** (defensible axes, not fit on the answer). Labelled PC axes; a faint grid in the void.
- **Normal cloud:** the calm-window embeddings as a soft cluster near the origin — "this infant's learned normal."
- **Trajectory:** the window-by-window path, colored by time (cool → warm), gently glowing.
- **Now-marker:** the current playhead position as a bright pulsing node with a short trailing comet.
- **The warp:** a surrounding lattice / field that **deforms and ripples with Surprise magnitude** — the "space warping every second." Embeddings interpolated smoothly between windows so it moves continuously as you scrub.
- **Interaction:** orbit-drag + slow idle auto-rotate; hover a point → its window index / clock time.
- **Honesty:** axis caption says exactly what it is (principal components of the JEPA embedding); no accuracy number painted on it.

---

## 8. Tech choices `[PROPOSED]`

- **3-D:** `react-three-fiber` + `three` (+ `drei` helpers) inside the existing Next.js dashboard. (Vanilla three.js is the fallback if r3f fights the build.)
- **Charts:** extend the existing hand-rolled `TraceChart` / add a light SVG layer — labelled axes, legends, gridlines, per the `/dataviz` palette (ticket ⑦).
- **Data path:** extend the #30 trace contract with a `world_model` block (ticket ④); the demo reads the recorded `trace.json` (decision 4), served offline (`next build`).

---

## 9. Open redlines for the owner

1. **Layout** — hero + HUD (§4) vs. dashboard grid.
2. **Narrative** — ~75 s auto-play + scrub (§2/§5); shorter/longer? auto-play vs. manual-only?
3. **Anything to add or cut** from the panel set (§6).

## 10. Definition of done for #57

Owner approves this doc (redlines resolved) → **#57 closes** → **② (train JEPA)** and **⑤ (immersive shell)** become the frontier. `/to-spec` / `/to-tickets` can then enrich the downstream tickets against this single source of truth.
