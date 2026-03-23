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
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800 shrink-0">
          <div className="flex items-center gap-3">
            <span className="text-slate-100 font-bold text-base">
              Infant {bedNum}
            </span>
            <ConcernBadge level={alert.concern_level} />
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-500 hover:text-slate-300 text-xl leading-none px-1"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
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

          <div>
            <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">
              Clinical Reasoning
            </p>
            <p className="text-sm text-slate-300 leading-relaxed">
              {alert.clinical_reasoning}
            </p>
          </div>

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
