export type ConcernLevel = "RED" | "YELLOW" | "GREEN";

export type ClinicalLabel = "CRITICAL" | "WATCH" | "STABLE";

export const CONCERN_TO_LABEL: Record<ConcernLevel, ClinicalLabel> = {
  RED: "CRITICAL",
  YELLOW: "WATCH",
  GREEN: "STABLE",
};

/** Mirrors NeonatalAlert in src/agent/schemas.py. timestamp is ISO string from JSON. */
export interface NeonatalAlert {
  patient_id: string;
  timestamp: string;
  concern_level: ConcernLevel;
  risk_score: number;
  primary_indicators: string[];
  clinical_reasoning: string;
  recommended_action: string;
  confidence: number;
  retrieved_context: string[];
  self_check_passed: boolean;
  protocol_compliant: boolean;
  past_similar_events: number;
  latency_ms: number | null;
  /** Present on live API after schema update; omit on older backends. */
  z_scores?: Record<string, number>;
}

/** Mirrors api/main.py patient_history SELECT columns. */
export interface HistoryEntry {
  timestamp: string;
  concern_level: ConcernLevel;
  risk_score: number;
  top_feature: string | null;
  top_z_score: number | null;
  signal_pattern: string | null;
  brady_classification: string | null;
  agent_version: string | null;
}

/** Keys match HRV_FEATURE_COLS in src/features/constants.py. */
export const HRV_LABEL: Record<string, string> = {
  mean_rr: "Mean RR",
  sdnn: "SDNN",
  rmssd: "RMSSD",
  pnn50: "pNN50",
  lf_hf_ratio: "LF/HF Ratio",
  rr_ms_min: "RR Min",
  rr_ms_max: "RR Max",
  "rr_ms_25%": "RR p25",
  "rr_ms_50%": "RR p50",
  "rr_ms_75%": "RR p75",
};
