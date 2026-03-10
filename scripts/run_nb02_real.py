#!/usr/bin/env python3
"""Run notebook 02 real PICS loading logic (config + load cells)."""
import os
os.environ["MPLBACKEND"] = "Agg"
# Use project-local dir — /tmp can be restricted under nohup
_cwd = os.path.dirname(os.path.abspath(__file__))
os.environ["MPLCONFIGDIR"] = os.path.join(_cwd, "..", ".mpl_config")
# Avoid matplotlib font crash on macOS (KeyError '_items' / slow system_profiler)
# when system_profiler not on PATH, matplotlib falls back to standard font dirs
os.environ["PATH"] = "/usr/bin:/bin:/usr/local/bin"
import matplotlib
matplotlib.use("Agg")  # non-interactive backend — required for nohup
from pathlib import Path

import numpy as np
import pandas as pd
import wfdb
import neurokit2 as nk

REPO_ROOT = Path(os.getcwd())
if REPO_ROOT.name == "notebooks":
    REPO_ROOT = REPO_ROOT.parent

USE_REAL_DATA = True
REAL_DATA_DIR = REPO_ROOT / "data" / "raw" / "physionet.org" / "files" / "picsdb" / "1.0.0"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
PATIENTS = ["infant1", "infant2", "infant3", "infant4", "infant5",
            "infant6", "infant7", "infant8", "infant9", "infant10"]
FS_ECG = 500
ECTOPIC_THRESHOLD = 0.20

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
print(f"REPO_ROOT:     {REPO_ROOT}")
print(f"REAL_DATA_DIR: {REAL_DATA_DIR}")
print(f"PROCESSED_DIR: {PROCESSED_DIR}")


def load_rr_from_wfdb(record_path, fs, ectopic_threshold):
    """Load full recording, trim flat prefix, then process."""
    record = wfdb.rdsamp(str(record_path))
    ecg_signal = record[0][:, 0]
    if isinstance(record[1], dict) and "fs" in record[1]:
        fs = record[1]["fs"]
    print(f"  Signal names: {record[1]['sig_name']}")

    # Trim flat prefix (affects infant5 — >12 min flat at start)
    window = 100
    start_idx = 0
    for i in range(0, len(ecg_signal) - window, window):
        if ecg_signal[i : i + window].std() > 0.001:
            start_idx = i
            break
    if start_idx > 0:
        print(f"  Trimmed flat prefix: {start_idx} samples ({start_idx/fs:.1f}s)")
    ecg_signal = ecg_signal[start_idx:]

    signals, info = nk.ecg_process(ecg_signal, sampling_rate=fs)
    r_peaks = info["ECG_R_Peaks"]
    first_r_peak_abs = int(start_idx + r_peaks[0])
    rr_ms = np.diff(r_peaks) / fs * 1000.0

    rolling_median = np.median(rr_ms)
    mask = np.abs(rr_ms - rolling_median) / rolling_median < ectopic_threshold
    rr_clean = rr_ms[mask]

    print(f"  Raw beats: {len(rr_ms)}, after ectopic removal: {len(rr_clean)}")
    print(f"  first_r_peak_absolute: {first_r_peak_abs} samples ({first_r_peak_abs/fs:.2f}s)")
    return rr_clean, first_r_peak_abs


if USE_REAL_DATA:
    first_r_peak_rows = []
    for patient_id in PATIENTS:
        try:
            record_path = REAL_DATA_DIR / f"{patient_id}_ecg"
            rr_clean, first_r_peak_abs = load_rr_from_wfdb(record_path, FS_ECG, ECTOPIC_THRESHOLD)
            out_path = PROCESSED_DIR / f"{patient_id}_rr_clean.csv"
            pd.DataFrame({"rr_ms": rr_clean}).to_csv(out_path, index=False)
            print(f"  Saved: {out_path}  ({len(rr_clean)} rows)")
            first_r_peak_rows.append({"record_name": patient_id, "first_r_peak_absolute": first_r_peak_abs})
        except FileNotFoundError as e:
            print(f"  ERROR: {patient_id} record not found at {record_path}: {e}")
            raise
        except Exception as e:
            print(f"  WARNING: {patient_id} skipped ({e})")
    frp_df = pd.DataFrame(first_r_peak_rows)
    frp_df.to_csv(PROCESSED_DIR / "first_r_peaks.csv", index=False)
    print(f"\nSaved: {PROCESSED_DIR / 'first_r_peaks.csv'}")
    print(frp_df.to_string(index=False))
else:
    print("USE_REAL_DATA=False")
