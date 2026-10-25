/**
 * A contract-valid mock trace for infant7, standing in for the recorder (#31)
 * until it lands. Shaped exactly to docs/design/trace-telemetry-contract.md so
 * the view is built against the real seam, not an ad-hoc shape.
 *
 * Honesty (Ledger H1): only heart_rate / rr_interval / respiration / apnea_events
 * carry real: true. The extra bedside channels the prototype drew are kept for
 * visual density but flagged real: false so the UI marks them "simulated".
 */

import { Trace, WorldModel } from "./trace-types";
// Real JEPA world-model block (#60), exported by scripts/export_jepa_trace.py from the
// trained checkpoint on infant7 [1240,1419]. The one part of this fixture that is NOT
// synthesised — real embeddings, real novelty/surprise, on the shared grid.
import worldModelInfant7 from "./world-model-infant7.json";

const N = 180;
const ONSET = 90;
const SUSTAINED = 135;

function smoothstep(x: number): number {
  if (x <= 0) return 0;
  if (x >= 1) return 1;
  return x * x * (3 - 2 * x);
}

// Deterministic pseudo-noise — no Date.now()/Math.random(), stable across renders.
function noise(i: number, seed: number): number {
  const x = Math.sin(i * 12.9898 + seed * 78.233) * 43758.5453;
  return (x - Math.floor(x) - 0.5) * 2;
}

interface SeriesSpec {
  base: number;
  dev: number;
  drift?: number;
  noise?: number;
  seed: number;
}

function series(o: SeriesSpec): number[] {
  const pts: number[] = [];
  for (let i = 0; i < N; i++) {
    let v: number;
    if (i < ONSET) v = o.base;
    else if (i < SUSTAINED)
      v = o.base + (o.dev - o.base) * smoothstep((i - ONSET) / (SUSTAINED - ONSET));
    else v = o.dev + (o.drift ?? 0) * (i - SUSTAINED);
    v += noise(i, o.seed) * (o.noise ?? 0);
    pts.push(Math.round(v * 100) / 100);
  }
  return pts;
}

function bandExit(pts: number[], low: number, high: number): number | null {
  for (let i = 0; i < pts.length; i++) {
    if (pts[i] < low || pts[i] > high) return i;
  }
  return null;
}

// z from a value series given a personal baseline.
function zSeries(values: number[], mean: number, std: number): number[] {
  return values.map((v) => Math.round(((v - mean) / std) * 100) / 100);
}

function firstZCross(z: number[], trigger: number, direction: "low" | "high"): number | null {
  for (let i = 0; i < z.length; i++) {
    if (direction === "low" ? z[i] <= -trigger : z[i] >= trigger) return i;
  }
  return null;
}

const clock = (i: number): string => {
  const mins = Math.round((i / (N - 1)) * 360); // window spans 6h for the demo
  const hh = Math.floor(mins / 60);
  const mm = mins % 60;
  return `${hh < 10 ? "0" : ""}${hh}:${mm < 10 ? "0" : ""}${mm}`;
};

const labels = Array.from({ length: N }, (_, i) => clock(i));

// ---- Data In: 4 real + 4 simulated (Ledger H1) ----
function channel(
  key: string,
  label: string,
  unit: string,
  real: boolean,
  spec: SeriesSpec,
  low: number,
  high: number,
) {
  const samples = series(spec);
  const band_exit_idx = bandExit(samples, low, high);
  return {
    key,
    label,
    unit,
    real,
    samples,
    band: { low, high },
    band_exit_idx,
    flagged: band_exit_idx !== null,
  };
}

const dataChannels = [
  channel("heart_rate", "Heart rate", "bpm", true, { base: 148, dev: 116, noise: 2.2, seed: 1 }, 120, 170),
  channel("rr_interval", "RR interval", "ms", true, { base: 405, dev: 508, noise: 4, seed: 6 }, 350, 470),
  channel("respiration", "Respiration rate", "/min", true, { base: 46, dev: 66, noise: 2, seed: 2 }, 30, 60),
  channel("apnea_events", "Apnea events", "count", true, { base: 0, dev: 4, noise: 0.3, seed: 9 }, -1, 1),
  channel("spo2", "SpO₂", "%", false, { base: 96, dev: 87, noise: 0.9, seed: 3 }, 90, 100),
  channel("perfusion_index", "Perfusion index", "%", false, { base: 1.7, dev: 0.7, noise: 0.08, seed: 4 }, 1.0, 3.0),
  channel("mean_bp", "Mean art. BP", "mmHg", false, { base: 43, dev: 33, noise: 1.1, seed: 5 }, 35, 55),
  channel("skin_temp", "Skin temp", "°C", false, { base: 36.7, dev: 36.9, noise: 0.08, seed: 7 }, 36.0, 37.5),
];

// ---- Tier 1: 12 HRV features; 5 can trigger, 7 display-only ----
interface T1Spec {
  key: string;
  label: string;
  direction: "low" | "high" | null;
  base: number;
  dev: number;
  mean: number;
  std: number;
  noise: number;
  seed: number;
}

function t1Feature(s: T1Spec) {
  const value_series = series({ base: s.base, dev: s.dev, noise: s.noise, seed: s.seed });
  const z_series = zSeries(value_series, s.mean, s.std);
  const trigger_feature = s.direction !== null;
  const z_trigger = 2.0;
  const failure_idx = trigger_feature
    ? firstZCross(z_series, z_trigger, s.direction as "low" | "high")
    : null;
  return {
    key: s.key,
    label: s.label,
    direction: s.direction,
    trigger_feature,
    z_series,
    value_series,
    baseline: { mean: s.mean, std: s.std },
    z_trigger,
    failure_idx,
    flagged: failure_idx !== null,
  };
}

const t1Features = [
  // 5 trigger-capable (DEFAULT_DIRECTIONS)
  t1Feature({ key: "sdnn", label: "SDNN", direction: "low", base: 15.5, dev: 7.5, mean: 15.5, std: 2.7, noise: 0.6, seed: 12 }),
  t1Feature({ key: "rmssd", label: "RMSSD", direction: "low", base: 12.5, dev: 6.5, mean: 12.5, std: 1.8, noise: 0.5, seed: 11 }),
  t1Feature({ key: "sample_asymmetry", label: "Sample asymmetry", direction: "high", base: 0.9, dev: 1.7, mean: 0.9, std: 0.22, noise: 0.03, seed: 19 }),
  t1Feature({ key: "sampen", label: "Sample entropy", direction: "low", base: 1.15, dev: 1.02, mean: 1.15, std: 0.12, noise: 0.02, seed: 18 }),
  t1Feature({ key: "mean_rr", label: "Mean RR", direction: "low", base: 415, dev: 402, mean: 415, std: 22, noise: 4, seed: 14 }),
  // 7 display-only (direction: null)
  t1Feature({ key: "pnn50", label: "pNN50", direction: null, base: 9.0, dev: 7.8, mean: 9.0, std: 2.4, noise: 0.5, seed: 13 }),
  t1Feature({ key: "lf_hf_ratio", label: "LF/HF ratio", direction: null, base: 1.3, dev: 1.42, mean: 1.3, std: 0.35, noise: 0.06, seed: 17 }),
  t1Feature({ key: "rr_ms_min", label: "RR min", direction: null, base: 360, dev: 372, mean: 360, std: 30, noise: 5, seed: 21 }),
  t1Feature({ key: "rr_ms_max", label: "RR max", direction: null, base: 470, dev: 462, mean: 470, std: 34, noise: 6, seed: 22 }),
  t1Feature({ key: "rr_ms_25%", label: "RR p25", direction: null, base: 388, dev: 396, mean: 388, std: 25, noise: 4, seed: 23 }),
  t1Feature({ key: "rr_ms_50%", label: "RR p50", direction: null, base: 410, dev: 418, mean: 410, std: 26, noise: 4, seed: 24 }),
  t1Feature({ key: "rr_ms_75%", label: "RR p75", direction: null, base: 436, dev: 444, mean: 436, std: 28, noise: 5, seed: 25 }),
];

const concordant = t1Features.filter((f) => f.trigger_feature && f.flagged).length;

// ---- Tier 2: CUSUM ----
const cPlus: number[] = (() => {
  const pts: number[] = [];
  let v = 0;
  for (let i = 0; i < N; i++) {
    const inc = i < ONSET ? (noise(i, 21) - 0.1) * 0.03 : (i - ONSET) * 0.01 + 0.02;
    v = Math.max(0, v + inc);
    pts.push(Math.round(v * 100) / 100);
  }
  return pts;
})();
const H = 5.0;
const crossingIdx = cPlus.findIndex((v) => v >= H);

export const MOCK_TRACE_INFANT7: Trace = {
  schema_version: "1.1.0",
  patient_id: "infant7",
  generated_at: "2026-07-15T04:12:00Z",
  source_commit: "mock-fixture",
  time_grid: {
    n: N,
    unit: "window",
    step_seconds: 30,
    labels,
    phases: {
      normal: [0, ONSET - 1],
      onset: [ONSET, SUSTAINED - 1],
      sustained: [SUSTAINED, N - 1],
    },
  },
  data_in: { channels: dataChannels },
  tier1: {
    features: t1Features,
    floor: {
      level: "RED",
      concordant_count: concordant,
      soft_floor: false,
      kind: "HARD",
    },
    indicators: ["sample_asymmetry", "sdnn"],
    verdict_text:
      "Deterministic deviation floor (RED): " +
      concordant +
      " HRV features deviating together beyond their personal thresholds — sample asymmetry rising while SDNN, RMSSD and sample entropy fall. Concordant deviation sets a HARD RED floor no later tier can quiet.",
  },
  tier2: {
    c_plus_series: cPlus,
    h: H,
    k: 0.5,
    crossing_idx: crossingIdx < 0 ? null : crossingIdx,
    fired: crossingIdx >= 0,
    level: "YELLOW",
    quiet: {
      may_quiet: false,
      gates: [
        { key: "warmup", label: "Warmed up (≥20 windows)", pass: true, detail: "n_updates=141 ≥ 20" },
        { key: "low_drift", label: "No building trend (C⁺ < 0.25·h)", pass: false, detail: "prior C⁺=4.8 ≥ 1.25" },
        { key: "guard", label: "Not recently alarmed (≥20 w)", pass: true, detail: "no prior signal" },
      ],
      soft_floor_target: false,
      note: "Tier 2 may only quiet a SOFT single-feature YELLOW — never the HARD RED floor.",
    },
    verdict_text:
      "CUSUM Drift (YELLOW): C⁺ crossed the decision interval h=5 after a sustained one-directional trend — the deviation is a real drift, not a transient artifact. The low-drift quiet gate fails, so this cannot quiet even a soft floor.",
  },
  tier3: {
    ran: true,
    query:
      "Personalised HRV deviations: sample_asymmetry high (z≈+3.1), sdnn low (z≈-3.0), with apnea–bradycardia coupling in a 28-week preterm infant — early sepsis risk?",
    retrieved: [
      {
        id: "NICE-NG195-1.3.2",
        source: "NICE NG195",
        snippet:
          "In babies with red-flag risk factors or clinical indicators of possible sepsis, investigate and consider empirical antibiotics.",
      },
      {
        id: "AAP-COFN-preterm-4",
        source: "AAP/COFN 2018",
        snippet:
          "Apnea, bradycardia and poor perfusion can precede confirmed infection in preterm infants.",
      },
      {
        id: "HeRO-HRC-index",
        source: "HeRO / HRC",
        snippet:
          "Reduced heart-rate variability with transient decelerations raises the HRC index, a validated adjunct that can precede clinical sepsis.",
      },
    ],
    reasoning:
      "Reduced beat-to-beat variability (low SDNN, RMSSD, sample entropy) with a rising sample-asymmetry burden and coupled apnea–bradycardia matches the abnormal heart-rate-characteristics pattern that can precede clinical sepsis by hours in a 28-week preterm infant. Interpreted as a decision-support adjunct — culture remains the reference standard.",
    self_check: {
      passed: true,
      note: "Cited actions match retrieved guideline scope; no over-reach flagged; concurs with the Tier 1 RED floor rather than overriding it.",
    },
    concern_level: "RED",
    confidence: 0.86,
    recommended_action: "Immediate clinical review — consider sepsis workup (blood culture, CBC, CRP).",
    primary_indicators: ["sample_asymmetry", "sdnn"],
    escalate_only_note: "Tier 3 may raise concern above the floor but never lower it.",
  },
  verdict: {
    patient_id: "infant7",
    level: "RED",
    risk: 0.94,
    confidence: 0.86,
    safety_floor: "RED",
    escalated_by: ["deviation"],
    recommended_action: "Immediate clinical review — consider sepsis workup (blood culture, CBC, CRP).",
    primary_indicators: ["sample_asymmetry", "sdnn"],
    citations: ["NICE-NG195-1.3.2", "AAP-COFN-preterm-4", "HeRO-HRC-index"],
    assessments: [
      { source: "deviation", level: "RED", risk: 0.94, confidence: 1.0, rationale: "HARD RED floor: concordant HRV deviation." },
      { source: "temporal", level: "YELLOW", risk: 1.0, confidence: 0.9, rationale: "CUSUM Drift confirmed; quiet gate fails." },
      { source: "rag", level: "RED", risk: 0.94, confidence: 0.86, rationale: "Guidelines concur; recommends sepsis workup." },
    ],
    rationale:
      "HARD RED floor set by concordant HRV deviation, confirmed as a sustained drift by CUSUM and grounded against sepsis guidelines by the reasoning tier. Escalated by the deviation tier; the floor holds RED through every downstream tier.",
  },
  // The real spine (decision 4): actual JEPA embeddings on the shared grid, not synthesised.
  world_model: worldModelInfant7 as unknown as WorldModel,
};
