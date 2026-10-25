/**
 * TypeScript mirror of the trace telemetry contract —
 * docs/design/trace-telemetry-contract.md (#30). The recorder (#31) emits a
 * trace.json validating against this; this view consumes it and never invents
 * a field the recorder didn't write.
 */

import { ConcernLevel } from "./types";

/** §1 — the one axis every replayable series is sampled on. */
export interface TimeGrid {
  n: number;
  unit: "window" | "second";
  step_seconds: number;
  labels: string[];
  phases: {
    normal: [number, number] | null;
    onset: [number, number] | null;
    sustained: [number, number] | null;
  };
}

/** §2 — one raw bedside stream. `real: false` MUST render a "simulated" marker (Ledger H1). */
export interface DataChannel {
  key: string;
  label: string;
  unit: string;
  real: boolean;
  samples: number[];
  band: { low: number; high: number };
  band_exit_idx: number | null;
  flagged: boolean;
}

export interface DataIn {
  channels: DataChannel[];
}

/** §3 — one deviation feature, replayed window-by-window. */
export interface Tier1Feature {
  key: string;
  label: string;
  direction: "low" | "high" | null;
  trigger_feature: boolean;
  z_series: number[];
  value_series: number[];
  baseline: { mean: number; std: number };
  z_trigger: number;
  failure_idx: number | null;
  flagged: boolean;
}

export type FloorKind = "HARD" | "SOFT" | "NONE";

export interface Tier1 {
  features: Tier1Feature[];
  floor: {
    level: ConcernLevel;
    concordant_count: number;
    soft_floor: boolean;
    kind: FloorKind;
  };
  indicators: string[];
  verdict_text: string;
}

/** §4 — CUSUM trajectory + quiet gates. */
export interface QuietGate {
  key: string;
  label: string;
  pass: boolean;
  detail: string;
}

export interface Tier2 {
  c_plus_series: number[];
  h: number;
  k: number;
  crossing_idx: number | null;
  fired: boolean;
  level: ConcernLevel;
  quiet: {
    may_quiet: boolean;
    gates: QuietGate[];
    soft_floor_target: boolean;
    note: string;
  };
  verdict_text: string;
}

/** §5 — RAG tier. Short-circuit honesty: skipped ⇒ { ran: false } only. */
export interface RetrievedPassage {
  id: string;
  source: string;
  snippet: string;
}

export interface Tier3Ran {
  ran: true;
  query: string;
  retrieved: RetrievedPassage[];
  reasoning: string;
  self_check: { passed: boolean; note: string };
  concern_level: ConcernLevel;
  confidence: number;
  recommended_action: string;
  primary_indicators: string[];
  escalate_only_note: string;
}

export type Tier3 = Tier3Ran | { ran: false };

/** §6 — the merged Verdict + its trail (post-#23 shape). */
export interface TraceAssessment {
  source: string;
  level: ConcernLevel;
  risk: number;
  confidence: number;
  rationale: string;
}

export interface TraceVerdict {
  patient_id: string;
  level: ConcernLevel;
  risk: number;
  confidence: number;
  safety_floor: ConcernLevel;
  escalated_by: string[];
  recommended_action: string;
  primary_indicators: string[];
  citations: string[];
  assessments: TraceAssessment[];
  rationale: string;
}

/**
 * §7 — the JEPA world-model trajectory (#60). REAL target-encoder embeddings for the
 * recorded window, on the shared time grid, produced by `scripts/export_jepa_trace.py`
 * from the trained checkpoint (never hand-authored). Optional: recorder traces predating
 * #60 omit it; the demo's 3-D embedding hero (#62) requires it.
 *
 * Honesty (Ledger H1 / spec §7): `pca.fitted_on: "normal"` — the 3-D axes are fitted on the
 * *normal phase only*, not the departure. The 3-D position drift is modest (`pca_visible_sep`,
 * the departure is diffuse across embedding dims); the **novelty** (full-D Mahalanobis, unit =
 * calm-SD) is what leaves the cloud and should drive the warp magnitude. No accuracy number.
 */
export interface WorldModelPoint {
  idx: number; // shared-grid window index [0, n)
  pca3: [number, number, number]; // embedding projected onto the 3 normal-phase PCs
  novelty: number; // Mahalanobis distance from the learned-normal cloud
  surprise: number; // horizon-aggregated prediction error, z-scored to calm
}

export interface WorldModel {
  real: boolean;
  infant: string;
  window: [number, number]; // absolute recorded-window span [w0, w1]
  embed_dim: number;
  pca: {
    fitted_on: "normal";
    variance_explained: [number, number, number];
    axis_labels: [string, string, string];
  };
  trajectory: WorldModelPoint[]; // length n — one point per grid window
  normal_cloud: [number, number, number][]; // calm embeddings in the PCA basis (the cluster)
  novelty_baseline_p95: number; // calm-cloud edge (95th pct) — the warp's "normal" radius
  surprise: { series: number[]; calm_mean: number; calm_std: number };
  sep_rise_calm_sd: number; // novelty rise across the window, in calm-SD (honest headline)
  pca_visible_sep: number; // 3-D drift in cloud-spread units (how much the eye sees in 3-D)
  caption: string; // exactly what the axes are — painted on the panel
}

/** Top-level trace.json. */
export interface Trace {
  schema_version: string;
  patient_id: string;
  generated_at: string;
  source_commit: string;
  time_grid: TimeGrid;
  data_in: DataIn;
  tier1: Tier1;
  tier2: Tier2;
  tier3: Tier3;
  verdict: TraceVerdict;
  world_model?: WorldModel; // §7 (#60) — additive; absent on pre-#60 recorder traces
}
