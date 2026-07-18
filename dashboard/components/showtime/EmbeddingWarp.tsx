"use client";

/**
 * EmbeddingWarp — the 3-D embedding-warp centerpiece (#62).
 *
 * The demo's hero. Renders the REAL JEPA world-model trajectory (`trace.world_model`,
 * exported in #60) as a 3-D scene on the shared playhead: this infant's learned-normal
 * cloud, the window-by-window latent path colored by time, a pulsing now-marker, and a
 * reference lattice whose floor **ripples with novelty** — the "space warping every second."
 *
 * Hand-rolled Canvas-2D perspective projection (no three.js / r3f): the dashboard is
 * deliberately dependency-light (hand-rolled sparklines elsewhere), the point count is tiny
 * (~600), and this keeps `next build` bullet-proof. Spec §8's vanilla fallback, taken one
 * step further for robustness; swap to react-three-fiber later if true WebGL depth is wanted.
 *
 * Honesty (#60 finding, spec §7): the raw 3-D *position* drift is modest — the departure is
 * diffuse across embedding dims — so the drama is driven by **novelty** (full-D Mahalanobis
 * distance, unit = calm-SD), which rises to ~2× the calm cloud-edge. The now-marker glow and
 * the lattice ripple scale with novelty; the PC axes carry no accuracy number, only what they
 * are. The caption states exactly that.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { WorldModel } from "@/lib/trace-types";
import { usePlayhead } from "@/components/trace/playhead";

type Vec3 = [number, number, number];

const PHASE_COLOR = { normal: "#38bdf8", onset: "#fbbf24", sustained: "#ef4444" } as const;
// Trajectory time-gradient: cool (early) → warm (late).
const COOL: Vec3 = [56, 189, 248]; // #38bdf8
const WARM: Vec3 = [239, 68, 68]; // #ef4444

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}
function mix(a: Vec3, b: Vec3, t: number): string {
  return `rgb(${Math.round(lerp(a[0], b[0], t))}, ${Math.round(lerp(a[1], b[1], t))}, ${Math.round(
    lerp(a[2], b[2], t),
  )})`;
}

/** Rotate then perspective-project a world point to screen space. Returns null if behind camera. */
function project(
  p: Vec3,
  az: number,
  el: number,
  dist: number,
  focal: number,
  cx: number,
  cy: number,
): { x: number; y: number; depth: number; scale: number } | null {
  const [px, py, pz] = p;
  // yaw around vertical (Y)
  const ca = Math.cos(az);
  const sa = Math.sin(az);
  const x = px * ca + pz * sa;
  let z = -px * sa + pz * ca;
  let y = py;
  // pitch around X
  const ce = Math.cos(el);
  const se = Math.sin(el);
  const y2 = y * ce - z * se;
  const z2 = y * se + z * ce;
  y = y2;
  z = z2;
  const depth = z + dist;
  if (depth <= 0.05) return null;
  const s = focal / depth;
  return { x: cx + x * s, y: cy - y * s, depth, scale: s };
}

export function EmbeddingWarp({ wm }: { wm: WorldModel }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { p, phase, clock, reduced } = usePlayhead();

  // Live playhead + orbit state read by the RAF loop without re-subscribing each frame.
  const pRef = useRef(p);
  pRef.current = p;
  const phaseRef = useRef(phase);
  phaseRef.current = phase;
  const orbit = useRef({ az: 0.7, el: 0.32, dragging: false, lastX: 0, lastY: 0, auto: true });
  const projectedRef = useRef<{ x: number; y: number; idx: number }[]>([]);
  const [hover, setHover] = useState<{ x: number; y: number; idx: number } | null>(null);

  // World-space scale: normalise every coordinate by the max magnitude across cloud + path,
  // then blow up to a fixed world radius so the camera framing is stable regardless of infant.
  const { cloud, path, norm, R } = useMemo(() => {
    const traj = wm.trajectory.map((t) => t.pca3 as Vec3);
    const cl = wm.normal_cloud as Vec3[];
    let m = 1e-6;
    for (const q of [...traj, ...cl]) for (const v of q) m = Math.max(m, Math.abs(v));
    return { cloud: cl, path: traj, norm: m, R: 2.2 };
  }, [wm]);

  const nAt = useCallback((i: number) => wm.trajectory[i]?.novelty ?? 0, [wm]);
  const sAt = useCallback((i: number) => wm.trajectory[i]?.surprise ?? 0, [wm]);
  const cloudEdge = wm.novelty_baseline_p95 || 1;

  // Interpolated readouts for the HUD (fractional playhead).
  const i0 = Math.max(0, Math.min(wm.trajectory.length - 1, Math.floor(p)));
  const i1 = Math.min(wm.trajectory.length - 1, i0 + 1);
  const tt = p - i0;
  const noveltyNow = lerp(nAt(i0), nAt(i1), tt);
  const surpriseNow = lerp(sAt(i0), sAt(i1), tt);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let raf = 0;
    let t0 = 0;
    let elapsed = 0;

    const sx = (v: Vec3): Vec3 => [(v[0] / norm) * R, (v[1] / norm) * R, (v[2] / norm) * R];
    const worldCloud = cloud.map(sx);
    const worldPath = path.map(sx);

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const rect = canvas.getBoundingClientRect();
      canvas.width = Math.max(1, Math.floor(rect.width * dpr));
      canvas.height = Math.max(1, Math.floor(rect.height * dpr));
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    const draw = (ts: number) => {
      if (!t0) t0 = ts;
      const dt = Math.min(0.05, (ts - t0) / 1000);
      t0 = ts;
      if (!reduced) elapsed += dt;

      const rect = canvas.getBoundingClientRect();
      const W = rect.width;
      const H = rect.height;
      const cx = W * 0.5;
      const cy = H * 0.52;
      const focal = Math.min(W, H) * 0.9;
      const dist = R * 3.4;

      const o = orbit.current;
      if (o.auto && !o.dragging && !reduced) o.az += dt * 0.12;
      const az = o.az;
      const el = o.el;

      ctx.clearRect(0, 0, W, H);

      const pv = pRef.current;
      const j0 = Math.max(0, Math.min(worldPath.length - 1, Math.floor(pv)));
      const j1 = Math.min(worldPath.length - 1, j0 + 1);
      const ft = pv - j0;
      const now: Vec3 = [
        lerp(worldPath[j0][0], worldPath[j1][0], ft),
        lerp(worldPath[j0][1], worldPath[j1][1], ft),
        lerp(worldPath[j0][2], worldPath[j1][2], ft),
      ];
      const nov = lerp(nAt(j0), nAt(j1), ft);
      const novR = nov / cloudEdge; // >1 ⇒ outside the learned-normal cloud

      // ---- reference lattice floor that ripples with novelty (the "warp") ----
      const GRID = 13;
      const half = R * 1.32;
      const floorY = -R * 1.05;
      // radial wave emanating from the now-marker's ground projection; taller as novelty grows
      const amp = R * 0.16 * (0.35 + Math.min(2.4, novR));
      const waveH = (wx: number, wz: number): number => {
        const rad = Math.hypot(wx - now[0], wz - now[2]);
        return Math.sin(rad * 2.1 - elapsed * 2.4) * Math.exp(-rad * 0.55);
      };
      const gx2w = (g: number) => -half + (g / (GRID - 1)) * half * 2;
      const gpt = (gx: number, gz: number): { v: Vec3; h: number } => {
        const wx = gx2w(gx);
        const wz = gx2w(gz);
        const h = waveH(wx, wz);
        return { v: [wx, floorY + h * amp, wz], h };
      };
      ctx.lineWidth = 1;
      for (let gx = 0; gx < GRID; gx++) {
        for (let gz = 0; gz < GRID; gz++) {
          const g0 = gpt(gx, gz);
          const a = project(g0.v, az, el, dist, focal, cx, cy);
          if (!a) continue;
          for (const [ox, oz] of [
            [1, 0],
            [0, 1],
          ] as const) {
            if (gx + ox >= GRID || gz + oz >= GRID) continue;
            const g1 = gpt(gx + ox, gz + oz);
            const b = project(g1.v, az, el, dist, focal, cx, cy);
            if (!b) continue;
            // brighten lines lifted by the ripple (|wave| high) — the crests catch the light
            const lift = Math.min(1, (Math.abs(g0.h) + Math.abs(g1.h)) * 0.5);
            ctx.strokeStyle = `rgba(56, 189, 248, ${0.04 + lift * 0.24})`;
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.stroke();
          }
        }
      }

      // ---- collect drawables for painter's-algorithm depth sort ----
      type Item = { depth: number; render: () => void };
      const items: Item[] = [];

      // learned-normal cloud
      for (const c of worldCloud) {
        const pr = project(c, az, el, dist, focal, cx, cy);
        if (!pr) continue;
        const r = Math.max(0.6, pr.scale * 0.011);
        items.push({
          depth: pr.depth,
          render: () => {
            ctx.fillStyle = "rgba(125, 211, 252, 0.22)";
            ctx.beginPath();
            ctx.arc(pr.x, pr.y, r, 0, Math.PI * 2);
            ctx.fill();
          },
        });
      }

      // trajectory path up to the playhead, colored cool→warm by time
      const upTo = Math.min(worldPath.length - 1, Math.ceil(pv));
      for (let i = 1; i <= upTo; i++) {
        const a = project(worldPath[i - 1], az, el, dist, focal, cx, cy);
        const b = project(worldPath[i], az, el, dist, focal, cx, cy);
        if (!a || !b) continue;
        const tcol = i / (worldPath.length - 1);
        const comet = i > pv - 14; // brighten the last ~14 windows (the comet trail)
        items.push({
          depth: (a.depth + b.depth) * 0.5,
          render: () => {
            ctx.strokeStyle = mix(COOL, WARM, tcol);
            ctx.globalAlpha = comet ? 0.95 : 0.5;
            ctx.lineWidth = comet ? 2.1 : 1.3;
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.stroke();
            ctx.globalAlpha = 1;
          },
        });
      }

      // now-marker: pulsing node, glow ∝ novelty, color by phase
      const nm = project(now, az, el, dist, focal, cx, cy);
      if (nm) {
        const col = PHASE_COLOR[phaseRef.current];
        const pulse = reduced ? 1 : 0.82 + 0.18 * Math.sin(elapsed * 3.6);
        const glow = (18 + Math.min(2.6, novR) * 34) * pulse;
        items.push({
          depth: nm.depth - 1e-3, // draw in front of coincident path
          render: () => {
            const g = ctx.createRadialGradient(nm.x, nm.y, 0, nm.x, nm.y, glow);
            g.addColorStop(0, col);
            g.addColorStop(0.25, `${col}aa`);
            g.addColorStop(1, `${col}00`);
            ctx.fillStyle = g;
            ctx.beginPath();
            ctx.arc(nm.x, nm.y, glow, 0, Math.PI * 2);
            ctx.fill();
            ctx.fillStyle = "#fff";
            ctx.beginPath();
            ctx.arc(nm.x, nm.y, 3.2 * pulse, 0, Math.PI * 2);
            ctx.fill();
          },
        });
      }

      items.sort((a, b) => b.depth - a.depth);
      for (const it of items) it.render();

      // ---- labelled PC axes (drawn on top, in front) ----
      const axes: { v: Vec3; label: string }[] = [
        { v: [R * 1.15, 0, 0], label: wm.pca.axis_labels[0] },
        { v: [0, R * 1.15, 0], label: wm.pca.axis_labels[1] },
        { v: [0, 0, R * 1.15], label: wm.pca.axis_labels[2] },
      ];
      const origin = project([0, 0, 0], az, el, dist, focal, cx, cy);
      if (origin) {
        for (const ax of axes) {
          const tip = project(ax.v, az, el, dist, focal, cx, cy);
          if (!tip) continue;
          ctx.strokeStyle = "rgba(148, 163, 184, 0.35)";
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(origin.x, origin.y);
          ctx.lineTo(tip.x, tip.y);
          ctx.stroke();
          ctx.fillStyle = "rgba(148, 163, 184, 0.75)";
          ctx.font = "10px ui-monospace, monospace";
          ctx.fillText(ax.label, tip.x + 3, tip.y - 2);
        }
      }

      // cache projected path points for hover hit-testing
      const proj: { x: number; y: number; idx: number }[] = [];
      for (let i = 0; i < worldPath.length; i++) {
        const pr = project(worldPath[i], az, el, dist, focal, cx, cy);
        if (pr) proj.push({ x: pr.x, y: pr.y, idx: i });
      }
      projectedRef.current = proj;

      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, [wm, cloud, path, norm, R, reduced, cloudEdge, nAt, sAt]);

  // ---- pointer interaction: orbit-drag + hover tooltip ----
  const onDown = (e: React.PointerEvent) => {
    const o = orbit.current;
    o.dragging = true;
    o.auto = false;
    o.lastX = e.clientX;
    o.lastY = e.clientY;
    e.currentTarget.setPointerCapture(e.pointerId);
    (e.currentTarget as HTMLElement).style.cursor = "grabbing";
  };
  const onMove = (e: React.PointerEvent) => {
    const o = orbit.current;
    if (o.dragging) {
      o.az += (e.clientX - o.lastX) * 0.008;
      o.el = Math.max(-1.2, Math.min(1.2, o.el + (e.clientY - o.lastY) * 0.006));
      o.lastX = e.clientX;
      o.lastY = e.clientY;
      return;
    }
    // hover: nearest projected path point within threshold
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    let best: { x: number; y: number; idx: number } | null = null;
    let bd = 14 * 14;
    for (const q of projectedRef.current) {
      const d = (q.x - mx) ** 2 + (q.y - my) ** 2;
      if (d < bd) {
        bd = d;
        best = q;
      }
    }
    setHover(best);
  };
  const onUp = (e: React.PointerEvent) => {
    orbit.current.dragging = false;
    e.currentTarget.releasePointerCapture?.(e.pointerId);
    (e.currentTarget as HTMLElement).style.cursor = "grab";
  };

  const outside = noveltyNow > cloudEdge;

  return (
    <div className="relative flex-1 overflow-hidden">
      <div className="absolute inset-0 noir-grid opacity-30" />
      <div className="absolute inset-0 noir-vignette" />

      <canvas
        ref={canvasRef}
        className="absolute inset-0 h-full w-full cursor-grab touch-none"
        onPointerDown={onDown}
        onPointerMove={onMove}
        onPointerUp={onUp}
        onPointerLeave={() => setHover(null)}
      />

      {/* header */}
      <div className="pointer-events-none absolute left-1/2 top-5 -translate-x-1/2 text-center">
        <div className="text-[11px] uppercase tracking-[0.3em] text-slate-500">
          World model · JEPA latent embedding
        </div>
        <div className="mt-0.5 font-mono text-[9.5px] text-slate-600">
          PC1 {(wm.pca.variance_explained[0] * 100).toFixed(0)}% · PC2{" "}
          {(wm.pca.variance_explained[1] * 100).toFixed(0)}% · PC3{" "}
          {(wm.pca.variance_explained[2] * 100).toFixed(0)}% variance · basis fit on normal phase
        </div>
      </div>

      {/* live novelty / surprise readout */}
      <div className="pointer-events-none absolute right-6 top-5 text-right font-mono">
        <div className="text-[10px] text-slate-500">novelty vs learned normal</div>
        <div
          className="text-2xl leading-tight"
          style={{ color: outside ? PHASE_COLOR[phase] : "#7dd3fc" }}
        >
          {noveltyNow.toFixed(2)}
          <span className="ml-1 text-[10px] text-slate-500">calm-SD</span>
        </div>
        <div className="mt-0.5 text-[10px] text-slate-500">
          cloud edge {cloudEdge.toFixed(2)} · {outside ? "outside" : "inside"}
        </div>
        <div className="mt-2 text-[10px] text-slate-500">surprise</div>
        <div className="text-sm" style={{ color: surpriseNow > 0 ? "#fbbf24" : "#64748b" }}>
          {surpriseNow >= 0 ? "+" : ""}
          {surpriseNow.toFixed(2)}
          <span className="ml-1 text-[9px] text-slate-500">SD</span>
        </div>
      </div>

      {/* hover tooltip */}
      {hover && (
        <div
          className="pointer-events-none absolute z-10 rounded border border-white/10 bg-black/70 px-1.5 py-1 font-mono text-[9.5px] text-slate-200"
          style={{ left: hover.x + 10, top: hover.y + 8 }}
        >
          window {wm.trajectory[hover.idx]?.idx ?? hover.idx} · {wm.window[0] + hover.idx}
          <br />
          novelty {nAt(hover.idx).toFixed(2)} · surprise {sAt(hover.idx) >= 0 ? "+" : ""}
          {sAt(hover.idx).toFixed(2)}
        </div>
      )}

      {/* honest caption */}
      <div className="pointer-events-none absolute bottom-4 left-1/2 max-w-[560px] -translate-x-1/2 px-4 text-center">
        <div className="font-mono text-[9.5px] leading-relaxed text-slate-600">{wm.caption}</div>
        <div className="mt-1 text-[9px] text-slate-700">
          drag to orbit · {clock} · warp intensity tracks novelty (real JEPA output)
        </div>
      </div>
    </div>
  );
}
