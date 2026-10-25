"use client";

import { useState } from "react";
import { DataChannel, Tier1, Tier1Feature, Tier2, Tier3 } from "@/lib/trace-types";
import { TraceChart, ChartSeries } from "./TraceChart";
import { usePlayhead } from "./playhead";

function valueAt(points: number[], p: number): number {
  const i = Math.max(0, Math.min(points.length - 1, Math.round(p)));
  return points[i];
}
function fmt(v: number): string {
  return String(Math.abs(v) >= 100 ? Math.round(v) : Math.round(v * 10) / 10);
}

/** One graph card: header readout + chart + legend. Reads the shared playhead for its "now" value. */
function GraphCard({
  name,
  unit,
  base,
  series,
  labels,
  flagged,
  threshold,
  simulated,
  tall,
}: {
  name: string;
  unit: string;
  base: number | string;
  series: ChartSeries;
  labels: string[];
  flagged: boolean;
  threshold?: number | null;
  simulated?: boolean;
  tall?: boolean;
}) {
  const { p } = usePlayhead();
  const now = valueAt(series.points, p);
  const breached =
    (series.band && (now < series.band.low || now > series.band.high)) ||
    (threshold != null && now >= threshold);

  return (
    <div
      className={`relative bg-white border rounded-[10px] p-3 mb-3 last:mb-0 ${
        flagged ? "border-[#f3c6c6] shadow-[inset_4px_0_0_#dc2626]" : "border-[#cbd7e6] shadow-[inset_4px_0_0_#059669]"
      }`}
    >
      <div className="flex items-baseline justify-between mb-2">
        <div className="font-mono text-sm text-slate-800 font-semibold">
          {name} <span className="text-[#8494a8] font-normal text-xs">{unit}</span>
          {simulated && (
            <span className="ml-2 font-mono text-[10px] uppercase tracking-wide text-amber-700 bg-amber-100 border border-amber-300 rounded px-1.5 py-0.5">
              simulated
            </span>
          )}
        </div>
        <div className="font-mono text-[13px] text-right">
          <span className="text-slate-800 font-bold text-[15px]">{fmt(now)}</span>{" "}
          <span className={`text-[11px] uppercase ${breached ? "text-[#dc2626]" : "text-[#059669]"}`}>
            {breached ? "flag" : "ok"}
          </span>
          <div className="text-[#8494a8] text-[11px]">base {base}</div>
        </div>
      </div>
      <TraceChart series={series} labels={labels} height={tall ? 230 : 130} />
      <div className="flex flex-wrap gap-3 mt-2 font-mono text-[11px] text-[#52627a]">
        <span className="inline-flex items-center gap-1.5" style={{ color: series.color }}>
          <i className="w-3.5 border-t-2 border-current inline-block" /> reading
        </span>
        {series.band && (
          <span className="inline-flex items-center gap-1.5">
            <i className="w-3.5 h-2.5 bg-emerald-500/20 rounded-sm inline-block" /> baseline band
          </span>
        )}
        {threshold != null && (
          <span className="inline-flex items-center gap-1.5 text-[#dc2626]">
            <i className="w-3.5 border-t-2 border-dashed border-[#dc2626] inline-block" /> threshold h={threshold}
          </span>
        )}
        <span className="inline-flex items-center gap-1.5">
          <i className="w-2.5 h-2.5 rounded-full bg-[#dc2626] inline-block" /> deviation
        </span>
      </div>
    </div>
  );
}

function CollapsibleGroup({
  tag,
  count,
  bad,
  defaultOpen,
  children,
}: {
  tag: string;
  count: string;
  bad: boolean;
  defaultOpen: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="mb-3 last:mb-0">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2.5 font-mono text-[12.5px] uppercase tracking-wide text-[#52627a] px-3 py-2.5 rounded-lg bg-[#e2eaf4] hover:bg-[#d8e2ee]"
      >
        <span className={`font-bold ${bad ? "text-[#dc2626]" : "text-[#059669]"}`}>● {tag}</span>
        <span className="text-[#8494a8]">{count}</span>
        <span className={`ml-auto transition-transform ${open ? "" : "-rotate-90"}`}>▾</span>
      </button>
      {open && <div className="pt-2.5">{children}</div>}
    </div>
  );
}

/** Plain-English tier verdict — rendered verbatim from the trace (Ledger H3), never authored here. */
function Statement({ text, warn }: { text: string; warn?: boolean }) {
  return (
    <div
      className={`mt-3 bg-white border border-[#cbd7e6] rounded-[10px] p-3.5 ${
        warn ? "border-l-4 border-l-[#d97706]" : "border-l-4 border-l-[#dc2626]"
      }`}
    >
      <div className="font-mono text-[10px] tracking-wider uppercase text-[#8494a8] mb-1.5">Tier verdict</div>
      <p className="m-0 text-sm leading-relaxed text-slate-800">{text}</p>
    </div>
  );
}

function toChannelSeries(ch: DataChannel): ChartSeries {
  return {
    points: ch.samples,
    band: ch.band,
    failureIdx: ch.band_exit_idx,
    color: ch.real ? "#2563eb" : "#9333ea",
    unit: ch.unit,
  };
}

export function DataInPanel({ channels, labels }: { channels: DataChannel[]; labels: string[] }) {
  return (
    <div>
      {channels.map((ch) => (
        <GraphCard
          key={ch.key}
          name={ch.label}
          unit={ch.unit}
          base={ch.samples[0]}
          series={toChannelSeries(ch)}
          labels={labels}
          flagged={ch.flagged}
          simulated={!ch.real}
        />
      ))}
    </div>
  );
}

function toFeatureSeries(f: Tier1Feature): ChartSeries {
  return {
    points: f.value_series,
    band: {
      low: f.baseline.mean - f.baseline.std * f.z_trigger,
      high: f.baseline.mean + f.baseline.std * f.z_trigger,
    },
    failureIdx: f.failure_idx,
    color: f.flagged ? "#dc2626" : "#059669",
    unit: "",
  };
}

export function Tier1Panel({ tier1, labels }: { tier1: Tier1; labels: string[] }) {
  const flagged = tier1.features.filter((f) => f.flagged);
  const within = tier1.features.filter((f) => !f.flagged);
  return (
    <div>
      <CollapsibleGroup tag="Flagged" count={`${flagged.length} features`} bad defaultOpen>
        {flagged.map((f) => (
          <GraphCard
            key={f.key}
            name={f.label}
            unit=""
            base={fmt(f.baseline.mean)}
            series={toFeatureSeries(f)}
            labels={labels}
            flagged
          />
        ))}
      </CollapsibleGroup>
      <CollapsibleGroup tag="Within baseline" count={`${within.length} features`} bad={false} defaultOpen={false}>
        {within.map((f) => (
          <GraphCard
            key={f.key}
            name={f.label}
            unit={f.trigger_feature ? "" : "· display-only"}
            base={fmt(f.baseline.mean)}
            series={toFeatureSeries(f)}
            labels={labels}
            flagged={false}
          />
        ))}
      </CollapsibleGroup>
      <Statement text={tier1.verdict_text} />
    </div>
  );
}

export function Tier2Panel({ tier2, labels }: { tier2: Tier2; labels: string[] }) {
  return (
    <div>
      <GraphCard
        name="CUSUM C⁺"
        unit=""
        base={0}
        series={{
          points: tier2.c_plus_series,
          band: null,
          threshold: tier2.h,
          failureIdx: tier2.crossing_idx,
          color: "#dc2626",
          unit: "",
        }}
        labels={labels}
        flagged={tier2.fired}
        threshold={tier2.h}
        tall
      />
      <div className="mt-3 bg-white border border-[#cbd7e6] rounded-[10px] p-3.5">
        <div className="font-mono text-[10px] tracking-wider uppercase text-[#8494a8] mb-2">Quiet gates — why may_quiet = {tier2.quiet.may_quiet ? "✓" : "✗"}</div>
        <table className="w-full text-[13px] text-slate-800">
          <tbody>
            {tier2.quiet.gates.map((g) => (
              <tr key={g.key} className="border-b border-slate-100 last:border-0">
                <td className="py-1.5 pr-2">
                  <span className={`font-mono font-bold ${g.pass ? "text-[#059669]" : "text-[#dc2626]"}`}>{g.pass ? "✓" : "✗"}</span>{" "}
                  {g.label}
                </td>
                <td className="py-1.5 text-right font-mono text-[11px] text-[#8494a8]">{g.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-2 mb-0 font-mono text-[11px] text-[#52627a]">{tier2.quiet.note}</p>
      </div>
      <Statement text={tier2.verdict_text} warn />
    </div>
  );
}

export function Tier3Panel({ tier3 }: { tier3: Tier3 }) {
  const [openCite, setOpenCite] = useState<string | null>(null);
  if (!tier3.ran) {
    return (
      <div className="bg-white border border-[#cbd7e6] rounded-[10px] p-3.5 text-sm text-[#52627a]">
        Tier 3 was skipped — the merged Tier 1 + Tier 2 level was GREEN, so the reasoning tier did not run on this window.
      </div>
    );
  }
  return (
    <div>
      <div className="bg-white border border-[#cbd7e6] rounded-[10px] p-3.5 mb-3">
        <span className="font-mono text-[11px] tracking-wider uppercase text-sky-500 bg-sky-50 inline-block px-2.5 py-1 rounded-md mb-2.5">
          1 · Retrieve
        </span>
        <p className="text-[13px] text-[#52627a] mb-2 font-mono">query: <b className="text-slate-800">{tier3.query}</b></p>
        <ul className="list-none m-0 p-0">
          {tier3.retrieved.map((r) => (
            <li key={r.id} className="text-[13px] text-[#52627a] pl-[18px] relative mb-1.5">
              <b className="text-slate-800">{r.source}</b> — {r.snippet}
            </li>
          ))}
        </ul>
      </div>

      <div className="bg-white border border-[#cbd7e6] rounded-[10px] p-3.5 mb-3">
        <span className="font-mono text-[11px] tracking-wider uppercase text-sky-500 bg-sky-50 inline-block px-2.5 py-1 rounded-md mb-2.5">
          2 · Reason
        </span>
        <p className="text-sm leading-relaxed text-slate-800 m-0">{tier3.reasoning}</p>
      </div>

      <div className="bg-white border border-[#cbd7e6] rounded-[10px] p-3.5 mb-3">
        <span className="font-mono text-[11px] tracking-wider uppercase text-[#059669] bg-emerald-50 inline-block px-2.5 py-1 rounded-md mb-2.5">
          3 · Self-check
        </span>
        <div className="flex items-center gap-2 text-[13px] text-[#52627a] mb-1.5">
          <span className={`font-mono font-bold ${tier3.self_check.passed ? "text-[#059669]" : "text-[#dc2626]"}`}>
            {tier3.self_check.passed ? "✓" : "✗"}
          </span>
          {tier3.self_check.note}
        </div>
        <div className="flex items-center gap-2 text-[13px] text-[#52627a]">
          <span className="font-mono font-bold text-[#059669]">✓</span>
          {tier3.escalate_only_note}
        </div>
      </div>

      <div className="flex flex-wrap gap-2 mt-2.5">
        {tier3.retrieved.map((r) => (
          <button
            key={r.id}
            onClick={() => setOpenCite((c) => (c === r.id ? null : r.id))}
            className="font-mono text-[11.5px] text-sky-700 border border-[#bfdbec] bg-sky-50 px-2.5 py-1 rounded-md hover:border-sky-400"
          >
            {r.source} ▾
          </button>
        ))}
      </div>
      {tier3.retrieved
        .filter((r) => r.id === openCite)
        .map((r) => (
          <div key={r.id} className="mt-2 text-[12.5px] text-[#52627a] leading-relaxed border-l-2 border-[#bfdbec] pl-3 py-1.5">
            [{r.id}] {r.snippet}
          </div>
        ))}
    </div>
  );
}
