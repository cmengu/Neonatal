"""The Verdict Cascade — the one place the verdict policy lives.

Runs the tiers, takes the Safety Floor from the deviation tier, and merges into a
single Verdict. Per ADR-0001 the Verdict is never below the floor.

Ticket #2 wires one tier (Deviation), so composition is: verdict = the floor, and
any tier may escalate above it. The *asymmetric de-escalation* half of ADR-0001
(Tier 2 may lower to the floor; Tier 3 may not) lands with the CUSUM / RAG tickets —
this module is structured so those slot in without a rewrite.
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
