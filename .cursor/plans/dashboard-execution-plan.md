# NeonatalGuard Dashboard — Execution Plan

**Overall Progress:** `100% (7/7 steps complete) — Pre-implemented before plan was written. All steps verified against actual codebase on 2026-03-24.`

> **v2 — post pre-check.** All 5 critical flaws and 3 logic warnings from the pre-check pass resolved. See Decisions Log below.

---

## TLDR

Build a Next.js 14 NICU ward dashboard inside `dashboard/` at the repo root. The dashboard shows 10 bed cards in a dark clinical grid — most grey (GREEN/STABLE), some amber (YELLOW/WATCH), one pulsing red (RED/CRITICAL). Clicking a card opens a right-side drawer with clinical reasoning, recommended action, and alert history. Data starts from seeded mock data; a single env var (`NEXT_PUBLIC_USE_REAL_API=true`) switches the API client to hit the live FastAPI backend at `localhost:8000`. Auto-refreshes every 90 seconds with a visible countdown.

---

## Critical Decisions

- **Decision 1: Dark clinical theme** — NICU screens operate in dimmed rooms. Slate-900 background matches bedside monitoring equipment conventions (Philips IntelliVue).
- **Decision 2: Clinical labels (STABLE / WATCH / CRITICAL), not pipeline literals** — "RED / YELLOW / GREEN" are internal identifiers. Clinical staff expect severity language. Mapping lives once in `lib/types.ts`.
- **Decision 3: Mock/real toggle via build-time env var** — `NEXT_PUBLIC_USE_REAL_API` is inlined at build time. No runtime branching in production.
- **Decision 4: Polling over SSE for ward overview** — SSE endpoint is per-patient and designed for single-patient use. Polling 10 patients in parallel every 90s is simpler.
- **Decision 5: 90-second refresh** — Neonatal sepsis progresses in 2–4 hours. 90s gives ~80–160 data points before clinical action is required.

---

## Decisions Log (pre-check resolutions)

| # | Flaw | Resolution applied |
|---|---|---|
| F1 | Placeholder `/path/to/repo` paths | Replaced with `/Users/ngchenmeng/Neonatal` throughout |
| F2 | `HRV_LABEL` keys didn't match `HRV_FEATURE_COLS` | Keys now match `src/features/constants.py` exactly |
| F3 | Unused `const now` in `mock-data.ts` would fail `tsc` | `const now` removed |
| F4 | Drawer click bubbled through to backdrop, closing on any interaction | `onClick={(e) => e.stopPropagation()}` added to `<aside>` |
| F5 | Subtask said "6 GREEN" but mock has 7 GREEN, agent would corrupt data | Subtask corrected to "7 GREEN, 2 YELLOW, 1 RED = 10 total" |
| W1 | `layout.tsx` not updated — `h-screen` layout would break without `h-full` on body | Step 1 adds `layout.tsx` update |
| W2 | `curl` smoke test unreliable for client-rendered Next.js | Replaced with `npm run build` + browser open instruction |
| W3 | `WardGrid.tsx` received function prop without `"use client"` | `"use client"` added to `WardGrid.tsx` |

---

## Agent Failure Protocol

1. A verification command fails → read the full error output.
2. Cause is unambiguous → make ONE targeted fix → re-run the same verification command.
3. If still failing after one fix → **STOP**. Output the full current contents of every file modified in this step. Report: (a) command run, (b) full error verbatim, (c) fix attempted, (d) current state of each modified file, (e) why you cannot proceed.
4. Never attempt a second fix without human instruction.
5. Never modify files not named in the current step.

---

## Clarification Gate

All unknowns resolved. No human gate required before Step 1.

| Unknown | Required | Source | Blocking | Resolved |
|---------|----------|--------|----------|----------|
| Frontend stack | Next.js 14, TypeScript, Tailwind | Human | All | ✅ |
| Patient IDs | infant1–infant10 | Codebase | Step 2 | ✅ |
| HRV feature names | `HRV_FEATURE_COLS` from `src/features/constants.py` | Codebase | Step 2 | ✅ |
| Refresh interval | 90 seconds | Human | Step 5 | ✅ |
| Colour system | Slate-900 bg, severity card borders | Human | Step 3 | ✅ |
| API base URL | `http://localhost:8000` | `api/main.py` | Step 2 | ✅ |

---

## Pre-Flight — Run Before Any Code Changes

```bash
# 1. Confirm dashboard/ does not yet exist
ls /Users/ngchenmeng/Neonatal/dashboard 2>/dev/null \
  && echo "EXISTS — stop and investigate" \
  || echo "NOT FOUND — safe to proceed"

# 2. Confirm Node >= 18
node --version

# 3. Confirm npm available
npm --version

# 4. Confirm HRV feature names (used in Step 2 HRV_LABEL)
grep -A 15 "HRV_FEATURE_COLS" /Users/ngchenmeng/Neonatal/src/features/constants.py

# 5. Record backend test baseline
cd /Users/ngchenmeng/Neonatal && python -m pytest tests/ -q 2>/dev/null | tail -1
```

**Baseline Snapshot (agent fills during pre-flight):**
```
Node version:             ____
npm version:              ____
dashboard/ exists:        NOT FOUND
HRV_FEATURE_COLS:         [mean_rr, sdnn, rmssd, pnn50, lf_hf_ratio, rr_ms_min, rr_ms_max, rr_ms_25%, rr_ms_50%, rr_ms_75%]
Backend test count:       ____
```

**Checks (all must pass before Step 1):**
- [ ] `dashboard/` does not exist
- [ ] Node >= 18
- [ ] npm available
- [ ] `HRV_FEATURE_COLS` output matches the 10 keys above

---

## Steps Analysis

```
Step 1 (Scaffold)             — Non-critical — verification only — Idempotent: No
Step 2 (Types + data + client) — Critical     — full code review  — Idempotent: Yes
Step 3 (BedCard + Badge)      — Non-critical — verification only — Idempotent: Yes
Step 4 (WardGrid + StatusBar) — Non-critical — verification only — Idempotent: Yes
Step 5 (useWardData hook)     — Critical     — full code review  — Idempotent: Yes
Step 6 (Drawer + History)     — Non-critical — verification only — Idempotent: Yes
Step 7 (Wire page.tsx + test) — Non-critical — verification only — Idempotent: Yes
```

---

## Tasks

### Phase 1 — Project Scaffold + Data Layer

**Goal:** `dashboard/` exists, `npm run build` passes, TypeScript types + mock data + API client are in place.

---

- [x] 🟩 **Step 1: Scaffold Next.js 14 project** — *Non-critical: creates new isolated directory, no existing code touched*

  **Idempotent:** No — `create-next-app` fails if directory exists. Pre-flight confirms it does not.

  **Context:** Creates the bare Next.js 14 App Router project with TypeScript and Tailwind, then makes four targeted replacements: `tailwind.config.ts` (adds `pulse-ring` keyframe), `globals.css` (slate-900 base), `app/layout.tsx` (adds `h-full` to body — required for `h-screen` ward layout), `app/page.tsx` (removes default boilerplate).

  ```bash
  cd /Users/ngchenmeng/Neonatal
  npx create-next-app@14 dashboard \
    --typescript \
    --tailwind \
    --eslint \
    --app \
    --no-src-dir \
    --import-alias "@/*"
  ```

  **After scaffold, confirm the file exists before replacing it:**
  ```bash
  ls dashboard/tailwind.config.ts && echo "OK" || ls dashboard/tailwind.config.js
  ```
  If the file is `tailwind.config.js` (not `.ts`), replace that file instead and update the extension reference in this step.

  **File: `dashboard/tailwind.config.ts`** — replace entire file:
  ```typescript
  import type { Config } from "tailwindcss";

  const config: Config = {
    content: [
      "./app/**/*.{ts,tsx}",
      "./components/**/*.{ts,tsx}",
      "./hooks/**/*.{ts,tsx}",
      "./lib/**/*.{ts,tsx}",
    ],
    theme: {
      extend: {
        animation: {
          "pulse-ring": "pulse-ring 1.8s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        },
        keyframes: {
          "pulse-ring": {
            "0%, 100%": { boxShadow: "0 0 0 0 rgba(220, 38, 38, 0.7)" },
            "50%": { boxShadow: "0 0 0 10px rgba(220, 38, 38, 0)" },
          },
        },
      },
    },
    plugins: [],
  };

  export default config;
  ```

  **File: `dashboard/app/globals.css`** — replace entire file:
  ```css
  @tailwind base;
  @tailwind components;
  @tailwind utilities;

  html,
  body {
    height: 100%;
    background-color: rgb(15 23 42); /* slate-900 */
    color: rgb(241 245 249); /* slate-100 */
  }
  ```

  **File: `dashboard/app/layout.tsx`** — replace entire file:
  ```typescript
  import type { Metadata } from "next";
  import "./globals.css";

  export const metadata: Metadata = {
    title: "NeonatalGuard",
    description: "NICU early-warning dashboard",
  };

  export default function RootLayout({
    children,
  }: {
    children: React.ReactNode;
  }) {
    return (
      <html lang="en" className="h-full">
        <body className="h-full bg-slate-900 text-slate-100">{children}</body>
      </html>
    );
  }
  ```

  **File: `dashboard/app/page.tsx`** — replace entire file with empty shell:
  ```typescript
  export default function Home() {
    return <main className="min-h-screen bg-slate-900" />;
  }
  ```

  **Git Checkpoint:**
  ```bash
  git add dashboard/
  git commit -m "step 1: scaffold Next.js 14 dashboard with Tailwind pulse-ring and h-full layout"
  ```

  **Subtasks:**
  - [x] 🟩 `create-next-app` runs without error
  - [x] 🟩 `tailwind.config.ts` (or `.js`) updated with `pulse-ring` keyframe
  - [x] 🟩 `globals.css` sets `height: 100%` on `html, body`
  - [x] 🟩 `layout.tsx` sets `className="h-full"` on both `<html>` and `<body>`
  - [x] 🟩 `page.tsx` emptied of default boilerplate

  **✓ Verification Test:**

  **Type:** Integration

  **Action:**
  ```bash
  cd /Users/ngchenmeng/Neonatal/dashboard && npm run build 2>&1 | tail -8
  ```

  **Expected:** Exits 0. Output contains `Route (app)` table or `✓ Compiled`. No `Type error` or `error TS` lines.

  **Pass:** Exit code 0, no error lines.

  **Fail:**
  - `Module not found: tailwindcss` → scaffold didn't install deps → run `npm install`
  - `Type error` in `layout.tsx` → `React` not imported — add `import React from "react"` if needed, or confirm `tsconfig.json` has `"jsx": "preserve"`
  - `tailwind.config.ts not found` → scaffold created `.js` not `.ts` → rename file, update content accordingly

---

- [x] 🟩 **Step 2: Types + mock data + API client** — *Critical: defines the data contract consumed by every component and hook*

  **Idempotent:** Yes — creates new files in `lib/`, no existing files modified.

  **Context:** Three files form the complete data layer. `types.ts` mirrors `NeonatalAlert` from `src/agent/schemas.py` and `HistoryEntry` from `api/main.py`'s history query columns. `mock-data.ts` seeds 10 patients (7 GREEN, 2 YELLOW, 1 RED). `api-client.ts` toggles between mock and real via `NEXT_PUBLIC_USE_REAL_API`.

  **Pre-Read Gate:**
  Before writing any file, run all three and confirm output:
  ```bash
  # Confirm NeonatalAlert field names
  grep -n "concern_level\|patient_id\|primary_indicators\|risk_score\|retrieved_context\|self_check_passed\|protocol_compliant\|past_similar_events\|latency_ms" \
    /Users/ngchenmeng/Neonatal/src/agent/schemas.py

  # Confirm history query column order
  grep -A 15 "SELECT timestamp" /Users/ngchenmeng/Neonatal/api/main.py

  # Confirm exact HRV feature column names
  grep -A 15 "HRV_FEATURE_COLS" /Users/ngchenmeng/Neonatal/src/features/constants.py
  ```
  All three must match the code written below. If any field name differs from `schemas.py` output → STOP and report.

  **File: `dashboard/lib/types.ts`**
  ```typescript
  export type ConcernLevel = "RED" | "YELLOW" | "GREEN";

  export type ClinicalLabel = "CRITICAL" | "WATCH" | "STABLE";

  export const CONCERN_TO_LABEL: Record<ConcernLevel, ClinicalLabel> = {
    RED: "CRITICAL",
    YELLOW: "WATCH",
    GREEN: "STABLE",
  };

  // Mirrors NeonatalAlert in src/agent/schemas.py exactly.
  // timestamp is string (ISO) because JSON serialisation converts datetime.
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
  }

  // Mirrors columns from api/main.py patient_history SELECT query.
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

  // Keys are the exact values from HRV_FEATURE_COLS in src/features/constants.py.
  // rr_ms_25%, rr_ms_50%, rr_ms_75% contain % — fallback to raw key if not in map.
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
  ```

  **File: `dashboard/lib/mock-data.ts`**
  ```typescript
  import { NeonatalAlert, HistoryEntry } from "./types";

  const minsAgo = (m: number): string =>
    new Date(Date.now() - m * 60_000).toISOString();

  // Distribution: 1 RED, 2 YELLOW, 7 GREEN = 10 total
  export const MOCK_ALERTS: NeonatalAlert[] = [
    // RED (1)
    {
      patient_id: "infant1",
      timestamp: minsAgo(3),
      concern_level: "RED",
      risk_score: 0.84,
      primary_indicators: ["rmssd", "lf_hf_ratio", "pnn50"],
      clinical_reasoning:
        "Marked suppression of RMSSD (z=-3.2) and pNN50 (z=-2.9) combined with elevated LF/HF ratio (z=+2.8) is consistent with autonomic withdrawal preceding neonatal sepsis. Three bradycardia events in the last 6 hours reinforce the pre-sepsis HRV signature. Risk score 0.84 exceeds the RED threshold.",
      recommended_action: "Immediate clinical review",
      confidence: 0.91,
      retrieved_context: [],
      self_check_passed: true,
      protocol_compliant: true,
      past_similar_events: 2,
      latency_ms: 420,
    },
    // YELLOW (2)
    {
      patient_id: "infant2",
      timestamp: minsAgo(7),
      concern_level: "YELLOW",
      risk_score: 0.58,
      primary_indicators: ["lf_hf_ratio", "rmssd"],
      clinical_reasoning:
        "Moderate LF/HF elevation (z=+2.1) with mild RMSSD suppression (z=-1.6). Pattern is indeterminate — consistent with either early autonomic stress or normal sleep-state variation in a preterm neonate. No bradycardia events in the last 6 hours.",
      recommended_action: "Reassess in 2 hours",
      confidence: 0.72,
      retrieved_context: [],
      self_check_passed: true,
      protocol_compliant: true,
      past_similar_events: 1,
      latency_ms: 388,
    },
    {
      patient_id: "infant3",
      timestamp: minsAgo(12),
      concern_level: "YELLOW",
      risk_score: 0.47,
      primary_indicators: ["sdnn", "rmssd"],
      clinical_reasoning:
        "SDNN mildly reduced (z=-1.4) alongside borderline RMSSD suppression (z=-1.2). Isolated finding with no bradycardia. Consistent with feed-related HRV suppression but warrants monitoring given gestational age.",
      recommended_action: "Increase monitoring frequency to every 15 minutes",
      confidence: 0.68,
      retrieved_context: [],
      self_check_passed: true,
      protocol_compliant: true,
      past_similar_events: 0,
      latency_ms: 301,
    },
    // GREEN (7)
    {
      patient_id: "infant4",
      timestamp: minsAgo(4),
      concern_level: "GREEN",
      risk_score: 0.18,
      primary_indicators: ["rmssd"],
      clinical_reasoning:
        "All HRV parameters within normal variation range for this patient's baseline. RMSSD z-score -0.3. No bradycardia events.",
      recommended_action: "Continue routine monitoring",
      confidence: 0.91,
      retrieved_context: [],
      self_check_passed: true,
      protocol_compliant: true,
      past_similar_events: 0,
      latency_ms: 290,
    },
    {
      patient_id: "infant5",
      timestamp: minsAgo(6),
      concern_level: "GREEN",
      risk_score: 0.12,
      primary_indicators: ["sdnn"],
      clinical_reasoning:
        "Stable HRV profile. SDNN within personal baseline range (z=+0.4). No events.",
      recommended_action: "Continue routine monitoring",
      confidence: 0.93,
      retrieved_context: [],
      self_check_passed: true,
      protocol_compliant: true,
      past_similar_events: 0,
      latency_ms: 275,
    },
    {
      patient_id: "infant6",
      timestamp: minsAgo(9),
      concern_level: "GREEN",
      risk_score: 0.22,
      primary_indicators: ["lf_hf_ratio"],
      clinical_reasoning:
        "Mild LF/HF elevation (z=+0.9) within normal variation. No autonomic withdrawal pattern. No bradycardia.",
      recommended_action: "Continue routine monitoring",
      confidence: 0.88,
      retrieved_context: [],
      self_check_passed: true,
      protocol_compliant: true,
      past_similar_events: 0,
      latency_ms: 310,
    },
    {
      patient_id: "infant7",
      timestamp: minsAgo(2),
      concern_level: "GREEN",
      risk_score: 0.09,
      primary_indicators: ["rmssd"],
      clinical_reasoning:
        "All indicators stable. HRV consistent with normal sleep-cycle variation.",
      recommended_action: "Continue routine monitoring",
      confidence: 0.95,
      retrieved_context: [],
      self_check_passed: true,
      protocol_compliant: true,
      past_similar_events: 0,
      latency_ms: 265,
    },
    {
      patient_id: "infant8",
      timestamp: minsAgo(14),
      concern_level: "GREEN",
      risk_score: 0.31,
      primary_indicators: ["pnn50"],
      clinical_reasoning:
        "pNN50 slightly below baseline (z=-0.8). No clinical significance at this level. Risk score 0.31 within GREEN range.",
      recommended_action: "Continue routine monitoring",
      confidence: 0.87,
      retrieved_context: [],
      self_check_passed: true,
      protocol_compliant: true,
      past_similar_events: 0,
      latency_ms: 298,
    },
    {
      patient_id: "infant9",
      timestamp: minsAgo(5),
      concern_level: "GREEN",
      risk_score: 0.15,
      primary_indicators: ["sdnn"],
      clinical_reasoning:
        "SDNN within expected range. No deviations of clinical concern. Stable baseline.",
      recommended_action: "Continue routine monitoring",
      confidence: 0.92,
      retrieved_context: [],
      self_check_passed: true,
      protocol_compliant: true,
      past_similar_events: 0,
      latency_ms: 280,
    },
    {
      patient_id: "infant10",
      timestamp: minsAgo(8),
      concern_level: "GREEN",
      risk_score: 0.26,
      primary_indicators: ["rmssd"],
      clinical_reasoning:
        "Mild RMSSD variation (z=-0.7) within normal range. No bradycardia. Stable post-feed profile.",
      recommended_action: "Continue routine monitoring",
      confidence: 0.89,
      retrieved_context: [],
      self_check_passed: true,
      protocol_compliant: true,
      past_similar_events: 0,
      latency_ms: 305,
    },
  ];

  // History entries only provided for patients with notable recent history.
  // All other patients return empty array (displays "No previous alerts.").
  export const MOCK_HISTORY: Record<string, HistoryEntry[]> = {
    infant1: [
      { timestamp: minsAgo(93), concern_level: "RED", risk_score: 0.81, top_feature: "rmssd", top_z_score: -3.1, signal_pattern: "pre_sepsis", brady_classification: "recurrent_without_suppression", agent_version: "multi_agent" },
      { timestamp: minsAgo(183), concern_level: "YELLOW", risk_score: 0.52, top_feature: "lf_hf_ratio", top_z_score: 2.2, signal_pattern: "indeterminate", brady_classification: null, agent_version: "multi_agent" },
      { timestamp: minsAgo(273), concern_level: "GREEN", risk_score: 0.21, top_feature: "rmssd", top_z_score: -0.8, signal_pattern: "normal_variation", brady_classification: null, agent_version: "multi_agent" },
    ],
    infant2: [
      { timestamp: minsAgo(97), concern_level: "YELLOW", risk_score: 0.55, top_feature: "lf_hf_ratio", top_z_score: 1.9, signal_pattern: "indeterminate", brady_classification: null, agent_version: "multi_agent" },
      { timestamp: minsAgo(187), concern_level: "GREEN", risk_score: 0.28, top_feature: "rmssd", top_z_score: -0.6, signal_pattern: "normal_variation", brady_classification: null, agent_version: "multi_agent" },
    ],
  };
  ```

  **File: `dashboard/lib/api-client.ts`**
  ```typescript
  import { NeonatalAlert, HistoryEntry } from "./types";
  import { MOCK_ALERTS, MOCK_HISTORY } from "./mock-data";

  const USE_REAL_API = process.env.NEXT_PUBLIC_USE_REAL_API === "true";
  const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

  export async function getPatientAlert(
    patientId: string
  ): Promise<NeonatalAlert> {
    if (!USE_REAL_API) {
      const found = MOCK_ALERTS.find((a) => a.patient_id === patientId);
      if (!found) throw new Error(`No mock data for ${patientId}`);
      return found;
    }
    const res = await fetch(`${API_BASE}/assess/${patientId}`, {
      method: "POST",
      cache: "no-store",
    });
    if (!res.ok) throw new Error(`API error ${res.status} for ${patientId}`);
    return res.json();
  }

  export async function getPatientHistory(
    patientId: string,
    n = 7
  ): Promise<HistoryEntry[]> {
    if (!USE_REAL_API) {
      return MOCK_HISTORY[patientId] ?? [];
    }
    const res = await fetch(`${API_BASE}/patient/${patientId}/history?n=${n}`, {
      cache: "no-store",
    });
    if (!res.ok) return [];
    return res.json();
  }

  export async function getSystemHealth(): Promise<"ok" | "degraded"> {
    if (!USE_REAL_API) return "ok";
    try {
      const res = await fetch(`${API_BASE}/health`, { cache: "no-store" });
      if (!res.ok) return "degraded";
      const data = await res.json();
      return data.qdrant === "ok" ? "ok" : "degraded";
    } catch (_e) {
      return "degraded";
    }
  }
  ```

  **What it does:** Establishes the full TypeScript data contract, seeds 10 patients in a realistic clinical distribution, and provides a single build-time env toggle for mock vs real API.

  **Why this approach:** All components and hooks import only from this layer. The mock/real boundary is centralised; no component touches `fetch` directly. `HRV_LABEL` keys match `HRV_FEATURE_COLS` exactly so real API indicator names render correctly.

  **Assumptions:**
  - `NeonatalAlert` fields confirmed via Pre-Read Gate grep against `src/agent/schemas.py`.
  - History columns (`timestamp`, `concern_level`, `risk_score`, `top_feature`, `top_z_score`, `signal_pattern`, `brady_classification`, `agent_version`) confirmed via Pre-Read Gate grep against `api/main.py`.

  **Risks:**
  - FastAPI serialises `datetime` as ISO string (confirmed by Pydantic default) → `new Date(alert.timestamp)` will parse correctly.
  - `NEXT_PUBLIC_USE_REAL_API` must be set before `npm run build` or `npm run dev`, not after → noted in Step 7 verification.

  **Git Checkpoint:**
  ```bash
  git add dashboard/lib/
  git commit -m "step 2: add types (matching schemas.py), mock data (10 patients), api-client"
  ```

  **Subtasks:**
  - [x] 🟩 `types.ts` written; `HRV_LABEL` keys match `HRV_FEATURE_COLS` from `constants.py`
  - [x] 🟩 `mock-data.ts` has exactly 10 entries (1 RED, 2 YELLOW, 7 GREEN); no unused variables
  - [x] 🟩 `api-client.ts` exports `getPatientAlert`, `getPatientHistory`, `getSystemHealth`

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  cd /Users/ngchenmeng/Neonatal/dashboard && npx tsc --noEmit 2>&1 | head -20
  ```

  **Expected:** Zero output (no `error TS` lines).

  **Pass:** Exit code 0, no error lines.

  **Fail:**
  - `error TS6133: 'X' is declared but its value is never read` → unused variable in `mock-data.ts` → remove it
  - `Cannot find module '@/lib/types'` → `tsconfig.json` path alias not set → confirm `"@/*": ["./*"]` is in `compilerOptions.paths`
  - `Type 'string' is not assignable to type 'ConcernLevel'` → typo in a mock entry's `concern_level` value → check all 10 entries

---

### Phase 2 — Components

**Goal:** All visual components exist and type-check cleanly.

---

- [x] 🟩 **Step 3: ConcernBadge + BedCard** — *Non-critical: pure presentational, no side effects*

  **Idempotent:** Yes — new files only.

  **Context:** `ConcernBadge` maps `ConcernLevel` → clinical label + colour pill. `BedCard` is the Level 1+2 surface: full-card colour coding, `animate-pulse-ring` only on RED, patient ID, badge, risk bar, top HRV indicator, time since assessment.

  **File: `dashboard/components/ConcernBadge.tsx`**
  ```typescript
  import { ConcernLevel, CONCERN_TO_LABEL } from "@/lib/types";

  const BADGE_CLASSES: Record<ConcernLevel, string> = {
    RED: "bg-red-700 text-red-100 font-semibold tracking-wide",
    YELLOW: "bg-amber-600 text-amber-50 font-medium",
    GREEN: "bg-slate-600 text-slate-300 font-normal",
  };

  export function ConcernBadge({ level }: { level: ConcernLevel }) {
    return (
      <span
        className={`inline-block rounded px-2 py-0.5 text-xs uppercase ${BADGE_CLASSES[level]}`}
      >
        {CONCERN_TO_LABEL[level]}
      </span>
    );
  }
  ```

  **File: `dashboard/components/BedCard.tsx`**
  ```typescript
  "use client";

  import { NeonatalAlert, HRV_LABEL } from "@/lib/types";
  import { ConcernBadge } from "./ConcernBadge";

  const CARD_BG: Record<string, string> = {
    RED: "bg-red-950 border-2 border-red-600",
    YELLOW: "bg-amber-950 border-2 border-amber-500",
    GREEN: "bg-slate-800 border border-slate-700",
  };

  function timeAgo(iso: string): string {
    const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 60_000);
    if (diff < 1) return "< 1 min ago";
    if (diff === 1) return "1 min ago";
    return `${diff} min ago`;
  }

  interface BedCardProps {
    alert: NeonatalAlert;
    onClick: () => void;
  }

  export function BedCard({ alert, onClick }: BedCardProps) {
    const isRed = alert.concern_level === "RED";
    const bedNum = alert.patient_id.replace("infant", "").padStart(2, "0");
    const topIndicator = alert.primary_indicators[0]
      ? HRV_LABEL[alert.primary_indicators[0]] ??
        alert.primary_indicators[0].toUpperCase()
      : "—";
    const riskPct = Math.round(alert.risk_score * 100);

    return (
      <button
        type="button"
        onClick={onClick}
        className={`
          relative w-full rounded-lg p-4 text-left transition-opacity hover:opacity-90 cursor-pointer
          ${CARD_BG[alert.concern_level]}
          ${isRed ? "animate-pulse-ring" : ""}
        `}
        aria-label={`Infant ${bedNum} — ${alert.concern_level}`}
      >
        <div className="flex items-start justify-between mb-3">
          <span className="text-slate-100 text-lg font-bold tracking-tight">
            Infant {bedNum}
          </span>
          <ConcernBadge level={alert.concern_level} />
        </div>

        <div className="mb-3">
          <div className="flex justify-between text-xs text-slate-400 mb-1">
            <span>Risk</span>
            <span>{riskPct}%</span>
          </div>
          <div className="h-1.5 w-full rounded-full bg-slate-700 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${
                isRed
                  ? "bg-red-500"
                  : alert.concern_level === "YELLOW"
                  ? "bg-amber-400"
                  : "bg-slate-500"
              }`}
              style={{ width: `${riskPct}%` }}
            />
          </div>
        </div>

        <div className="flex items-center justify-between text-xs">
          <span className="text-slate-200 font-medium">{topIndicator}</span>
          <span className="text-slate-500">{timeAgo(alert.timestamp)}</span>
        </div>
      </button>
    );
  }
  ```

  **Git Checkpoint:**
  ```bash
  git add dashboard/components/ConcernBadge.tsx dashboard/components/BedCard.tsx
  git commit -m "step 3: add ConcernBadge and BedCard with pulse-ring for RED"
  ```

  **Subtasks:**
  - [x] 🟩 `ConcernBadge` maps all three levels
  - [x] 🟩 `BedCard` applies `animate-pulse-ring` only when `concern_level === "RED"`
  - [x] 🟩 `CARD_BG` keys cover `RED`, `YELLOW`, `GREEN`

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  cd /Users/ngchenmeng/Neonatal/dashboard && npx tsc --noEmit 2>&1 | head -20
  ```

  **Pass:** Exit 0, no `error TS` lines.

  **Fail:**
  - `Property 'concern_level' does not exist` → `@/lib/types` alias not resolving → check `tsconfig.json` paths

---

- [x] 🟩 **Step 4: WardGrid + StatusBar** — *Non-critical: layout components*

  **Idempotent:** Yes — new files only.

  **Context:** `WardGrid` sorts alerts by severity (RED first) and renders `BedCard`s in a responsive grid. `"use client"` is required because it receives the `onSelectPatient` callback from `page.tsx`. `StatusBar` shows system identity, health dot, last refreshed time, and countdown pill.

  **File: `dashboard/components/WardGrid.tsx`**
  ```typescript
  "use client";

  import { NeonatalAlert } from "@/lib/types";
  import { BedCard } from "./BedCard";

  const SEVERITY_ORDER: Record<string, number> = { RED: 0, YELLOW: 1, GREEN: 2 };

  interface WardGridProps {
    alerts: NeonatalAlert[];
    onSelectPatient: (alert: NeonatalAlert) => void;
  }

  export function WardGrid({ alerts, onSelectPatient }: WardGridProps) {
    const sorted = [...alerts].sort(
      (a, b) =>
        SEVERITY_ORDER[a.concern_level] - SEVERITY_ORDER[b.concern_level]
    );

    return (
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3 p-4">
        {sorted.map((alert) => (
          <BedCard
            key={alert.patient_id}
            alert={alert}
            onClick={() => onSelectPatient(alert)}
          />
        ))}
      </div>
    );
  }
  ```

  **File: `dashboard/components/StatusBar.tsx`**
  ```typescript
  "use client";

  interface StatusBarProps {
    wardName?: string;
    lastRefreshed: Date | null;
    countdown: number;
    health: "ok" | "degraded" | "loading";
  }

  function pad(n: number) {
    return String(n).padStart(2, "0");
  }

  export function StatusBar({
    wardName = "NICU Ward A",
    lastRefreshed,
    countdown,
    health,
  }: StatusBarProps) {
    const mins = Math.floor(countdown / 60);
    const secs = countdown % 60;

    return (
      <header className="flex items-center justify-between px-4 py-3 bg-slate-950 border-b border-slate-800 shrink-0">
        <div className="flex items-center gap-3">
          <span className="text-slate-100 font-semibold text-sm tracking-wide">
            NeonatalGuard
          </span>
          <span className="text-slate-500 text-xs">/</span>
          <span className="text-slate-400 text-xs">{wardName}</span>
        </div>

        <div className="flex items-center gap-4 text-xs text-slate-400">
          <span className="flex items-center gap-1.5">
            <span
              className={`inline-block h-2 w-2 rounded-full ${
                health === "ok"
                  ? "bg-emerald-500"
                  : health === "degraded"
                  ? "bg-red-500"
                  : "bg-slate-600"
              }`}
            />
            {health === "ok"
              ? "System OK"
              : health === "degraded"
              ? "Degraded"
              : "Checking…"}
          </span>

          {lastRefreshed && (
            <span>
              Updated{" "}
              {lastRefreshed.toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
          )}

          <span className="rounded-full bg-slate-800 px-2.5 py-1 font-mono text-slate-300">
            Next refresh {pad(mins)}:{pad(secs)}
          </span>
        </div>
      </header>
    );
  }
  ```

  **Git Checkpoint:**
  ```bash
  git add dashboard/components/WardGrid.tsx dashboard/components/StatusBar.tsx
  git commit -m "step 4: add WardGrid (severity-sorted, use client) and StatusBar with countdown"
  ```

  **Subtasks:**
  - [x] 🟩 `WardGrid.tsx` has `"use client"` at top
  - [x] 🟩 `SEVERITY_ORDER` sorts RED=0, YELLOW=1, GREEN=2
  - [x] 🟩 `StatusBar` countdown renders as `MM:SS` via `pad()`

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  cd /Users/ngchenmeng/Neonatal/dashboard && npx tsc --noEmit 2>&1 | head -20
  ```

  **Pass:** Exit 0, no errors.

  **Fail:**
  - `Type '(alert: NeonatalAlert) => void' is not assignable` → `onSelectPatient` prop type mismatch → confirm `NeonatalAlert` import is identical in both `WardGrid` and caller

---

### Phase 3 — Hooks + Drawer

**Goal:** Data flows from mock/API into the ward grid. Drawer opens on card click and stays open on internal interaction.

---

- [x] 🟩 **Step 5: useWardData + usePatientHistory** — *Critical: all data flow, polling, and countdown state*

  **Idempotent:** Yes — new files only. Creates `dashboard/hooks/` directory.

  **Context:** `useWardData` fetches all 10 patients in parallel every 90 seconds using `Promise.allSettled` (individual patient failures do not block the rest). It maintains three pieces of state: `alerts`, `lastRefreshed`, `countdown`. `usePatientHistory` fetches on demand when a patient is selected, resets when selection clears.

  **Pre-Read Gate:**
  ```bash
  # Confirm MOCK_ALERTS has exactly 10 entries
  grep -c '"patient_id"' /Users/ngchenmeng/Neonatal/dashboard/lib/mock-data.ts
  # Must return 10. If not → STOP, the mock data from Step 2 is incomplete.
  ```

  **File: `dashboard/hooks/useWardData.ts`**
  ```typescript
  "use client";

  import { useCallback, useEffect, useRef, useState } from "react";
  import { NeonatalAlert } from "@/lib/types";
  import { getPatientAlert, getSystemHealth } from "@/lib/api-client";

  const PATIENT_IDS = [
    "infant1", "infant2", "infant3", "infant4", "infant5",
    "infant6", "infant7", "infant8", "infant9", "infant10",
  ];

  const REFRESH_INTERVAL = 90; // seconds

  export function useWardData() {
    const [alerts, setAlerts] = useState<NeonatalAlert[]>([]);
    const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);
    const [countdown, setCountdown] = useState(REFRESH_INTERVAL);
    const [health, setHealth] = useState<"ok" | "degraded" | "loading">(
      "loading"
    );

    const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const refreshRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const fetchAll = useCallback(async () => {
      const results = await Promise.allSettled(
        PATIENT_IDS.map((id) => getPatientAlert(id))
      );
      const resolved = results
        .filter(
          (r): r is PromiseFulfilledResult<NeonatalAlert> =>
            r.status === "fulfilled"
        )
        .map((r) => r.value);
      setAlerts(resolved);
      setLastRefreshed(new Date());
      setCountdown(REFRESH_INTERVAL);

      const h = await getSystemHealth();
      setHealth(h);
    }, []);

    useEffect(() => {
      fetchAll();

      countdownRef.current = setInterval(() => {
        setCountdown((prev) => (prev <= 1 ? REFRESH_INTERVAL : prev - 1));
      }, 1000);

      refreshRef.current = setInterval(fetchAll, REFRESH_INTERVAL * 1000);

      return () => {
        if (countdownRef.current) clearInterval(countdownRef.current);
        if (refreshRef.current) clearInterval(refreshRef.current);
      };
    }, [fetchAll]);

    return { alerts, lastRefreshed, countdown, health };
  }
  ```

  **File: `dashboard/hooks/usePatientHistory.ts`**
  ```typescript
  "use client";

  import { useEffect, useState } from "react";
  import { HistoryEntry } from "@/lib/types";
  import { getPatientHistory } from "@/lib/api-client";

  export function usePatientHistory(patientId: string | null) {
    const [history, setHistory] = useState<HistoryEntry[]>([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
      if (!patientId) {
        setHistory([]);
        return;
      }
      setLoading(true);
      getPatientHistory(patientId, 7)
        .then(setHistory)
        .catch(() => setHistory([]))
        .finally(() => setLoading(false));
    }, [patientId]);

    return { history, loading };
  }
  ```

  **What it does:** `useWardData` polls 10 patients in parallel every 90s, ticks countdown every 1s, checks system health after each refresh. `usePatientHistory` fetches on demand when drawer opens, resets on close.

  **Why this approach:** `Promise.allSettled` over `Promise.all` — one patient's API failure doesn't block the other 9. Countdown resets to 90 on every `fetchAll`, bounding drift to one 90s window. Separate interval references prevent interval accumulation across StrictMode double-mounts.

  **Assumptions:**
  - `getPatientAlert` and `getSystemHealth` exported from `@/lib/api-client` (confirmed Step 2).
  - `page.tsx` (the consumer) will be `"use client"` — hooks require a client component parent.

  **Risks:**
  - StrictMode in dev double-invokes `useEffect` → two interval pairs created → `fetchAll` runs immediately twice on mount. The cleanup function clears both on unmount. In dev this causes a brief double-fetch; in prod (no StrictMode) this does not occur. Harmless.

  **Git Checkpoint:**
  ```bash
  git add dashboard/hooks/
  git commit -m "step 5: add useWardData (90s polling + countdown) and usePatientHistory"
  ```

  **Subtasks:**
  - [x] 🟩 `dashboard/hooks/` directory exists with both files
  - [x] 🟩 `useWardData` initialises `countdown` at 90 and ticks down every second
  - [x] 🟩 `fetchAll` uses `Promise.allSettled`; partial failures don't prevent other patients rendering
  - [x] 🟩 `usePatientHistory` resets `history` to `[]` when `patientId` is null

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  cd /Users/ngchenmeng/Neonatal/dashboard && npx tsc --noEmit 2>&1 | head -20
  ```

  **Pass:** Exit 0, no errors.

  **Fail:**
  - `useCallback is not exported from 'react'` → add `useCallback` to import → `import { useCallback, useEffect, useRef, useState } from "react"`
  - `PromiseFulfilledResult` not found → add `/// <reference lib="ES2015.promise" />` at top of file, or confirm `tsconfig.json` has `"lib": ["ES2017", "DOM"]`

---

- [x] 🟩 **Step 6: PatientDrawer + AlertHistory** — *Non-critical: presentational drawer, Level 3+4 content*

  **Idempotent:** Yes — new files only.

  **Context:** `AlertHistory` renders a compact timeline of past alerts. `PatientDrawer` is a right-side slide-over. The `<aside>` panel has `onClick={(e) => e.stopPropagation()}` to prevent clicks from bubbling to the backdrop's `onClose` handler — without this, no interaction inside the drawer is possible.

  **File: `dashboard/components/AlertHistory.tsx`**
  ```typescript
  import { HistoryEntry, HRV_LABEL, CONCERN_TO_LABEL } from "@/lib/types";

  const DOT: Record<string, string> = {
    RED: "bg-red-500",
    YELLOW: "bg-amber-400",
    GREEN: "bg-slate-500",
  };

  export function AlertHistory({
    history,
    loading,
  }: {
    history: HistoryEntry[];
    loading: boolean;
  }) {
    if (loading) {
      return (
        <p className="text-slate-500 text-xs py-4 text-center">
          Loading history…
        </p>
      );
    }
    if (history.length === 0) {
      return (
        <p className="text-slate-500 text-xs py-4 text-center">
          No previous alerts.
        </p>
      );
    }

    return (
      <ol className="space-y-3">
        {history.map((entry, i) => {
          const label =
            CONCERN_TO_LABEL[entry.concern_level] ?? entry.concern_level;
          const feature = entry.top_feature
            ? HRV_LABEL[entry.top_feature] ?? entry.top_feature
            : null;
          const t = new Date(entry.timestamp).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          });
          const d = new Date(entry.timestamp).toLocaleDateString([], {
            month: "short",
            day: "numeric",
          });
          return (
            <li key={i} className="flex items-start gap-3">
              <span
                className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${
                  DOT[entry.concern_level] ?? "bg-slate-600"
                }`}
              />
              <div>
                <span className="text-slate-300 text-xs font-medium">
                  {label}
                </span>
                <span className="text-slate-500 text-xs ml-2">
                  {d} {t}
                </span>
                {feature && (
                  <span className="block text-slate-500 text-xs">
                    {feature}
                    {entry.top_z_score !== null
                      ? ` z=${entry.top_z_score > 0 ? "+" : ""}${entry.top_z_score?.toFixed(1)}`
                      : ""}
                  </span>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    );
  }
  ```

  **File: `dashboard/components/PatientDrawer.tsx`**
  ```typescript
  "use client";

  import { NeonatalAlert, HRV_LABEL } from "@/lib/types";
  import { ConcernBadge } from "./ConcernBadge";
  import { AlertHistory } from "./AlertHistory";
  import { usePatientHistory } from "@/hooks/usePatientHistory";

  const ACTION_CALLOUT: Record<string, string> = {
    RED: "bg-red-950 border border-red-700 text-red-100",
    YELLOW: "bg-amber-950 border border-amber-600 text-amber-100",
    GREEN: "bg-slate-800 border border-slate-700 text-slate-300",
  };

  interface PatientDrawerProps {
    alert: NeonatalAlert | null;
    onClose: () => void;
  }

  export function PatientDrawer({ alert, onClose }: PatientDrawerProps) {
    const { history, loading } = usePatientHistory(alert?.patient_id ?? null);

    if (!alert) return null;

    const bedNum = alert.patient_id.replace("infant", "").padStart(2, "0");
    const riskPct = Math.round(alert.risk_score * 100);

    return (
      <>
        {/* Backdrop — clicking outside closes drawer */}
        <div
          className="fixed inset-0 bg-black/40 z-30"
          onClick={onClose}
          aria-hidden="true"
        />

        {/* Drawer panel — stopPropagation prevents backdrop from firing on internal clicks */}
        <aside
          className="fixed right-0 top-0 h-full w-full max-w-md bg-slate-900 border-l border-slate-800 z-40 flex flex-col overflow-hidden shadow-2xl"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800 shrink-0">
            <div className="flex items-center gap-3">
              <span className="text-slate-100 font-bold text-base">
                Infant {bedNum}
              </span>
              <ConcernBadge level={alert.concern_level} />
            </div>
            <button
              onClick={onClose}
              className="text-slate-500 hover:text-slate-300 text-xl leading-none px-1"
              aria-label="Close"
            >
              ×
            </button>
          </div>

          {/* Scrollable body */}
          <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
            {/* Recommended action — Level 3, first and most prominent */}
            <div
              className={`rounded-lg px-4 py-3 ${
                ACTION_CALLOUT[alert.concern_level]
              }`}
            >
              <p className="text-xs font-semibold uppercase tracking-wider mb-1 opacity-70">
                Recommended Action
              </p>
              <p className="text-sm font-medium leading-snug">
                {alert.recommended_action}
              </p>
            </div>

            {/* Risk score gauge */}
            <div>
              <div className="flex justify-between text-xs text-slate-400 mb-1">
                <span>Risk Score</span>
                <span className="text-slate-200 font-semibold">{riskPct}%</span>
              </div>
              <div className="h-2 w-full rounded-full bg-slate-800 overflow-hidden">
                <div
                  className={`h-full rounded-full ${
                    alert.concern_level === "RED"
                      ? "bg-red-500"
                      : alert.concern_level === "YELLOW"
                      ? "bg-amber-400"
                      : "bg-slate-500"
                  }`}
                  style={{ width: `${riskPct}%` }}
                />
              </div>
            </div>

            {/* Primary indicators */}
            <div>
              <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">
                Primary Indicators
              </p>
              <div className="flex flex-wrap gap-2">
                {alert.primary_indicators.map((ind) => (
                  <span
                    key={ind}
                    className="rounded bg-slate-800 px-2 py-1 text-xs text-slate-300 border border-slate-700"
                  >
                    {HRV_LABEL[ind] ?? ind.toUpperCase()}
                  </span>
                ))}
              </div>
            </div>

            {/* Clinical reasoning */}
            <div>
              <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">
                Clinical Reasoning
              </p>
              <p className="text-sm text-slate-300 leading-relaxed">
                {alert.clinical_reasoning}
              </p>
            </div>

            {/* Confidence + past events + timestamp */}
            <div className="flex gap-6 text-xs">
              <div>
                <span className="block text-slate-500 uppercase tracking-wider mb-0.5">
                  Confidence
                </span>
                <span className="text-slate-200 font-medium">
                  {Math.round(alert.confidence * 100)}%
                </span>
              </div>
              <div>
                <span className="block text-slate-500 uppercase tracking-wider mb-0.5">
                  Past Events
                </span>
                <span className="text-slate-200 font-medium">
                  {alert.past_similar_events}
                </span>
              </div>
              <div>
                <span className="block text-slate-500 uppercase tracking-wider mb-0.5">
                  Assessed
                </span>
                <span className="text-slate-200 font-medium">
                  {new Date(alert.timestamp).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              </div>
            </div>

            {/* Alert history */}
            <div>
              <p className="text-xs text-slate-500 uppercase tracking-wider mb-3">
                Alert History (last 7)
              </p>
              <AlertHistory history={history} loading={loading} />
            </div>
          </div>
        </aside>
      </>
    );
  }
  ```

  **Git Checkpoint:**
  ```bash
  git add dashboard/components/AlertHistory.tsx dashboard/components/PatientDrawer.tsx
  git commit -m "step 6: add AlertHistory and PatientDrawer with stopPropagation fix"
  ```

  **Subtasks:**
  - [x] 🟩 `<aside>` has `onClick={(e) => e.stopPropagation()}`
  - [x] 🟩 Recommended action callout is the first element in the scrollable body
  - [x] 🟩 `AlertHistory` renders "No previous alerts." when `history.length === 0`

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  cd /Users/ngchenmeng/Neonatal/dashboard && npx tsc --noEmit 2>&1 | head -20
  ```

  **Pass:** Exit 0, no errors.

  **Fail:**
  - `Cannot find module '@/hooks/usePatientHistory'` → `hooks/` directory not created → confirm `dashboard/hooks/usePatientHistory.ts` exists from Step 5

---

### Phase 4 — Wire + Final Build

**Goal:** `page.tsx` wires all parts. `npm run build` exits 0. Visual smoke test passes in browser.

---

- [x] 🟩 **Step 7: Wire page.tsx + create .env.local + final build** — *Non-critical: wires existing parts*

  **Idempotent:** Yes — replaces the placeholder `page.tsx` from Step 1.

  **Context:** `page.tsx` is the single route. Uses `useWardData` for data, `useState` for selected patient. Must be `"use client"` because it uses hooks. Creates `.env.local` (not committed) for the env toggle.

  **File: `dashboard/app/page.tsx`** — replace the Step 1 placeholder entirely:
  ```typescript
  "use client";

  import { useState } from "react";
  import { NeonatalAlert } from "@/lib/types";
  import { useWardData } from "@/hooks/useWardData";
  import { WardGrid } from "@/components/WardGrid";
  import { StatusBar } from "@/components/StatusBar";
  import { PatientDrawer } from "@/components/PatientDrawer";

  export default function Home() {
    const { alerts, lastRefreshed, countdown, health } = useWardData();
    const [selected, setSelected] = useState<NeonatalAlert | null>(null);

    return (
      <div className="flex flex-col h-screen bg-slate-900 overflow-hidden">
        <StatusBar
          lastRefreshed={lastRefreshed}
          countdown={countdown}
          health={health}
        />
        <main className="flex-1 overflow-y-auto">
          <WardGrid alerts={alerts} onSelectPatient={setSelected} />
        </main>
        <PatientDrawer alert={selected} onClose={() => setSelected(null)} />
      </div>
    );
  }
  ```

  **File: `dashboard/.env.local`** — create this file (it is gitignored):
  ```
  NEXT_PUBLIC_USE_REAL_API=false
  NEXT_PUBLIC_API_BASE=http://localhost:8000
  ```

  **Confirm `.env.local` is gitignored** — `create-next-app` includes `.env*.local` in `.gitignore` by default. Verify:
  ```bash
  grep "env.local" /Users/ngchenmeng/Neonatal/dashboard/.gitignore
  ```
  If not present, append `.env.local` to `.gitignore`.

  **Git Checkpoint:**
  ```bash
  git add dashboard/app/page.tsx dashboard/.gitignore
  # Do NOT git add .env.local
  git commit -m "step 7: wire page.tsx — useWardData + WardGrid + StatusBar + PatientDrawer"
  ```

  **Subtasks:**
  - [x] 🟩 `page.tsx` is `"use client"`
  - [x] 🟩 `.env.local` created with `NEXT_PUBLIC_USE_REAL_API=false`
  - [x] 🟩 `.env.local` is gitignored (not staged, not committed)

  **✓ Verification Test:**

  **Type:** Integration + E2E (visual)

  **Action — build check:**
  ```bash
  cd /Users/ngchenmeng/Neonatal/dashboard && npm run build 2>&1 | tail -10
  ```
  **Expected:** Exit 0. Output contains `Route (app)` table with `/` listed. No `error TS` or `Failed to compile` lines.

  **Action — visual smoke test:**
  ```bash
  cd /Users/ngchenmeng/Neonatal/dashboard && npm run dev
  ```
  Open `http://localhost:3000` in a browser and verify visually:

  | Check | What to look for |
  |---|---|
  | 10 bed cards render | Grid of 10 cards labelled Infant 01–10 |
  | RED card is first and pulses | Infant 01 card has red background, pulsing ring animation |
  | YELLOW cards are amber, static | Infant 02 and 03 amber border, no animation |
  | GREEN cards are slate | Infant 04–10 dark grey, no animation |
  | Status bar shows countdown | Top-right: "Next refresh 01:XX" counting down |
  | Click a card opens drawer | Drawer slides in from right with recommended action at top |
  | Click inside drawer stays open | Scrolling or clicking text does NOT close the drawer |
  | Click backdrop closes drawer | Clicking outside the drawer closes it |

  **Pass:** All 8 visual checks pass.

  **Fail:**
  - `Failed to compile` in build output → run `npx tsc --noEmit` to identify the type error
  - Ward grid empty → `useWardData` not returning mock data → confirm `.env.local` has `NEXT_PUBLIC_USE_REAL_API=false` and restart dev server
  - Drawer closes immediately when clicked → `stopPropagation` missing on `<aside>` → check `PatientDrawer.tsx` Step 6 fix is present
  - Countdown not decrementing → `countdownRef` interval not starting → check `useEffect` in `useWardData.ts` mounts correctly

  **To test real API toggle:**
  1. Ensure FastAPI backend is running: `cd /Users/ngchenmeng/Neonatal && uvicorn api.main:app --reload`
  2. Change `.env.local` to `NEXT_PUBLIC_USE_REAL_API=true`
  3. Restart dev server (`ctrl+c` then `npm run dev`)
  4. Open browser Network tab — POST requests to `http://localhost:8000/assess/infant1` etc. should appear

---

## Regression Guard

**Systems at risk:** None. All changes are in `dashboard/` — a new isolated directory. No Python files, no `src/`, `api/`, or `eval/` files are modified.

**Regression verification:**
```bash
cd /Users/ngchenmeng/Neonatal && python -m pytest tests/ -q 2>/dev/null | tail -1
# Must match backend test count from pre-flight baseline
```

---

## Rollback Procedure

```bash
# All 7 steps are contained in dashboard/ only.
rm -rf /Users/ngchenmeng/Neonatal/dashboard/

# Confirm no other files were modified
git status  # must show only dashboard/ deletions/untracked

# Restore
git checkout -- .
```

No schema changes, no migrations, no existing file modifications. Rollback is a single directory delete.

---

## Pre-Flight Checklist

| Phase | Check | How to Confirm | Status |
|-------|-------|----------------|--------|
| Pre-flight | Node >= 18 | `node --version` | ⬜ |
| Pre-flight | `dashboard/` does not exist | `ls dashboard/` returns error | ⬜ |
| Pre-flight | `HRV_FEATURE_COLS` confirmed | grep output matches 10 keys | ⬜ |
| Pre-flight | Backend tests pass | `pytest tests/ -q` exits 0 | ⬜ |
| Step 1 | Build passes | `npm run build` exits 0 | ⬜ |
| Step 2 | Types correct | `tsc --noEmit` exits 0 | ⬜ |
| Steps 3–6 | Type-check after each | `tsc --noEmit` exits 0 | ⬜ |
| Step 7 | Final build + visual | `npm run build` exits 0, 8 visual checks pass | ⬜ |

---

## Risk Heatmap

| Step | Risk Level | What Could Go Wrong | Early Detection | Idempotent |
|------|-----------|---------------------|-----------------|------------|
| Step 1 | 🟡 Medium | Scaffold creates `.js` not `.ts` for tailwind config | Check `ls dashboard/tailwind.config.*` immediately | No |
| Step 2 | 🟢 Low | Field name drift from schemas.py | Pre-Read Gate greps schemas.py before writing | Yes |
| Step 3 | 🟢 Low | `animate-pulse-ring` not found by Tailwind JIT | Visual check in browser | Yes |
| Step 4 | 🟢 Low | Missing `"use client"` on WardGrid | `tsc --noEmit` | Yes |
| Step 5 | 🟡 Medium | Countdown drift over long session | Bounded by fetchAll reset; acceptable | Yes |
| Step 6 | 🔴 High | Drawer closes on click if stopPropagation missing | Verified in Step 7 visual check item 7 | Yes |
| Step 7 | 🟡 Medium | `h-screen` breaks without `h-full` on body | Verified in Step 1 layout.tsx update | Yes |

---

## Success Criteria

| Feature | Target | Verification |
|---------|--------|--------------|
| Build passes | `npm run build` exits 0 | **Do:** `npm run build` → **Expect:** exit 0, route table in output |
| 10 bed cards render | Grid shows Infant 01–10 | **Do:** open `localhost:3000` → **Expect:** 10 cards |
| RED dominates visually | Infant 01 first, pulsing | **Do:** view grid → **Expect:** red card at top-left, border pulsing |
| YELLOW static, GREEN inert | Amber/slate, no animation | **Do:** view grid → **Expect:** no animation on non-RED cards |
| Drawer opens + stays open | Click opens; internal click doesn't close | **Do:** click any card, then click inside drawer → **Expect:** drawer stays open |
| Countdown ticks | Status bar counts down | **Do:** watch status bar for 5s → **Expect:** seconds decrement |
| Real API toggle works | Env var switches data source | **Do:** set `NEXT_PUBLIC_USE_REAL_API=true`, restart → **Expect:** POST requests in Network tab |
| Backend tests unchanged | Same count as pre-flight | **Do:** `pytest tests/ -q` → **Expect:** count ≥ pre-flight baseline |

---

⚠️ **Do not mark a step 🟩 Done until its verification test passes.**
⚠️ **Do not proceed past a Human Gate without explicit human input.**
⚠️ **Do not batch multiple steps into one git commit.**
⚠️ **If idempotent = No, confirm the step has not already run before executing.**
