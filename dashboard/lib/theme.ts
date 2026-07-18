/**
 * Clinical-noir design tokens — one source for the palettes that were previously hardcoded
 * across the showtime components (concernColor, PHASE_COLOR, TIER, AMBER). Re-theming is now
 * one edit, not a scavenger hunt. Values are unchanged from the originals.
 */

/** Concern-level palette (GREEN < YELLOW < RED), the clinical mapping. */
export const CONCERN = { GREEN: "#22c55e", YELLOW: "#eab308", RED: "#ef4444" } as const;

/** Per-tier accent hues, so the eye tracks a tier across panels (spec §3). */
export const TIER = { t1: "#38bdf8", t2: "#a78bfa", t3: "#fbbf24" } as const;

/** Scenario-phase hues used by the 3-D now-marker + beat cues. */
export const PHASE = { normal: "#38bdf8", onset: "#fbbf24", sustained: "#ef4444" } as const;
