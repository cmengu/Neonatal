"""Build an AssessmentContext for a real patient — without the ONNX classifier.

The classifier is being retired (ADR-0002), so this reads the personalised z-scores
and HRV values straight from the processed CSVs, the same data the old pipeline
loaded, minus the ONNX inference. When Tier 2 arrives it will extend the context
with window history; for now Tier 1 needs only the latest window's z-scores.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.assessment.types import AssessmentContext
from src.features.constants import HRV_FEATURE_COLS

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_PROCESSED = REPO_ROOT / "data" / "processed"
_BRADY_RR_MS = 600.0  # mean_rr > 600ms == HR < 100bpm


def load_context(patient_id: str) -> AssessmentContext:
    """Load the latest window's personalised deviations and HRV values for a patient."""
    feat_path = _PROCESSED / f"{patient_id}_features.csv"
    windowed_path = _PROCESSED / f"{patient_id}_windowed.csv"
    if not feat_path.exists():
        raise FileNotFoundError(f"No features file: {feat_path}")
    if not windowed_path.exists():
        raise FileNotFoundError(f"No windowed file: {windowed_path}")

    feat_df = pd.read_csv(feat_path)
    windowed_df = pd.read_csv(windowed_path)
    if len(feat_df) == 0 or len(windowed_df) == 0:
        raise ValueError(f"{patient_id}: empty CSV files")

    latest = windowed_df.iloc[-1]
    z_scores = {
        col: float(latest[f"{col}_dev"])
        for col in HRV_FEATURE_COLS
        if f"{col}_dev" in windowed_df.columns
    }

    latest_feat = feat_df.iloc[-1]
    hrv_values = {
        col: float(latest_feat[col]) for col in HRV_FEATURE_COLS if col in feat_df.columns
    }

    n_events = (
        int((feat_df["mean_rr"] > _BRADY_RR_MS).sum()) if "mean_rr" in feat_df.columns else 0
    )

    return AssessmentContext(
        patient_id=patient_id,
        z_scores=z_scores,
        hrv_values=hrv_values,
        n_events=n_events,
    )


def personal_baseline(patient_id: str) -> dict[str, dict[str, float]]:
    """Per-infant baseline mean/std for each HRV feature, over that infant's own history.

    Used only to *display* the baseline the deviations are measured against (in the RAG
    prompts + ``get_top_deviated``); it never drives routing — the personalised z-scores in
    the context already carry the deviation. Replaces the old ONNX pipeline's LOOKBACK-window
    ``personal_baseline`` with a simple whole-record per-feature mean/std.
    """
    feat_path = _PROCESSED / f"{patient_id}_features.csv"
    if not feat_path.exists():
        return {}
    feat_df = pd.read_csv(feat_path)
    baseline: dict[str, dict[str, float]] = {}
    for col in HRV_FEATURE_COLS:
        if col in feat_df.columns:
            series = feat_df[col]
            baseline[col] = {
                "mean": float(series.mean()),
                "std": float(series.std() or 1.0),
            }
    return baseline
