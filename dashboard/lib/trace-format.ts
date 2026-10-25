/**
 * Shared trace formatting helpers — one home for the small functions the trace/showtime
 * panels all need, so they can't silently diverge (the `valueAt` copies in panels.tsx and
 * the showtime rail had already drifted). Pure, presentational, no playhead access.
 */

import { CONCERN } from "./theme";

/** Clinical concern → its palette hex. GREEN < YELLOW < RED. */
export function concernColor(level: string): string {
  return level === "RED" ? CONCERN.RED : level === "YELLOW" ? CONCERN.YELLOW : CONCERN.GREEN;
}

/** Compact numeric label: whole numbers ≥100, else one decimal. */
export function fmt(v: number): string {
  return String(Math.abs(v) >= 100 ? Math.round(v) : Math.round(v * 10) / 10);
}

/** Value of a per-window series at the (fractional) playhead, clamped to range. */
export function valueAt(points: number[], p: number): number {
  const i = Math.max(0, Math.min(points.length - 1, Math.round(p)));
  return points[i] ?? 0;
}
