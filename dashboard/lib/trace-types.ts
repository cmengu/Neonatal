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
}
