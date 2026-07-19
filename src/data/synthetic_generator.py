"""Generate synthetic ``AssessmentView`` objects — an instrument, not an evidence source.

All HRV_FEATURE_COLS are generated with literature-based neonatal distributions. Values are
clamped to physiological minimums to prevent negative HRV values. Deterministic per
patient_id — same ID always produces the same result.

Post-#7 this emits an ``AssessmentView`` (the retired ONNX ``PipelineResult`` is gone): both
the concern ``level`` and ``risk`` come from the real Tier-1 ``DeviationAssessor`` run over
the generated z-scores, not from a disease-conditioned draw.

**What this may and may not be used for (D10).** Perturbations injected here characterise
the *detector*: detection delay against effect size, false alarms per patient-day, run
length under normal conditions, the smallest departure the cascade can see. Every such
perturbation is named by its magnitude — ``departure={"sdnn": -0.30}`` — and never by a
disease. This module can support "the watcher detects a departure of magnitude δ within N
seconds at X false alarms per patient-day". It can never support any claim about sepsis, or
about a real infant. The published precedent for that separation is Montazeri
Ghahjaverestan et al. 2021, who characterised an apnea-bradycardia detector on simulated
data and validated the clinical claim only on real preterm ECG.

The ``sepsis`` / ``sepsis_severity`` parameters were removed in #86; see the note above
``_GA_PARAMS``.

Sources: Fyfe et al. 2003, Goulding et al. 2015 (PMC), Longin et al. 2005; the two HeRO
discriminators are measured on this cohort (see the note below ``_GA_PARAMS``).
"""
from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

from src.agent.state import AssessmentView
from src.assessment.deviation import DeviationAssessor
from src.assessment.types import AssessmentContext
from src.features.constants import HRV_FEATURE_COLS

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
        "sampen":    (1.02, 0.30), "sample_asymmetry": (3.38, 1.68),
    },
    "28-32wk": {
        "mean_rr":   (432, 30), "sdnn": (18, 6),  "rmssd": (12, 4),
        "pnn50":     (2.5, 1.2), "lf_hf_ratio": (1.5, 0.5),
        "rr_ms_min": (378, 28), "rr_ms_max":   (486, 35),
        "rr_ms_25%": (420, 24), "rr_ms_50%":   (432, 28), "rr_ms_75%": (444, 24),
        "sampen":    (1.02, 0.30), "sample_asymmetry": (3.38, 1.68),
    },
    "32-36wk": {
        "mean_rr":   (444, 32), "sdnn": (28, 8),  "rmssd": (20, 6),
        "pnn50":     (4.0, 1.8), "lf_hf_ratio": (1.2, 0.4),
        "rr_ms_min": (360, 32), "rr_ms_max":   (528, 42),
        "rr_ms_25%": (425, 28), "rr_ms_50%":   (444, 32), "rr_ms_75%": (463, 28),
        "sampen":    (1.02, 0.30), "sample_asymmetry": (3.38, 1.68),
    },
}

# The two HeRO discriminators carry the SAME (mu, sigma) in all three GA bands, and that
# is deliberate. Unlike the ten time-domain features above — whose GA gradients come from
# Fyfe/Goulding/Longin — no GA-stratified source was found for sampen or sample_asymmetry,
# and PICS carries no gestational age, so no gradient can be measured here either.
# Inventing one would be fabrication dressed as physiology.
#
# The values are measured on this cohort under the long-window computation (#85 /
# scripts/regenerate_hrv_features.py, 1,272 sampled windows across all 10 infants):
#   sampen            mean 1.024, SD 0.288
#   sample_asymmetry  mean 3.375, robust SD 1.681 (IQR/1.349; the raw SD of 6.31 is
#                     meaningless on a heavy-tailed ratio)
# sample_asymmetry independently reproduces Kovatchev 2003's reported healthy baseline
# of 3.3 (SD 1.6) — see src/features/hrv.py.
#
# KNOWN DIRECTION, NOT ENCODED: sample entropy rises with postmenstrual age as preterm
# infants mature. The direction is established; the magnitudes are not, so no gradient
# is applied rather than guessing one.

# Physiological minimums — values below these are impossible in live neonates
_FEATURE_MIN: dict[str, float] = {
    "mean_rr": 200.0, "sdnn": 0.5, "rmssd": 0.5, "pnn50": 0.0,
    "lf_hf_ratio": 0.01,
    "rr_ms_min": 150.0, "rr_ms_max": 300.0,
    "rr_ms_25%": 280.0, "rr_ms_50%": 300.0, "rr_ms_75%": 310.0,
    # SampEn is an entropy (>0; the observed cohort minimum is 0.19) and
    # sample_asymmetry is a ratio of sums of squares (>0; cohort minimum 0.03).
    # Both floors sit below anything measured, so they clamp only impossible draws.
    "sampen": 0.05, "sample_asymmetry": 0.02,
}

# Sepsis-direction shifts were REMOVED in #86 — do not reinstate.
#
# This module previously accepted ``sepsis=True`` plus a ``sepsis_severity`` float and
# applied fractional shifts toward a "septic" HRV profile. ``generate_lora_data.py``
# used it to mint a training set that was 40% synthetic sepsis cases, with severity
# drawn from ``uniform(0.6, 1.0)`` — a label that was a number somebody typed, not an
# outcome anyone adjudicated. That set fine-tuned a LoRA adapter which a clinician-facing
# tier then loaded. The whole chain is gone (D13).
#
# The constraint that survives it (D10): this generator is a **measuring instrument for
# the detector**, never a source of evidence about infants. Perturbations injected here
# characterise what the cascade can see — detection delay, false-alarm rate, sensitivity
# floor — and are described by their *magnitude*, never by a disease name. See #83.

# Fail loudly at import time if HRV_FEATURE_COLS and _GA_PARAMS keys drift apart.
# Both must enumerate the same 10 features; any mismatch produces a RuntimeError
# that surfaces during tests rather than silently producing incomplete results.
_GA_KEYS = set(next(iter(_GA_PARAMS.values())).keys())
if set(HRV_FEATURE_COLS) != _GA_KEYS:
    raise RuntimeError(
        f"synthetic_generator: HRV_FEATURE_COLS {set(HRV_FEATURE_COLS)} "
        f"does not match _GA_PARAMS keys {_GA_KEYS}. "
        "Update one of src/features/constants.py or src/data/synthetic_generator.py."
    )


def generate_synthetic_result(
    patient_id: str,
    ga_range: str = "28-32wk",
    departure: Mapping[str, float] | None = None,
    n_brady_events: int = 0,
) -> AssessmentView:
    """
    Generate a deterministic synthetic ``AssessmentView``.

    Parameters
    ----------
    patient_id     : RNG seed source — same ID always produces the same result.
    ga_range       : "24-28wk", "28-32wk", or "32-36wk".
    departure      : Optional per-feature *fractional* shift applied to this patient's
                     own baseline, e.g. ``{"sdnn": -0.30, "sample_asymmetry": +0.25}``
                     for a 30% variability drop with a 25% rise in deceleration burden.
                     Keys must be in HRV_FEATURE_COLS. This replaces the removed
                     ``sepsis``/``sepsis_severity`` pair (#86).

                     Say what moved and by how much — never what disease it represents.
                     A departure is an instrument setting used to characterise the
                     detector (#83, D10); it carries no claim about any infant, and the
                     magnitude is the whole point, since the measurement being made is
                     "what is the smallest departure this cascade can see".
    n_brady_events : Number of bradycardia events to inject.
    """
    if ga_range not in _GA_PARAMS:
        raise ValueError(f"ga_range must be one of {list(_GA_PARAMS)}, got '{ga_range}'")
    departure = dict(departure or {})
    unknown = set(departure) - set(HRV_FEATURE_COLS)
    if unknown:
        raise ValueError(
            f"departure keys must be HRV features; unknown: {sorted(unknown)}. "
            f"Valid: {HRV_FEATURE_COLS}"
        )

    params = _GA_PARAMS[ga_range]
    # hashlib.md5 is stable across Python sessions; hash() is not (PYTHONHASHSEED varies).
    seed = int(hashlib.md5(patient_id.encode()).hexdigest(), 16) % (2**32)
    rng  = np.random.default_rng(seed)

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
        shift = departure.get(feat, 0.0)
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

    # Both level and risk come from the *real* deterministic Tier-1 assessor run over the
    # synthetic z-scores (post-#7 there is no ONNX probability to threshold).
    #
    # risk was previously sampled from a disease-conditioned distribution — a "septic"
    # flag drew it from N(0.80·severity, 0.06). That made the number encode the label
    # rather than the physiology, so anything trained on it learned the flag and not the
    # signal (#86). Taking the assessor's own risk keeps one definition of "how far from
    # baseline" in the codebase instead of a second one that can silently drift from it.
    dev = DeviationAssessor().assess(
        AssessmentContext(patient_id=patient_id, z_scores=z_scores, hrv_values=hrv_values)
    )

    return AssessmentView(
        patient_id=patient_id,
        level=dev.level.value,
        risk=dev.risk,
        z_scores=z_scores,
        hrv_values=hrv_values,
        personal_baseline=personal_baseline,
        n_events=n_brady_events,
    )
