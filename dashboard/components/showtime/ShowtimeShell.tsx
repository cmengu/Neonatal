"use client";

import { Trace } from "@/lib/trace-types";
import { PlayheadProvider, usePlayhead } from "@/components/trace/playhead";
import { Timeline } from "@/components/trace/Timeline";
import { EmbeddingWarp } from "@/components/showtime/EmbeddingWarp";
import { DataInPanel, Tier1Panel, Tier2Panel } from "@/components/showtime/TierPanels";
import { AgentTheater } from "@/components/showtime/AgentTheater";

/**
 * ShowtimeShell — the immersive stage (#61).
 *
 * One `PlayheadProvider` owns the shared clock; every panel reads it via `usePlayhead()`
 * so the whole page scrubs together. Layout is the spec's hero + HUD: elevated tier rail
 * (left, #63), the real 3-D world-model hero (center, #62), the agent-reasoning theater
 * (right, #64), and the shared timeline scrubber (bottom).
 */

function concernColor(level: string): string {
  return level === "RED" ? "#ef4444" : level === "YELLOW" ? "#eab308" : "#22c55e";
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

/** Cinematic beat caption shown while demo-mode choreographs the run (#66). */
function DemoBeatOverlay() {
  const { beat, demo } = usePlayhead();
  if (!beat) return null;
  return (
    <div className="pointer-events-none absolute bottom-6 left-1/2 z-20 w-[min(560px,80%)] -translate-x-1/2">
      <div
        className="glass animate-[noir-float-up_0.4s_ease-out] rounded-xl border border-white/[0.08] px-5 py-3 text-center"
        style={{ boxShadow: "0 8px 40px rgba(0,0,0,0.5)" }}
      >
        <div className="flex items-center justify-center gap-2">
          {demo && <span className="h-1.5 w-1.5 rounded-full bg-amber-400 motion-safe:animate-pulse" />}
          <span className="text-[12px] font-semibold uppercase tracking-[0.2em] text-slate-100">
            {beat.title}
          </span>
        </div>
        <p className="mt-1 text-[11.5px] leading-relaxed text-slate-400">{beat.sub}</p>
      </div>
    </div>
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
        <div className="relative flex min-h-0 flex-1">
          <aside className="w-[384px] shrink-0 space-y-3.5 overflow-y-auto border-r border-white/[0.06] p-3.5">
            <DataInPanel trace={trace} />
            <Tier1Panel trace={trace} />
            <Tier2Panel trace={trace} />
          </aside>
          <HeroStage trace={trace} />
          <aside className="w-[380px] shrink-0 overflow-y-auto border-l border-white/[0.06] p-3.5">
            <AgentTheater trace={trace} />
          </aside>
          <DemoBeatOverlay />
        </div>
        <Timeline />
      </div>
    </PlayheadProvider>
  );
}
