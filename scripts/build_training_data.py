"""Build combined_features_labelled.csv for Phase 1 classifier training.

Joins each patient's _features.csv (raw HRV) with _windowed.csv (labels) on window_idx.
Saves to data/processed/combined_features_labelled.csv.
Run from repo root: python scripts/build_training_data.py
"""
import pandas as pd
from pathlib import Path

PROCESSED = Path("data/processed")
PATIENTS = [f"infant{i}" for i in range(1, 11)]

FEATURE_COLS = [
    "mean_rr", "sdnn", "rmssd", "pnn50", "lf_hf_ratio",
    "rr_ms_min", "rr_ms_max", "rr_ms_25%", "rr_ms_50%", "rr_ms_75%"
]

rows = []
for pid in PATIENTS:
    feat_path  = PROCESSED / f"{pid}_features.csv"
    label_path = PROCESSED / f"{pid}_windowed.csv"

    if not feat_path.exists():
        print(f"  SKIP {pid}: {feat_path} not found")
        continue
    if not label_path.exists():
        print(f"  SKIP {pid}: {label_path} not found")
        continue

    feat_df  = pd.read_csv(feat_path)
    label_df = pd.read_csv(label_path)[["window_idx", "label"]]
    # inner join drops warmup windows (idx 0–9) which have no label row in _windowed.csv
    # because run_nb04.py drops the first LOOKBACK=10 rows before writing labels
    merged   = feat_df.merge(label_df, on="window_idx", how="inner")

    missing_feat = [c for c in FEATURE_COLS if c not in merged.columns]
    assert not missing_feat, f"{pid}: feature columns missing after merge: {missing_feat}"

    rows.append(merged)
    print(f"  {pid}: {len(merged)} rows  (pos={merged['label'].sum()}, neg={(merged['label']==0).sum()})")

assert len(rows) == 10, f"Expected 10 patients, got {len(rows)} — check that data/processed/ is accessible from {Path.cwd()}"

combined = pd.concat(rows, ignore_index=True)
out_path = PROCESSED / "combined_features_labelled.csv"
combined.to_csv(out_path, index=False)

print(f"\nSaved: {out_path}")
print(f"Shape:            {combined.shape}")
print(f"Positive labels:  {combined['label'].sum()} / {len(combined)} ({100*combined['label'].mean():.1f}%)")
print(f"NaN count:        {combined.isnull().sum().sum()}")
print(f"Columns:          {list(combined.columns)}")
