"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { NeonatalAlert } from "@/lib/types";
import { getPatientAlert, getSystemHealth } from "@/lib/api-client";

const PATIENT_IDS = [
  "infant1",
  "infant2",
  "infant3",
  "infant4",
  "infant5",
  "infant6",
  "infant7",
  "infant8",
  "infant9",
  "infant10",
];

const REFRESH_INTERVAL = 90; // seconds

export function useWardData() {
  const [alerts, setAlerts] = useState<NeonatalAlert[]>([]);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);
  const [countdown, setCountdown] = useState(REFRESH_INTERVAL);
  const [health, setHealth] = useState<"ok" | "degraded" | "loading">(
    "loading"
  );

  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const refreshRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchAll = useCallback(async () => {
    const results = await Promise.allSettled(
      PATIENT_IDS.map((id) => getPatientAlert(id))
    );
    const resolved = results
      .filter(
        (r): r is PromiseFulfilledResult<NeonatalAlert> =>
          r.status === "fulfilled"
      )
      .map((r) => r.value);
    setAlerts(resolved);
    setLastRefreshed(new Date());
    setCountdown(REFRESH_INTERVAL);

    const h = await getSystemHealth();
    setHealth(h);
  }, []);

  useEffect(() => {
    fetchAll();

    countdownRef.current = setInterval(() => {
      setCountdown((prev) => (prev <= 1 ? REFRESH_INTERVAL : prev - 1));
    }, 1000);

    refreshRef.current = setInterval(fetchAll, REFRESH_INTERVAL * 1000);

    return () => {
      if (countdownRef.current) clearInterval(countdownRef.current);
      if (refreshRef.current) clearInterval(refreshRef.current);
    };
  }, [fetchAll]);

  return { alerts, lastRefreshed, countdown, health };
}
