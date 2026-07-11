"""Tier 1 — the Deviation assessor: instantaneous, stateless, deterministic.

Consolidates the concern-level logic that was scattered across ``level_from_score``
and the deterministic half of the ``self_check`` override into one pure function of
the infant's own z-scores. It cannot overfit (no learning) and sets the Safety Floor.

The thresholds live in one place (``DeviationThresholds``) instead of the five
literals they replaced. Defaults: |z| >= 2 -> YELLOW, |z| >= 3 -> RED — the same
z=2 the supervisor used to route on, and the z=3 the old override floored at.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.assessment.types import Assessment, AssessmentContext, ConcernLevel


@dataclass(frozen=True)
class DeviationThresholds:
    """The one config for the deterministic floor. Frozen so it's a safe default arg."""

    z_yellow: float = 2.0
    z_red: float = 3.0


class DeviationAssessor:
    """Maps the largest personalised z-score deviation to a concern level."""

    def __init__(self, thresholds: DeviationThresholds = DeviationThresholds()) -> None:
        self._t = thresholds

    def assess(self, context: AssessmentContext) -> Assessment:
        if context.z_scores:
            top_feature, top_z = max(context.z_scores.items(), key=lambda kv: abs(kv[1]))
            max_abs = abs(top_z)
        else:
            top_feature, top_z, max_abs = "none", 0.0, 0.0

        if max_abs >= self._t.z_red:
            level = ConcernLevel.RED
        elif max_abs >= self._t.z_yellow:
            level = ConcernLevel.YELLOW
        else:
            level = ConcernLevel.GREEN

        risk = min(max_abs / self._t.z_red, 1.0)
        rationale = (
            f"Deterministic deviation floor: |z|={max_abs:.1f} on {top_feature} "
            f"(z={top_z:+.1f}) vs this infant's baseline. "
            f"Thresholds: YELLOW>={self._t.z_yellow}, RED>={self._t.z_red}."
        )
        # confidence is 1.0: a deterministic rule is certain it applied correctly.
        return Assessment(
            level=level, risk=risk, confidence=1.0, rationale=rationale, source="deviation"
        )
