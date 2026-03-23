"use client";

import { useEffect, useState } from "react";
import { HistoryEntry } from "@/lib/types";
import { getPatientHistory } from "@/lib/api-client";

export function usePatientHistory(patientId: string | null) {
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!patientId) {
      setHistory([]);
      return;
    }
    setLoading(true);
    getPatientHistory(patientId, 7)
      .then(setHistory)
      .catch(() => setHistory([]))
      .finally(() => setLoading(false));
  }, [patientId]);

  return { history, loading };
}
