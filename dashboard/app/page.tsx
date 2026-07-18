"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { NeonatalAlert } from "@/lib/types";
import { useWardData } from "@/hooks/useWardData";
import { WardGrid } from "@/components/WardGrid";
import { StatusBar } from "@/components/StatusBar";
import { PatientDrawer } from "@/components/PatientDrawer";

export default function Home() {
  const { alerts, lastRefreshed, countdown, health } = useWardData();
  const [selected, setSelected] = useState<NeonatalAlert | null>(null);
  const router = useRouter();

  // A RED bed drills into its cascade trace; other beds open the summary drawer.
  const handleSelect = (alert: NeonatalAlert) => {
    if (alert.concern_level === "RED") {
      router.push(`/trace/${alert.patient_id}`);
      return;
    }
    setSelected(alert);
  };

  return (
    <div className="flex flex-col h-screen bg-slate-900 overflow-hidden">
      <StatusBar
        lastRefreshed={lastRefreshed}
        countdown={countdown}
        health={health}
      />
      <main className="flex-1 overflow-y-auto">
        <WardGrid alerts={alerts} onSelectPatient={handleSelect} />
      </main>
      <PatientDrawer alert={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
