"use client";

/**
 * Tier 3 agent-reasoning theater (#64).
 *
 * Animates the recorded-real Tier-3 RAG on the shared playhead: a supervisor →
 * signal / brady / clinical / protocol **handover chain** that lights up in sequence,
 * **retrieval cards** that reveal as each specialist "reaches into" its source, the
 * reasoning **streamed token-by-token**, the **escalate-only** structural beat, and the
 * self-check. The whole sequence is a function of the playhead's position inside the
 * Tier-3-active window, so scrubbing plays / rewinds it (spec decision 5: one clock).
 *
 * Honesty (map decision 3 + the no-sepsis-labels reality): Tier 3 is decision-support.
 * What NeonatalGuard *detects* is the HRV **departure** from this infant's baseline;
 * sepsis is the **hypothesis** the retrieval surfaces, physiologically grounded (HeRO/HRC,
 * NICE) but **not a diagnosis** — culture remains the reference standard, and the tier is
 * escalate-only (it may raise concern, never lower it). That framing is on screen, up top,
 * so the cinematic delivery can never be misread as "the AI found sepsis." Content is read
 * verbatim from trace §5 (Ledger H3); only the framing + choreography are authored here.
 */

import { useMemo } from "react";
import { Trace, Tier3, Tier1 } from "@/lib/trace-types";
import { usePlayhead } from "@/components/trace/playhead";

const AMBER = "#fbbf24";

interface Specialist {
  key: string;
  label: string;
  role: string;
  match: RegExp; // which retrieved sources this specialist pulls
}

// The real Tier-3 handover chain (supervisor dispatches; specialists hand off in order).
const CHAIN: Specialist[] = [
  { key: "supervisor", label: "Supervisor", role: "routes the case to specialists", match: /^$/ },
  { key: "signal", label: "Signal", role: "HRV autonomic pattern", match: /hero|hrc|hrv/i },
  { key: "brady", label: "Brady / Apnea", role: "apnea–bradycardia coupling", match: /apnea|brady|aap|cofn/i },
  { key: "clinical", label: "Clinical", role: "correlates the picture", match: /$^/ },
  { key: "protocol", label: "Protocol", role: "guideline grounding", match: /nice|ng195|guideline/i },
];

/** Earliest window where the merged level goes non-GREEN — when Tier 3 would actually run. */
function tier3StartIdx(tier1: Tier1, crossing: number | null, n: number): number {
  const breaches = tier1.features
    .filter((f) => f.flagged && f.failure_idx != null && f.failure_idx >= 0)
    .map((f) => f.failure_idx as number);
  const candidates = [...breaches, ...(crossing != null ? [crossing] : [])];
  return candidates.length ? Math.min(...candidates) : Math.floor(n * 0.5);
}

function Node({
  s,
  active,
  done,
}: {
  s: Specialist;
  active: boolean;
  done: boolean;
}) {
  const on = active || done;
  return (
    <div className="flex items-start gap-2.5">
      <div className="flex flex-col items-center">
        <span
          className="mt-1 h-2.5 w-2.5 rounded-full transition-all duration-300"
          style={{
            background: on ? AMBER : "#334155",
            boxShadow: active ? `0 0 12px ${AMBER}` : "none",
            transform: active ? "scale(1.25)" : "scale(1)",
          }}
        />
        {s.key !== "protocol" && (
          <span
            className="my-0.5 w-px flex-1 transition-colors duration-300"
            style={{ background: done ? `${AMBER}77` : "#334155", minHeight: 18 }}
          />
        )}
      </div>
      <div className={`pb-2 transition-opacity duration-300 ${on ? "opacity-100" : "opacity-45"}`}>
        <div className="font-mono text-[11px]" style={{ color: on ? "#fde68a" : "#64748b" }}>
          {s.label}
          {active && <span className="ml-1.5 animate-pulse text-[9px] text-amber-400">working…</span>}
        </div>
        <div className="text-[9.5px] text-slate-600">{s.role}</div>
      </div>
    </div>
  );
}

export function AgentTheater({ trace }: { trace: Trace }) {
  const { p, grid } = usePlayhead();
  const t3: Tier3 = trace.tier3;

  const t3Start = useMemo(
    () => tier3StartIdx(trace.tier1, trace.tier2.crossing_idx, grid.n),
    [trace.tier1, trace.tier2.crossing_idx, grid.n],
  );

  // Progress of the reasoning sequence: 0 at the escalation point → 1 after `span` windows.
  const span = Math.max(24, Math.round(grid.n * 0.25));
  const progress = Math.max(0, Math.min(1, (p - t3Start) / span));
  const active = p >= t3Start && t3.ran;

  if (!t3.ran) {
    return (
      <div className="glass rounded-xl border border-white/[0.06] p-4">
        <Header />
        <div className="mt-3 text-[11px] leading-relaxed text-slate-500">
          Skipped on a calm window — the merged Tier 1 + Tier 2 level was GREEN, so the reasoning
          tier short-circuits (it never runs, and never pays the LLM, on a clean window).
        </div>
      </div>
    );
  }

  if (!active) {
    return (
      <div className="glass rounded-xl border border-white/[0.06] p-4">
        <Header />
        <div className="mt-3 text-[11px] leading-relaxed text-slate-500">
          Idle — merged level still GREEN. Tier 3 arms at window <b className="text-slate-400">{t3Start}</b>,
          when the concordant floor + drift push the case past GREEN. Scrub forward to watch the
          specialists hand off.
        </div>
      </div>
    );
  }

  // stage gates over progress
  const dispatched = progress > 0.08;
  const activeNode = Math.min(CHAIN.length - 1, Math.floor(progress / (1 / CHAIN.length)));
  const reasoningChars = Math.floor(Math.max(0, (progress - 0.3) / 0.55) * t3.reasoning.length);
  const reasoningShown = t3.reasoning.slice(0, Math.min(t3.reasoning.length, Math.max(0, reasoningChars)));
  const selfCheckShown = progress > 0.9;

  // escalate-only beat: did Tier 3 raise above the floor, or concur with it?
  const raisedAbove = t3.concern_level === "RED" && trace.verdict.safety_floor !== "RED";

  return (
    <div className="glass rounded-xl border border-white/[0.06] p-4">
      <Header />

      {/* the query the signal specialist forms from the HRV departure (a hypothesis) */}
      <div className="mt-3 rounded-lg border border-white/[0.06] bg-black/20 p-2.5">
        <div className="mb-1 text-[9px] uppercase tracking-wider text-slate-600">
          Hypothesis query · from the HRV departure
        </div>
        <p className="font-mono text-[10.5px] leading-relaxed text-slate-400">{t3.query}</p>
      </div>

      {/* handover chain */}
      <div className="mt-3.5">
        <div className="mb-2 text-[9px] uppercase tracking-wider text-slate-600">Handover chain</div>
        {CHAIN.map((s, i) => {
          const passages = t3.retrieved.filter((r) => s.match.test(r.source) || s.match.test(r.id));
          return (
            <div key={s.key}>
              <Node s={s} active={dispatched && activeNode === i} done={dispatched && activeNode > i} />
              {activeNode >= i &&
                dispatched &&
                passages.map((r) => (
                  <div
                    key={r.id}
                    className="ml-5 mb-2 animate-[noir-float-up_0.4s_ease-out] rounded-lg border p-2"
                    style={{ borderColor: `${AMBER}33`, background: `${AMBER}0a` }}
                  >
                    <div className="mb-0.5 flex items-center gap-1.5">
                      <span className="text-[9px]" style={{ color: AMBER }}>
                        ⟢ pulled
                      </span>
                      <span className="font-mono text-[10px] font-semibold" style={{ color: "#fde68a" }}>
                        {r.source}
                      </span>
                    </div>
                    <p className="text-[10px] leading-relaxed text-slate-400">{r.snippet}</p>
                  </div>
                ))}
            </div>
          );
        })}
      </div>

      {/* streamed reasoning */}
      {progress > 0.3 && (
        <div className="mt-2">
          <div className="mb-1 text-[9px] uppercase tracking-wider text-slate-600">Reasoning</div>
          <p className="text-[11px] leading-relaxed text-slate-300">
            {reasoningShown}
            {reasoningChars < t3.reasoning.length && (
              <span className="ml-0.5 inline-block h-3 w-1.5 animate-pulse bg-amber-400/70 align-middle" />
            )}
          </p>
        </div>
      )}

      {/* escalate-only + self-check beat */}
      {selfCheckShown && (
        <div className="mt-3 space-y-2 border-t border-white/[0.06] pt-3">
          <Beat
            ok
            label="Escalate-only"
            text={
              raisedAbove
                ? `Tier 3 assessed ${t3.concern_level} and raised concern above the floor.`
                : `Tier 3 assessed ${t3.concern_level} — concurred with the ${trace.verdict.safety_floor} floor. It may raise concern, never lower it.`
            }
          />
          <Beat ok={t3.self_check.passed} label="Self-check" text={t3.self_check.note} />
        </div>
      )}
    </div>
  );
}

function Header() {
  return (
    <div>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full" style={{ background: AMBER, boxShadow: `0 0 8px ${AMBER}` }} />
          <span className="text-[11px] font-medium uppercase tracking-[0.14em] text-slate-300">
            Tier 3 · Agent reasoning
          </span>
        </div>
        <span className="text-[9px] uppercase tracking-wider text-slate-600">decision-support</span>
      </div>
      {/* the honesty frame — always visible, so the cinematic delivery can't be misread */}
      <p className="mt-2 text-[9.5px] leading-relaxed text-slate-500">
        Detects an HRV <span className="text-slate-300">departure from this infant&apos;s baseline</span>;
        sepsis is the <span className="text-slate-300">hypothesis</span> the guidelines surface — grounded
        (HeRO/HRC, NICE) but <span className="text-slate-300">not a diagnosis</span>. Culture remains the
        reference standard; the tier is escalate-only.
      </p>
    </div>
  );
}

function Beat({ ok, label, text }: { ok: boolean; label: string; text: string }) {
  return (
    <div className="flex items-start gap-2 text-[10.5px]">
      <span className="mt-px font-mono font-bold" style={{ color: ok ? "#6ee7b7" : "#fcd34d" }}>
        {ok ? "✓" : "⚠"}
      </span>
      <span>
        <span className="text-slate-300">{label}</span>{" "}
        <span className="text-slate-500">— {text}</span>
      </span>
    </div>
  );
}
