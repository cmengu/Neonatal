"""PipelineResult and supporting dataclasses.

Interface between the signal pipeline and Phases 3–6.
The LangGraph agent only ever sees PipelineResult objects — never raw HRV arrays.
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
class BradycardiaEvent:
    """Single detected bradycardia window."""
    timestamp_idx: int
    rr_interval_ms: float
    duration_beats: int


@dataclass
class PipelineResult:
    """
    Typed output of NeonatalPipeline.run(). Consumed by the LangGraph agent.

    The ONNX model predicts bradycardia-onset risk — NOT sepsis directly.
    Clinical framing: recurrent bradycardia is a validated physiological precursor
    to sepsis diagnosis in extremely preterm infants. The agent uses risk_score as a
    proxy for early deterioration and retrieves clinical KB context accordingly.

    Attributes
    ----------
    patient_id        : e.g. 'infant1'
    risk_score        : ONNX bradycardia-onset probability, 0.0–1.0
    risk_level        : RED > 0.70, YELLOW > 0.40, GREEN otherwise
    z_scores          : {feature: z-score} from run_nb04.py LOOKBACK=10 rolling baseline
    hrv_values        : {feature: raw HRV value} — same keys as z_scores
    personal_baseline : {feature: {"mean": float, "std": float}} — LOOKBACK window stats
    detected_events   : windows where mean_rr > 600ms (HR < 100 bpm)
    """
    patient_id: str
    risk_score: float
    risk_level: Literal["RED", "YELLOW", "GREEN"]
    z_scores: dict
    hrv_values: dict
    personal_baseline: dict
    detected_events: list[BradycardiaEvent] = field(default_factory=list)

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

    @staticmethod
    def level_from_score(score: float) -> Literal["RED", "YELLOW", "GREEN"]:
        if score > 0.70:
            return "RED"
        if score > 0.40:
            return "YELLOW"
        return "GREEN"
