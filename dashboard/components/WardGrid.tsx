"use client";

import { NeonatalAlert } from "@/lib/types";
import { BedCard } from "./BedCard";

const SEVERITY_ORDER: Record<string, number> = { RED: 0, YELLOW: 1, GREEN: 2 };

interface WardGridProps {
  alerts: NeonatalAlert[];
  onSelectPatient: (alert: NeonatalAlert) => void;
}

export function WardGrid({ alerts, onSelectPatient }: WardGridProps) {
  const sorted = [...alerts].sort(
    (a, b) =>
      SEVERITY_ORDER[a.concern_level] - SEVERITY_ORDER[b.concern_level]
  );

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3 p-4">
      {sorted.map((alert) => (
        <BedCard
          key={alert.patient_id}
          alert={alert}
          onClick={() => onSelectPatient(alert)}
        />
      ))}
    </div>
  );
}
