#!/usr/bin/env python3
"""Run notebook 04 baseline deviation logic. Produces *_windowed.csv and all_patients_windowed.csv."""
import os
os.environ["MPLBACKEND"] = "Agg"
_cwd = os.path.dirname(os.path.abspath(__file__))
os.environ["MPLCONFIGDIR"] = os.path.join(_cwd, "..", ".mpl_config")
# Avoid matplotlib font crash on macOS (KeyError '_items' / slow system_profiler)
os.environ["PATH"] = "/usr/bin:/bin:/usr/local/bin"
import matplotlib
matplotlib.use("Agg")  # non-interactive backend — required for nohup
import logging
from pathlib import Path
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")

import numpy as np
import pandas as pd

REPO_ROOT = Path(os.getcwd())
if REPO_ROOT.name == "notebooks":
    REPO_ROOT = REPO_ROOT.parent

PROCESSED_DIR = REPO_ROOT / "data" / "processed"
PATIENTS = [f"infant{i}" for i in range(1, 11)]
WINDOW_SIZE = 50
STEP_SIZE = 25
LOOKBACK = 10
FS_ECG = 500
HRV_COLS = [
    "mean_rr", "sdnn", "rmssd", "pnn50", "lf_hf_ratio",
    "rr_ms_min", "rr_ms_max", "rr_ms_25%", "rr_ms_50%", "rr_ms_75%"
]

frp_df = pd.read_csv(PROCESSED_DIR / "first_r_peaks.csv")
missing = [p for p in PATIENTS if p not in frp_df["record_name"].values]
assert not missing, f"first_r_peaks.csv is missing patients: {missing}"
FIRST_R_PEAKS = dict(zip(frp_df["record_name"], frp_df["first_r_peak_absolute"].astype(int)))

logging.info("REPO_ROOT:     %s", REPO_ROOT)
logging.info("PROCESSED_DIR: %s", PROCESSED_DIR)
logging.info("LOOKBACK:      %s windows", LOOKBACK)
logging.info("Patients:      %s", PATIENTS)
logging.info("First R-peaks: %s", FIRST_R_PEAKS)


def align_labels_to_windows(patient_id):
    rr_ms = pd.read_csv(PROCESSED_DIR / f"{patient_id}_rr_clean.csv")["rr_ms"].values
    labels_df = pd.read_csv(PROCESSED_DIR / f"{patient_id}_labels.csv")
    rr_samples = rr_ms / 1000.0 * FS_ECG
    first_r_peak_abs = FIRST_R_PEAKS[patient_id]
    cumulative_pos = first_r_peak_abs + np.cumsum(rr_samples)
    n_windows = (len(rr_ms) - WINDOW_SIZE) // STEP_SIZE + 1
    labelled_windows = set()
    dropped_prefix = 0
    dropped_range = 0
    for _, row in labels_df.iterrows():
        sample_idx = row["sample_idx"]
        if sample_idx < first_r_peak_abs:
            dropped_prefix += 1
            continue
        matches = np.where(cumulative_pos >= sample_idx)[0]
        if len(matches) == 0:
            dropped_range += 1
            continue
        beat_idx = int(matches[0])
        window_idx = min(beat_idx // STEP_SIZE, n_windows - 1)
        if 0 <= window_idx < n_windows:
            labelled_windows.add(window_idx)
        else:
            dropped_range += 1
    # Alignment bug check: if any annotation is within rr range, at least one must map
    if len(labels_df) > 0:
        in_range = (labels_df["sample_idx"] <= cumulative_pos[-1]).any()
        if in_range:
            assert len(labelled_windows) > 0, (
                f"{patient_id}: annotations in range but all dropped — alignment bug"
            )
    logging.info("  %s: %s annotations -> %s labelled windows (dropped_prefix=%s, dropped_range=%s, first_r_peak_abs=%s)",
                 patient_id, len(labels_df), len(labelled_windows), dropped_prefix, dropped_range, first_r_peak_abs)
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
    logging.info("  %s: %s windows after warmup drop (pos=%s, neg=%s, ratio=%.2f%%)",
                 patient_id, len(result), n_pos, n_neg, 100 * n_pos / max(len(result), 1))
    assert result.isnull().sum().sum() == 0
    return result


all_patients = []
for patient_id in PATIENTS:
    logging.info("-- %s --", patient_id)
    labelled_windows = align_labels_to_windows(patient_id)
    windowed_df = compute_deviations(patient_id, labelled_windows)
    out_path = PROCESSED_DIR / f"{patient_id}_windowed.csv"
    windowed_df.to_csv(out_path, index=False)
    logging.info("  Saved: %s", out_path)
    all_patients.append(windowed_df)

combined = pd.concat(all_patients, ignore_index=True)
combined.to_csv(PROCESSED_DIR / "all_patients_windowed.csv", index=False)
logging.info("Notebook 04 complete.")
logging.info("Combined shape:   %s", combined.shape)
logging.info("Total pos labels: %s / %s", combined['label'].sum(), len(combined))
logging.info("Overall pos rate: %.2f%%", 100 * combined['label'].mean())
logging.info("NaN in combined: %s", combined.isnull().sum().sum())
