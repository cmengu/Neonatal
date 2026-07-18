"use client";

import { useCallback, useRef } from "react";
import { usePlayhead } from "./playhead";

/**
 * Shared timeline scrubber (#29 v3 item 11). One playhead drives every chart on
 * the page; the three phase windows come straight from the trace's
 * recorder-computed grid.phases.
 */
export function Timeline() {
  const { p, grid, setP, playing, togglePlay, setPlaying, clock, phase, demo, startDemo, stopDemo } =
    usePlayhead();
  const trackRef = useRef<HTMLDivElement>(null);
  const scrubbing = useRef(false);

  const n = grid.n;
  const pct = (p / (n - 1)) * 100;

  const seek = useCallback(
    (clientX: number) => {
      const el = trackRef.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      setP(((clientX - r.left) / r.width) * (n - 1));
    },
    [setP, n],
  );

  const zonePct = (range: [number, number] | null): { left: number; width: number } | null => {
    if (!range) return null;
    return {
      left: (range[0] / (n - 1)) * 100,
      width: ((range[1] - range[0] + 1) / (n - 1)) * 100,
    };
  };

  const normal = zonePct(grid.phases.normal);
  const onset = zonePct(grid.phases.onset);
  const sustained = zonePct(grid.phases.sustained);

  const jump = (range: [number, number] | null) => {
    if (!range) return;
    stopDemo();
    setPlaying(false);
    setP(Math.round((range[0] + range[1]) / 2));
  };

  return (
    <div className="flex items-center gap-4 px-5 h-[72px] bg-[#0b1220] border-b border-slate-800">
      <button
        onClick={togglePlay}
        title="play / pause"
        className="w-9 h-9 rounded-full flex-none bg-sky-400 text-slate-950 text-[15px] font-bold flex items-center justify-center hover:brightness-110"
      >
        {playing ? "❚❚" : "▶"}
      </button>
      <button
        onClick={() => (demo ? stopDemo() : startDemo())}
        title="choreographed demo"
        className={`h-9 flex-none rounded-full px-3.5 text-[11px] font-semibold uppercase tracking-wider flex items-center gap-1.5 transition-colors ${
          demo
            ? "bg-amber-400 text-slate-950 hover:brightness-110"
            : "border border-amber-400/50 text-amber-300 hover:bg-amber-400/10"
        }`}
      >
        {demo ? "◼ stop" : "✨ demo"}
      </button>

      <div className="flex-1">
        <div className="flex font-mono text-[10.5px] uppercase tracking-wider mb-1.5">
          <button className="flex-1 flex items-center gap-1.5 text-slate-500 hover:text-slate-200" onClick={() => jump(grid.phases.normal)}>
            <span className="w-2 h-2 rounded-sm bg-emerald-500" /> Normal window
          </button>
          <button className="flex-1 flex items-center gap-1.5 text-slate-500 hover:text-slate-200" onClick={() => jump(grid.phases.onset)}>
            <span className="w-2 h-2 rounded-sm bg-amber-500" /> Onset · deviation flagged
          </button>
          <button className="flex-1 flex items-center gap-1.5 text-slate-500 hover:text-slate-200" onClick={() => jump(grid.phases.sustained)}>
            <span className="w-2 h-2 rounded-sm bg-red-500" /> Sustained
          </button>
        </div>
        <div
          ref={trackRef}
          className="relative h-[22px] rounded-md overflow-hidden cursor-pointer border border-slate-800"
          onPointerDown={(e) => {
            scrubbing.current = true;
            stopDemo();
            setPlaying(false);
            e.currentTarget.setPointerCapture(e.pointerId);
            seek(e.clientX);
          }}
          onPointerMove={(e) => scrubbing.current && seek(e.clientX)}
          onPointerUp={() => (scrubbing.current = false)}
        >
          {normal && <div className="absolute top-0 bottom-0 bg-emerald-500/[0.16]" style={{ left: `${normal.left}%`, width: `${normal.width}%` }} />}
          {onset && <div className="absolute top-0 bottom-0 bg-amber-500/[0.18]" style={{ left: `${onset.left}%`, width: `${onset.width}%` }} />}
          {sustained && <div className="absolute top-0 bottom-0 bg-red-500/[0.18]" style={{ left: `${sustained.left}%`, width: `${sustained.width}%` }} />}
          {onset && <div className="absolute top-0 bottom-0 w-px bg-slate-400/35" style={{ left: `${onset.left}%` }} />}
          {sustained && <div className="absolute top-0 bottom-0 w-px bg-slate-400/35" style={{ left: `${sustained.left}%` }} />}
          <div className="absolute -top-[3px] -bottom-[3px] w-0.5 bg-white shadow-[0_0_8px_rgba(255,255,255,0.6)]" style={{ left: `${pct}%` }}>
            <span className="absolute -left-[5px] -top-1 w-3 h-3 rounded-full bg-white" />
          </div>
        </div>
      </div>

      <div className="font-mono text-[13px] text-slate-200 whitespace-nowrap min-w-[128px] text-right">
        <b className="text-sky-400">{clock}</b>
        <span className="block text-[10px] text-slate-500 uppercase tracking-wide">{phase}</span>
      </div>
    </div>
  );
}
