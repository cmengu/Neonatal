"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { TimeGrid } from "@/lib/trace-types";

export interface DemoBeat {
  title: string;
  sub: string;
}

interface PlayheadState {
  /** Fractional index 0..n-1. */
  p: number;
  playing: boolean;
  grid: TimeGrid;
  setP: (p: number) => void;
  togglePlay: () => void;
  setPlaying: (v: boolean) => void;
  /** Phase name at the current playhead. */
  phase: "normal" | "onset" | "sustained";
  clock: string;
  reduced: boolean;
  /** Choreographed demo-mode (#66): auto-plays the curated beat sheet on the shared clock. */
  demo: boolean;
  startDemo: () => void;
  stopDemo: () => void;
  /** The current narrated beat while demo-mode runs (null otherwise). */
  beat: DemoBeat | null;
}

const Ctx = createContext<PlayheadState | null>(null);

// The choreography (#66, spec §2): keyframes map demo-time fraction → timeline fraction, so
// the run moves briskly through the calm baseline and *lingers* on the drama (onset → sustained
// → verdict). Piecewise-linear between keyframes; time-based so pacing is framerate-independent.
const DEMO_SECONDS = 52;
const DEMO_KEYS: [number, number][] = [
  [0.0, 0.0],
  [0.15, 0.45],
  [0.45, 0.62],
  [0.75, 0.8],
  [0.92, 1.0],
  [1.0, 1.0],
];

function demoTimelineFrac(tf: number): number {
  for (let i = 1; i < DEMO_KEYS.length; i++) {
    const [t1, p1] = DEMO_KEYS[i];
    if (tf <= t1) {
      const [t0, p0] = DEMO_KEYS[i - 1];
      const u = t1 === t0 ? 1 : (tf - t0) / (t1 - t0);
      return p0 + (p1 - p0) * u;
    }
  }
  return 1;
}

function beatFor(pf: number): DemoBeat {
  if (pf >= 0.985) return { title: "Verdict · RED", sub: "The cascade merges to RED — the Safety Floor holds; Tier 3 concurs, escalate-only." };
  if (pf >= 0.75) return { title: "Sustained", sub: "CUSUM confirms the drift; the embedding leaves the learned-normal cloud and surprise rises." };
  if (pf >= 0.5) return { title: "Onset", sub: "Tier 1 deviations flag against this infant's baseline; the world model starts to drift." };
  return { title: "Baseline", sub: "infant7 sits in its learned-normal cloud — every tier calm on one shared clock." };
}

export function usePlayhead(): PlayheadState {
  const v = useContext(Ctx);
  if (!v) throw new Error("usePlayhead outside PlayheadProvider");
  return v;
}

function phaseAt(grid: TimeGrid, p: number): "normal" | "onset" | "sustained" {
  const idx = Math.round(p);
  const { onset, sustained } = grid.phases;
  if (sustained && idx >= sustained[0]) return "sustained";
  if (onset && idx >= onset[0]) return "onset";
  return "normal";
}

export function PlayheadProvider({
  grid,
  children,
}: {
  grid: TimeGrid;
  children: React.ReactNode;
}) {
  const [p, setPState] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [reduced, setReduced] = useState(false);
  const [demo, setDemo] = useState(false);
  const [beat, setBeat] = useState<DemoBeat | null>(null);
  const pRef = useRef(0);
  const playingRef = useRef(false);
  const demoStartRef = useRef<number | null>(null);

  useEffect(() => {
    setReduced(
      window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    );
  }, []);

  const setP = useCallback(
    (next: number) => {
      const clamped = Math.max(0, Math.min(grid.n - 1, next));
      pRef.current = clamped;
      setPState(clamped);
    },
    [grid.n],
  );

  const setPlayingCb = useCallback((v: boolean) => {
    playingRef.current = v;
    setPlaying(v);
  }, []);

  const togglePlay = useCallback(() => {
    setDemo(false);
    setBeat(null);
    if (pRef.current >= grid.n - 1) setP(0);
    setPlayingCb(!playingRef.current);
  }, [grid.n, setP, setPlayingCb]);

  const startDemo = useCallback(() => {
    setPlayingCb(false);
    setP(0);
    demoStartRef.current = null;
    setBeat(beatFor(0));
    setDemo(true);
  }, [setP, setPlayingCb]);

  const stopDemo = useCallback(() => {
    setDemo(false);
    setBeat(null);
  }, []);

  // Single RAF driver advances the shared playhead when playing.
  useEffect(() => {
    if (!playing || reduced) return;
    let raf = 0;
    const tick = () => {
      const next = pRef.current + 0.45;
      if (next >= grid.n - 1) {
        setP(grid.n - 1);
        setPlayingCb(false);
        return;
      }
      setP(next);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, reduced, grid.n, setP, setPlayingCb]);

  // Choreographed demo driver (#66): time-based (RAF timestamp), so pacing is identical at
  // any framerate. Eases through the keyframes, narrates the beat, then drops into free-scrub.
  useEffect(() => {
    if (!demo) return;
    let raf = 0;
    const tick = (ts: number) => {
      if (demoStartRef.current == null) demoStartRef.current = ts;
      const elapsed = (ts - demoStartRef.current) / 1000;
      const tf = Math.min(1, elapsed / DEMO_SECONDS);
      const pf = demoTimelineFrac(tf);
      setP(pf * (grid.n - 1));
      setBeat(beatFor(pf));
      if (tf >= 1) {
        setP(grid.n - 1);
        setBeat({ title: "Explore", sub: "Scrub the timeline — every panel and the 3-D move together on the one clock." });
        setDemo(false);
        return;
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [demo, grid.n, setP]);

  const value: PlayheadState = {
    p,
    playing,
    grid,
    setP,
    togglePlay,
    setPlaying: setPlayingCb,
    phase: phaseAt(grid, p),
    clock: grid.labels[Math.round(p)] ?? "",
    reduced,
    demo,
    startDemo,
    stopDemo,
    beat,
  };

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
