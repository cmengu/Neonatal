"use client";

import { ReactNode } from "react";
import { Trace } from "@/lib/trace-types";
import { PlayheadProvider, usePlayhead } from "@/components/trace/playhead";
import { Timeline } from "@/components/trace/Timeline";
import { EmbeddingWarp } from "@/components/showtime/EmbeddingWarp";
import { DataInPanel, Tier1Panel, Tier2Panel } from "@/components/showtime/TierPanels";

/**
 * ShowtimeShell — the immersive stage (#61).
 *
 * One `PlayheadProvider` owns the shared clock; every panel reads it via `usePlayhead()`
 * so the whole page scrubs together. Layout is the spec's hero + HUD: elevated tier rail
 * (left, #63), the real 3-D world-model hero (center, #62), the agent theater (right),
 * and the shared timeline scrubber (bottom). The agent theater gets its cinematic
 * treatment in #64.
 */

const TIER = { t3: "#fbbf24" } as const;

function concernColor(level: string): string {
  return level === "RED" ? "#ef4444" : level === "YELLOW" ? "#eab308" : "#22c55e";
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
        {tag && <span className="text-[9px] uppercase tracking-wider text-slate-600">{tag}</span>}
      </div>
      {children}
    </div>
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

export function ShowtimeShell({ trace }: { trace: Trace }) {
  return (
    <PlayheadProvider grid={trace.time_grid}>
      <div className="fixed inset-0 flex flex-col text-slate-100" style={{ background: "#070b12" }}>
        <TopBar trace={trace} />
        <div className="flex min-h-0 flex-1">
          <aside className="w-[384px] shrink-0 space-y-3.5 overflow-y-auto border-r border-white/[0.06] p-3.5">
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
