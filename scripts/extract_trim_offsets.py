#!/usr/bin/env python3
"""
Extract flat-prefix trim offsets from raw ECG records for all 10 patients.

Re-runs the same trim-detection logic as NB02 Cell 1 (window=100, std > 0.001).
Writes data/processed/trim_offsets.csv for NB04 label alignment.

Run from repo root: python scripts/extract_trim_offsets.py
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd
import wfdb

REPO_ROOT = Path(os.getcwd())
RAW_DIR = REPO_ROOT / "data" / "raw" / "physionet.org" / "files" / "picsdb" / "1.0.0"
OUT_PATH = REPO_ROOT / "data" / "processed" / "trim_offsets.csv"
PATIENTS = [f"infant{i}" for i in range(1, 11)]
FS_ECG = 500
WINDOW = 100  # must match NB02 trim-detection window size
STD_THRESH = 0.001  # must match NB02 threshold

rows = []
for patient_id in PATIENTS:
    record_path = str(RAW_DIR / f"{patient_id}_ecg")
    record = wfdb.rdsamp(record_path, sampto=500000)
    ecg_signal = record[0][:, 0].astype(float)

    start_idx = 0
    for i in range(0, len(ecg_signal) - WINDOW, WINDOW):
        if ecg_signal[i : i + WINDOW].std() > STD_THRESH:
            start_idx = i
            break

    rows.append({"record_name": patient_id, "start_idx_samples": start_idx})
    print(
        f"  {patient_id}: start_idx_samples = {start_idx} "
        f"({start_idx / FS_ECG:.1f}s trimmed)"
    )

df = pd.DataFrame(rows)
df.to_csv(OUT_PATH, index=False)
print(f"\nSaved: {OUT_PATH}")
print(df.to_string(index=False))
