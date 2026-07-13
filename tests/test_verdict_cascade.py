"""VerdictCascade — composition and the Safety Floor.

Tested entirely with fake Assessors, so no ONNX / Groq / Qdrant is touched. This is
the payoff of the seam: the composition policy (ADR-0001) is verifiable in isolation.
"""
import itertools

from src.assessment.cascade import VerdictCascade
from src.assessment.types import Assessment, AssessmentContext, ConcernLevel


class FakeAssessor:
    """An Assessor that always returns a fixed Assessment — satisfies the Protocol."""

    def __init__(self, level: ConcernLevel, source: str, risk: float = 0.5):
        self._a = Assessment(
            level=level, risk=risk, confidence=0.9,
            rationale="fake assessment for testing purposes", source=source,
        )

    def assess(self, context: AssessmentContext) -> Assessment:
        return self._a


def _ctx() -> AssessmentContext:
    return AssessmentContext(patient_id="t", z_scores={"rmssd": -2.0}, hrv_values={}, detected_events=0)


def test_single_tier_verdict_equals_that_tier():
    c = VerdictCascade(tiers=[FakeAssessor(ConcernLevel.YELLOW, "deviation")])
    assert c.assess(_ctx()).level == ConcernLevel.YELLOW


def test_verdict_never_below_floor():
    # Floor tier (deviation) says YELLOW; a later tier says GREEN -> verdict stays YELLOW.
    c = VerdictCascade(tiers=[
        FakeAssessor(ConcernLevel.YELLOW, "deviation"),
        FakeAssessor(ConcernLevel.GREEN, "other"),
    ])
    assert c.assess(_ctx()).level == ConcernLevel.YELLOW


def test_later_tier_can_escalate_above_floor():
    c = VerdictCascade(tiers=[
        FakeAssessor(ConcernLevel.GREEN, "deviation"),
        FakeAssessor(ConcernLevel.RED, "other"),
    ])
    assert c.assess(_ctx()).level == ConcernLevel.RED


def test_verdict_carries_the_assessment_trail():
    c = VerdictCascade(tiers=[FakeAssessor(ConcernLevel.RED, "deviation")])
    v = c.assess(_ctx())
    assert len(v.assessments) == 1
    assert v.assessments[0].source == "deviation"
    assert v.safety_floor == ConcernLevel.RED


def test_cascade_runs_with_only_fakes_no_external_deps():
    c = VerdictCascade(tiers=[FakeAssessor(ConcernLevel.GREEN, "deviation")])
    assert c.assess(_ctx()).patient_id == "t"


def test_floor_regression_property_is_the_ci_gate():
    """FNR=0 safety gate: for every floor/other combination, the verdict is never
    below the deviation floor. If this ever fails, a critical alert could be suppressed."""
    levels = [ConcernLevel.GREEN, ConcernLevel.YELLOW, ConcernLevel.RED]
    for floor_l, other_l in itertools.product(levels, repeat=2):
        c = VerdictCascade(tiers=[
            FakeAssessor(floor_l, "deviation"),
            FakeAssessor(other_l, "other"),
        ])
        assert c.assess(_ctx()).level >= floor_l


# --- #4: Tier 2 (temporal) composition -----------------------------------------


def test_tier2_temporal_cannot_lower_below_floor():
    # ADR-0001: Tier 2 may de-escalate down to — never below — the Safety Floor.
    # A calm temporal tier does not quiet a YELLOW deviation floor.
    c = VerdictCascade(tiers=[
        FakeAssessor(ConcernLevel.YELLOW, "deviation"),
        FakeAssessor(ConcernLevel.GREEN, "temporal"),
    ])
    v = c.assess(_ctx())
    assert v.level == ConcernLevel.YELLOW
    assert v.safety_floor == ConcernLevel.YELLOW


def test_tier2_temporal_can_escalate_a_drift_above_the_floor():
    # A Drift the instantaneous floor missed: deviation GREEN, temporal YELLOW -> YELLOW.
    c = VerdictCascade(tiers=[
        FakeAssessor(ConcernLevel.GREEN, "deviation"),
        FakeAssessor(ConcernLevel.YELLOW, "temporal"),
    ])
    v = c.assess(_ctx())
    assert v.level == ConcernLevel.YELLOW
    assert "temporal" in v.escalated_by


def test_real_temporal_drift_escalates_the_verdict_before_the_floor_trips():
    """End-to-end with the real Tier 1 + Tier 2: a sustained sub-floor drift makes the
    cascade escalate before any single window crosses the instantaneous floor."""
    from src.assessment.cusum import CusumThresholds, TemporalAssessor
    from src.assessment.deviation import DeviationAssessor

    cascade = VerdictCascade(tiers=[
        DeviationAssessor(),
        TemporalAssessor(thresholds=CusumThresholds(h=2.0)),
    ])
    drift = AssessmentContext(patient_id="t", z_scores={"sdnn": -1.5, "rmssd": -1.5})
    escalated = any(cascade.assess(drift).level != ConcernLevel.GREEN for _ in range(100))
    assert escalated
    # ...and the deviation floor on that window is GREEN (nothing reached |z|>=2).
    assert DeviationAssessor().assess(drift).level == ConcernLevel.GREEN
