"""The Verdict Cascade — the one place the verdict policy lives.

Runs the tiers, takes the Safety Floor from the deviation tier, and merges into a
single Verdict. Per ADR-0001 the Verdict is never below the floor.

Composition (ADR-0001): the verdict is never below the Safety Floor (Tier 1's
deterministic minimum), and any tier may escalate above it. As of #4 the second tier
is real — the deterministic CUSUM ``TemporalAssessor`` (``source="temporal"``) — so a
gradual Drift now escalates the verdict even when no single window trips the floor.

The floor rule already encodes the *safe* half of ADR-0001's asymmetric de-escalation:
a temporal Assessment *below* the floor is clamped up to it (Tier 2 may quiet down to —
never below — the floor). The *stronger* half — Tier 2 overriding a Tier 3 escalation
downward while Tier 3 stays escalate-only — is deliberately deferred to #5, when Tier 3
(RAG) exists and it becomes testable; building it now, against no Tier 3, would be
speculative and unverifiable. This module is structured so that lands without a rewrite.
"""
from __future__ import annotations

from collections.abc import Sequence

from src.assessment.assessor import Assessor
from src.assessment.types import Assessment, AssessmentContext, ConcernLevel, Verdict, most_severe


class VerdictCascade:
    """Composes tier Assessments into one Verdict under the Safety Floor rule."""

    def __init__(self, tiers: Sequence[Assessor], floor_source: str = "deviation") -> None:
        if not tiers:
            raise ValueError("VerdictCascade needs at least one tier")
        self._tiers = list(tiers)
        self._floor_source = floor_source

    def assess(self, context: AssessmentContext) -> Verdict:
        assessments: list[Assessment] = [t.assess(context) for t in self._tiers]

        # Safety Floor: the deterministic minimum from the deviation tier.
        floor = most_severe(
            *[a.level for a in assessments if a.source == self._floor_source]
        )

        # Verdict is never below the floor; tiers may escalate above it.
        level = most_severe(*[a.level for a in assessments], floor)
        escalated_by = [a.source for a in assessments if a.level > floor]

        # Headline (risk / rationale / confidence) comes from the most severe assessment.
        headline = max(assessments, key=lambda a: (a.level, a.risk))

        return Verdict(
            patient_id=context.patient_id,
            level=level,
            risk=headline.risk,
            confidence=headline.confidence,
            rationale=headline.rationale,
            safety_floor=floor,
            assessments=assessments,
            escalated_by=escalated_by,
        )
