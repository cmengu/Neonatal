#!/usr/bin/env python3
"""Respiration channel -> cardiorespiratory feature stream (issue #3).

Reads the PICS respiration and ECG annotation streams for every infant and, using
the pure functions in ``src.features.respiration``, writes alongside the existing
processed features:

  * ``infantN_resp_features.csv``       — windowed respiratory rate / variability / apnea burden
  * ``infantN_apnea_episodes.csv``      — one row per apnea episode, with its coupled bradycardia
  * ``all_patients_resp_features.csv``  — the per-infant windowed streams concatenated
  * ``cardioresp_coupling_summary.csv`` — per-infant + cohort apnea->bradycardia coupling vs a
    random-placement null (the evidence that the coupling is real)

Sampling frequencies are read from each record's header, never assumed: PICS
respiration is 50 Hz for most infants but 500 Hz for infant1, and ECG is 500 Hz
except 250 Hz for infant1/5. Everything is aligned in seconds.
"""
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import wfdb

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.features.constants import RESP_FEATURE_COLS  # noqa: E402
from src.features.respiration import (  # noqa: E402
    APNEA_MAX_PAUSE_S,
    APNEA_MIN_PAUSE_S,
    COUPLING_LAG_S,
    apnea_bradycardia_coupling,
    apnea_coincident_flags,
    clean_breath_times,
    detect_apnea_episodes,
    event_times_seconds,
    min_heart_rate_bpm,
    respiration_feature_rows,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S"
)

PATIENTS = [f"infant{i}" for i in range(1, 11)]
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
RAW_DIR = REPO_ROOT / "data" / "raw" / "physionet.org" / "files" / "picsdb" / "1.0.0"

RESP_ROW_COLS = ["record_name", "window_idx", "t_start_s", "t_end_s"] + RESP_FEATURE_COLS
EPISODE_COLS = [
    "record_name",
    "onset_s",
    "offset_s",
    "duration_s",
    "coincident_bradycardia",
    "nearest_brady_lag_s",
    "min_hr_bpm",
]
SUMMARY_COLS = [
    "record_name", "ecg_fs", "resp_fs", "duration_h", "n_breaths", "n_apnea",
    "n_signal_dropouts", "n_bradycardia", "n_coincident", "coincidence_rate",
    "expected_by_chance", "enrichment",
]


def load_event_times(record: str, extension: str):
    """Return (event_times_seconds, fs, sig_len) for a WFDB stream, fs from the header."""
    header = wfdb.rdheader(str(RAW_DIR / record))
    ann = wfdb.rdann(str(RAW_DIR / record), extension)
    return event_times_seconds(ann.sample, header.fs), float(header.fs), header.sig_len


def build_episode_rows(patient_id, episodes, brady_s, beats_s):
    """Annotate each apnea episode with its coupled bradycardia and HR nadir."""
    flags = apnea_coincident_flags(episodes, brady_s, COUPLING_LAG_S)
    brady = np.asarray(brady_s, dtype=np.float64)
    rows = []
    for episode, coincident in zip(episodes, flags):
        window_hi = episode["offset_s"] + COUPLING_LAG_S
        in_window = brady[(brady >= episode["onset_s"]) & (brady <= window_hi)]
        # Lag from the pause ending to the coupled bradycardia (negative = during the pause).
        nearest_lag = (
            float(in_window.min() - episode["offset_s"]) if in_window.size else float("nan")
        )
        rows.append(
            {
                "record_name": patient_id,
                "onset_s": episode["onset_s"],
                "offset_s": episode["offset_s"],
                "duration_s": episode["duration_s"],
                "coincident_bradycardia": int(coincident),
                "nearest_brady_lag_s": nearest_lag,
                "min_hr_bpm": min_heart_rate_bpm(beats_s, episode["onset_s"], window_hi),
            }
        )
    return rows


def process_patient(patient_id):
    """Compute and persist the respiration stream + apnea episodes; return (features, coupling)."""
    breaths_raw, resp_fs, resp_len = load_event_times(f"{patient_id}_resp", "resp")
    brady_s, ecg_fs, _ = load_event_times(f"{patient_id}_ecg", "atr")
    beats_s, _, _ = load_event_times(f"{patient_id}_ecg", "qrsc")

    breaths = clean_breath_times(breaths_raw)
    duration_s = resp_len / resp_fs
    episodes = detect_apnea_episodes(breaths, APNEA_MIN_PAUSE_S, APNEA_MAX_PAUSE_S)
    dropouts = int(np.sum(np.diff(breaths) > APNEA_MAX_PAUSE_S)) if breaths.size > 1 else 0

    # Windowed respiration feature stream (criterion 1).
    feature_rows = respiration_feature_rows(breaths, patient_id, apnea_episodes=episodes)
    features_df = pd.DataFrame(feature_rows, columns=RESP_ROW_COLS)
    features_df.to_csv(PROCESSED_DIR / f"{patient_id}_resp_features.csv", index=False)

    # Apnea episodes + their coupled bradycardia / HR nadir (criteria 2 & 3).
    episode_rows = build_episode_rows(patient_id, episodes, brady_s, beats_s)
    pd.DataFrame(episode_rows, columns=EPISODE_COLS).to_csv(
        PROCESSED_DIR / f"{patient_id}_apnea_episodes.csv", index=False
    )

    coupling = apnea_bradycardia_coupling(episodes, brady_s, duration_s)
    summary = {
        "record_name": patient_id,
        "ecg_fs": int(ecg_fs),
        "resp_fs": int(resp_fs),
        "duration_h": round(duration_s / 3600.0, 2),
        "n_breaths": int(breaths.size),
        "n_apnea": coupling["n_apnea"],
        "n_signal_dropouts": dropouts,
        "n_bradycardia": coupling["n_bradycardia"],
        "n_coincident": coupling["n_coincident"],
        "coincidence_rate": round(coupling["coincidence_rate"], 4),
        "expected_by_chance": round(coupling["expected_by_chance"], 3),
        "enrichment": round(coupling["enrichment"], 2) if np.isfinite(coupling["enrichment"]) else np.nan,
        # kept out of the CSV row order but used for the pooled cohort null:
        "_expected_raw": coupling["expected_by_chance"],
    }
    logging.info(
        "  %s: fs(ecg/resp)=%d/%d  breaths=%d  apnea=%d (dropouts>%.0fs=%d)  brady=%d  coincident=%d  enrichment=%.2fx",
        patient_id, ecg_fs, resp_fs, breaths.size, coupling["n_apnea"],
        APNEA_MAX_PAUSE_S, dropouts, coupling["n_bradycardia"], coupling["n_coincident"],
        coupling["enrichment"],
    )
    return features_df, summary


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    logging.info("RAW_DIR:       %s", RAW_DIR)
    logging.info("PROCESSED_DIR: %s", PROCESSED_DIR)

    all_features, summaries = [], []
    for patient_id in PATIENTS:
        logging.info("── %s ──────────────────────────────", patient_id)
        try:
            features_df, summary = process_patient(patient_id)
            all_features.append(features_df)
            summaries.append(summary)
        except FileNotFoundError as exc:
            logging.warning("%s skipped (missing record: %s)", patient_id, exc)
        except Exception as exc:
            logging.error("%s failed: %s", patient_id, exc)
            raise

    if all_features:
        combined = pd.concat(all_features, ignore_index=True)
        combined.to_csv(PROCESSED_DIR / "all_patients_resp_features.csv", index=False)
        logging.info("all_patients_resp_features.csv: %s", combined.shape)

    if summaries:
        summary_df = pd.DataFrame(summaries)[SUMMARY_COLS]
        summary_df.to_csv(PROCESSED_DIR / "cardioresp_coupling_summary.csv", index=False)
        logging.info("cardioresp_coupling_summary.csv: %s", summary_df.shape)

        pooled_coincident = int(summary_df["n_coincident"].sum())
        pooled_expected = float(sum(s["_expected_raw"] for s in summaries))
        pooled_enrichment = pooled_coincident / pooled_expected if pooled_expected > 0 else float("nan")
        logging.info(
            "COHORT apnea=%d  bradycardia=%d  coincident=%d  expected_by_chance=%.2f  ENRICHMENT=%.2fx",
            int(summary_df["n_apnea"].sum()), int(summary_df["n_bradycardia"].sum()),
            pooled_coincident, pooled_expected, pooled_enrichment,
        )

    logging.info("Respiration feature stream complete.")


if __name__ == "__main__":
    main()
