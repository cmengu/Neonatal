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
