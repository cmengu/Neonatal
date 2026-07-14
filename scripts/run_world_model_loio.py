"""Run the world-model Surprise LOIO spike on the real 10-infant PICS cohort (issue #6).

This is the deliverable of the research gate's gating question: *does per-window Surprise
rise in the lead window before the annotated bradycardia events on held-out infants?* It
fits a per-infant VAR(1) forecaster (``src.world_model.forecaster``), scores per-window
Surprise, runs the LOIO evaluation (``src.world_model.loio``), prints the headline number,
and writes a plot + a machine-readable results JSON that the ticket resolution links to.

Run from repo root:  ``python scripts/run_world_model_loio.py``

Honesty notes carried from the gate:
- Bradycardia viability ≠ sepsis validation. This tests whether the per-infant model
  carries lead-time signal on *our* ``.atr`` bradycardia events, nothing more.
- The models share no population weights; each infant is scored only by its own model,
  standardised to its own baseline. ``lead``/``guard`` are fixed a priori (not tuned here).
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless — no display, deterministic PNG (mirrors scripts/verify_matplotlib_agg)
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.world_model.forecaster import FORECAST_FEATURES, PerInfantForecaster
from src.world_model.loio import (
    DEFAULT_GUARD,
    DEFAULT_LEAD,
    InfantResult,
    evaluate_infant,
    peri_event_trace,
    summarise,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
PROCESSED = REPO_ROOT / "data" / "processed"
ASSETS = REPO_ROOT / "docs" / "research" / "assets"
RESULTS_JSON = PROCESSED / "world_model_loio_results.json"
PLOT_PATH = ASSETS / "world-model-surprise-loio.png"

INFANTS = [f"infant{i}" for i in range(1, 11)]
BEATS_PER_HOP = 25  # run_nb03: 50-beat windows, 25-beat hop → seconds/window ≈ 25 · median_RR


def seconds_per_window(patient_id: str) -> float | None:
    """Approximate wall-clock seconds advanced per window index, from the infant's RR.

    Windows hop 25 beats (``run_nb03``), so seconds/window ≈ 25 · median RR. Used only to
    annotate the lead time in seconds; None if the RR file is missing."""
    rr_path = PROCESSED / f"{patient_id}_rr_clean.csv"
    if not rr_path.exists():
        return None
    rr_ms = pd.read_csv(rr_path)["rr_ms"].to_numpy(dtype=float)
    if rr_ms.size == 0:
        return None
    return BEATS_PER_HOP * float(np.median(rr_ms)) / 1000.0


def load_infant(patient_id: str) -> tuple[np.ndarray, np.ndarray] | None:
    """Return (feature matrix in FORECAST_FEATURES order, label vector) or None if absent."""
    path = PROCESSED / f"{patient_id}_windowed.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path).sort_values("window_idx").reset_index(drop=True)
    missing = [c for c in FORECAST_FEATURES if c not in df.columns]
    if missing:
        raise SystemExit(f"{patient_id}: missing forecast features {missing}")
    x = df[list(FORECAST_FEATURES)].to_numpy(dtype=float)
    labels = df["label"].to_numpy(dtype=int)
    return x, labels


def run() -> None:
    forecaster = PerInfantForecaster()
    results: list[InfantResult] = []
    traces: list[np.ndarray] = []
    secs_per_win: dict[str, float | None] = {}

    print(f"World-model Surprise LOIO — lead={DEFAULT_LEAD} guard={DEFAULT_GUARD} windows")
    print(f"features: {', '.join(FORECAST_FEATURES)}\n")
    print(f"{'infant':9} {'events':>6} {'lead':>5} {'base':>6} {'AUC':>6}  {'s/win':>6}")

    for pid in INFANTS:
        loaded = load_infant(pid)
        if loaded is None:
            continue
        x, labels = loaded
        params = forecaster.fit(x)  # per-infant, no shared weights
        surprise = forecaster.surprise_stream(params, x)
        res = evaluate_infant(pid, surprise, labels, lead=DEFAULT_LEAD, guard=DEFAULT_GUARD)
        results.append(res)
        traces.append(
            peri_event_trace(surprise, labels, res.baseline_mean, res.baseline_std, half=DEFAULT_GUARD)
        )
        spw = seconds_per_window(pid)
        secs_per_win[pid] = spw
        print(
            f"{pid:9} {res.n_events:6d} {res.n_lead:5d} {res.n_baseline:6d} "
            f"{res.auc:6.3f}  {spw:6.1f}" if spw else
            f"{pid:9} {res.n_events:6d} {res.n_lead:5d} {res.n_baseline:6d} {res.auc:6.3f}     na"
        )

    summary = summarise(results)

    # Lead-time in seconds, using each infant's own seconds/window.
    lead_secs: list[float] = []
    for res in results:
        spw = secs_per_win.get(res.patient_id)
        if spw:
            lead_secs.extend(w * spw for w in res.lead_time_windows)

    print("\n" + "=" * 60)
    print(f"POOLED LOIO AUC (lead vs baseline):   {summary.pooled_auc:.3f}")
    print(f"mean / median per-infant AUC:         {summary.mean_infant_auc:.3f} / {summary.median_infant_auc:.3f}")
    print(f"infants / events:                     {summary.n_infants} / {summary.total_events}")
    print(f"lead / baseline windows (pooled):     {summary.total_lead_windows} / {summary.total_baseline_windows}")
    if summary.lead_time_windows:
        lw = np.array(summary.lead_time_windows)
        print(
            f"lead time (events with a pre-onset rise): n={lw.size}/{summary.total_events}, "
            f"median={np.median(lw):.0f} win"
            + (f" ≈ {np.median(lead_secs):.0f} s" if lead_secs else "")
        )
    print("=" * 60)

    _write_plot(summary, traces)
    _write_json(summary, secs_per_win, lead_secs)
    print(f"\nplot   → {PLOT_PATH.relative_to(REPO_ROOT)}")
    print(f"results → {RESULTS_JSON.relative_to(REPO_ROOT)}")


def _write_plot(summary, traces: list[np.ndarray]) -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))

    # Panel 1: peri-event mean Surprise (within-infant z), pooled across infants.
    if traces:
        stacked = np.vstack(traces)
        mean_trace = np.nanmean(stacked, axis=0)
        offsets = np.arange(-DEFAULT_GUARD, DEFAULT_GUARD + 1)
        ax1.axvspan(-DEFAULT_LEAD, 0, color="orange", alpha=0.15, label=f"lead window ({DEFAULT_LEAD} win)")
        ax1.axvline(0, color="crimson", lw=1.2, ls="--", label="bradycardia onset")
        ax1.axhline(0, color="grey", lw=0.8)
        ax1.plot(offsets, mean_trace, color="navy", lw=1.8)
        ax1.set_xlabel("windows relative to bradycardia onset")
        ax1.set_ylabel("Surprise (within-infant SD over baseline)")
        ax1.set_title("Peri-event Surprise (mean across infants)")
        ax1.legend(fontsize=8, loc="upper left")

    # Panel 2: per-infant AUC vs the pooled headline + chance line.
    pids = [r.patient_id.replace("infant", "") for r in summary.per_infant]
    aucs = [r.auc for r in summary.per_infant]
    ax2.bar(pids, aucs, color="steelblue")
    ax2.axhline(0.5, color="grey", ls=":", label="chance (0.5)")
    ax2.axhline(summary.pooled_auc, color="crimson", ls="--", label=f"pooled LOIO {summary.pooled_auc:.3f}")
    ax2.set_ylim(0, 1)
    ax2.set_xlabel("infant")
    ax2.set_ylabel("lead-vs-baseline AUC")
    ax2.set_title("Per-infant Surprise AUC (held out)")
    ax2.legend(fontsize=8, loc="lower right")

    fig.suptitle(
        "World-model Surprise — LOIO bradycardia-anticipation spike (issue #6). "
        "Bradycardia viability, not sepsis validation.",
        fontsize=10,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(PLOT_PATH, dpi=120)
    plt.close(fig)


def _write_json(summary, secs_per_win, lead_secs) -> None:
    RESULTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    lw = summary.lead_time_windows
    payload = {
        "lead_windows": DEFAULT_LEAD,
        "guard_windows": DEFAULT_GUARD,
        "features": list(FORECAST_FEATURES),
        "pooled_auc": summary.pooled_auc,
        "mean_infant_auc": summary.mean_infant_auc,
        "median_infant_auc": summary.median_infant_auc,
        "n_infants": summary.n_infants,
        "total_events": summary.total_events,
        "total_lead_windows": summary.total_lead_windows,
        "total_baseline_windows": summary.total_baseline_windows,
        "lead_time_windows_median": float(np.median(lw)) if lw else None,
        "lead_time_seconds_median": float(np.median(lead_secs)) if lead_secs else None,
        "n_events_with_lead_rise": len(lw),
        "per_infant": [
            {
                "patient_id": r.patient_id,
                "auc": r.auc,
                "n_events": r.n_events,
                "n_lead": r.n_lead,
                "n_baseline": r.n_baseline,
                "seconds_per_window": secs_per_win.get(r.patient_id),
            }
            for r in summary.per_infant
        ],
    }
    RESULTS_JSON.write_text(json.dumps(payload, indent=2))


if __name__ == "__main__":
    run()
