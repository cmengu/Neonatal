import { Trace } from "./trace-types";
import { MOCK_TRACE_INFANT7 } from "./mock-trace";

/**
 * Where getTrace reads from — the #30 contract shape in all three modes:
 *  - "recorded" (default): the #31 recorder's file, served same-origin from
 *    public/trace/{id}.json
 *  - "api": GET {API_BASE}/trace/{id} from a running recorder/backend
 *  - "mock": the deterministic in-repo fixture (contract-valid, marked simulated)
 */
type TraceMode = "recorded" | "api" | "mock";

const TRACE_MODE: TraceMode = (() => {
  const mode = process.env.NEXT_PUBLIC_TRACE_MODE;
  if (mode === "recorded" || mode === "api" || mode === "mock") return mode;
  // Back-compat with the pre-#50 flag
  if (process.env.NEXT_PUBLIC_USE_REAL_API === "true") return "api";
  return "recorded";
})();

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

const MOCK_TRACES: Record<string, Trace> = {
  infant7: MOCK_TRACE_INFANT7,
};

export async function getTrace(patientId: string): Promise<Trace> {
  if (TRACE_MODE === "mock") {
    const found = MOCK_TRACES[patientId];
    if (!found) throw new Error(`No recorded trace for ${patientId}`);
    return found;
  }
  const url =
    TRACE_MODE === "api"
      ? `${API_BASE}/trace/${patientId}`
      : `/trace/${patientId}.json`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`Trace load error ${res.status} for ${patientId}`);
  return res.json();
}
