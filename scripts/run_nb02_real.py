#!/usr/bin/env python3
"""Run notebook 02 real PICS loading logic (config + load cells)."""
from pathlib import Path
import os

REPO_ROOT = Path(os.getcwd())
if REPO_ROOT.name == "notebooks":
    REPO_ROOT = REPO_ROOT.parent

USE_REAL_DATA = True
REAL_DATA_DIR = REPO_ROOT / "data" / "raw" / "physionet.org" / "files" / "picsdb" / "1.0.0"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
PATIENTS = ["infant1", "infant10"]
FS_ECG = 500
ECTOPIC_THRESHOLD = 0.20

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
print(f"REPO_ROOT:     {REPO_ROOT}")
print(f"REAL_DATA_DIR: {REAL_DATA_DIR}")
print(f"PROCESSED_DIR: {PROCESSED_DIR}")

import wfdb
import neurokit2 as nk
import numpy as np
import pandas as pd


def load_rr_from_wfdb(record_path, fs, ectopic_threshold, max_samples=300000):
    """Load first max_samples (5 min at 500Hz) to keep runtime manageable."""
    record = wfdb.rdsamp(str(record_path), sampto=min(max_samples, 500000))
    ecg_signal = record[0][:, 0]
    if isinstance(record[1], dict) and "fs" in record[1]:
        fs = record[1]["fs"]
    print(f"  Signal names: {record[1]['sig_name']}")

    signals, info = nk.ecg_process(ecg_signal, sampling_rate=fs)
    r_peaks = info["ECG_R_Peaks"]
    rr_ms = np.diff(r_peaks) / fs * 1000.0

    rolling_median = np.median(rr_ms)
    mask = np.abs(rr_ms - rolling_median) / rolling_median < ectopic_threshold
    rr_clean = rr_ms[mask]

    print(f"  Raw beats: {len(rr_ms)}, after ectopic removal: {len(rr_clean)}")
    return rr_clean


if USE_REAL_DATA:
    for patient_id in PATIENTS:
        record_path = REAL_DATA_DIR / f"{patient_id}_ecg"
        rr_clean = load_rr_from_wfdb(record_path, FS_ECG, ECTOPIC_THRESHOLD)
        out_path = PROCESSED_DIR / f"{patient_id}_rr_clean.csv"
        pd.DataFrame({"rr_ms": rr_clean}).to_csv(out_path, index=False)
        print(f"  Saved: {out_path}  ({len(rr_clean)} rows)")
else:
    print("USE_REAL_DATA=False")
