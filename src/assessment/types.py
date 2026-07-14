"""The currency of the Verdict Cascade — the types every tier and caller shares.

See CONTEXT.md for the domain definitions of ConcernLevel, Assessment, Verdict, and
AssessmentContext. ConcernLevel is deliberately ordered by *severity* (not
alphabetically) so the Safety Floor can be computed with ``max``.
"""
from __future__ import annotations

from enum import Enum
from functools import total_ordering

from pydantic import BaseModel, Field


@total_ordering
class ConcernLevel(Enum):
    """Triage severity of an Assessment or Verdict, ordered GREEN < YELLOW < RED.

    A plain Enum (not a str-mixin) so our severity ordering isn't shadowed by
    lexicographic string comparison. Serialises to its value ("RED", ...) under
    Pydantic ``model_dump(mode="json")``.
    """

    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"

    @property
    def _severity(self) -> int:
        return {"GREEN": 0, "YELLOW": 1, "RED": 2}[self.value]

    def __lt__(self, other: object) -> bool:
        if isinstance(other, ConcernLevel):
            return self._severity < other._severity
        return NotImplemented


def most_severe(*levels: ConcernLevel, default: ConcernLevel = ConcernLevel.GREEN) -> ConcernLevel:
    """Return the highest-severity level, or ``default`` if none are given."""
    return max(levels, default=default)


class AssessmentContext(BaseModel):
    """Everything a tier needs to assess an infant's current state.

    Grows over time: Tier 1 (Deviation) reads only ``z_scores``; later tiers add
    window history and CUSUM state. Kept permissive so new fields don't break callers.
    """

    patient_id: str
    z_scores: dict[str, float] = Field(default_factory=dict)
    hrv_values: dict[str, float] = Field(default_factory=dict)
    detected_events: int = 0


class Assessment(BaseModel):
    """One tier's judgement — the uniform currency every Assessor emits."""

    level: ConcernLevel
    risk: float
    confidence: float
    rationale: str
    source: str  # which tier produced it: "deviation" | "temporal" | "rag"


class Verdict(BaseModel):
    """The single merged judgement the clinician sees, plus the trail that produced it."""

    patient_id: str
    level: ConcernLevel
    risk: float
    confidence: float
    rationale: str
    safety_floor: ConcernLevel
    assessments: list[Assessment]
    escalated_by: list[str] = Field(default_factory=list)
