#!/usr/bin/env python3
"""Regenerate the per-infant HRV feature CSVs so they carry the #13 HeRO discriminators.

Why this script exists
----------------------
``HRV_FEATURE_COLS`` declares 12 features. Every ``data/processed/infant*_features.csv``
on disk carries 10: ``sampen`` and ``sample_asymmetry`` are absent. Issue #13 added both
to ``src/features/hrv.py`` and wired them into ``DeviationAssessor.DEFAULT_DIRECTIONS``
as trigger-capable (``sampen`` low-only, ``sample_asymmetry`` high-only) — but the
extraction step was never re-run, so **two of Tier 1's five triggers have never fired.**
The three that do fire (``sdnn``, ``rmssd``, ``mean_rr``) are the generic measures #13
was specifically meant to move past.

``scripts/run_nb03.py`` already computes both correctly. It cannot be re-run as-is here
because its label step needs ``data/raw/physionet.org/...``, which is absent from this
checkout — and the label CSVs are unchanged by #13 anyway.

This script therefore re-runs *only* the feature half, with the same window geometry and
the same trailing-SampEn construction as ``run_nb03.py``, and parallelises across infants
(they are independent). SampEn over a 4096-beat window costs ~53 ms, and there are
~152k windows, so single-threaded this is ~2.3 h; across 8 cores it is ~20 min.

Staged by default
-----------------
Writes to ``data/processed/staging/`` rather than overwriting. The JEPA checkpoint and
the recorded demo trace were both produced from the 10-feature stream; silently changing
the data under them would invalidate the demo's numbers without anyone noticing. Promote
deliberately (``--promote``) once the downstream retrain (#75) is ready to follow.

Usage
-----
    PYTHONPATH=. python scripts/regenerate_hrv_features.py            # stage all 10
    PYTHONPATH=. python scripts/regenerate_hrv_features.py --sample 200  # fast estimate
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.features.constants import HRV_FEATURE_COLS  # noqa: E402
from src.features.hrv import get_window_features  # noqa: E402

PROCESSED = REPO_ROOT / "data" / "processed"
STAGING = PROCESSED / "staging"
PATIENTS = [f"infant{i}" for i in range(1, 11)]

# Window geometry — must stay identical to scripts/run_nb03.py, or the regenerated
# features will not align row-for-row with the existing labels and windowed CSVs.
WINDOW_SIZE = 50
STEP_SIZE = 25
SAMPEN_WINDOW = 4096
SAMPEN_MIN_N = 512


def extract_features(patient_id: str, sample_every: int = 1) -> pd.DataFrame:
    """Re-extract one infant's HRV features, including the #13 HeRO discriminators.

    ``sample_every`` > 1 keeps only every Nth window — for estimating the feature
    distribution quickly without paying for all ~15k windows per infant. The returned
    ``window_idx`` remains the true index, so a sampled frame is never mistaken for a
    complete one.
    """
    rr_ms = pd.read_csv(PROCESSED / f"{patient_id}_rr_clean.csv")["rr_ms"].values

    rows = []
    win_idx = 0
    start = 0
    while start + WINDOW_SIZE <= len(rr_ms):
        if win_idx % sample_every == 0:
            window = rr_ms[start : start + WINDOW_SIZE]
            end = start + WINDOW_SIZE
            long_window = rr_ms[max(0, end - SAMPEN_WINDOW) : end]
            if len(long_window) < SAMPEN_MIN_N:
                long_window = np.array([])  # cold start → both discriminators NaN, never fabricated
            rows.append(get_window_features(window, patient_id, win_idx, rr_long=long_window))
        start += STEP_SIZE
        win_idx += 1

    df = pd.DataFrame(rows)
    expected = ["record_name", "window_idx"] + HRV_FEATURE_COLS
    missing = [c for c in expected if c not in df.columns]
    assert not missing, f"{patient_id}: missing columns {missing}"
    return df[expected]


def _worker(args: tuple[str, int, bool]) -> tuple[str, int, str]:
    patient_id, sample_every, write = args
    df = extract_features(patient_id, sample_every=sample_every)
    out = ""
    if write:
        STAGING.mkdir(parents=True, exist_ok=True)
        out = str(STAGING / f"{patient_id}_features.csv")
        df.to_csv(out, index=False)
    else:
        STAGING.mkdir(parents=True, exist_ok=True)
        out = str(STAGING / f"{patient_id}_features_sample.csv")
        df.to_csv(out, index=False)
    return patient_id, len(df), out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--sample", type=int, default=1,
        help="Keep every Nth window (default 1 = all). Use e.g. 100 for a fast estimate.",
    )
    ap.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 4))
    ap.add_argument(
        "--promote", action="store_true",
        help="Overwrite data/processed/*_features.csv from staging. Invalidates the "
             "JEPA checkpoint and recorded trace — do this only alongside #75.",
    )
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")

    if args.promote:
        promoted = 0
        for pid in PATIENTS:
            src = STAGING / f"{pid}_features.csv"
            if src.exists():
                pd.read_csv(src).to_csv(PROCESSED / f"{pid}_features.csv", index=False)
                promoted += 1
        logging.info("promoted %d/%d staged feature files", promoted, len(PATIENTS))
        return

    full = args.sample == 1
    logging.info(
        "regenerating %s windows for %d infants on %d workers",
        "ALL" if full else f"every {args.sample}th", len(PATIENTS), args.workers,
    )

    tasks = [(pid, args.sample, full) for pid in PATIENTS]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_worker, t): t[0] for t in tasks}
        for fut in as_completed(futures):
            pid, n, out = fut.result()
            logging.info("  %-9s %6d windows → %s", pid, n, Path(out).name)

    logging.info("done. staged under %s", STAGING)


if __name__ == "__main__":
    main()
