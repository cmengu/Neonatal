"""Tier 1 — the Deviation assessor: instantaneous, stateless, deterministic.

Consolidates the concern-level logic that was scattered across ``level_from_score``
and the deterministic half of the ``self_check`` override into one pure function of
the infant's own z-scores. It cannot overfit (no learning) and sets the Safety Floor.

Per issue #8 the rule is **direction-aware** and **concordance-gated**, because
``max(abs(z))`` over co-equal features was not faithful to the validated science
(docs/research/hrv-features-neonatal-validity.md):

- Only a deviation in the *pathological* direction counts. In impending sepsis
  variability collapses (low ``sdnn``/``rmssd``) and decelerations lengthen the RR tail
  (high ``rr_ms_max``/``rr_ms_75%``); a *high*-variability outlier is reassuring, not a
  risk (Griffin & Moorman 2001, PMID 11134441; Fairchild & O'Shea 2010, PMID 20813272).
- Contested / adult-band / floor-effect features (``lf_hf_ratio``, ``rr_ms_min``,
  ``rr_ms_50%``, ``pnn50``) are removed from the *trigger* set — they may stay in the
  context for display but never drive the floor (Billman 2013; Moorman 2011).
- Concordance: one pathological feature caps at YELLOW; **>=2** concordant features are
  needed for RED — the ``max``-over-co-equal rule inflated false positives.

This is a **per-infant SPC triage threshold**, not a validated clinical cutoff, and is
deliberately *not* HeRO's fitted fold-risk index. Thresholds stay in one place
(``DeviationThresholds``) and are per-feature / per-direction so a future calibration on
real outcome data is a config change, not a rewrite.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from src.assessment.types import Assessment, AssessmentContext, ConcernLevel

Direction = Literal["low", "high", "both"]

# The pathological direction of each HRV feature that is allowed to drive the floor.
# Features absent from this map are display-only and never trigger (see module docstring).
#   low  -> variability collapse is the sepsis signature
#   high -> the deceleration tail (long RR intervals)
#   both -> genuinely bidirectional (tachycardia = short RR, or decel/brady = long RR)
DEFAULT_DIRECTIONS: dict[str, Direction] = {
    "sdnn": "low",
    "rmssd": "low",
    "rr_ms_max": "high",
    "rr_ms_75%": "high",
    "mean_rr": "both",
}

# Pathological deviation (in per-infant SD) at which risk saturates to 1.0. Scales the
# continuous ``risk`` scalar only; it does not gate the concern level (concordance does).
_RISK_SATURATION = 3.0


def pathological_magnitude(
    directions: Mapping[str, Direction], feature: str, z: float
) -> float:
    """How far ``feature``'s z-score deviates *in its pathological direction*.

    Returns 0.0 for a display-only feature (absent from ``directions``) or one that
    deviates the *reassuring* way. This is the single definition of direction-awareness
    (issue #8), shared by the Tier 1 floor and the Tier 2 CUSUM composite so the two
    tiers agree on what "pathological" means.
    """
    direction = directions.get(feature)
    if direction == "low":
        return max(0.0, -z)
    if direction == "high":
        return max(0.0, z)
    if direction == "both":
        return abs(z)
    return 0.0


@dataclass(frozen=True)
class DeviationThresholds:
    """The one config for the deterministic floor. Frozen so it's a safe default arg.

    ``z_trigger`` is the default magnitude (per-infant SD) at which a feature counts as
    deviating pathologically. ``per_feature`` overrides it for named features, and
    ``directions`` sets which direction is pathological for each feature — so the "true
    threshold", once discovered from real outcome data, is a config change, not a rewrite.
    """

    z_trigger: float = 2.0
    per_feature: Mapping[str, float] = field(default_factory=dict)
    directions: Mapping[str, Direction] = field(
        default_factory=lambda: dict(DEFAULT_DIRECTIONS)
    )

    def threshold_for(self, feature: str) -> float:
        return self.per_feature.get(feature, self.z_trigger)


class DeviationAssessor:
    """Counts personalised z-scores deviating in their pathological direction and maps
    the concordant count to a concern level: 0 -> GREEN, 1 -> YELLOW, >=2 -> RED."""

    def __init__(self, thresholds: DeviationThresholds = DeviationThresholds()) -> None:
        self._t = thresholds

    def _pathological_magnitude(self, feature: str, z: float) -> float:
        """How far ``feature`` deviates in its pathological direction (0.0 if it is not a
        trigger feature or deviates the reassuring way)."""
        return pathological_magnitude(self._t.directions, feature, z)

    def assess(self, context: AssessmentContext) -> Assessment:
        triggered = [
            (feature, z, mag)
            for feature, z in context.z_scores.items()
            if (mag := self._pathological_magnitude(feature, z)) >= self._t.threshold_for(feature)
        ]
        triggered.sort(key=lambda t: t[2], reverse=True)

        # Concordance gate → concern level, and the HARD/SOFT floor distinction (ADR-0003):
        # ≥2 concordant is the un-quietable HARD floor (RED); exactly one feature is the
        # quietable SOFT floor (YELLOW); zero is GREEN. A YELLOW here is *by construction* a
        # single-feature signal, which is precisely ADR-0003's quietable SOFT floor.
        if len(triggered) >= 2:
            level = ConcernLevel.RED
            soft_floor = False
        elif len(triggered) == 1:
            level = ConcernLevel.YELLOW
            soft_floor = True
        else:
            level = ConcernLevel.GREEN
            soft_floor = False

        strongest = max(
            (self._pathological_magnitude(f, z) for f, z in context.z_scores.items()),
            default=0.0,
        )
        risk = min(strongest / _RISK_SATURATION, 1.0)

        if triggered:
            named = ", ".join(
                f"{f} {self._t.directions[f]} (z={z:+.1f})" for f, z, _ in triggered
            )
            detail = f"{len(triggered)} feature(s) deviating pathologically — {named}"
        else:
            detail = "no HRV feature deviating in a pathological direction"

        rationale = (
            f"Deterministic deviation floor ({level.value}): {detail} vs this infant's own "
            f"baseline. Per-infant SPC triage threshold (~{self._t.z_trigger:g} SD, "
            f"direction-aware): one feature caps at YELLOW, two concordant reach RED. "
            f"Not a validated clinical cutoff."
        )
        # confidence is 1.0: a deterministic rule is certain it applied correctly.
        return Assessment(
            level=level, risk=risk, confidence=1.0, rationale=rationale, source="deviation",
            soft_floor=soft_floor,
        )
