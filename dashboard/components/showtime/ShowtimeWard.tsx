"use client";

/**
 * ShowtimeWard — the demo's opening beat + entry point (#65).
 *
 * The "scale → drill-in" shot (spec §2, t=0–8 s): a dark NICU grid of calm beds with
 * one infant destabilising (infant7, pulsing), then a click drills into the immersive
 * cascade (#61 at /showtime/[id]). Clinical-noir to match the stage it opens into.
 *
 * Honesty (map decision 3 + the no-sepsis-labels reality): only infant7 carries a real
 * recorded trace, so only infant7 is the live, clickable focus. The calm beds are
 * context — shown as "stable", with **no fabricated per-infant risk scores or clinical
 * text** (the legacy mock ward painted those, and even mislabelled a different infant as
 * "pre-sepsis" — the overclaim #5 rejected). Here nothing is claimed that isn't real.
 */

import Link from "next/link";

const TURNING = "infant7";
const BEDS = Array.from({ length: 10 }, (_, i) => `infant${i + 1}`);

function bedNo(id: string): string {
  return id.replace("infant", "").padStart(2, "0");
}

function CalmBed({ id }: { id: string }) {
  return (
    <div className="glass relative rounded-xl border border-white/[0.06] p-4 opacity-80">
      <div className="flex items-start justify-between">
        <span className="text-[15px] font-semibold tracking-tight text-slate-300">
          Bed {bedNo(id)}
        </span>
        <span className="inline-flex items-center gap-1.5 rounded px-1.5 py-0.5 text-[9px] uppercase tracking-wider text-emerald-300">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> stable
        </span>
      </div>
      <div className="mt-6 flex items-center gap-2 text-[10px] text-slate-600">
        <span className="font-mono">monitoring · within baseline</span>
      </div>
    </div>
  );
}

function TurningBed() {
  return (
    <Link
      href={`/showtime/${TURNING}`}
      className="group relative block animate-[noir-float-up_0.5s_ease-out] rounded-xl border-2 p-4 transition-transform hover:scale-[1.03]"
      style={{
        borderColor: "#ef4444",
        background: "rgba(30,10,12,0.6)",
        boxShadow: "0 0 0 1px rgba(239,68,68,0.25), 0 0 32px rgba(239,68,68,0.28)",
      }}
      aria-label="Infant 07 — destabilising — open immersive cascade"
    >
      {/* pulsing ring */}
      <span
        className="pointer-events-none absolute inset-0 rounded-xl motion-safe:animate-ping"
        style={{ boxShadow: "0 0 0 2px rgba(239,68,68,0.5)", animationDuration: "2.4s" }}
      />
      <div className="relative">
        <div className="flex items-start justify-between">
          <span className="text-[15px] font-bold tracking-tight text-slate-50">Bed 07</span>
          <span className="inline-flex items-center gap-1.5 rounded bg-red-500/15 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-red-300">
            <span className="h-1.5 w-1.5 rounded-full bg-red-500" /> destabilising
          </span>
        </div>
        <div className="mt-3 text-[11px] leading-relaxed text-slate-300">
          Sustained HRV departure from this infant&apos;s baseline — the cascade is live.
        </div>
        <div className="mt-3 inline-flex items-center gap-1.5 font-mono text-[11px] text-red-300 transition-colors group-hover:text-red-200">
          open immersive cascade
          <span className="transition-transform group-hover:translate-x-0.5">→</span>
        </div>
      </div>
    </Link>
  );
}

export function ShowtimeWard() {
  return (
    <div className="relative min-h-screen text-slate-100" style={{ background: "#070b12" }}>
      <div className="pointer-events-none absolute inset-0 noir-grid opacity-30" />
      <div className="pointer-events-none absolute inset-0 noir-vignette" />

      <div className="relative mx-auto max-w-6xl px-6 py-8">
        <header className="mb-6 flex items-end justify-between">
          <div>
            <div className="flex items-center gap-3">
              <span className="text-lg font-semibold tracking-wide">NeonatalGuard</span>
              <span className="text-[10px] uppercase tracking-[0.3em] text-slate-500">NICU ward</span>
            </div>
            <p className="mt-1 text-[12px] text-slate-500">
              Ten beds, one turning. Open the destabilising infant to watch the full cascade on one clock.
            </p>
          </div>
          <div className="text-right font-mono text-[11px] text-slate-600">
            <div>
              <span className="text-emerald-300">9</span> stable ·{" "}
              <span className="text-red-300">1</span> destabilising
            </div>
            <div className="mt-0.5 text-slate-700">demo ward · infant7 carries the recorded cascade</div>
          </div>
        </header>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {BEDS.map((id) => (id === TURNING ? <TurningBed key={id} /> : <CalmBed key={id} id={id} />))}
        </div>

        <p className="mt-6 font-mono text-[9.5px] text-slate-700">
          Calm beds are context — shown as stable, with no fabricated per-infant metrics. Only infant7
          carries a real recorded trace, so only infant7 drills in.
        </p>
      </div>
    </div>
  );
}
