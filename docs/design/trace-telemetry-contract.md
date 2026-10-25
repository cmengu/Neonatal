# Trace telemetry contract — the per-tier `trace.json`

**Wayfinder ticket:** [#30](https://github.com/cmengu/Neonatal/issues/30) · **Map:** [#22](https://github.com/cmengu/Neonatal/issues/22) · **Strand:** Demo (the seam between backend recording and the frontend).

This is the contract for the single JSON artifact that the recording script (**#31**) emits
and the dashboard trace view (**#32**) consumes. It is the *seam*: the recorder is done when it
writes a file that validates against this, and the UI is done when it renders one that validates.
Neither side reaches across it.

Two hard constraints shape every field below:

1. **Honesty.** The trace carries what the real cascade actually produced on a real recorded
   infant window — nothing the pipeline can't stand behind. Three places where the #29 prototype
   asks for richer data than the current backend emits are called out explicitly in the
   [Honesty ledger](#honesty-ledger); each has a default and is flagged for the human to override.
2. **One shared time grid** (#29 v3, item 11). Every replayable series in the trace — every Data In
   channel, every Tier 1 feature series, the Tier 2 CUSUM trajectory — is sampled on the **same
   axis of the same length**, so a single UI playhead `P` indexes all of them at once.

Field shapes map to real objects: `Assessment` / `Verdict` (`src/assessment/types.py`, post-#23),
`CusumState` / `QuietGates` / `CusumThresholds` (`src/assessment/cusum.py`),
`DeviationAssessor` (`src/assessment/deviation.py`), and `AgentState` / `NeonatalAlert`
(`src/agent/graph.py`, `src/agent/schemas.py`).

---

## Top-level shape

```jsonc
{
  "schema_version": "1.0.0",          // bump on any breaking change to this contract
  "patient_id": "infant7",           // the one real recorded window this trace replays
  "generated_at": "2026-07-15T...",   // ISO-8601, stamped by the recorder (#31)
  "source_commit": "fc86e31",         // git SHA of the cascade that produced this trace

  "time_grid": { ... },               // §1 — the one axis everything is sampled on
  "data_in":   { ... },               // §2 — raw bedside streams (honest channel set)
  "tier1":     { ... },               // §3 — Deviation: per-feature series + floor
  "tier2":     { ... },               // §4 — CUSUM C⁺ trajectory + quiet gates
  "tier3":     { ... },               // §5 — RAG: query, retrieval, reasoning, self-check
  "verdict":   { ... }                // §6 — the merged Verdict + its trail
}
```

The recorder emits exactly these keys. The UI reads them and never invents a field the recorder
didn't write; if a tier is absent (e.g. Tier 3 short-circuited on a GREEN window — see §5), its
key is present with `"ran": false` rather than missing.

---

## §1 — `time_grid` (the shared axis)

Every series in the trace is an array of the **same length** `n`, aligned index-for-index to this
grid. The UI playhead is an integer index `0 ≤ P < n`; moving it moves every chart together.

```jsonc
"time_grid": {
  "n": 180,                       // number of samples on the axis (== length of every series)
  "unit": "window",               // "window" | "second" — what one index step means
  "step_seconds": 30,             // real seconds per index step (windows are 30 s in this repo)
  "labels": ["00:00", ...],       // length n, human clock labels for the timeline ruler
  "phases": {                     // #29 v3 item 11 — the three clickable timeline windows
    "normal":    [0, 89],         // [start_idx, end_idx] inclusive — baseline, all calm
    "onset":     [90, 134],       // Tier 1 first flags somewhere in here (band exit)
    "sustained": [135, 179]       // Tier 2 CUSUM crosses h somewhere in here
  }
}
```

- **Phase boundaries are recorder-computed, not hand-set** (#29 v3): `onset.start` is the first
  index at which the Tier 1 rule flags any feature (band exit); `sustained.start` is the index at
  which the Tier 2 CUSUM first crosses `h`. The recorder derives them by replaying the window
  range through the real assessors and recording where each event first occurs.
- A trace whose window never escalates (all-GREEN bed) carries `onset` / `sustained` as `null`.

---

## §2 — `data_in` (raw bedside streams)

One graph per channel (#29 v3 item 1: "show *all* the data, good or bad"). Each channel carries its
full raw sample stream on the shared grid, its own baseline band so "good" channels render too, and
the index at which it leaves the band (`null` if it never does).

```jsonc
"data_in": {
  "channels": [
    {
      "key": "heart_rate",
      "label": "Heart rate",
      "unit": "bpm",
      "real": true,               // ← honesty flag: true = genuinely recorded (Ledger H1)
      "samples": [148, 150, ...], // length n, on the shared grid
      "band": { "low": 100, "high": 200 },   // normal band drawn behind the trace
      "band_exit_idx": 96,        // first index outside band; null if never
      "flagged": true             // did this channel ever leave its band? drives grouping
    }
    // ...one object per channel
  ]
}
```

**Honest channel set (Ledger H1).** The recorded data behind this repo is an **ECG-derived
RR-interval stream** plus its **respiration / apnea** annotations (`data/processed/*_rr_clean.csv`,
`*_resp_features.csv`, `*_apnea_episodes.csv`). The channels the recorder can emit with
`real: true` are therefore:

| `key`            | Source                                          | `real` |
|------------------|-------------------------------------------------|:------:|
| `heart_rate`     | derived from the RR-interval stream (60000/RR)  | ✅ |
| `rr_interval`    | `*_rr_clean.csv`                                | ✅ |
| `respiration`    | `*_resp_features.csv`                           | ✅ |
| `apnea_events`   | `*_apnea_episodes.csv` (event markers on grid)  | ✅ |

The prototype also drew SpO₂, perfusion index, mean BP, skin temp, and pulse pressure. **We do not
record those.** Per Ledger H1 the default is: **the recorder emits only `real: true` channels.** If
the demo wants extra channels for visual density, each MUST carry `real: false` and the UI MUST
render a visible "simulated for illustration" marker on that card — the trace never passes off a
synthetic stream as recorded. *(Override point — see Ledger.)*

---

## §3 — `tier1` (Deviation — instantaneous floor, replayed to a series)

The `DeviationAssessor` is stateless and judges one window. To feed the prototype's per-feature
series that "plays to a failure point," the recorder **replays the assessor window-by-window** over
the range and records each feature's z-score trajectory + the index where it crosses its trigger.

```jsonc
"tier1": {
  "features": [
    {
      "key": "sdnn",
      "label": "SDNN",
      "direction": "low",              // DEFAULT_DIRECTIONS side; null for a display-only feature
      "trigger_feature": true,         // is this feature allowed to drive the floor? (in DEFAULT_DIRECTIONS)
      "z_series": [-0.2, -0.4, ...],   // length n — the {feature}_dev column over the range
      "value_series": [48.1, ...],     // length n — raw HRV value (for the readout)
      "baseline": { "mean": 52.0, "std": 6.1 },   // per-infant band (personal_baseline)
      "z_trigger": 2.0,                // DeviationThresholds.threshold_for(feature)
      "failure_idx": 118,              // first idx where pathological_magnitude ≥ z_trigger; null
      "flagged": true                  // did it ever trigger? drives the collapse groups (v3 item 4)
    }
    // ...one per feature in HRV_FEATURE_COLS (12 features — all shown, v3 item 3). Only the 5 in
    // DEFAULT_DIRECTIONS (sdnn, rmssd, sampen, sample_asymmetry, mean_rr) can trigger; the other 7
    // (pnn50, lf_hf_ratio, the rr_ms_* order statistics) are display-only — direction:null,
    // trigger_feature:false, always flagged:false. The UI groups them under "within baseline"
    // rather than implying a threshold they can never cross.
  ],
  "floor": {                           // the Safety Floor this tier sets at the final window
    "level": "RED",                    // ConcernLevel the deviation tier produced
    "concordant_count": 2,             // how many features triggered (≥2 ⇒ HARD RED)
    "soft_floor": false,               // Assessment.soft_floor — is this a quietable single-feature YELLOW?
    "kind": "HARD"                     // "HARD" (RED/≥2) | "SOFT" (single-feature YELLOW) | "NONE" (GREEN)
  },
  "indicators": ["sample_asymmetry", "sdnn"],   // Assessment.primary_indicators (#23), strongest first
  "verdict_text": "Deterministic deviation floor (RED): 2 feature(s) deviating ..."  // Ledger H3
}
```

- `direction`, `z_trigger`, `baseline` and the flag rule all come straight from
  `DeviationAssessor` + `DeviationThresholds` — no new logic, just capture-per-window.
- `failure_idx` is where the prototype pulses its red dot for that feature.
- `flagged` makes the "Flagged (open) / Within baseline (collapsed)" grouping **data-driven**
  (#29 v3 item 4), not hard-coded in the UI.
- `verdict_text` is the tier's own `Assessment.rationale` verbatim (Ledger H3) — the UI renders
  it as the plain-English Tier-1 verdict card (#29 v3 item 5); it is **not** written in the frontend.

---

## §4 — `tier2` (Temporal / CUSUM — the drift trajectory + quiet gates)

The recorder replays the window range through `TemporalAssessor`, capturing the running `C⁺`
(`CusumState.c_plus`) at every step so the prototype's single CUSUM chart can animate to its
crossing, then records the quiet-gate evaluation at the decision window.

```jsonc
"tier2": {
  "c_plus_series": [0.0, 0.3, ...],  // length n — CusumState.c_plus captured each replayed window
  "h": 5.0,                          // CusumThresholds.h — the decision interval (drawn as a line)
  "k": 0.5,                          // CusumThresholds.k — the slack (for the caption)
  "crossing_idx": 141,               // first idx where c_plus ≥ h (the Drift fire); null if never
  "fired": true,                     // did the CUSUM signal a Drift in this window?
  "level": "YELLOW",                 // the Assessment.level Tier 2 produced (Drift ⇒ YELLOW)

  "quiet": {                         // why may_quiet was / wasn't granted (#29 v3 — the gate table)
    "may_quiet": false,              // Assessment.may_quiet — the final grant
    "gates": [                       // each QuietGates condition, with the value that decided it
      { "key": "warmup",    "label": "Warmed up (≥20 windows)",       "pass": true,  "detail": "n_updates=141 ≥ 20" },
      { "key": "low_drift", "label": "No building trend (C⁺<0.25·h)", "pass": false, "detail": "prior C⁺=4.8 ≥ 1.25" },
      { "key": "guard",     "label": "Not recently alarmed (≥20 w)",  "pass": true,  "detail": "no prior signal" }
    ],
    "soft_floor_target": false,      // was there a SOFT floor to quiet at all? (tier1.floor.kind == "SOFT")
    "note": "Tier 2 may only quiet a SOFT single-feature YELLOW — never the HARD RED floor."
  },
  "verdict_text": "CUSUM Drift (YELLOW): first sustained Drift for this infant ..."  // Assessment.rationale (Ledger H3)
}
```

- `c_plus_series`, `h`, `k`, `crossing_idx` come from replaying `TemporalAssessor` — the running
  sum *is* the accumulated evidence, so capturing `CusumState.c_plus` per step is the honest series.
- The **gate table** is the prototype's "why `may_quiet = ✗`" panel. Each entry mirrors one
  `QuietGates` condition (`warmup_windows`, `max_c_plus_frac`, `guard_windows`) with the actual
  value the recorder observed, so the UI shows *which* gate failed, not just the boolean.
- `soft_floor_target` + `note` encode the SOFT-vs-HARD rule the prototype calls out: a HARD RED
  floor is never quietable, so on this trace the gate outcome is moot for the verdict — the panel
  states that explicitly rather than implying a quiet could have changed the RED.

---

## §5 — `tier3` (RAG — query, retrieval, reasoning, self-check)

Maps to the real `AgentState` surface (`build_query → retrieve → reason → self_check → assemble`)
and the final `NeonatalAlert`. **Short-circuit honesty:** the cascade skips Tier 3 entirely when the
merged Tier 1 + Tier 2 level is GREEN. If it didn't run, the recorder writes `{"ran": false}` and
nothing else; the UI renders a "skipped on a calm window" state, never an empty reasoning block.

```jsonc
"tier3": {
  "ran": true,
  "query": "Personalised HRV deviations: sample_asymmetry high (z=+3.1), sdnn low ...",  // AgentState.rag_query
  "retrieved": [                     // AgentState.rag_context — only traceable() guideline chunks (#5 gate)
    { "id": "NICE-NG195-1.3.2", "source": "NICE NG195", "snippet": "In babies with red-flag ..." },
    { "id": "AAP-COFN-preterm-4", "source": "AAP/COFN", "snippet": "Preterm infants with apnea ..." }
  ],
  "reasoning": "Reduced variability (low SDNN/SampEn) with a rising deceleration burden ...",  // LLMOutput.clinical_reasoning
  "self_check": {                    // self_check_node — Verify pass/fail
    "passed": true,
    "note": "Cited actions match retrieved guideline scope; no over-reach flagged."
  },
  "concern_level": "RED",            // LLMOutput.concern_level (escalate-only — see verdict)
  "confidence": 0.86,                // LLMOutput.confidence
  "recommended_action": "Immediate clinical review",   // LLMOutput.recommended_action (APPROVED_ACTIONS)
  "primary_indicators": ["sample_asymmetry", "sdnn"],  // LLMOutput.primary_indicators
  "escalate_only_note": "Tier 3 may raise concern above the floor but never lower it."
}
```

**Ledger H2 — reasoning granularity.** The prototype (#29 v3 item 7) renders a *5-step inference
chain with per-step self-checks*. The real graph emits **one** `clinical_reasoning` string and
**one** `self_check_passed` boolean. Default: the contract carries **exactly what the graph
emits** — the single `reasoning` block and the single `self_check` result — plus the `query` and
`retrieved` passages, which are real. The UI may *present* the reasoning as retrieve → reason →
self-check stages (those three graph nodes are real), but the trace does **not** fabricate five
distinct steps or per-step self-checks the backend never produced. *(Override point — if the demo
needs a genuine multi-step chain, that is a graph change to emit structured steps, not a contract
invention; it would add a `reasoning_steps: [...]` array here. Flagged for the human.)*

---

## §6 — `verdict` (the merged Verdict + its trail)

The one consolidated card (#29 prototype "Report"). Direct from the post-#23 `Verdict`.

```jsonc
"verdict": {
  "patient_id": "infant7",
  "level": "RED",                    // Verdict.level — the final concern
  "risk": 0.94,                      // Verdict.risk (from the headline assessment)
  "confidence": 0.86,                // Verdict.confidence
  "safety_floor": "RED",             // Verdict.safety_floor — the un-lowerable minimum
  "escalated_by": ["deviation"],     // Verdict.escalated_by — which tiers rose above the floor
  "recommended_action": "Immediate clinical review",   // Verdict.recommended_action (#23)
  "primary_indicators": ["sample_asymmetry", "sdnn"],  // Verdict.primary_indicators (#23)
  "citations": ["NICE-NG195-1.3.2", "AAP-COFN-preterm-4"],   // Verdict.citations (#23)
  "assessments": [                   // Verdict.assessments — the full trail, one per tier that ran
    { "source": "deviation", "level": "RED",    "risk": 0.94, "confidence": 1.0,  "rationale": "..." },
    { "source": "temporal",  "level": "YELLOW", "risk": 1.0,  "confidence": 0.9,  "rationale": "..." },
    { "source": "rag",       "level": "RED",    "risk": 0.94, "confidence": 0.86, "rationale": "..." }
  ],
  "rationale": "..."                 // Verdict.rationale (the headline tier's) — the "how reached" trail text
}
```

- `citations` are the guideline ids; they join to the `tier3.retrieved[].id` entries so the UI's
  click-to-expand citation snippets resolve against the same objects.
- `escalated_by` + `safety_floor` drive the prototype's "how this verdict was reached" trail and
  the persistent Safety Floor track (the floor fills red across every downstream tier).

---

## Honesty ledger

Three places the #29 prototype asks for more than the current backend honestly produces. Each has a
**default** (chosen to keep the codebase's standing honesty guardrail — never present the fabricated
as recorded) and is an **override point** for the human running the map.

| # | Tension | Default in this contract | Override (and its cost) |
|---|---------|--------------------------|-------------------------|
| **H1** | Prototype draws 8 bedside channels (SpO₂, BP, perfusion, skin temp, pulse pressure); we record only RR-interval + respiration/apnea. | Emit only `real: true` channels (`heart_rate`, `rr_interval`, `respiration`, `apnea_events`); any extra channel MUST carry `real: false` + a visible "simulated" marker. | Add synthetic channels for visual density — allowed only if flagged `real:false` in the trace and marked in the UI. Passing them as recorded is ruled out. |
| **H2** | Prototype shows a 5-step reasoning chain + per-step self-checks; the graph emits one reasoning string + one self-check bool. | Carry the single `reasoning` + single `self_check`, plus the real `query` + `retrieved` passages. UI may stage them as retrieve/reason/self-check (real nodes) but not fabricate 5 steps. | Extend the graph to emit structured `reasoning_steps`; then add that array to §5. This is backend work, not a contract fiction. |
| **H3** | Prototype wants plain-English per-tier verdict text "from the code." | Each tier's `verdict_text` **is** that tier's `Assessment.rationale` (Tier 1/2) / `clinical_reasoning` (Tier 3), emitted by the pipeline and rendered verbatim — never authored in the frontend. | None needed — this one resolves cleanly to a real field; recorded here so #31/#32 don't re-litigate it. |

---

## What this unblocks

- **#31 (recording script → `trace.json`)** — the recorder's output shape is now fixed. Its job:
  pick the real `infant7` window range, replay it through `DeviationAssessor` (per-window),
  `TemporalAssessor` (capturing `c_plus` each step), and the RAG graph (once, at the decision
  window), and serialize to this schema. The three Ledger defaults are its honesty contract.
- **#32 (build the trace view)** — the UI's input shape is now fixed. It reads this file and renders
  the prototype-v3 layout: shared timeline scrubber over §1, per-channel Data In cards from §2,
  collapsible Tier 1 feature groups from §3, the CUSUM chart + gate table from §4, the reasoning
  block from §5, and the consolidated Verdict card + Safety Floor track from §6.

Both sides validate against this document; a mismatch is a contract bug, fixed here first.
