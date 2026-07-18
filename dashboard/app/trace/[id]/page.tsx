"use client";

import { useEffect, useState } from "react";
import { Trace } from "@/lib/trace-types";
import { getTrace } from "@/lib/trace-client";
import { PlayheadProvider } from "@/components/trace/playhead";
import { Timeline } from "@/components/trace/Timeline";
import { TraceCanvas } from "@/components/trace/TraceCanvas";

export default function TracePage({ params }: { params: { id: string } }) {
  const { id } = params;
  const [trace, setTrace] = useState<Trace | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getTrace(id)
      .then((t) => !cancelled && setTrace(t))
      .catch((e) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (error) {
    return (
      <div className="h-screen flex flex-col items-center justify-center bg-[#0a0e16] text-slate-300 gap-4">
        <p className="font-mono text-sm text-slate-400">No recorded trace for {id}.</p>
        <a href="/" className="font-mono text-[12.5px] px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-100">
          ← Ward
        </a>
      </div>
    );
  }

  if (!trace) {
    return (
      <div className="h-screen flex items-center justify-center bg-[#0a0e16] text-slate-500 font-mono text-sm">
        Loading trace…
      </div>
    );
  }

  return (
    <PlayheadProvider grid={trace.time_grid}>
      <div className="flex flex-col h-screen bg-[#0a0e16] overflow-hidden">
        <Timeline />
        <TraceCanvas trace={trace} />
      </div>
    </PlayheadProvider>
  );
}
