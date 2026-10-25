import { Trace } from "./trace-types";
import { MOCK_TRACE_INFANT7 } from "./mock-trace";

const USE_REAL_API = process.env.NEXT_PUBLIC_USE_REAL_API === "true";
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

const MOCK_TRACES: Record<string, Trace> = {
  infant7: MOCK_TRACE_INFANT7,
};

/**
 * Load the recorded trace for one infant. Until the recorder (#31) is wired,
 * only infant7 has a fixture. In real-API mode the recorder serves the file at
 * GET /trace/{id}; either way the shape is the #30 contract.
 */
export async function getTrace(patientId: string): Promise<Trace> {
  if (!USE_REAL_API) {
    const found = MOCK_TRACES[patientId];
    if (!found) throw new Error(`No recorded trace for ${patientId}`);
    return found;
  }
  const res = await fetch(`${API_BASE}/trace/${patientId}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Trace API error ${res.status} for ${patientId}`);
  return res.json();
}
