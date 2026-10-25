# Cascade-trace prototype — user feedback round 2 (15 Jul 2026)

Feedback on the #29 prototype (`dashboard/prototypes/cascade-trace-PROTOTYPE.html`),
captured verbatim-in-spirit and applied in `cascade-trace-PROTOTYPE-v2.html`.
Amends the design decisions recorded on issue #29; feeds #30 (trace contract) and #32 (build).

## Keep

- Core design and UI/UX overall.
- The **Run trace** staged-reveal UX — loved. (But see pacing below.)

## Change

| # | Feedback | v2 response |
|---|----------|-------------|
| 1 | **Way too many words.** | All copy cut to fragments: node faces = kicker + title + one mono line; callouts collapsed to single-line notes; citations shortened. |
| 2 | **Cleaner background.** | Radial gradient removed → flat ground + faint dot grid (signals "canvas"). |
| 3 | **A canvas: zoom in/out, swipe left/right with the cursor.** | Full pan/zoom stage — drag to pan, scroll/pinch to zoom (cursor-centred), −/+/fit controls. |
| 4 | **Default view = overview of everything, lines connecting each node.** | Opens fitted to the whole pipeline; SVG connector lines between all five nodes, lit in sequence by the run trace. |
| 5 | **Data In gets a dropdown too.** | Data In expands like the tiers. |
| 6 | **Multiple graphs per tier, one graph per row.** | Tier 1 = three per-feature graphs stacked (rmssd / sdnn / mean_rr, each with baseline band); Tier 2 = CUSUM row; Data In = three sensor rows (HR / RR-interval / respiration). Z-score bars replaced by these. |
| 7 | **Data In dropdown = runnable graph of all sensor input, running continuously.** | Live scrolling strip-charts, run forever (with brady dips + apnea pauses in the synthetic signal). |
| 8 | **Tier 1 & 2 graphs: run until the failure point, then a pulsing red dot there.** | Each series plays from the left, stops at its own crossing (band exit / h=5), pulsing red dot marks the point. |
| 9 | **Verdict at the last tier only — no clutter.** | RED/YELLOW pills removed from Tier 1/2/3 node faces; the Verdict card is the pipeline's final node and the only place a verdict appears. (Safety-floor track kept — it's the signature element, not a verdict.) |
| 10 | **Run trace ~2× longer.** | Step interval 350 ms → 700 ms. |

## Implications for #30 (trace contract)

The trace JSON must now carry, in addition to what #29 pinned:

- **Data In**: raw per-sensor sample streams for the window (not just summary stats) — enough to replay the live strip-charts.
- **Tier 1**: per-feature *time series* + baseline band + the index of the band-exit (failure) point — not just final z-scores.
- **Tier 2**: full CUSUM C⁺ trajectory + the threshold-crossing index.
- Verdict pills per tier are no longer displayed on node faces, but the underlying per-tier assessments stay in the trace for the drawer/report.
