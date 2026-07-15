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
}

const Ctx = createContext<PlayheadState | null>(null);

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
  const pRef = useRef(0);
  const playingRef = useRef(false);

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
    if (pRef.current >= grid.n - 1) setP(0);
    setPlayingCb(!playingRef.current);
  }, [grid.n, setP, setPlayingCb]);

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
  };

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
