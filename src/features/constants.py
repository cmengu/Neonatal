"""
Shared constants for the HRV feature pipeline.

``HRV_FEATURE_COLS`` is the single source of truth for the ordered list of
HRV feature column names produced by ``src.features.hrv.compute_hrv_features()``.

Import this list everywhere column names are needed instead of re-defining it
locally.  Files that must stay in sync:
  - src/features/hrv.py          (defines the computation; keys must match)
  - scripts/run_nb03.py          (schema assertion in extract_features)
  - scripts/run_nb04.py          (HRV_COLS loop in compute_deviations)
  - scripts/build_training_data.py (FEATURE_COLS assertion after merge)
  - scripts/generate_nb04.py    (HRV_COLS in generated notebook cell1)
"""

HRV_FEATURE_COLS = [
    "mean_rr",
    "sdnn",
    "rmssd",
    "pnn50",
    "lf_hf_ratio",
    "rr_ms_min",
    "rr_ms_max",
    "rr_ms_25%",
    "rr_ms_50%",
    "rr_ms_75%",
]
