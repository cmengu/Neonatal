# Trace contract — §7 `world_model` (addendum, #60)

**Extends** the #30 trace telemetry contract (`docs/design/trace-telemetry-contract.md`, on the
unmerged #30 branch) with one **additive, optional** block. Kept as a separate addendum only
because the base contract doc has not merged to `main` yet; **fold this in as §7 when it does.**
The enforceable mirror already lives on this branch in `dashboard/lib/trace-types.ts`
(`WorldModel`), and the producer is `scripts/export_jepa_trace.py`.

## Why

Decision 4 of map #56: the demo's 3-D embedding hero (#62) and its Surprise warp are driven by
the **real trained JEPA** on the **real recorded window** — not a hand-drawn curve. This block
carries those real model outputs on the **shared time grid** (§1), so the 3-D moves on the same
clock as data-in, Tier 1, Tier 2 and Tier 3.

## Shape

```jsonc
"world_model": {
  "real": true,
  "infant": "infant7",
  "window": [2740, 2919],          // absolute recorded-window span [w0, w1]
  "embed_dim": 48,
  "pca": {
    "fitted_on": "normal",          // axes fitted on the NORMAL PHASE only (spec §7)
    "variance_explained": [0.21, 0.17, 0.13],
    "axis_labels": ["PC1", "PC2", "PC3"]
  },
  "trajectory": [                   // length === time_grid.n, one point per grid window
    { "idx": 0, "pca3": [x, y, z], "novelty": 0.66, "surprise": -0.98 }
    // …
  ],
  "normal_cloud": [[x, y, z], …],   // calm embeddings in the PCA basis — the cluster to draw
  "novelty_baseline_p95": 1.33,     // calm-cloud edge; the warp's "normal" radius
  "surprise": { "series": [...], "calm_mean": 0.0123, "calm_std": 0.0041 },
  "sep_rise_calm_sd": 1.56,         // honest headline: novelty rise across the window, in calm-SD
  "pca_visible_sep": 0.51,          // 3-D drift in cloud-spread units (what the eye sees in 3-D)
  "caption": "Principal components of the JEPA target-encoder embedding, fitted on this infant's normal phase. …"
}
```

## Invariants (the honesty bar)

1. **Grid alignment.** `trajectory.length === time_grid.n`, and `trajectory[i].idx === i` maps to
   absolute window `window[0] + i`. Every point is on the shared clock.
2. **Axes are not fit on the answer.** `pca.fitted_on === "normal"` — the basis comes from the
   pre-onset phase only. (Empirically this basis also *maximises* visible separation vs.
   full-calm or whole-window bases: the departure is diffuse across embedding dims, so no
   3-axis projection is dramatic — see `pca_visible_sep ≈ 0.5`.)
3. **Novelty carries the drama, not the 3-D position.** `novelty` is the full-D Mahalanobis
   distance from the learned-normal cloud (unit = calm-SD); it rises to ~2× the `novelty_baseline_p95`
   cloud edge across the window. **#62 should drive the warp magnitude from `novelty`**, using
   `pca3` only for the trajectory path + now-marker. This is the honest reading of the signal.
4. **All real, all reproducible.** Regenerate with
   `PYTHONPATH=. python3 scripts/export_jepa_trace.py`. "Calm" ground truth is the model-blind
   rolling `‖x_dev‖` (never a label) — identical protocol to `jepa_score.demo_trajectory`.
5. **No accuracy number on screen.** The `caption` states exactly what the axes are; the block
   carries no AUC/accuracy field to paint on the hero.

## Consumers

- `dashboard/lib/trace-types.ts` — `WorldModel` (TS mirror; `world_model?` is optional on `Trace`).
- `dashboard/lib/mock-trace.ts` — imports `world-model-infant7.json` as the real spine of the
  otherwise-synthesised infant7 fixture; bumped `schema_version` 1.0.0 → **1.1.0** (additive).
- **#62** (3-D warp) reads `world_model`; a recorder trace without it must degrade gracefully
  (the field is optional).
