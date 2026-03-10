#!/usr/bin/env python3
"""Run notebook 03 HRV extraction logic."""
import os
os.environ["MPLBACKEND"] = "Agg"
_cwd = os.path.dirname(os.path.abspath(__file__))
os.environ["MPLCONFIGDIR"] = os.path.join(_cwd, "..", ".mpl_config")
# Avoid matplotlib font crash on macOS (KeyError '_items' / slow system_profiler)
os.environ["PATH"] = "/usr/bin:/bin:/usr/local/bin"
import matplotlib
matplotlib.use("Agg")  # non-interactive backend — required for nohup
import sys
import os
from pathlib import Path

REPO_ROOT = Path(os.getcwd())
if REPO_ROOT.name == "notebooks":
    REPO_ROOT = REPO_ROOT.parent

sys.path.insert(0, str(REPO_ROOT))
from src.features.hrv import get_window_features

import wfdb
import pandas as pd
import numpy as np

PATIENTS = [f"infant{i}" for i in range(1, 11)]
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
RAW_DIR = REPO_ROOT / "data" / "raw" / "physionet.org" / "files" / "picsdb" / "1.0.0"
WINDOW_SIZE = 50
STEP_SIZE = 25

print(f"REPO_ROOT:     {REPO_ROOT}")
print(f"PROCESSED_DIR: {PROCESSED_DIR}")
print(f"RAW_DIR:       {RAW_DIR}")


def extract_features(patient_id):
    rr_path = PROCESSED_DIR / f"{patient_id}_rr_clean.csv"
    rr_ms = pd.read_csv(rr_path)["rr_ms"].values

    rows = []
    win_idx = 0
    start = 0

    while start + WINDOW_SIZE <= len(rr_ms):
        window = rr_ms[start : start + WINDOW_SIZE]
        row = get_window_features(window, patient_id, win_idx)
        rows.append(row)
        start += STEP_SIZE
        win_idx += 1

    df = pd.DataFrame(rows)
    expected_cols = [
        "record_name", "window_idx",
        "rr_ms_mean", "rr_ms_std", "rr_ms_min",
        "rr_ms_max", "rr_ms_25%", "rr_ms_50%", "rr_ms_75%"
    ]
    missing = [c for c in expected_cols if c not in df.columns]
    assert not missing, f"Missing columns: {missing}"
    return df[expected_cols]


def extract_labels(patient_id):
    ann_path = RAW_DIR / f"{patient_id}_ecg"
    ann = wfdb.rdann(str(ann_path), "atr")

    rows = [
        {"sample_idx": int(s), "symbol": sym}
        for s, sym in zip(ann.sample, ann.symbol)
    ]
    df = pd.DataFrame(rows)
    print(f"  {patient_id}: {len(df)} annotations")
    print(f"  symbols: {sorted(df['symbol'].unique())}")
    return df


for patient_id in PATIENTS:
    print(f"\n── {patient_id} ──────────────────────────────")
    try:
        features_df = extract_features(patient_id)
        feat_path = PROCESSED_DIR / f"{patient_id}_features.csv"
        features_df.to_csv(feat_path, index=False)
        print(f"  features: {features_df.shape} → {feat_path}")

        labels_df = extract_labels(patient_id)
        label_path = PROCESSED_DIR / f"{patient_id}_labels.csv"
        labels_df.to_csv(label_path, index=False)
        print(f"  labels:   {labels_df.shape} → {label_path}")
    except FileNotFoundError as e:
        print(f"  WARNING: {patient_id} skipped (missing rr_clean: {e})")
    except Exception as e:
        print(f"  ERROR: {patient_id} failed: {e}")
        raise

print("\n✅ Notebook 03 complete.")
