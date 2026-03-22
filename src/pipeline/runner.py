"""NeonatalPipeline: wraps ONNX bradycardia-onset inference + CSV loading into PipelineResult.

The ONNX model predicts bradycardia-onset risk (PICS .atr labels: HR < 100 bpm, >= 2 beats),
used as a proxy for early physiological deterioration preceding sepsis. Do not describe
risk_score as a "sepsis probability" — it is a bradycardia-onset probability.

All paths are resolved relative to this file, not CWD. Safe to import and
instantiate from any working directory.
Run from repo root: python -c "from src.pipeline.runner import NeonatalPipeline; ..."
"""
from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

from src.pipeline.result import BradycardiaEvent, PipelineResult

# LOOKBACK must match run_nb04.py constant — the rolling window used to compute z-scores
_LOOKBACK = 10


class NeonatalPipeline:
    """
    Load-on-instantiation ONNX runner. Safe to import before the model is trained.
    Raises FileNotFoundError (with clear message) if ONNX file not found.
    """

    def __init__(self) -> None:
        import onnxruntime as ort

        onnx_path = REPO_ROOT / "models" / "exports" / "neonatalguard_v1.onnx"
        cols_path = REPO_ROOT / "models" / "exports" / "feature_cols.pkl"

        if not onnx_path.exists():
            raise FileNotFoundError(
                f"ONNX model not found: {onnx_path}. Run src/models/export_onnx.py first."
            )
        if not cols_path.exists():
            raise FileNotFoundError(
                f"Feature cols not found: {cols_path}. Run src/models/train_classifier.py first."
            )

        self._sess = ort.InferenceSession(str(onnx_path))
        with open(cols_path, "rb") as f:
            self._feature_cols: list[str] = pickle.load(f)

    def run(self, patient_id: str) -> PipelineResult:
        """
        Build PipelineResult from pre-processed CSVs for patient_id.

        z_scores come from _windowed.csv (computed by run_nb04.py with LOOKBACK=10).
        personal_baseline is computed from the same LOOKBACK window that produced the
        stored z-scores, so (hrv_values[feat] - baseline.mean) / baseline.std ≈ z_scores[feat].
        """
        processed     = REPO_ROOT / "data" / "processed"
        feat_path     = processed / f"{patient_id}_features.csv"
        windowed_path = processed / f"{patient_id}_windowed.csv"

        if not feat_path.exists():
            raise FileNotFoundError(f"No features file: {feat_path}")
        if not windowed_path.exists():
            raise FileNotFoundError(f"No windowed file: {windowed_path}")

        feat_df     = pd.read_csv(feat_path)
        windowed_df = pd.read_csv(windowed_path)

        if len(feat_df) == 0 or len(windowed_df) == 0:
            raise ValueError(f"{patient_id}: empty CSV files")

        # Current state: latest row of each file.
        # feat_df has LOOKBACK more rows than windowed_df (the first LOOKBACK windows
        # are excluded from windowed because rolling baseline needs a full lookback).
        # Both .iloc[-1] should land on the same window_idx — assert to catch
        # any case where one file was regenerated without the other.
        latest_feat     = feat_df.iloc[-1]
        latest_windowed = windowed_df.iloc[-1]

        feat_idx     = int(latest_feat["window_idx"])
        windowed_idx = int(latest_windowed["window_idx"])
        if feat_idx != windowed_idx:
            raise ValueError(
                f"{patient_id}: window_idx mismatch between _features.csv "
                f"({feat_idx}) and _windowed.csv ({windowed_idx}). "
                "Re-run run_nb03.py then run_nb04.py to regenerate both files."
            )

        hrv_values = {col: float(latest_feat[col]) for col in self._feature_cols}

        # z-scores pre-computed by run_nb04.py
        z_scores = {
            col: float(latest_windowed[f"{col}_dev"])
            for col in self._feature_cols
            if f"{col}_dev" in windowed_df.columns
        }

        # Personal baseline: LOOKBACK window immediately before the latest window.
        # This matches exactly what run_nb04.py used to compute the stored z-scores.
        latest_idx      = len(feat_df) - 1
        lookback_start  = max(0, latest_idx - _LOOKBACK)
        baseline_window = feat_df.iloc[lookback_start:latest_idx]

        personal_baseline = {
            col: {
                "mean": float(baseline_window[col].mean()),
                "std":  float(baseline_window[col].std(ddof=1) + 1e-6),
            }
            for col in self._feature_cols
            if col in feat_df.columns
        }

        # FIX-5: Runtime skew check — warns if stored z-scores diverge from recomputed values.
        # Catches lookback-window mismatch between runner.py (_LOOKBACK) and run_nb04.py.
        import logging as _log
        import math as _math

        _skew_warnings: list[str] = []
        for _feat in self._feature_cols:
            if _feat not in z_scores or _feat not in personal_baseline:
                continue
            _stored_z = z_scores[_feat]
            _x = hrv_values[_feat]
            _mean = personal_baseline[_feat]["mean"]
            _std = personal_baseline[_feat]["std"]
            _recomputed = (_x - _mean) / _std
            if not (_math.isfinite(_stored_z) and _math.isfinite(_recomputed)):
                continue
            if abs(_recomputed - _stored_z) > 0.5:
                _skew_warnings.append(
                    f"{_feat}: stored_z={_stored_z:.3f} recomputed={_recomputed:.3f} "
                    f"diff={abs(_recomputed - _stored_z):.3f}"
                )
        if _skew_warnings:
            _log.warning(
                "FIX-5 baseline skew detected for %s — runner.py and run_nb04.py "
                "may be using different lookback windows:\n%s",
                patient_id,
                "\n".join(_skew_warnings),
            )
            if len(_skew_warnings) == len(self._feature_cols):
                raise RuntimeError(
                    f"All features show baseline skew for {patient_id}. "
                    "Check _LOOKBACK in runner.py matches LOOKBACK in run_nb04.py."
                )

        # ONNX inference
        feature_vector = np.array(
            [[hrv_values[f] for f in self._feature_cols]], dtype=np.float32
        )
        onnx_output = self._sess.run(None, {"hrv_features": feature_vector})

        prob_matrix = onnx_output[1]
        if not isinstance(prob_matrix, np.ndarray) or prob_matrix.shape != (1, 2):
            raise RuntimeError(
                f"Unexpected ONNX output shape {getattr(prob_matrix, 'shape', type(prob_matrix))}; "
                "expected (1, 2). Re-export with zipmap=False."
            )
        risk_score = float(np.clip(prob_matrix[0, 1], 0.0, 1.0))

        # Bradycardia events: windows where mean_rr > 600ms (HR < 100 bpm).
        # Note: PICS .atr annotations aggregate clustered events into single episodes,
        # so this count will exceed the training label count. Use for situational
        # awareness only, not for replicating training-label logic.
        events: list[BradycardiaEvent] = []
        if "mean_rr" in feat_df.columns:
            brady_df = feat_df[feat_df["mean_rr"] > 600.0]
            events = [
                BradycardiaEvent(
                    timestamp_idx=int(row["window_idx"]) if "window_idx" in brady_df.columns else i,
                    rr_interval_ms=float(row["mean_rr"]),
                    duration_beats=1,
                )
                for i, row in enumerate(brady_df.to_dict("records"))
            ]

        return PipelineResult(
            patient_id=patient_id,
            risk_score=risk_score,
            risk_level=PipelineResult.level_from_score(risk_score),
            z_scores=z_scores,
            hrv_values=hrv_values,
            personal_baseline=personal_baseline,
            detected_events=events,
        )
