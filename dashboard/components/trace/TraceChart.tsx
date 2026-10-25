"use client";

import { useEffect, useRef } from "react";
import { usePlayhead } from "./playhead";

export interface ChartSeries {
  /** The value plotted per grid index. */
  points: number[];
  /** Optional normal band drawn behind the trace. */
  band?: { low: number; high: number } | null;
  /** Optional horizontal threshold line (e.g. CUSUM h). */
  threshold?: number | null;
  /** Index where the series first deviates — pulsed once the playhead passes it. */
  failureIdx?: number | null;
  color: string;
  unit: string;
}

type Theme = "light" | "dark";

interface TraceChartProps {
  series: ChartSeries;
  labels: string[];
  height?: number;
  big?: boolean;
  /** "light" for the /trace route; "dark" for the clinical-noir showtime shell (#63). */
  theme?: Theme;
}

/** Per-theme chart chrome. Data colors come from the series; only the frame changes. */
const PALETTES: Record<Theme, {
  bg: string | null;
  grid: string;
  tick: string;
  axis: string;
  faint: string;
  playhead: string;
  bandFill: string;
  bandStroke: string;
  threshold: string;
  marker: string;
}> = {
  light: {
    bg: "#fbfdff",
    grid: "#e6edf5",
    tick: "#8494a8",
    axis: "#64748b",
    faint: "rgba(100,116,139,0.26)",
    playhead: "rgba(30,41,59,0.5)",
    bandFill: "rgba(16,185,129,0.10)",
    bandStroke: "rgba(16,185,129,0.35)",
    threshold: "#dc2626",
    marker: "#dc2626",
  },
  dark: {
    bg: null, // transparent — let the noir panel show through
    grid: "rgba(148,163,184,0.12)",
    tick: "#64748b",
    axis: "#94a3b8",
    faint: "rgba(148,163,184,0.24)",
    playhead: "rgba(226,232,240,0.42)",
    bandFill: "rgba(34,197,94,0.12)",
    bandStroke: "rgba(34,197,94,0.42)",
    threshold: "#f87171",
    marker: "#f87171",
  },
};

function fmt(v: number): number {
  return Math.abs(v) >= 100 ? Math.round(v) : Math.round(v * 10) / 10;
}

/**
 * Canvas line chart. Full faint series, a bold segment up to the shared playhead,
 * band + threshold + labelled axes, and a pulsing dot at the deviation point. All
 * charts on the page share one playhead. `theme` swaps the frame (light for the
 * /trace route, dark for the showtime shell) without touching the series colors.
 */
export function TraceChart({ series, labels, height = 130, big = false, theme = "light" }: TraceChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { p, reduced } = usePlayhead();
  const n = series.points.length;

  useEffect(() => {
    const cv = canvasRef.current;
    if (!cv) return;
    const dpr = window.devicePixelRatio || 1;
    const w = cv.clientWidth || 300;
    const h = height;
    cv.width = w * dpr;
    cv.height = h * dpr;
    const ctx = cv.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const c = PALETTES[theme];
    const m = big
      ? { l: 66, r: 22, t: 16, b: 44 }
      : { l: 46, r: 12, t: 10, b: 26 };
    const pts = series.points;

    let lo = Infinity;
    let hi = -Infinity;
    for (const v of pts) {
      if (v < lo) lo = v;
      if (v > hi) hi = v;
    }
    if (series.band) {
      lo = Math.min(lo, series.band.low);
      hi = Math.max(hi, series.band.high);
    }
    if (series.threshold != null) hi = Math.max(hi, series.threshold);
    const pad = (hi - lo) * 0.12 + 1e-6;
    const min = lo - pad;
    const max = hi + pad;

    const pw = w - m.l - m.r;
    const ph = h - m.t - m.b;
    const X = (i: number) => m.l + (i / (n - 1)) * pw;
    const Y = (v: number) => m.t + ph - ((v - min) / (max - min)) * ph;
    const fs = big ? 13 : 10;

    ctx.clearRect(0, 0, w, h);
    if (c.bg) {
      ctx.fillStyle = c.bg;
      ctx.fillRect(0, 0, w, h);
    }

    // y ticks
    ctx.font = `${fs}px ui-monospace, monospace`;
    ctx.textBaseline = "middle";
    ctx.strokeStyle = c.grid;
    ctx.lineWidth = 1;
    [min, (min + max) / 2, max].forEach((yv) => {
      ctx.beginPath();
      ctx.moveTo(m.l, Y(yv));
      ctx.lineTo(w - m.r, Y(yv));
      ctx.stroke();
      ctx.fillStyle = c.tick;
      ctx.textAlign = "right";
      ctx.fillText(String(fmt(yv)), m.l - 6, Y(yv));
    });

    // x ticks
    ctx.textBaseline = "top";
    ctx.textAlign = "center";
    [0, Math.floor(n / 2), n - 1].forEach((xi) => {
      ctx.fillStyle = c.tick;
      ctx.fillText(labels[xi] ?? "", X(xi), h - m.b + 6);
    });

    // axis titles
    ctx.fillStyle = c.axis;
    ctx.textBaseline = "alphabetic";
    ctx.textAlign = "center";
    ctx.fillText("time", m.l + pw / 2, h - (big ? 12 : 6));
    ctx.save();
    ctx.translate(big ? 18 : 12, m.t + ph / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = "center";
    ctx.fillText(series.unit || "value", 0, 0);
    ctx.restore();

    // band
    if (series.band) {
      ctx.fillStyle = c.bandFill;
      ctx.fillRect(m.l, Y(series.band.high), pw, Y(series.band.low) - Y(series.band.high));
      ctx.strokeStyle = c.bandStroke;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(m.l, Y(series.band.low));
      ctx.lineTo(w - m.r, Y(series.band.low));
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(m.l, Y(series.band.high));
      ctx.lineTo(w - m.r, Y(series.band.high));
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // threshold
    if (series.threshold != null) {
      ctx.strokeStyle = c.threshold;
      ctx.setLineDash([5, 3]);
      ctx.lineWidth = 1.3;
      ctx.beginPath();
      ctx.moveTo(m.l, Y(series.threshold));
      ctx.lineTo(w - m.r, Y(series.threshold));
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // faint full series
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      if (i) ctx.lineTo(X(i), Y(pts[i]));
      else ctx.moveTo(X(i), Y(pts[i]));
    }
    ctx.strokeStyle = c.faint;
    ctx.lineWidth = 1;
    ctx.stroke();

    // bold up to playhead
    const head = Math.max(0, Math.min(n - 1, Math.round(p)));
    ctx.beginPath();
    for (let j = 0; j <= head; j++) {
      if (j) ctx.lineTo(X(j), Y(pts[j]));
      else ctx.moveTo(X(j), Y(pts[j]));
    }
    ctx.strokeStyle = series.color;
    ctx.lineWidth = big ? 2.4 : 1.9;
    ctx.stroke();

    // playhead line + dot
    ctx.strokeStyle = c.playhead;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(X(head), m.t);
    ctx.lineTo(X(head), m.t + ph);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(X(head), Y(pts[head]), big ? 3.6 : 2.6, 0, Math.PI * 2);
    ctx.fillStyle = series.color;
    ctx.fill();

    // deviation marker (static; RAF is owned by the playhead, not per-chart)
    if (series.failureIdx != null && series.failureIdx >= 0 && head >= series.failureIdx) {
      const fx = X(series.failureIdx);
      const fy = Y(pts[series.failureIdx]);
      const pulse = 0.5;
      ctx.beginPath();
      ctx.arc(fx, fy, (big ? 4 : 3) + pulse * 2, 0, Math.PI * 2);
      ctx.fillStyle = c.marker;
      ctx.fill();
      ctx.beginPath();
      ctx.arc(fx, fy, (big ? 7 : 5) + pulse * (big ? 10 : 7), 0, Math.PI * 2);
      ctx.strokeStyle = theme === "dark" ? `rgba(248,113,113,${0.5 - pulse * 0.4})` : `rgba(220,38,38,${0.5 - pulse * 0.4})`;
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }
  }, [p, series, labels, height, big, n, reduced, theme]);

  return (
    <canvas
      ref={canvasRef}
      className="block w-full rounded-md"
      style={{ height, background: PALETTES[theme].bg ?? "transparent" }}
    />
  );
}
