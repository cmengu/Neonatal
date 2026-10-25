"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Trace } from "@/lib/trace-types";
import { CONCERN_TO_LABEL } from "@/lib/types";
import { usePlayhead } from "./playhead";
import { DataInPanel, Tier1Panel, Tier2Panel, Tier3Panel } from "./panels";

const NODE_W = 460;
const XS = [20, 520, 1020, 1520, 2020];
const NODE_TOP = 150;
const STEP_MS = 700;

type NodeKey = "data" | "t1" | "t2" | "t3" | "verdict";
const ORDER: NodeKey[] = ["data", "t1", "t2", "t3", "verdict"];

function TierNode({
  id,
  kicker,
  title,
  desc,
  x,
  open,
  arrived,
  onToggle,
  isData,
  children,
}: {
  id: string;
  kicker: string;
  title: string;
  desc: string;
  x: number;
  open: boolean;
  arrived: boolean;
  onToggle: () => void;
  isData?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div
      id={id}
      className={`absolute rounded-[14px] bg-slate-900 border transition-[border-color,opacity,transform] duration-500 ${
        arrived ? "opacity-100 translate-y-0" : "opacity-25 translate-y-1.5"
      } ${open ? "border-sky-400" : "border-slate-800 hover:border-slate-600"}`}
      style={{ width: NODE_W, left: x, top: NODE_TOP }}
    >
      <button
        onClick={onToggle}
        className="w-full text-left px-5 py-4 cursor-pointer select-none"
      >
        <div className="font-mono text-[11px] tracking-wider text-slate-500 uppercase">{kicker}</div>
        <div className={`text-lg font-semibold mt-1.5 flex items-center gap-2 ${isData ? "text-sky-400" : "text-slate-100"}`}>
          {title}
          <span className={`ml-auto text-[13px] text-slate-500 transition-transform ${open ? "rotate-180 text-sky-400" : ""}`}>▾</span>
        </div>
        <div className="text-[13px] text-slate-400 mt-1 font-mono">{desc}</div>
      </button>
      {open && (
        <div className="border-t border-slate-800 p-4 bg-[#eef3fa] rounded-b-[14px]">
          <div className="max-h-[780px] overflow-y-auto pr-1.5">{children}</div>
        </div>
      )}
    </div>
  );
}

export function TraceCanvas({ trace }: { trace: Trace }) {
  const { setP, setPlaying, reduced } = usePlayhead();
  const labels = trace.time_grid.labels;
  const verdict = trace.verdict;

  const [open, setOpen] = useState<Record<NodeKey, boolean>>({
    data: true,
    t1: true,
    t2: true,
    t3: false,
    verdict: false,
  });
  const [arrived, setArrived] = useState<Record<NodeKey, boolean>>({
    data: false,
    t1: false,
    t2: false,
    t3: false,
    verdict: false,
  });
  const [floorSet, setFloorSet] = useState(false);
  const [litEdges, setLitEdges] = useState(0);
  const [reportOpen, setReportOpen] = useState(false);
  const [toast, setToast] = useState(false);

  // pan / zoom
  const viewportRef = useRef<HTMLDivElement>(null);
  const [transform, setTransform] = useState({ x: 14, y: 8, scale: 1 });
  const panning = useRef(false);
  const moved = useRef(false);
  const start = useRef({ x: 0, y: 0 });

  const toggle = (k: NodeKey) => {
    if (moved.current) return;
    setOpen((o) => ({ ...o, [k]: !o[k] }));
  };

  const focusLeft = useCallback(() => {
    const vw = viewportRef.current?.clientWidth ?? 1200;
    const W = XS[1] + NODE_W + 60;
    setTransform({ x: 14, y: 8, scale: Math.min(vw / W, 1.1) });
  }, []);

  const fitAll = useCallback(() => {
    const vp = viewportRef.current;
    if (!vp) return;
    const W = 2540;
    const H = 640;
    const scale = Math.min(vp.clientWidth / W, vp.clientHeight / H, 1.0) * 0.96;
    setTransform({ x: (vp.clientWidth - 2540 * scale) / 2, y: 16 * scale, scale });
  }, []);

  const runTrace = useCallback(() => {
    setArrived({ data: false, t1: false, t2: false, t3: false, verdict: false });
    setFloorSet(false);
    setLitEdges(0);
    setP(0);
    setPlaying(false);
    const step = reduced ? 0 : STEP_MS;
    ORDER.forEach((k, i) => {
      setTimeout(() => {
        setArrived((a) => ({ ...a, [k]: true }));
        if (k === "t1" && trace.tier1.floor.kind !== "NONE") setFloorSet(true);
        setLitEdges((n) => Math.max(n, i));
        if (k === "verdict" && !reduced) setPlaying(true);
      }, step * (i + 1));
    });
  }, [reduced, setP, setPlaying, trace.tier1.floor.kind]);

  useEffect(() => {
    focusLeft();
    runTrace();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const vp = viewportRef.current;
    if (!vp) return;
    const s2 = Math.min(2.5, Math.max(0.2, transform.scale * Math.exp(-e.deltaY * 0.0016)));
    const r = vp.getBoundingClientRect();
    const cx = e.clientX - r.left;
    const cy = e.clientY - r.top;
    setTransform((t) => ({
      x: cx - (cx - t.x) * (s2 / t.scale),
      y: cy - (cy - t.y) * (s2 / t.scale),
      scale: s2,
    }));
  };

  const zoomBy = (f: number) => {
    const vp = viewportRef.current;
    if (!vp) return;
    const s2 = Math.min(2.5, Math.max(0.2, transform.scale * f));
    const cx = vp.clientWidth / 2;
    const cy = vp.clientHeight / 2;
    setTransform((t) => ({
      x: cx - (cx - t.x) * (s2 / t.scale),
      y: cy - (cy - t.y) * (s2 / t.scale),
      scale: s2,
    }));
  };

  const escalate = () => {
    setToast(true);
    setTimeout(() => setToast(false), 3200);
  };

  const floorLabel = trace.tier1.floor.kind === "HARD" ? "RED set ▲" : trace.tier1.floor.kind === "SOFT" ? "soft floor" : "ungraded";

  return (
    <>
      <div className="flex items-center gap-3 px-[18px] h-[54px] border-b border-slate-800 bg-[#0a0e16] relative z-20">
        <a href="/" className="font-mono text-[12.5px] px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-100">
          ← Ward
        </a>
        <span className="text-sm font-bold flex items-center gap-2">
          Infant {trace.patient_id.replace("infant", "").padStart(2, "0")}
          <span className="font-mono text-[10px] tracking-wide px-1.5 py-0.5 rounded text-red-400 bg-red-950 border border-red-900">
            {CONCERN_TO_LABEL[verdict.level]}
          </span>
        </span>
        <div className="flex-1" />
        <span className="font-mono text-[11px] text-slate-500 hidden md:inline">drag to pan · scroll to zoom · click a node</span>
        <div className="flex gap-1">
          <button onClick={() => zoomBy(0.8)} className="font-mono text-[12.5px] px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-100">−</button>
          <button onClick={() => zoomBy(1.25)} className="font-mono text-[12.5px] px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-100">+</button>
          <button onClick={fitAll} className="font-mono text-[12.5px] px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-100">⤢ fit all</button>
        </div>
        <button onClick={runTrace} className="font-mono text-[12.5px] px-3 py-1.5 rounded-lg bg-sky-400 border border-sky-400 text-slate-950 font-semibold hover:brightness-110">
          ▶ Run trace
        </button>
      </div>

      <div
        ref={viewportRef}
        onWheel={onWheel}
        onPointerDown={(e) => {
          if ((e.target as HTMLElement).closest(".overflow-y-auto")) return;
          panning.current = true;
          moved.current = false;
          start.current = { x: e.clientX, y: e.clientY };
          // NB: do not capture the pointer here — capturing on pointerdown
          // redirects the ensuing click away from inner node buttons, so a
          // plain click could never expand a tier. Capture only once a drag
          // actually begins (in pointermove).
        }}
        onPointerMove={(e) => {
          if (!panning.current) return;
          const dx = e.clientX - start.current.x;
          const dy = e.clientY - start.current.y;
          if (Math.abs(dx) + Math.abs(dy) > 3) {
            if (!moved.current) {
              moved.current = true;
              (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
            }
            setTransform((t) => ({ ...t, x: t.x + dx, y: t.y + dy }));
            start.current = { x: e.clientX, y: e.clientY };
          }
        }}
        onPointerUp={() => (panning.current = false)}
        className="relative overflow-hidden cursor-grab flex-1"
        style={{
          backgroundImage: "radial-gradient(rgba(148,163,184,0.07) 1px, transparent 1.5px)",
          backgroundSize: "30px 30px",
          touchAction: "none",
        }}
      >
        <div
          className="absolute left-0 top-0"
          style={{
            width: 2600,
            height: 1900,
            transformOrigin: "0 0",
            transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.scale})`,
          }}
        >
          <svg width={2600} height={1900} className="absolute left-0 top-0 pointer-events-none overflow-visible">
            {XS.slice(0, 4).map((x, i) => {
              const x1 = x + NODE_W;
              const x2 = XS[i + 1];
              const y = NODE_TOP + 48;
              const lit = i < litEdges;
              return (
                <path
                  key={i}
                  d={`M ${x1} ${y} C ${x1 + 55} ${y}, ${x2 - 55} ${y}, ${x2 - 6} ${y}`}
                  className={`fill-none transition-[stroke,opacity] duration-300 ${lit ? "stroke-sky-400 opacity-100" : "stroke-slate-600 opacity-40"}`}
                  strokeWidth={2.5}
                />
              );
            })}
          </svg>

          {/* safety floor */}
          <div
            className="absolute rounded-[14px] border border-red-900 bg-red-950/10 px-5 py-3.5 flex items-center gap-6"
            style={{ left: 20, top: 20, width: 2480 }}
          >
            <span className="font-mono text-sm tracking-wider text-red-500 uppercase whitespace-nowrap font-semibold">
              Safety Floor
              <small className="block text-[10px] tracking-wide text-slate-500 mt-0.5 normal-case">lower bound on severity</small>
            </span>
            <div className="flex-1 h-[52px] rounded-[9px] relative overflow-hidden bg-[#0b1424] border border-slate-800">
              <div
                className="absolute left-0 top-0 bottom-0 bg-gradient-to-r from-red-900/50 to-red-500/30 border-r-2 border-red-500 transition-[width] duration-1000"
                style={{ width: floorSet ? "100%" : "0%" }}
              />
              <div className="absolute inset-0 flex">
                {[
                  { k: "input", v: "ungraded", set: false },
                  { k: "Tier 1", v: floorLabel, set: true },
                  { k: "Tier 2", v: "held ≥ floor", set: false },
                  { k: "Tier 3", v: "held ≥ floor", set: false },
                  { k: "verdict", v: "held ≥ floor", set: false },
                ].map((m, i) => (
                  <div
                    key={i}
                    className={`flex-1 flex flex-col items-center justify-center font-mono text-[13px] gap-0.5 border-r border-dashed border-red-900/35 last:border-r-0 ${
                      m.set ? "text-red-500" : "text-slate-400"
                    }`}
                  >
                    <span className={`text-[10px] tracking-wider uppercase ${m.set ? "text-red-500" : "text-slate-500"}`}>{m.k}</span>
                    {m.set ? <b className="text-red-500 text-[15px]">{m.v}</b> : m.v}
                  </div>
                ))}
              </div>
            </div>
            <span className="font-mono text-[12.5px] text-slate-400 whitespace-nowrap max-w-[220px] leading-relaxed">
              <b className="text-red-500">Once set</b> at Tier 1, no later tier can lower it — only raise.
            </span>
          </div>

          <TierNode id="n-data" kicker="Input" title="Data In" desc={`${trace.data_in.channels.length} bedside channels · synced to timeline`} x={XS[0]} open={open.data} arrived={arrived.data} onToggle={() => toggle("data")} isData>
            <DataInPanel channels={trace.data_in.channels} labels={labels} />
          </TierNode>

          <TierNode id="n-t1" kicker="Tier 1 · Deviation" title="Instant math" desc={`${trace.tier1.features.length} HRV features vs own baseline`} x={XS[1]} open={open.t1} arrived={arrived.t1} onToggle={() => toggle("t1")}>
            <Tier1Panel tier1={trace.tier1} labels={labels} />
          </TierNode>

          <TierNode id="n-t2" kicker="Tier 2 · Temporal" title="CUSUM drift" desc="is the deviation a real trend?" x={XS[2]} open={open.t2} arrived={arrived.t2} onToggle={() => toggle("t2")}>
            <Tier2Panel tier2={trace.tier2} labels={labels} />
          </TierNode>

          <TierNode id="n-t3" kicker="Tier 3 · RAG reasoning" title="Guideline grounding" desc="retrieve · reason · self-check" x={XS[3]} open={open.t3} arrived={arrived.t3} onToggle={() => toggle("t3")}>
            <Tier3Panel tier3={trace.tier3} />
          </TierNode>

          {/* verdict node */}
          <div
            className={`absolute rounded-[14px] cursor-pointer transition-[opacity,transform] duration-500 ${arrived.verdict ? "opacity-100 translate-y-0 shadow-[0_10px_40px_rgba(239,68,68,0.12)]" : "opacity-25 translate-y-1.5"}`}
            style={{
              width: 480,
              left: XS[4],
              top: NODE_TOP,
              background: "linear-gradient(180deg, rgba(127,29,29,.12), #0f172a 45%)",
              border: "1px solid #7f1d1d",
            }}
            onClick={() => !moved.current && setReportOpen(true)}
          >
            <div className="flex items-center gap-3 px-[18px] py-4 border-b border-slate-800">
              <span className="text-lg font-bold">Verdict</span>
              <span className="font-mono text-[11.5px] tracking-wide text-red-500 border border-red-900 bg-red-950 px-2 py-1 rounded-md">
                {verdict.level} · {CONCERN_TO_LABEL[verdict.level]}
              </span>
              <span className="ml-auto font-mono text-[11.5px] text-slate-400">
                risk <b className="text-red-500 text-[15px]">{Math.round(verdict.risk * 100)}%</b>
              </span>
            </div>
            <div className="px-[18px] py-4">
              <div className="bg-red-950 border border-red-900 rounded-[9px] px-3.5 py-3">
                <div className="font-mono text-[10.5px] tracking-wider text-red-300 uppercase mb-1.5">Recommended action</div>
                <p className="m-0 text-sm leading-normal text-red-100">{verdict.recommended_action}</p>
              </div>
              <ul className="list-none mt-3.5 p-0 flex flex-col gap-1.5">
                {verdict.assessments.map((a) => (
                  <li key={a.source} className="font-mono text-xs text-slate-400 flex gap-2.5">
                    <span className="text-slate-500 whitespace-nowrap uppercase">{a.source}</span>
                    {a.level} · {a.rationale}
                  </li>
                ))}
              </ul>
              <div className="font-mono text-[11px] text-sky-400 mt-3.5">▤ click for full report</div>
            </div>
            <div className="flex items-center gap-3 px-[18px] py-3.5 border-t border-slate-800">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  escalate();
                }}
                className="font-semibold text-[13.5px] text-white bg-red-500 rounded-[9px] px-4 py-2.5 hover:brightness-110"
              >
                Escalate
              </button>
              <span className="font-mono text-[11px] text-slate-500">pages attending · handoff report</span>
            </div>
          </div>
        </div>
      </div>

      {reportOpen && <ReportModal trace={trace} onClose={() => setReportOpen(false)} />}
      <div
        className={`fixed left-1/2 bottom-6 -translate-x-1/2 bg-[#052e22] border border-emerald-500 text-emerald-200 font-mono text-xs px-4 py-2.5 rounded-[10px] transition-all z-[60] ${
          toast ? "opacity-100 translate-y-0" : "opacity-0 translate-y-5 pointer-events-none"
        }`}
      >
        ✓ Attending paged · report queued
      </div>
    </>
  );
}

function ReportModal({ trace, onClose }: { trace: Trace; onClose: () => void }) {
  const v = trace.verdict;
  return (
    <div className="fixed inset-0 z-[55] bg-slate-950/70 backdrop-blur-sm flex items-center justify-center p-8" onClick={onClose}>
      <div className="w-[min(1040px,96vw)] max-h-[92vh] overflow-hidden flex flex-col bg-[#eef3fa] border border-[#cbd7e6] rounded-2xl shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-3 px-5 py-4 border-b border-[#cbd7e6]">
          <span className="text-[17px] font-bold text-slate-800">Verdict report — Infant {trace.patient_id.replace("infant", "").padStart(2, "0")}</span>
          <span className="font-mono text-xs uppercase tracking-wide px-2.5 py-1 rounded-md text-[#dc2626] bg-[#fdeaea]">
            {v.level} · {CONCERN_TO_LABEL[v.level]}
          </span>
          <button onClick={onClose} className="ml-auto w-8 h-8 rounded-lg border border-[#cbd7e6] bg-white text-[#52627a] hover:bg-[#e2eaf4]">✕</button>
        </div>
        <div className="px-5 py-5 overflow-y-auto">
          <div className="grid grid-cols-2 gap-3 mb-3.5">
            {[
              { k: "Concern level", val: `${v.level} · ${CONCERN_TO_LABEL[v.level]}`, red: true },
              { k: "Deterministic risk", val: v.risk.toFixed(2), red: true },
              { k: "Model confidence", val: v.confidence.toFixed(2), red: false },
              { k: "Safety floor", val: `${v.safety_floor} (${trace.tier1.floor.kind})`, red: true },
            ].map((c) => (
              <div key={c.k} className="bg-white border border-[#cbd7e6] rounded-[10px] px-3.5 py-3">
                <div className="font-mono text-[10px] tracking-wider uppercase text-[#8494a8] mb-1.5">{c.k}</div>
                <div className={`text-[15px] font-semibold ${c.red ? "text-[#dc2626]" : "text-slate-800"}`}>{c.val}</div>
              </div>
            ))}
          </div>
          <ReportSection title="Recommended action">
            <p className="m-0 text-sm leading-relaxed text-slate-800">{v.recommended_action}</p>
          </ReportSection>
          <ReportSection title="Cascade trail">
            <ul className="list-none m-0 p-0">
              {v.assessments.map((a) => (
                <li key={a.source} className="grid grid-cols-[92px_1fr] gap-2.5 py-2 border-b border-slate-100 last:border-0 text-[13.5px] text-slate-800">
                  <span className="font-mono text-[11px] text-[#8494a8] uppercase tracking-wide">{a.source}</span>
                  <span>{a.rationale}</span>
                </li>
              ))}
            </ul>
          </ReportSection>
          <ReportSection title="Primary indicators">
            <p className="m-0 text-sm text-slate-800">{v.primary_indicators.join(", ") || "—"}</p>
          </ReportSection>
          <ReportSection title="Grounding citations">
            {v.citations.length ? (
              v.citations.map((c) => (
                <span key={c} className="inline-block font-mono text-[11px] text-sky-700 border border-[#bfdbec] bg-sky-50 px-2 py-1 rounded-md mr-1.5 mt-1.5">
                  {c}
                </span>
              ))
            ) : (
              <span className="text-sm text-[#8494a8]">none</span>
            )}
          </ReportSection>
          <ReportSection title="How this verdict was reached">
            <p className="m-0 text-sm leading-relaxed text-slate-800">{v.rationale}</p>
            <p className="mt-2 mb-0 font-mono text-[11px] text-[#52627a]">escalated_by: [{v.escalated_by.join(", ")}] · safety_floor: {v.safety_floor} · {v.assessments.length} assessments</p>
          </ReportSection>
        </div>
      </div>
    </div>
  );
}

function ReportSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white border border-[#cbd7e6] rounded-[10px] px-3.5 py-3.5 mb-3">
      <h4 className="m-0 mb-2 text-xs font-mono tracking-wide uppercase text-[#52627a]">{title}</h4>
      {children}
    </div>
  );
}
