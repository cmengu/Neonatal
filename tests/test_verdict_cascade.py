"""VerdictCascade — composition and the Safety Floor.

Tested entirely with fake Assessors, so no ONNX / Groq / Qdrant is touched. This is
the payoff of the seam: the composition policy (ADR-0001) is verifiable in isolation.
"""
import itertools

from src.assessment.cascade import VerdictCascade
from src.assessment.types import Assessment, AssessmentContext, ConcernLevel


class FakeAssessor:
    """An Assessor that always returns a fixed Assessment — satisfies the Protocol.

    Exposes ``source`` on the object too (not just in the Assessment), so the cascade
    can identify a ``"rag"`` tier structurally and skip it without invoking. ``called``
    records whether ``assess`` ran — used to prove the Tier 3 short-circuit.
    """

    def __init__(self, level: ConcernLevel, source: str, risk: float = 0.5):
        self.source = source
        self.called = False
        self._a = Assessment(
            level=level, risk=risk, confidence=0.9,
            rationale="fake assessment for testing purposes", source=source,
        )

    def assess(self, context: AssessmentContext) -> Assessment:
        self.called = True
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


# --- #5: Tier 3 (RAG) escalate-only + short-circuit -----------------------------


def test_rag_is_skipped_when_base_is_green():
    """Short-circuit: the expensive Tier 3 is not invoked when the merged Tier 1/Tier 2
    level is GREEN — even though the rag fake *would* have said RED."""
    rag = FakeAssessor(ConcernLevel.RED, "rag")
    c = VerdictCascade(tiers=[FakeAssessor(ConcernLevel.GREEN, "deviation"), rag])
    v = c.assess(_ctx())
    assert v.level == ConcernLevel.GREEN
    assert rag.called is False  # never invoked on a clean window
    assert "rag" not in [a.source for a in v.assessments]


def test_rag_runs_and_escalates_when_base_is_non_green():
    """When Tier 1/Tier 2 are non-GREEN, Tier 3 runs and may raise concern."""
    rag = FakeAssessor(ConcernLevel.RED, "rag")
    c = VerdictCascade(tiers=[FakeAssessor(ConcernLevel.YELLOW, "deviation"), rag])
    v = c.assess(_ctx())
    assert rag.called is True
    assert v.level == ConcernLevel.RED
    assert "rag" in v.escalated_by


def test_rag_cannot_lower_below_the_floor_escalate_only():
    """Escalate-only: a rag GREEN can never talk a YELLOW floor down. The LLM tier is
    trusted to raise concern but never to suppress it (ADR-0001 / ADR-0003)."""
    rag = FakeAssessor(ConcernLevel.GREEN, "rag")
    c = VerdictCascade(tiers=[FakeAssessor(ConcernLevel.YELLOW, "deviation"), rag])
    v = c.assess(_ctx())
    assert rag.called is True  # floor is non-GREEN, so Tier 3 does run
    assert v.level == ConcernLevel.YELLOW  # ...but its GREEN is discarded
    assert v.safety_floor == ConcernLevel.YELLOW


def test_rag_cannot_lower_a_temporal_escalation():
    """ADR-0003 fork: Tier 2 does not quiet Tier 3, and Tier 3 does not quiet Tier 2.
    A temporal YELLOW stands even when the rag tier returns GREEN."""
    rag = FakeAssessor(ConcernLevel.GREEN, "rag")
    c = VerdictCascade(tiers=[
        FakeAssessor(ConcernLevel.GREEN, "deviation"),
        FakeAssessor(ConcernLevel.YELLOW, "temporal"),
        rag,
    ])
    v = c.assess(_ctx())
    assert rag.called is True  # merged base is YELLOW → Tier 3 runs
    assert v.level == ConcernLevel.YELLOW


def test_rag_escalate_only_holds_across_all_combinations():
    """Property: for every (floor, rag) pair, the rag tier never lowers the verdict below
    the floor — the escalate-only invariant, the Tier-3 analogue of the FNR=0 gate."""
    levels = [ConcernLevel.GREEN, ConcernLevel.YELLOW, ConcernLevel.RED]
    for floor_l, rag_l in itertools.product(levels, repeat=2):
        c = VerdictCascade(tiers=[
            FakeAssessor(floor_l, "deviation"),
            FakeAssessor(rag_l, "rag"),
        ])
        assert c.assess(_ctx()).level >= floor_l
