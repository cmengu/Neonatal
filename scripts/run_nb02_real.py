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

REPO_ROOT = Path(os.getcwd())
if REPO_ROOT.name == "notebooks":
    REPO_ROOT = REPO_ROOT.parent

USE_REAL_DATA = True
REAL_DATA_DIR = REPO_ROOT / "data" / "raw" / "physionet.org" / "files" / "picsdb" / "1.0.0"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
PATIENTS = ["infant1", "infant2", "infant3", "infant4", "infant5",
            "infant6", "infant7", "infant8", "infant9", "infant10"]
# Physiological RR band (issue #18). The old ectopic filter was a global-median
# percentage band that DELETED bradycardia (a large sustained RR jump reads as
# ectopic), so the bradycardia target never reached any tier. A bradycardia is a
# real interval; a multi-second gap is a sensor dropout. RR_MIN=200ms (HR 300,
# rejects double-detections) .. RR_MAX=2000ms (HR 30) preserves every annotated
# bradycardia onset in this cohort (measured onset RR maxes at ~1542ms) while
# dropping the handful of >2s recording gaps. Sample fs is per-infant (250 Hz for
# infant1/infant5, 500 Hz otherwise) — read from each header, never hardcoded.
RR_MIN_MS = 200.0
RR_MAX_MS = 2000.0

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
logging.info("REPO_ROOT:     %s", REPO_ROOT)
logging.info("REAL_DATA_DIR: %s", REAL_DATA_DIR)
logging.info("PROCESSED_DIR: %s", PROCESSED_DIR)


def load_rr_from_wfdb(record_path, rr_min_ms=RR_MIN_MS, rr_max_ms=RR_MAX_MS):
    """Build the RR stream from the reference QRS annotations (``.qrsc``).

    The ``.qrsc`` file is the dataset's *reference* R-peak set (ANNOTATORS:
    "Reference ECG r peaks") — gold-standard beat locations, so there is no need
    to re-detect peaks from the raw ECG (the old neurokit2 path). Sample fs is read
    per-infant from the header. RR intervals outside the physiological band are
    dropped (non-physiological jumps / sensor gaps), which — unlike the old
    global-median band — *keeps* bradycardia (issue #18).

    Returns ``(rr_clean_ms, beat_sample)`` where ``beat_sample[i]`` is the raw-space
    sample index of the beat ENDING interval ``rr_clean_ms[i]``. Carrying the true
    sample position lets NB04 align ``.atr`` onsets to windows exactly, with no fs
    assumption and no cumulative-sum drift across dropped beats.
    """
    record_path = Path(record_path)
    header = wfdb.rdheader(str(record_path))
    fs = int(header.fs)
    logging.info("  Signal: %s samples @ %s Hz (%.1f h)", header.sig_len, fs, header.sig_len / fs / 3600)

    ann = wfdb.rdann(str(record_path), "qrsc")
    peaks = np.asarray(ann.sample, dtype=np.int64)
    peaks = np.sort(np.unique(peaks))
    if len(peaks) < 2:
        raise ValueError(f"Too few reference QRS annotations for {record_path}.")

    rr_ms = np.diff(peaks) / fs * 1000.0
    end_beat = peaks[1:]  # sample index of the beat ending each interval

    band = (rr_ms >= rr_min_ms) & (rr_ms <= rr_max_ms)
    rr_clean = rr_ms[band]
    beat_sample = end_beat[band]

    brady = int(np.sum(rr_clean > 600.0))
    logging.info(
        "  Reference beats: %s, RR intervals: %s, in-band: %s (dropped %s), "
        "bradycardia RR>600ms kept: %s, max RR: %.0fms",
        len(peaks), len(rr_ms), len(rr_clean), len(rr_ms) - len(rr_clean),
        brady, rr_clean.max() if len(rr_clean) else 0.0,
    )
    first_r_peak_abs = int(beat_sample[0]) if len(beat_sample) else int(peaks[0])
    logging.info("  first_r_peak_absolute: %s samples (%.2fs)", first_r_peak_abs, first_r_peak_abs / fs)
    return rr_clean, beat_sample, first_r_peak_abs


if USE_REAL_DATA:
    first_r_peak_rows = []
    for patient_id in PATIENTS:
        try:
            record_path = REAL_DATA_DIR / f"{patient_id}_ecg"
            rr_clean, beat_sample, first_r_peak_abs = load_rr_from_wfdb(record_path)
            out_path = PROCESSED_DIR / f"{patient_id}_rr_clean.csv"
            pd.DataFrame({"rr_ms": rr_clean, "beat_sample": beat_sample}).to_csv(out_path, index=False)
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
