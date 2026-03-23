#!/usr/bin/env python3
"""Run notebook 02 real PICS loading logic (config + load cells)."""
import logging
import os
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
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
CHUNK_HOURS = 1  # Process ECG in 1-hour chunks to avoid OOM

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
logging.info("REPO_ROOT:     %s", REPO_ROOT)
logging.info("REAL_DATA_DIR: %s", REAL_DATA_DIR)
logging.info("PROCESSED_DIR: %s", PROCESSED_DIR)


def load_rr_from_wfdb(record_path, fs, ectopic_threshold, chunk_hours=1):
    """Load recording in chunks, trim flat prefix, process each chunk, merge R-peaks."""
    record_path = Path(record_path)
    header = wfdb.rdheader(str(record_path))
    sig_len = header.sig_len
    if hasattr(header, "fs") and header.fs is not None:
        fs = int(header.fs)
    logging.info("  Signal: %s samples @ %s Hz (%.1f h)", sig_len, fs, sig_len / fs / 3600)

    # 1. Detect flat prefix using first ~16 min
    flat_detect_samples = min(500_000, sig_len)
    flat_chunk = wfdb.rdsamp(str(record_path), sampfrom=0, sampto=flat_detect_samples)
    ecg_flat = flat_chunk[0][:, 0].astype(np.float64)
    del flat_chunk

    window = 100
    start_idx = 0
    for i in range(0, len(ecg_flat) - window, window):
        if ecg_flat[i : i + window].std() > 0.001:
            start_idx = i
            break
    del ecg_flat
    if start_idx > 0:
        logging.info("  Trimmed flat prefix: %s samples (%.1fs)", start_idx, start_idx / fs)

    # 2. Process in chunks from start_idx to end
    chunk_samples = chunk_hours * 3600 * fs
    all_r_peaks = []
    chunk_start = start_idx
    chunk_idx = 0
    while chunk_start < sig_len:
        chunk_end = min(chunk_start + chunk_samples, sig_len)
        record_chunk = wfdb.rdsamp(str(record_path), sampfrom=chunk_start, sampto=chunk_end)
        ecg_chunk = record_chunk[0][:, 0].astype(np.float64)
        del record_chunk

        signals, info = nk.ecg_process(ecg_chunk, sampling_rate=fs)
        del ecg_chunk
        r_peaks_local = np.array(info["ECG_R_Peaks"], dtype=np.int64)
        if len(r_peaks_local) > 0:
            global_peaks = chunk_start + r_peaks_local
            all_r_peaks.extend(global_peaks.tolist())
        del r_peaks_local, signals, info

        chunk_idx += 1
        if chunk_idx % 5 == 0 or chunk_end >= sig_len:
            logging.info("  Chunk %s: %s–%s (%s peaks so far)", chunk_idx, chunk_start, chunk_end, len(all_r_peaks))
        chunk_start = chunk_end

    if len(all_r_peaks) == 0:
        raise ValueError(f"No R-peaks detected for {record_path}. Check signal quality.")
    all_r_peaks = np.sort(np.unique(all_r_peaks))

    first_r_peak_abs = int(all_r_peaks[0])
    rr_ms = np.diff(all_r_peaks) / fs * 1000.0
    del all_r_peaks

    rolling_median = np.median(rr_ms)
    mask = np.abs(rr_ms - rolling_median) / rolling_median < ectopic_threshold
    rr_clean = rr_ms[mask]

    logging.info("  Raw beats: %s, after ectopic removal: %s", len(rr_ms), len(rr_clean))
    logging.info("  first_r_peak_absolute: %s samples (%.2fs)", first_r_peak_abs, first_r_peak_abs / fs)
    return rr_clean, first_r_peak_abs


if USE_REAL_DATA:
    first_r_peak_rows = []
    for patient_id in PATIENTS:
        try:
            record_path = REAL_DATA_DIR / f"{patient_id}_ecg"
            rr_clean, first_r_peak_abs = load_rr_from_wfdb(
                record_path, FS_ECG, ECTOPIC_THRESHOLD, chunk_hours=CHUNK_HOURS
            )
            out_path = PROCESSED_DIR / f"{patient_id}_rr_clean.csv"
            pd.DataFrame({"rr_ms": rr_clean}).to_csv(out_path, index=False)
            logging.info("  Saved: %s  (%s rows)", out_path, len(rr_clean))
            first_r_peak_rows.append({"record_name": patient_id, "first_r_peak_absolute": first_r_peak_abs})
        except FileNotFoundError as e:
            logging.error("%s record not found at %s: %s", patient_id, record_path, e)
            raise
        except Exception as e:
            raise RuntimeError(f"{patient_id} failed: {e}") from e
    frp_df = pd.DataFrame(first_r_peak_rows)
    frp_df.to_csv(PROCESSED_DIR / "first_r_peaks.csv", index=False)
    logging.info("Saved: %s", PROCESSED_DIR / "first_r_peaks.csv")
    logging.info("\n%s", frp_df.to_string(index=False))
else:
    logging.info("USE_REAL_DATA=False")
