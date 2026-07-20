#!/usr/bin/env python3
"""Regenerate every number in docs/research/cascade-characterisation.md (#83, #84).

    PYTHONPATH=. python scripts/characterise_cascade.py            # full, ~10 min
    PYTHONPATH=. python scripts/characterise_cascade.py --quick    # ~1 min, coarser

Writes JSON to results/. Every figure quoted in the doc must come from here, so the
scorecard can be re-run rather than trusted.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from src.assessment.cusum import CusumThresholds, composite_deviation
from src.characterisation.harness import (
    ARL0_CAVEAT,
    SECONDS_PER_WINDOW,
    VARIABILITY_COLLAPSE,
    Departure,
    detection_delay,
    false_alarm_rate,
    operating_characteristic,
    synthesise_stream,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS = REPO_ROOT / "results"

CURRENT = CusumThresholds(k=0.5, h=5.0)
CANDIDATE = CusumThresholds(k=0.6, h=4.0)
DELTAS = (0.25, 0.5, 0.75, 1.0, 1.5, 2.0)


def composite_calibration(n_windows: int) -> dict:
    """The in-control mean of the CUSUM's input, and how a departure dilutes.

    This is the measurement that explains every other row: ``composite_deviation`` is a
    *rectified* statistic (``pathological_magnitude`` returns ``max(0, ·)``), so its
    in-control mean is strictly positive rather than zero. ``k`` must clear that floor or
    the accumulator drifts upward on noise alone.
    """
    in_control = float(
        np.mean([composite_deviation(c.z_scores) for c in synthesise_stream(n_windows, None, seed=7)])
    )
    # Analytic check: for N(0,1), E[max(0,-z)] = 1/sqrt(2*pi) for a one-sided feature and
    # E|z| = sqrt(2/pi) for a two-sided one. DEFAULT_DIRECTIONS has 4 one-sided + mean_rr.
    analytic = (4 * (1 / np.sqrt(2 * np.pi)) + np.sqrt(2 / np.pi)) / 5

    dilution = []
    for d in DELTAS:
        s = synthesise_stream(
            n_windows, Departure(magnitude_z=d, onset_window=0, features=VARIABILITY_COLLAPSE), seed=7
        )
        c = float(np.mean([composite_deviation(x.z_scores) for x in s]))
        dilution.append({"nominal_delta_z": d, "mean_composite": c, "ratio": c / d})

    return {
        "in_control_mean_composite": in_control,
        "in_control_analytic": float(analytic),
        "n_windows": n_windows,
        "dilution": dilution,
        "note": (
            "A departure moves 3 of the 5 direction-aware features, and the composite is "
            "their mean, so the CUSUM sees less than the nominal magnitude. The 'k = half "
            "the shift' rule assumes a zero-mean input and the full shift; neither holds here."
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--quick", action="store_true", help="fewer replicates / shorter runs")
    args = ap.parse_args()

    reps = 40 if args.quick else 120
    fa_reps = 20 if args.quick else 40
    incontrol = 4_000 if args.quick else 20_000

    RESULTS.mkdir(exist_ok=True)
    out: dict = {
        "config": {
            "replicates": reps,
            "false_alarm_replicates": fa_reps,
            "in_control_windows_per_run": incontrol,
            "seconds_per_window": SECONDS_PER_WINDOW,
        },
        "caveat": ARL0_CAVEAT,
    }

    print("1/4  composite calibration ...")
    out["composite_calibration"] = composite_calibration(4000)
    cal = out["composite_calibration"]
    print(f"     in-control mean composite = {cal['in_control_mean_composite']:.3f} "
          f"(analytic {cal['in_control_analytic']:.3f})")

    print("2/4  (k, h) operating characteristic ...")
    out["operating_characteristic"] = operating_characteristic(
        k_values=(0.25, 0.5, 0.75, 1.0),
        h_values=(3.0, 4.0, 5.0, 6.0, 8.0),
        magnitude_z=1.0,
        n_replicates=reps if not args.quick else 40,
        n_windows_incontrol=min(incontrol, 3000),
    )

    print("3/4  long-run ARL0 near the corrected k ...")
    arl = []
    for k in (0.50, 0.60, 0.68, 0.75, 0.85):
        for h in (4.0, 5.0):
            t = CusumThresholds(k=k, h=h)
            fa = false_alarm_rate(n_replicates=fa_reps, n_windows=incontrol, thresholds=t)
            dd = detection_delay(1.0, n_replicates=reps, thresholds=t, n_windows=3000)
            arl.append({"k": k, "h": h, **{x: fa[x] for x in
                        ("arl0_windows", "false_alarms_per_patient_day", "censored_fraction")},
                        "detection_rate": dd["detection_rate"],
                        "median_delay_windows": dd["median_delay_windows"],
                        "median_delay_seconds": dd["median_delay_seconds"],
                        "in_control_windows_observed": fa_reps * incontrol})
    out["long_run_arl0"] = arl

    print("4/4  delta sweep at both operating points ...")
    sweep = []
    for d in DELTAS:
        row = {"delta_z": d}
        for label, t in (("current_k0.5_h5.0", CURRENT), ("candidate_k0.6_h4.0", CANDIDATE)):
            r = detection_delay(d, n_replicates=reps, thresholds=t, n_windows=4000)
            row[label] = {
                "detection_rate": r["detection_rate"],
                "median_delay_windows": r["median_delay_windows"],
                "median_delay_seconds": r["median_delay_seconds"],
            }
        sweep.append(row)
    out["delta_sweep"] = sweep

    path = RESULTS / "cascade_characterisation.json"
    path.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
