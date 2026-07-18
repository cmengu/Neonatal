"""The Verdict Cascade — one Assessor seam, three tiers, one Verdict.

Public surface:
    Assessor            — the seam (Protocol) every tier implements
    VerdictCascade      — composes tiers into a Verdict under the Safety Floor
    DeviationAssessor   — Tier 1 (deterministic, stateless floor)
    load_context        — build an AssessmentContext for a real patient
    Assessment, Verdict, AssessmentContext, ConcernLevel — the shared currency
"""
from src.assessment.assessor import Assessor
from src.assessment.cascade import VerdictCascade
from src.assessment.context import load_context
from src.assessment.cusum import (
    CusumThresholds,
    InMemoryCusumStore,
    SqliteCusumStore,
    TemporalAssessor,
    composite_deviation,
)
from src.assessment.deviation import DeviationAssessor, DeviationThresholds
from src.assessment.jepa_surprise import JepaSurpriseAssessor
from src.assessment.types import (
    Assessment,
    AssessmentContext,
    ConcernLevel,
    Verdict,
    most_severe,
)

__all__ = [
    "Assessor",
    "VerdictCascade",
    "DeviationAssessor",
    "DeviationThresholds",
    "TemporalAssessor",
    "JepaSurpriseAssessor",
    "CusumThresholds",
    "InMemoryCusumStore",
    "SqliteCusumStore",
    "composite_deviation",
    "load_context",
    "Assessment",
    "AssessmentContext",
    "ConcernLevel",
    "Verdict",
    "most_severe",
]
