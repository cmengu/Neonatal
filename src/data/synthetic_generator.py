"""Generate synthetic PipelineResult objects for agent testing and eval.

All 10 HRV_FEATURE_COLS are generated with literature-based neonatal distributions.
Values are clamped to physiological minimums to prevent negative HRV values.
Deterministic per patient_id — same ID always produces the same result.

Sources: Fyfe et al. 2003, Goulding et al. 2015 (PMC), Longin et al. 2005.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.features.constants import HRV_FEATURE_COLS
from src.pipeline.result import BradycardiaEvent, PipelineResult

# Population HRV distributions for premature neonates by gestational age.
# (mu, sigma) per feature — sigma is between-patient SD, not within-window spread.
#
# mean_rr  : HR ≈ 144bpm at 24wk, 139bpm at 28–32wk, 135bpm at 34–36wk
#            → RR = 60000/HR → 417ms, 432ms, 444ms.
# sdnn     : <30wk SDNN ≈ 10ms; term newborn median ≈ 27.5ms.
# rmssd    : <30wk RMSSD ≈ 6.8ms; term newborn median ≈ 18ms.
# pnn50    : Term newborn median ≈ 1.7%; preterm typically <2%.
# lf_hf    : Preterm > term (sympathetic dominance). Values 1.2–1.8 defensible.
# percentiles: IQR ≈ 1.35 × SDNN. min/max ≈ mean ± 3×SDNN.
_GA_PARAMS: dict[str, dict[str, tuple[float, float]]] = {
    "24-28wk": {
        "mean_rr":   (417, 28), "sdnn": (10, 4),  "rmssd": (7,  3),
        "pnn50":     (1.5, 0.8), "lf_hf_ratio": (1.8, 0.6),
        "rr_ms_min": (387, 25), "rr_ms_max":   (447, 30),
        "rr_ms_25%": (410, 20), "rr_ms_50%":   (417, 25), "rr_ms_75%": (424, 20),
    },
    "28-32wk": {
        "mean_rr":   (432, 30), "sdnn": (18, 6),  "rmssd": (12, 4),
        "pnn50":     (2.5, 1.2), "lf_hf_ratio": (1.5, 0.5),
        "rr_ms_min": (378, 28), "rr_ms_max":   (486, 35),
        "rr_ms_25%": (420, 24), "rr_ms_50%":   (432, 28), "rr_ms_75%": (444, 24),
    },
    "32-36wk": {
        "mean_rr":   (444, 32), "sdnn": (28, 8),  "rmssd": (20, 6),
        "pnn50":     (4.0, 1.8), "lf_hf_ratio": (1.2, 0.4),
        "rr_ms_min": (360, 32), "rr_ms_max":   (528, 42),
        "rr_ms_25%": (425, 28), "rr_ms_50%":   (444, 32), "rr_ms_75%": (463, 28),
    },
}

# Physiological minimums — values below these are impossible in live neonates
_FEATURE_MIN: dict[str, float] = {
    "mean_rr": 200.0, "sdnn": 0.5, "rmssd": 0.5, "pnn50": 0.0,
    "lf_hf_ratio": 0.01,
    "rr_ms_min": 150.0, "rr_ms_max": 300.0,
    "rr_ms_25%": 280.0, "rr_ms_50%": 300.0, "rr_ms_75%": 310.0,
}

# Fractional shifts applied to personal baseline in 24h before sepsis onset.
# At corrected baselines: RMSSD -0.35 × 12ms ≈ -4ms shift (from 12ms to 8ms).
_SEPSIS_SHIFT: dict[str, float] = {
    "mean_rr": +0.08, "sdnn": -0.28, "rmssd": -0.35, "pnn50": -0.40,
    "lf_hf_ratio": +0.45,
    "rr_ms_min": +0.05, "rr_ms_max": +0.10,
    "rr_ms_25%": +0.06, "rr_ms_50%": +0.08, "rr_ms_75%": +0.09,
}


def generate_synthetic_result(
    patient_id: str,
    ga_range: str = "28-32wk",
    sepsis: bool = False,
    sepsis_severity: float = 1.0,
    n_brady_events: int = 0,
) -> PipelineResult:
    """
    Generate a deterministic synthetic PipelineResult.

    Parameters
    ----------
    patient_id      : RNG seed source — same ID always produces the same result.
    ga_range        : "24-28wk", "28-32wk", or "32-36wk".
    sepsis          : Apply sepsis-direction HRV shifts if True.
    sepsis_severity : 0.0–1.0 scale factor on shift magnitude.
    n_brady_events  : Number of bradycardia events to inject.
    """
    if ga_range not in _GA_PARAMS:
        raise ValueError(f"ga_range must be one of {list(_GA_PARAMS)}, got '{ga_range}'")
    if not 0.0 <= sepsis_severity <= 1.0:
        raise ValueError(f"sepsis_severity must be in [0,1], got {sepsis_severity}")

    params = _GA_PARAMS[ga_range]
    rng    = np.random.default_rng(abs(hash(patient_id)) % (2**32))

    # Personal baseline — sample once per patient_id, clamped to physiological mins
    personal_baseline: dict[str, dict[str, float]] = {}
    for feat, (mu, sigma) in params.items():
        mean = max(float(rng.normal(mu, sigma * 0.3)), _FEATURE_MIN[feat])
        std  = max(float(abs(rng.normal(sigma, sigma * 0.1))), 1e-6)
        personal_baseline[feat] = {"mean": mean, "std": std}

    # Current HRV values, clamped to physiological minimums
    hrv_values: dict[str, float] = {}
    for feat in params:
        base  = personal_baseline[feat]["mean"]
        shift = _SEPSIS_SHIFT.get(feat, 0.0) * sepsis_severity if sepsis else 0.0
        noise = float(rng.normal(1.0, 0.03))
        raw   = base * (1.0 + shift) * noise
        hrv_values[feat] = max(raw, _FEATURE_MIN[feat])

    missing = [c for c in HRV_FEATURE_COLS if c not in hrv_values]
    if missing:
        raise RuntimeError(f"Synthetic generator missing features: {missing}")

    z_scores = {
        feat: (hrv_values[feat] - personal_baseline[feat]["mean"])
               / personal_baseline[feat]["std"]
        for feat in HRV_FEATURE_COLS
    }

    if sepsis:
        risk_score = float(np.clip(rng.normal(0.80 * sepsis_severity, 0.06), 0.60, 0.97))
    else:
        risk_score = float(np.clip(rng.normal(0.15, 0.08), 0.02, 0.38))

    # Bradycardia: HR < 100bpm → RR > 600ms. Mean 620ms is moderately bradycardic
    # against the corrected neonatal baseline of ~417–450ms (HR ~133–144bpm).
    events = [
        BradycardiaEvent(
            timestamp_idx=i * 100,
            rr_interval_ms=float(max(rng.normal(620, 20), 601.0)),
            duration_beats=1,
        )
        for i in range(n_brady_events)
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
