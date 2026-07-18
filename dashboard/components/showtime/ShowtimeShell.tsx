"use client";

import { ReactNode, useMemo } from "react";
import { Trace } from "@/lib/trace-types";
import { PlayheadProvider, usePlayhead } from "@/components/trace/playhead";
import { Timeline } from "@/components/trace/Timeline";
import { EmbeddingWarp } from "@/components/showtime/EmbeddingWarp";

/**
 * ShowtimeShell — the immersive stage (#61).
 *
 * One `PlayheadProvider` owns the shared clock; every panel here reads it via
 * `usePlayhead()` so the whole page scrubs together. The layout is the spec's
 * hero + HUD: tier rail (left), the world-model hero (center), the agent theater
 * (right), and the shared timeline scrubber (bottom). Panels render REAL trace
 * values at the playhead — they are deliberately compact previews; the cinematic
 * versions land in #62 (3-D warp), #63 (tier charts) and #64 (agent theater).
 */

const TIER = { t1: "#38bdf8", t2: "#a78bfa", t3: "#fbbf24" } as const;

function concernColor(level: string): string {
  return level === "RED" ? "#ef4444" : level === "YELLOW" ? "#eab308" : "#22c55e";
}

function useIdx(): number {
  const { p, grid } = usePlayhead();
  return Math.min(grid.n - 1, Math.max(0, Math.round(p)));
}

// ---- primitives --------------------------------------------------------------

function Spark({
  series,
  idx,
  color,
  w = 150,
  h = 34,
}: {
  series: number[];
  idx: number;
  color: string;
  w?: number;
  h?: number;
}) {
  const { min, span } = useMemo(() => {
    const v = series.filter((x) => Number.isFinite(x));
    const mn = v.length ? Math.min(...v) : 0;
    const mx = v.length ? Math.max(...v) : 1;
    return { min: mn, span: mx - mn || 1 };
  }, [series]);
  const n = Math.max(series.length - 1, 1);
  const xy = (y: number, i: number) => {
    const val = Number.isFinite(y) ? y : min;
    return [(i / n) * w, h - ((val - min) / span) * h] as const;
  };
  const pts = series
    .slice(0, idx + 1)
    .map((y, i) => xy(y, i).map((v) => v.toFixed(1)).join(","))
    .join(" ");
  const [cx, cy] = xy(series[idx], idx);
  return (
    <svg width={w} height={h} className="overflow-visible">
      <polyline points={pts} fill="none" stroke={color} strokeWidth={1.5} opacity={0.9} />
      <circle cx={cx} cy={cy} r={6} fill={color} opacity={0.18} />
      <circle cx={cx} cy={cy} r={2.6} fill={color} />
    </svg>
  );
}

function PanelFrame({
  accent,
  label,
  tag,
  children,
}: {
  accent: string;
  label: string;
  tag?: string;
  children: ReactNode;
}) {
  return (
    <div className="glass rounded-xl border border-white/[0.06] p-3.5">
      <div className="mb-2.5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className="h-1.5 w-1.5 rounded-full"
            style={{ background: accent, boxShadow: `0 0 8px ${accent}` }}
          />
          <span className="text-[11px] font-medium uppercase tracking-[0.14em] text-slate-300">
            {label}
          </span>
        </div>
        {tag && (
          <span className="text-[9px] uppercase tracking-wider text-slate-600">{tag}</span>
        )}
      </div>
      {children}
    </div>
  );
}

// ---- panels ------------------------------------------------------------------

function DataInPanel({ trace }: { trace: Trace }) {
  const idx = useIdx();
  const chans = trace.data_in.channels.slice(0, 2);
  return (
    <PanelFrame accent="#64748b" label="Data in" tag="telemetry">
      <div className="space-y-2.5">
        {chans.map((c) => (
          <div key={c.key} className="flex items-center gap-3">
            <div className="min-w-[62px]">
              <div className="text-[10px] text-slate-500">{c.label}</div>
              <div className="font-mono text-sm text-slate-100">
                {(c.samples[idx] ?? 0).toFixed(0)}
                <span className="ml-0.5 text-[9px] text-slate-500">{c.unit}</span>
              </div>
            </div>
            <Spark series={c.samples} idx={idx} color="#94a3b8" w={128} />
          </div>
        ))}
      </div>
    </PanelFrame>
  );
}

function Tier1Panel({ trace }: { trace: Trace }) {
  const idx = useIdx();
  const triggers = trace.tier1.features.filter((f) => f.trigger_feature);
  const top = triggers.length
    ? triggers.reduce((a, b) =>
        Math.abs(b.z_series[idx] ?? 0) > Math.abs(a.z_series[idx] ?? 0) ? b : a,
      )
    : undefined;
  const floor = trace.tier1.floor;
  const fc = concernColor(floor.level);
  return (
    <PanelFrame accent={TIER.t1} label="Tier 1 · Deviation" tag="#63 elevates">
      <div className="mb-1.5 flex items-center justify-between">
        <span className="text-[10px] text-slate-500">{top?.label ?? "—"} · z-score</span>
        <span className="font-mono text-sm" style={{ color: TIER.t1 }}>
          {top ? (top.z_series[idx] ?? 0).toFixed(1) : "—"}
        </span>
      </div>
      {top && <Spark series={top.z_series} idx={idx} color={TIER.t1} w={288} />}
      <div className="mt-2 flex items-center gap-2 text-[10px]">
        <span className="text-slate-500">Safety Floor</span>
        <span
          className="rounded px-1.5 py-0.5 font-mono"
          style={{ background: `${fc}22`, color: fc }}
        >
          {floor.kind} · {floor.level}
        </span>
      </div>
    </PanelFrame>
  );
}

function Tier2Panel({ trace }: { trace: Trace }) {
  const idx = useIdx();
  const t2 = trace.tier2;
  const c = t2.c_plus_series[idx] ?? 0;
  const pct = Math.min(100, (c / (t2.h || 1)) * 100);
  const crossed = t2.crossing_idx != null && idx >= t2.crossing_idx;
  return (
    <PanelFrame accent={TIER.t2} label="Tier 2 · CUSUM drift" tag="#63 elevates">
      <div className="mb-1.5 flex items-center justify-between">
        <span className="text-[10px] text-slate-500">C⁺ accumulation</span>
        <span className="font-mono text-sm" style={{ color: crossed ? "#ef4444" : TIER.t2 }}>
          {c.toFixed(1)} / {t2.h}
        </span>
      </div>
      <Spark series={t2.c_plus_series} idx={idx} color={TIER.t2} w={288} />
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-800">
        <div
          className="h-full rounded-full transition-all duration-200"
          style={{ width: `${pct}%`, background: crossed ? "#ef4444" : TIER.t2 }}
        />
      </div>
      <div className="mt-1.5 text-[10px] text-slate-500">
        {crossed ? "Drift fired — sustained deterioration" : "accumulating…"}
      </div>
    </PanelFrame>
  );
}

function HeroStage({ trace }: { trace: Trace }) {
  // #62: the real 3-D embedding warp, driven by the #60 world_model block. Falls back to a
  // labelled placeholder only if a trace predates #60 (world_model is optional on the contract).
  if (trace.world_model) return <EmbeddingWarp wm={trace.world_model} />;
  return (
    <div className="relative flex flex-1 items-center justify-center overflow-hidden">
      <div className="absolute inset-0 noir-grid opacity-40" />
      <div className="absolute inset-0 noir-vignette" />
      <div className="font-mono text-[11px] text-slate-600">
        no world_model block on this trace · export via scripts/export_jepa_trace.py (#60)
      </div>
    </div>
  );
}

function Tier3Panel({ trace }: { trace: Trace }) {
  const t3 = trace.tier3;
  if (!t3.ran) {
    return (
      <PanelFrame accent={TIER.t3} label="Tier 3 · Agents" tag="skipped">
        <div className="text-[11px] text-slate-500">Skipped on a calm window.</div>
      </PanelFrame>
    );
  }
  return (
    <PanelFrame accent={TIER.t3} label="Tier 3 · Agent reasoning" tag="#64 animates">
      <div className="space-y-3">
        <div>
          <div className="mb-1 text-[9px] uppercase tracking-wider text-slate-600">
            Retrieved guidelines
          </div>
          <div className="flex flex-wrap gap-1.5">
            {t3.retrieved.map((r) => (
              <span
                key={r.id}
                className="rounded border px-1.5 py-0.5 font-mono text-[9.5px]"
                style={{ borderColor: `${TIER.t3}44`, color: TIER.t3 }}
              >
                {r.source}
              </span>
            ))}
          </div>
        </div>
        <div>
          <div className="mb-1 text-[9px] uppercase tracking-wider text-slate-600">Reasoning</div>
          <p className="text-[11.5px] leading-relaxed text-slate-300">{t3.reasoning}</p>
        </div>
        <div className="flex items-center gap-2 text-[10px]">
          <span
            className="rounded px-1.5 py-0.5"
            style={{ background: "#ffffff08", color: t3.self_check.passed ? "#6ee7b7" : "#fcd34d" }}
          >
            self-check {t3.self_check.passed ? "✓ passed" : "⚠"}
          </span>
          <span className="text-slate-500">escalate-only</span>
        </div>
      </div>
    </PanelFrame>
  );
}

function TopBar({ trace }: { trace: Trace }) {
  const { clock, phase } = usePlayhead();
  const v = trace.verdict;
  const vc = concernColor(v.level);
  return (
    <div className="glass flex h-14 items-center justify-between border-b border-white/[0.06] px-6">
      <div className="flex items-center gap-3">
        <span className="text-[13px] font-semibold tracking-wide text-slate-100">
          NeonatalGuard
        </span>
        <span className="text-[10px] uppercase tracking-[0.25em] text-slate-500">showtime</span>
        <span className="font-mono text-[11px] text-slate-500">· {trace.patient_id}</span>
      </div>
      <div className="flex items-center gap-4">
        <div className="font-mono text-[11px] text-slate-500">
          {clock} · <span className="uppercase">{phase}</span>
        </div>
        <span
          className="rounded-md px-2.5 py-1 text-[11px] font-semibold"
          style={{ background: `${vc}1e`, color: vc, boxShadow: `0 0 16px ${vc}44` }}
        >
          VERDICT · {v.level}
        </span>
      </div>
    </div>
  );
}

// ---- shell -------------------------------------------------------------------

export function ShowtimeShell({ trace }: { trace: Trace }) {
  return (
    <PlayheadProvider grid={trace.time_grid}>
      <div className="fixed inset-0 flex flex-col text-slate-100" style={{ background: "#070b12" }}>
        <TopBar trace={trace} />
        <div className="flex min-h-0 flex-1">
          <aside className="w-[340px] shrink-0 space-y-3.5 overflow-y-auto border-r border-white/[0.06] p-3.5">
            <DataInPanel trace={trace} />
            <Tier1Panel trace={trace} />
            <Tier2Panel trace={trace} />
          </aside>
          <HeroStage trace={trace} />
          <aside className="w-[380px] shrink-0 overflow-y-auto border-l border-white/[0.06] p-3.5">
            <Tier3Panel trace={trace} />
          </aside>
        </div>
        <Timeline />
      </div>
    </PlayheadProvider>
  );
}
