#!/usr/bin/env python3
"""Run notebook 04 baseline deviation logic. Produces *_windowed.csv and all_patients_windowed.csv."""
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(os.getcwd())
if REPO_ROOT.name == "notebooks":
    REPO_ROOT = REPO_ROOT.parent
sys.path.insert(0, str(REPO_ROOT))

PROCESSED_DIR = REPO_ROOT / "data" / "processed"
PATIENTS = [f"infant{i}" for i in range(1, 11)]
WINDOW_SIZE = 50
STEP_SIZE = 25
LOOKBACK = 10
FS_ECG = 500
HRV_COLS = [
    "rr_ms_mean", "rr_ms_std", "rr_ms_min",
    "rr_ms_max", "rr_ms_25%", "rr_ms_50%", "rr_ms_75%"
]

trim_df = pd.read_csv(PROCESSED_DIR / "trim_offsets.csv")
TRIM_OFFSETS = dict(zip(trim_df["record_name"], trim_df["start_idx_samples"].astype(int)))

print(f"REPO_ROOT:     {REPO_ROOT}")
print(f"PROCESSED_DIR: {PROCESSED_DIR}")
print(f"LOOKBACK:      {LOOKBACK} windows")
print(f"Patients:      {PATIENTS}")
print(f"Trim offsets:  {TRIM_OFFSETS}")


def align_labels_to_windows(patient_id):
    rr_ms = pd.read_csv(PROCESSED_DIR / f"{patient_id}_rr_clean.csv")["rr_ms"].values
    labels_df = pd.read_csv(PROCESSED_DIR / f"{patient_id}_labels.csv")
    rr_samples = rr_ms / 1000.0 * FS_ECG
    cumulative_pos = np.cumsum(rr_samples)
    n_windows = (len(rr_ms) - WINDOW_SIZE) // STEP_SIZE + 1
    trim_offset = TRIM_OFFSETS.get(patient_id, 0)
    labelled_windows = set()
    dropped_prefix = 0
    dropped_range = 0
    for _, row in labels_df.iterrows():
        sample_idx = row["sample_idx"]
        adjusted_sample_idx = sample_idx - trim_offset
        if adjusted_sample_idx < 0:
            dropped_prefix += 1
            continue
        matches = np.where(cumulative_pos >= adjusted_sample_idx)[0]
        if len(matches) == 0:
            dropped_range += 1
            continue
        beat_idx = int(matches[0])
        window_idx = min(beat_idx // STEP_SIZE, n_windows - 1)
        if 0 <= window_idx < n_windows:
            labelled_windows.add(window_idx)
        else:
            dropped_range += 1
    # Alignment bug check: if any annotation is within rr range and trim_offset=0, at least one must map
    if trim_offset == 0 and len(labels_df) > 0:
        in_range = (labels_df["sample_idx"] <= cumulative_pos[-1]).any()
        if in_range:
            assert len(labelled_windows) > 0, (
                f"{patient_id}: annotations in range but all dropped — alignment bug"
            )
    print(f"  {patient_id}: {len(labels_df)} annotations -> "
          f"{len(labelled_windows)} labelled windows "
          f"(dropped_prefix={dropped_prefix}, dropped_range={dropped_range}, "
          f"trim_offset={trim_offset})")
    return labelled_windows


def compute_deviations(patient_id, labelled_windows):
    features = pd.read_csv(PROCESSED_DIR / f"{patient_id}_features.csv")
    assert features["window_idx"].iloc[0] == 0
    assert (features["window_idx"].diff().dropna() == 1).all()
    dev_cols = {}
    for col in HRV_COLS:
        values = features[col].values
        roll_mean = np.full(len(values), np.nan)
        roll_std = np.full(len(values), np.nan)
        for i in range(LOOKBACK, len(values)):
            window_vals = values[i - LOOKBACK : i]
            roll_mean[i] = window_vals.mean()
            roll_std[i] = window_vals.std(ddof=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            deviation = np.where(
                roll_std == 0, 0.0, (values - roll_mean) / roll_std
            )
        dev_cols[f"{col}_dev"] = deviation
    result = pd.DataFrame(dev_cols)
    result.insert(0, "window_idx", features["window_idx"])
    result.insert(0, "record_name", features["record_name"])
    result = result.iloc[LOOKBACK:].reset_index(drop=True)
    result["label"] = result["window_idx"].apply(
        lambda w: 1 if w in labelled_windows else 0
    )
    n_pos = result["label"].sum()
    n_neg = len(result) - n_pos
    print(f"  {patient_id}: {len(result)} windows after warmup drop "
          f"(pos={n_pos}, neg={n_neg}, ratio={n_pos/max(len(result),1):.2%})")
    assert result.isnull().sum().sum() == 0
    return result


all_patients = []
for patient_id in PATIENTS:
    print(f"\n-- {patient_id} --")
    labelled_windows = align_labels_to_windows(patient_id)
    windowed_df = compute_deviations(patient_id, labelled_windows)
    out_path = PROCESSED_DIR / f"{patient_id}_windowed.csv"
    windowed_df.to_csv(out_path, index=False)
    print(f"  Saved: {out_path}")
    all_patients.append(windowed_df)

combined = pd.concat(all_patients, ignore_index=True)
combined.to_csv(PROCESSED_DIR / "all_patients_windowed.csv", index=False)
print(f"\nNotebook 04 complete.")
print(f"Combined shape:   {combined.shape}")
print(f"Total pos labels: {combined['label'].sum()} / {len(combined)}")
print(f"Overall pos rate: {combined['label'].mean():.2%}")
print(f"NaN in combined:  {combined.isnull().sum().sum()}")
