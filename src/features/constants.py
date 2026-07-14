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
    # HeRO discriminators added in issue #13 (replace the crude RR-tail proxies as
    # Tier-1 triggers): sample entropy (low-only) + sample asymmetry (high-only).
    "sampen",
    "sample_asymmetry",
]

# Ordered column names for the respiration-derived cardiorespiratory feature
# stream produced by ``src.features.respiration.compute_respiration_features()``
# (issue #3). Kept as the single source of truth exactly like HRV_FEATURE_COLS.
# The keys returned by compute_respiration_features() must stay in sync with this
# list; ``tests/test_respiration_features.py`` asserts the invariant.
RESP_FEATURE_COLS = [
    "resp_rate_bpm",       # detected respiration-peak rate over the window (breaths/min)
    "breath_interval_cv",  # respiratory variability: CV of inter-breath intervals
    "n_breaths",           # breath-peak count in the window
    "apnea_count",         # apnea episodes (>= APNEA_MIN_PAUSE_S) overlapping the window
    "apnea_seconds",       # total apnea-overlap seconds within the window
    "longest_apnea_s",     # longest single apnea overlap within the window
]
