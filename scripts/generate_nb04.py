#!/usr/bin/env python3
"""Generate notebooks/04_baseline_deviation.ipynb. Run from repo root: python scripts/generate_nb04.py"""
import os
from pathlib import Path

import nbformat

REPO_ROOT = Path(os.getcwd())
if REPO_ROOT.name == "notebooks":
    REPO_ROOT = REPO_ROOT.parent

nb = nbformat.v4.new_notebook()

cell1 = """import sys
import os
from pathlib import Path
import numpy as np
import pandas as pd

REPO_ROOT = Path(os.getcwd())
if REPO_ROOT.name == "notebooks":
    REPO_ROOT = REPO_ROOT.parent

sys.path.insert(0, str(REPO_ROOT))

# NOTE: PATIENTS must stay in sync with notebooks 02 and 03.
PATIENTS      = [f"infant{i}" for i in range(1, 11)]
PROCESSED_DIR = REPO_ROOT / "data" / "processed"

WINDOW_SIZE = 50    # beats — must match NB03
STEP_SIZE   = 25    # beats — must match NB03
LOOKBACK    = 10    # windows for rolling baseline
FS_ECG      = 500   # Hz

HRV_COLS = [
    "rr_ms_mean", "rr_ms_std", "rr_ms_min",
    "rr_ms_max", "rr_ms_25%", "rr_ms_50%", "rr_ms_75%"
]

# Load first R-peak positions — written by scripts/run_nb02_real.py (anchors cumulative_pos)
frp_df         = pd.read_csv(PROCESSED_DIR / "first_r_peaks.csv")
missing        = [p for p in PATIENTS if p not in frp_df["record_name"].values]
assert not missing, f"first_r_peaks.csv is missing patients: {missing}"
FIRST_R_PEAKS  = dict(zip(frp_df["record_name"], frp_df["first_r_peak_absolute"].astype(int)))

print(f"REPO_ROOT:     {REPO_ROOT}")
print(f"PROCESSED_DIR: {PROCESSED_DIR}")
print(f"LOOKBACK:      {LOOKBACK} windows")
print(f"Patients:      {PATIENTS}")
print(f"First R-peaks: {FIRST_R_PEAKS}")"""

cell2 = """def align_labels_to_windows(patient_id):
    \"\"\"
    Map annotation sample_idx -> window_idx using cumulative RR sum
    anchored to first_r_peak_absolute (recording coordinates).

    Method:
      1. Load rr_clean, first_r_peak_abs from FIRST_R_PEAKS
      2. cumulative_pos = first_r_peak_abs + np.cumsum(rr_samples) — in recording coords
      3. For each annotation: if sample_idx < first_r_peak_abs -> drop (before first beat)
      4. Find beat_idx: first beat where cumulative_pos >= sample_idx
      5. Map beat_idx -> window_idx: min(beat_idx // STEP_SIZE, n_windows - 1)
      6. Drop annotations outside valid window range

    Returns: set of window_idx values containing a bradycardia episode start.
    \"\"\"
    rr_ms     = pd.read_csv(PROCESSED_DIR / f"{patient_id}_rr_clean.csv")["rr_ms"].values
    labels_df = pd.read_csv(PROCESSED_DIR / f"{patient_id}_labels.csv")

    rr_samples         = rr_ms / 1000.0 * FS_ECG
    first_r_peak_abs   = FIRST_R_PEAKS[patient_id]
    cumulative_pos     = first_r_peak_abs + np.cumsum(rr_samples)
    n_windows          = (len(rr_ms) - WINDOW_SIZE) // STEP_SIZE + 1

    labelled_windows = set()
    dropped_prefix   = 0
    dropped_range    = 0

    for _, row in labels_df.iterrows():
        sample_idx = row["sample_idx"]

        # Drop annotations before first beat
        if sample_idx < first_r_peak_abs:
            dropped_prefix += 1
            continue

        # Find beat_idx: first beat whose cumulative position >= sample_idx
        matches = np.where(cumulative_pos >= sample_idx)[0]
        if len(matches) == 0:
            dropped_range += 1
            continue

        beat_idx   = int(matches[0])
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
    print(f"  {patient_id}: {len(labels_df)} annotations -> "
          f"{len(labelled_windows)} labelled windows "
          f"(dropped_prefix={dropped_prefix}, dropped_range={dropped_range}, "
          f"first_r_peak_abs={first_r_peak_abs})")
    return labelled_windows"""

cell3 = """def compute_deviations(patient_id, labelled_windows):
    \"\"\"
    Compute rolling z-score deviation from personal baseline.

    Steps:
      1. Load features CSV
      2. For each HRV column compute rolling mean and std over
         previous LOOKBACK windows (exclusive of current window)
      3. Z-score: (current - rolling_mean) / rolling_std
      4. Guard: if rolling_std == 0, deviation = 0.0
      5. Drop first LOOKBACK rows (warmup)
      6. Add binary label from labelled_windows
    \"\"\"
    features = pd.read_csv(PROCESSED_DIR / f"{patient_id}_features.csv")

    # Assert window_idx is contiguous from 0 — required for iloc[LOOKBACK:] to be correct
    assert features["window_idx"].iloc[0] == 0, \\
        f"{patient_id}: window_idx does not start at 0"
    assert (features["window_idx"].diff().dropna() == 1).all(), \\
        f"{patient_id}: window_idx is not contiguous"

    dev_cols = {}
    for col in HRV_COLS:
        values    = features[col].values
        roll_mean = np.full(len(values), np.nan)
        roll_std  = np.full(len(values), np.nan)

        for i in range(LOOKBACK, len(values)):
            window_vals  = values[i - LOOKBACK : i]
            roll_mean[i] = window_vals.mean()
            roll_std[i]  = window_vals.std(ddof=1)

        with np.errstate(invalid="ignore", divide="ignore"):
            deviation = np.where(
                roll_std == 0,
                0.0,
                (values - roll_mean) / roll_std
            )
        dev_cols[f"{col}_dev"] = deviation

    result = pd.DataFrame(dev_cols)
    result.insert(0, "window_idx",  features["window_idx"])
    result.insert(0, "record_name", features["record_name"])

    # Drop warmup rows — valid because window_idx is contiguous from 0
    result = result.iloc[LOOKBACK:].reset_index(drop=True)

    result["label"] = result["window_idx"].apply(
        lambda w: 1 if w in labelled_windows else 0
    )

    n_pos = result["label"].sum()
    n_neg = len(result) - n_pos
    print(f"  {patient_id}: {len(result)} windows after warmup drop "
          f"(pos={n_pos}, neg={n_neg}, ratio={n_pos/max(len(result),1):.2%})")

    nan_count = result.isnull().sum().sum()
    assert nan_count == 0, f"NaN in output for {patient_id}: {result.isnull().sum()}"

    return result"""

cell4 = """all_patients = []

for patient_id in PATIENTS:
    print(f"\\n-- {patient_id} --")
    labelled_windows = align_labels_to_windows(patient_id)
    windowed_df      = compute_deviations(patient_id, labelled_windows)

    out_path = PROCESSED_DIR / f"{patient_id}_windowed.csv"
    windowed_df.to_csv(out_path, index=False)
    print(f"  Saved: {out_path}")
    all_patients.append(windowed_df)

combined      = pd.concat(all_patients, ignore_index=True)
combined_path = PROCESSED_DIR / "all_patients_windowed.csv"
combined.to_csv(combined_path, index=False)

print(f"\\nNotebook 04 complete.")
print(f"Combined shape:   {combined.shape}")
print(f"Total pos labels: {combined['label'].sum()} / {len(combined)}")
print(f"Overall pos rate: {combined['label'].mean():.2%}")
print(f"NaN in combined:  {combined.isnull().sum().sum()}")"""

cell5 = """import matplotlib.pyplot as plt

fig, axes = plt.subplots(2, 5, figsize=(18, 6))
axes = axes.flatten()

for idx, patient_id in enumerate(PATIENTS):
    df  = pd.read_csv(PROCESSED_DIR / f"{patient_id}_windowed.csv")
    ax  = axes[idx]
    ax.plot(df["window_idx"], df["rr_ms_mean_dev"], linewidth=0.8, color="steelblue")
    pos = df[df["label"] == 1]
    ax.scatter(pos["window_idx"], pos["rr_ms_mean_dev"],
               color="red", s=30, zorder=5, label="bradycardia")
    ax.set_title(f"{patient_id} (n={len(df)}, pos={len(pos)})", fontsize=9)
    ax.set_xlabel("window_idx", fontsize=7)
    ax.set_ylabel("rr_ms_mean_dev", fontsize=7)
    ax.axhline(0, color="grey", linestyle="--", linewidth=0.5)

plt.suptitle("RR Mean Deviation with Bradycardia Events (red) — first_r_peak_abs alignment", fontsize=11)
plt.tight_layout()
plt.show()"""

nb.cells = [
    nbformat.v4.new_code_cell(cell1),
    nbformat.v4.new_code_cell(cell2),
    nbformat.v4.new_code_cell(cell3),
    nbformat.v4.new_code_cell(cell4),
    nbformat.v4.new_code_cell(cell5),
]

out_path = REPO_ROOT / "notebooks" / "04_baseline_deviation.ipynb"
with open(out_path, "w") as f:
    nbformat.write(nb, f)
print(f"Notebook written: {out_path}")
