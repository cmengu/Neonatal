"""The deterministic per-window view the RAG graph reasons over (issue #7).

Replaces the retired ONNX ``PipelineResult`` (ADR-0002): instead of an ONNX
``risk_score`` probability, the runtime is served by the Verdict Cascade. This lightweight
view carries the personalised deviations + the **deterministic** Tier-1 concern level/risk
that the RAG specialists reason over. The authoritative verdict is the cascade's composed
``Verdict`` (Tier 1 floor + Tier 2 Drift + Tier 3 RAG) — this view is only the Tier-3
input, so it deliberately does **not** run the stateful CUSUM (that composes once, at the
cascade, in ``src.assessment.runtime``).

Field notes:
- ``level`` / ``risk`` come from the **stateless** Tier-1 ``DeviationAssessor`` — safe to
  recompute here without touching the persisted CUSUM state.
- ``n_events`` is the count of bradycardia-suggestive windows from ``load_context``
  (``mean_rr > 600 ms`` ⇒ HR < 100). It replaces the old ONNX ``detected_events`` list;
  callers that need a count read ``n_events`` directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class FeatureDeviation:
    """Single HRV feature with its current value and z-score from personal baseline."""

    name: str
    value: float
    z_score: float
    baseline_mean: float
    baseline_std: float


@dataclass
class AssessmentView:
    """The Tier-3 (RAG) input view — personalised deviations + deterministic Tier-1 level.

    Attributes
    ----------
    patient_id        : e.g. 'infant1'
    level             : deterministic Tier-1 concern level (RED / YELLOW / GREEN)
    risk              : deterministic Tier-1 risk in [0, 1] (direction-aware, saturating) —
                        an *abnormality-departure* magnitude, NOT the retired ONNX probability
    z_scores          : {feature: z-score} personalised deviation for the latest window
    hrv_values        : {feature: raw HRV value} — same keys as z_scores
    personal_baseline : {feature: {"mean": float, "std": float}} per-infant baseline stats
    n_events          : count of bradycardia-suggestive windows (mean_rr > 600 ms)
    """

    patient_id: str
    level: Literal["RED", "YELLOW", "GREEN"]
    risk: float
    z_scores: dict[str, float]
    hrv_values: dict[str, float]
    personal_baseline: dict[str, dict[str, float]] = field(default_factory=dict)
    n_events: int = 0

    def get_top_deviated(self, n: int = 3) -> list[FeatureDeviation]:
        """Return the n features with highest absolute z-score deviation."""
        deviations = [
            FeatureDeviation(
                name=feat,
                value=self.hrv_values.get(feat, 0.0),
                z_score=z,
                baseline_mean=self.personal_baseline.get(feat, {}).get("mean", 0.0),
                baseline_std=self.personal_baseline.get(feat, {}).get("std", 1.0),
            )
            for feat, z in self.z_scores.items()
        ]
        return sorted(deviations, key=lambda d: abs(d.z_score), reverse=True)[:n]
