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
