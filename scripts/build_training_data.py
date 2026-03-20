"""Build combined_features_labelled.csv for Phase 1 classifier training.

Joins each patient's _features.csv (raw HRV) with _windowed.csv (labels) on window_idx.
Saves to data/processed/combined_features_labelled.csv.
Run from repo root: python scripts/build_training_data.py
"""
import logging
import sys
from pathlib import Path

import pandas as pd

# Resolve repo root from this file's location so the script runs correctly
# regardless of the working directory (unlike Path("data/processed") which
# silently fails if invoked from a subdirectory like notebooks/).
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.features.constants import HRV_FEATURE_COLS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)

PROCESSED = REPO_ROOT / "data" / "processed"
PATIENTS = [f"infant{i}" for i in range(1, 11)]

rows = []
for pid in PATIENTS:
    feat_path  = PROCESSED / f"{pid}_features.csv"
    label_path = PROCESSED / f"{pid}_windowed.csv"

    if not feat_path.exists():
        logging.warning("SKIP %s: %s not found", pid, feat_path)
        continue
    if not label_path.exists():
        logging.warning("SKIP %s: %s not found", pid, label_path)
        continue

    feat_df  = pd.read_csv(feat_path)
    label_df = pd.read_csv(label_path)[["window_idx", "label"]]
    # inner join drops warmup windows (idx 0–9) which have no label row in _windowed.csv
    # because run_nb04.py drops the first LOOKBACK=10 rows before writing labels
    merged   = feat_df.merge(label_df, on="window_idx", how="inner")

    missing_feat = [c for c in HRV_FEATURE_COLS if c not in merged.columns]
    if missing_feat:
        raise RuntimeError(
            f"{pid}: feature columns missing after merge: {missing_feat}. "
            f"Re-run scripts/run_nb03.py to regenerate _features.csv."
        )

    rows.append(merged)
    logging.info(
        "  %s: %d rows  (pos=%d, neg=%d)",
        pid, len(merged), merged["label"].sum(), (merged["label"] == 0).sum(),
    )

if len(rows) != 10:
    raise RuntimeError(
        f"Expected 10 patients, got {len(rows)} — "
        f"check that {PROCESSED} is accessible from {Path.cwd()}"
    )

combined = pd.concat(rows, ignore_index=True)
out_path = PROCESSED / "combined_features_labelled.csv"
combined.to_csv(out_path, index=False)

logging.info("Saved: %s", out_path)
logging.info("Shape:           %s", combined.shape)
logging.info(
    "Positive labels: %d / %d (%.1f%%)",
    combined["label"].sum(), len(combined), 100 * combined["label"].mean(),
)
logging.info("NaN count:       %d", combined.isnull().sum().sum())
logging.info("Columns:         %s", list(combined.columns))
