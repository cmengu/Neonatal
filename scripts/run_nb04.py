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

import sys
import numpy as np
import pandas as pd

REPO_ROOT = Path(os.getcwd())
if REPO_ROOT.name == "notebooks":
    REPO_ROOT = REPO_ROOT.parent

sys.path.insert(0, str(REPO_ROOT))
from src.features.constants import HRV_FEATURE_COLS

PROCESSED_DIR = REPO_ROOT / "data" / "processed"
PATIENTS = [f"infant{i}" for i in range(1, 11)]
WINDOW_SIZE = 50
STEP_SIZE = 25
LOOKBACK = 10
HRV_COLS = HRV_FEATURE_COLS

# Alignment uses the per-beat sample positions carried in each *_rr_clean.csv
# (issue #18); no global fs constant and no first_r_peaks reconstruction are needed.

logging.info("REPO_ROOT:     %s", REPO_ROOT)
logging.info("PROCESSED_DIR: %s", PROCESSED_DIR)
logging.info("LOOKBACK:      %s windows", LOOKBACK)
logging.info("Patients:      %s", PATIENTS)


def align_labels_to_windows(patient_id):
    """Map each ``.atr`` bradycardia-onset sample to the HRV window that contains it.

    Both the onset (``sample_idx``) and the per-beat ``beat_sample`` positions carried
    from NB02 live in the same raw-sample space, so alignment is a direct positional
    lookup — no fs constant (issue #18: infant1/infant5 are 250 Hz, not 500), and no
    ``cumsum(rr)`` reconstruction (which drifted at every beat the physiological band
    dropped). Window ``w`` of NB03 spans retained-beat indices ``[w·STEP, w·STEP+WINDOW)``.
    """
    rr_df = pd.read_csv(PROCESSED_DIR / f"{patient_id}_rr_clean.csv")
    beat_sample = rr_df["beat_sample"].values
    labels_df = pd.read_csv(PROCESSED_DIR / f"{patient_id}_labels.csv")
    n_beats = len(beat_sample)
    n_windows = (n_beats - WINDOW_SIZE) // STEP_SIZE + 1
    labelled_windows = set()
    dropped_prefix = 0
    dropped_range = 0
    for _, row in labels_df.iterrows():
        sample_idx = row["sample_idx"]
        if sample_idx < beat_sample[0]:
            dropped_prefix += 1
            continue
        # First retained beat at or after the onset sample.
        matches = np.where(beat_sample >= sample_idx)[0]
        if len(matches) == 0:
            dropped_range += 1
            continue
        beat_idx = int(matches[0])
        window_idx = min(beat_idx // STEP_SIZE, n_windows - 1)
        if 0 <= window_idx < n_windows:
            labelled_windows.add(window_idx)
        else:
            dropped_range += 1
    # Alignment sanity: if any annotation is within the recorded beat span, one must map.
    if len(labels_df) > 0:
        in_range = (labels_df["sample_idx"] <= beat_sample[-1]).any()
        if in_range:
            assert len(labelled_windows) > 0, (
                f"{patient_id}: annotations in range but all dropped — alignment bug"
            )
    logging.info("  %s: %s annotations -> %s labelled windows (dropped_prefix=%s, dropped_range=%s, first_beat_sample=%s)",
                 patient_id, len(labels_df), len(labelled_windows), dropped_prefix, dropped_range, int(beat_sample[0]))
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
