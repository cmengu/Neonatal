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
import logging
import sys
from pathlib import Path
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")

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

logging.info("REPO_ROOT:     %s", REPO_ROOT)
logging.info("PROCESSED_DIR: %s", PROCESSED_DIR)
logging.info("RAW_DIR:       %s", RAW_DIR)


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
    logging.info("  %s: %s annotations", patient_id, len(df))
    logging.info("  symbols: %s", sorted(df['symbol'].unique()))
    return df


for patient_id in PATIENTS:
    logging.info("── %s ──────────────────────────────", patient_id)
    try:
        features_df = extract_features(patient_id)
        feat_path = PROCESSED_DIR / f"{patient_id}_features.csv"
        features_df.to_csv(feat_path, index=False)
        logging.info("  features: %s → %s", features_df.shape, feat_path)

        labels_df = extract_labels(patient_id)
        label_path = PROCESSED_DIR / f"{patient_id}_labels.csv"
        labels_df.to_csv(label_path, index=False)
        logging.info("  labels:   %s → %s", labels_df.shape, label_path)
    except FileNotFoundError as e:
        logging.warning("%s skipped (missing rr_clean: %s)", patient_id, e)
    except Exception as e:
        logging.error("%s failed: %s", patient_id, e)
        raise

logging.info("Notebook 03 complete.")
