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
