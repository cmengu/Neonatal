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
