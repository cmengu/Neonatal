"use client";

/**
 * Elevated clinical-noir tier panels (#63).
 *
 * Turns the showtime rail's compact sparklines into legible, cinematic charts on the
 * shared playhead: data-in with the normal band + band-exit, Tier 1 deviation with a
 * per-feature chart, a concordance-highlighted feature grid, and the persistent
 * Safety-Floor track; Tier 2 with the C⁺-vs-h trajectory, its crossing, and the
 * quiet-gate table. Every value is read verbatim from the #30 trace (Ledger H3) — the
 * chart frame is the only thing authored here. Reuses the theme-aware `TraceChart`.
 */

import { ReactNode } from "react";
import { DataChannel, Tier1, Tier1Feature, Tier2 } from "@/lib/trace-types";
import { TraceChart, ChartSeries } from "@/components/trace/TraceChart";
import { usePlayhead } from "@/components/trace/playhead";

const TIER = { t1: "#38bdf8", t2: "#a78bfa" } as const;

function concernColor(level: string): string {
  return level === "RED" ? "#ef4444" : level === "YELLOW" ? "#eab308" : "#22c55e";
}
function fmt(v: number): string {
  return String(Math.abs(v) >= 100 ? Math.round(v) : Math.round(v * 10) / 10);
}
function valueAt(points: number[], p: number): number {
  const i = Math.max(0, Math.min(points.length - 1, Math.round(p)));
  return points[i] ?? 0;
}

function NoirCard({
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
        {tag && <span className="text-[9px] uppercase tracking-wider text-slate-600">{tag}</span>}
      </div>
      {children}
    </div>
  );
}

/** Header readout shared by the charts: now-value + ok/flag + baseline. */
function Readout({
  now,
  breached,
  base,
  unit,
}: {
  now: number;
  breached: boolean;
  base?: string;
  unit?: string;
}) {
  const col = breached ? "#f87171" : "#6ee7b7";
  return (
    <div className="text-right font-mono">
      <span className="text-[15px] font-semibold text-slate-100">{fmt(now)}</span>
      {unit && <span className="ml-1 text-[10px] text-slate-500">{unit}</span>}
      <span className="ml-2 text-[10px] uppercase" style={{ color: col }}>
        {breached ? "flag" : "ok"}
      </span>
      {base != null && <div className="text-[10px] text-slate-600">base {base}</div>}
    </div>
  );
}

// ---- Data-in --------------------------------------------------------------------

function channelSeries(ch: DataChannel): ChartSeries {
  return {
    points: ch.samples,
    band: ch.band,
    failureIdx: ch.band_exit_idx,
    color: ch.real ? "#38bdf8" : "#c084fc",
    unit: ch.unit,
  };
}

export function DataInPanel({ trace }: { trace: { data_in: { channels: DataChannel[] }; time_grid: { labels: string[] } } }) {
  const { p } = usePlayhead();
  const labels = trace.time_grid.labels;
  const chans = trace.data_in.channels.filter((c) => c.real).slice(0, 2);
  return (
    <NoirCard accent="#64748b" label="Data in" tag="telemetry">
      <div className="space-y-3">
        {chans.map((ch) => {
          const now = valueAt(ch.samples, p);
          const breached = ch.band && (now < ch.band.low || now > ch.band.high);
          return (
            <div key={ch.key}>
              <div className="mb-1 flex items-baseline justify-between">
                <span className="font-mono text-[11px] text-slate-300">
                  {ch.label} <span className="text-slate-600">{ch.unit}</span>
                  {!ch.real && (
                    <span className="ml-1.5 rounded border border-amber-500/40 px-1 py-px text-[8px] uppercase text-amber-400">
                      simulated
                    </span>
                  )}
                </span>
                <Readout now={now} breached={!!breached} unit={ch.unit} />
              </div>
              <TraceChart series={channelSeries(ch)} labels={labels} theme="dark" height={104} />
            </div>
          );
        })}
        <Legend band exit />
      </div>
    </NoirCard>
  );
}

// ---- Tier 1 deviation -----------------------------------------------------------

function featureSeries(f: Tier1Feature): ChartSeries {
  return {
    points: f.z_series,
    band: { low: -f.z_trigger, high: f.z_trigger },
    failureIdx: f.failure_idx,
    color: f.flagged ? "#f87171" : "#38bdf8",
    unit: "z",
  };
}

/** The persistent Safety-Floor track — a time strip that latches to the floor color at breach. */
function FloorTrack({ tier1, n }: { tier1: Tier1; n: number }) {
  const { p } = usePlayhead();
  const engage = Math.min(
    ...tier1.features.filter((f) => f.flagged && f.failure_idx != null && f.failure_idx >= 0).map((f) => f.failure_idx as number),
    n,
  );
  const fc = concernColor(tier1.floor.level);
  const engagePct = (Math.min(engage, n - 1) / (n - 1)) * 100;
  const headPct = (Math.max(0, Math.min(n - 1, Math.round(p))) / (n - 1)) * 100;
  return (
    <div className="mt-2">
      <div className="mb-1 flex items-center justify-between text-[9px] uppercase tracking-wider text-slate-600">
        <span>Safety-Floor track</span>
        <span style={{ color: fc }}>
          {tier1.floor.kind} · {tier1.floor.level} · {tier1.floor.concordant_count} concordant
        </span>
      </div>
      <div className="relative h-2.5 overflow-hidden rounded-full" style={{ background: "#1e293b" }}>
        {/* pre-engage: monitoring green; post-engage: latched floor color (un-lowerable) */}
        <div className="absolute inset-y-0 left-0" style={{ width: `${engagePct}%`, background: "#22c55e33" }} />
        <div
          className="absolute inset-y-0"
          style={{ left: `${engagePct}%`, right: 0, background: `${fc}`, boxShadow: `0 0 12px ${fc}` }}
        />
        <div className="absolute inset-y-0 w-0.5 bg-white/80" style={{ left: `${headPct}%` }} />
      </div>
      <div className="mt-1 text-[9px] text-slate-600">
        latches at window {engage} · un-lowerable by any later tier
      </div>
    </div>
  );
}

export function Tier1Panel({ trace }: { trace: { tier1: Tier1; time_grid: { labels: string[]; n: number } } }) {
  const { p } = usePlayhead();
  const t1 = trace.tier1;
  const labels = trace.time_grid.labels;
  const flagged = t1.features.filter((f) => f.flagged);
  const lead =
    flagged.length > 0
      ? flagged.reduce((a, b) => (Math.abs(valueAt(b.z_series, p)) > Math.abs(valueAt(a.z_series, p)) ? b : a))
      : t1.features[0];
  const now = lead ? valueAt(lead.z_series, p) : 0;
  return (
    <NoirCard accent={TIER.t1} label="Tier 1 · Deviation" tag="z vs personal baseline">
      {lead && (
        <>
          <div className="mb-1 flex items-baseline justify-between">
            <span className="font-mono text-[11px] text-slate-300">
              {lead.label}
              {t1.indicators.includes(lead.key) && (
                <span className="ml-1.5 text-[9px] uppercase text-sky-400">concordant</span>
              )}
            </span>
            <Readout now={now} breached={lead.flagged} unit="z" base={fmt(lead.baseline.mean)} />
          </div>
          <TraceChart series={featureSeries(lead)} labels={labels} theme="dark" height={118} />
        </>
      )}
      {/* every feature as a chip, concordant ones ringed */}
      <div className="mt-2.5 grid grid-cols-2 gap-1.5">
        {t1.features.map((f) => {
          const z = valueAt(f.z_series, p);
          const col = f.flagged ? "#f87171" : f.trigger_feature ? "#94a3b8" : "#475569";
          const concordant = t1.indicators.includes(f.key);
          return (
            <div
              key={f.key}
              className="flex items-center justify-between rounded border px-1.5 py-1 font-mono text-[10px]"
              style={{
                borderColor: concordant ? `${TIER.t1}66` : "rgba(255,255,255,0.06)",
                background: concordant ? `${TIER.t1}0f` : "transparent",
              }}
            >
              <span className="truncate text-slate-400" title={f.label}>
                {f.label}
                {!f.trigger_feature && <span className="text-slate-700"> ·d</span>}
              </span>
              <span style={{ color: col }}>{z >= 0 ? "+" : ""}{z.toFixed(1)}</span>
            </div>
          );
        })}
      </div>
      <FloorTrack tier1={t1} n={trace.time_grid.n} />
      <Legend band z deviation />
    </NoirCard>
  );
}

// ---- Tier 2 CUSUM ---------------------------------------------------------------

export function Tier2Panel({ trace }: { trace: { tier2: Tier2; time_grid: { labels: string[] } } }) {
  const { p } = usePlayhead();
  const t2 = trace.tier2;
  const labels = trace.time_grid.labels;
  const now = valueAt(t2.c_plus_series, p);
  const idx = Math.max(0, Math.min(t2.c_plus_series.length - 1, Math.round(p)));
  const crossed = t2.crossing_idx != null && idx >= t2.crossing_idx;
  const pct = Math.min(100, (now / (t2.h || 1)) * 100);
  return (
    <NoirCard accent={TIER.t2} label="Tier 2 · CUSUM drift" tag="C⁺ accumulation">
      <div className="mb-1 flex items-baseline justify-between">
        <span className="font-mono text-[11px] text-slate-300">C⁺ vs decision interval h</span>
        <div className="text-right font-mono">
          <span className="text-[15px] font-semibold" style={{ color: crossed ? "#f87171" : "#c4b5fd" }}>
            {now.toFixed(1)}
          </span>
          <span className="text-[11px] text-slate-500"> / {t2.h}</span>
          <div className="text-[10px] uppercase" style={{ color: crossed ? "#f87171" : "#6ee7b7" }}>
            {crossed ? "drift fired" : "accumulating"}
          </div>
        </div>
      </div>
      <TraceChart
        series={{ points: t2.c_plus_series, band: null, threshold: t2.h, failureIdx: t2.crossing_idx, color: "#a78bfa", unit: "C⁺" }}
        labels={labels}
        theme="dark"
        height={126}
      />
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-800">
        <div
          className="h-full rounded-full transition-all duration-200"
          style={{ width: `${pct}%`, background: crossed ? "#ef4444" : TIER.t2 }}
        />
      </div>
      {/* quiet-gate table */}
      <div className="mt-3">
        <div className="mb-1.5 flex items-center justify-between text-[9px] uppercase tracking-wider text-slate-600">
          <span>Quiet gates</span>
          <span style={{ color: t2.quiet.may_quiet ? "#6ee7b7" : "#f87171" }}>
            may_quiet {t2.quiet.may_quiet ? "✓" : "✗"}
          </span>
        </div>
        <div className="space-y-1">
          {t2.quiet.gates.map((g) => (
            <div key={g.key} className="flex items-start justify-between gap-2 text-[10.5px]">
              <span className="text-slate-400">
                <span className="font-mono font-bold" style={{ color: g.pass ? "#6ee7b7" : "#f87171" }}>
                  {g.pass ? "✓" : "✗"}
                </span>{" "}
                {g.label}
              </span>
              <span className="shrink-0 text-right font-mono text-[9px] text-slate-600">{g.detail}</span>
            </div>
          ))}
        </div>
        <p className="mt-1.5 text-[9.5px] leading-relaxed text-slate-600">{t2.quiet.note}</p>
      </div>
      <Legend threshold h={t2.h} cross />
    </NoirCard>
  );
}

// ---- shared legend --------------------------------------------------------------

function Legend({
  band,
  z,
  exit,
  deviation,
  threshold,
  cross,
  h,
}: {
  band?: boolean;
  z?: boolean;
  exit?: boolean;
  deviation?: boolean;
  threshold?: boolean;
  cross?: boolean;
  h?: number;
}) {
  return (
    <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 font-mono text-[9px] text-slate-500">
      {band && (
        <span className="inline-flex items-center gap-1">
          <i className="inline-block h-2 w-3 rounded-sm" style={{ background: "rgba(34,197,94,0.25)" }} />
          {z ? "±z_trigger band" : "baseline band"}
        </span>
      )}
      {exit && (
        <span className="inline-flex items-center gap-1">
          <i className="inline-block h-2 w-2 rounded-full bg-rose-400" /> band exit
        </span>
      )}
      {deviation && (
        <span className="inline-flex items-center gap-1">
          <i className="inline-block h-2 w-2 rounded-full bg-rose-400" /> deviation
        </span>
      )}
      {threshold && (
        <span className="inline-flex items-center gap-1 text-rose-300">
          <i className="inline-block w-3 border-t border-dashed border-rose-400" /> threshold h={h}
        </span>
      )}
      {cross && (
        <span className="inline-flex items-center gap-1">
          <i className="inline-block h-2 w-2 rounded-full bg-rose-400" /> crossing
        </span>
      )}
    </div>
  );
}
