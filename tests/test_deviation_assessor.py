"""Tier 1 DeviationAssessor — pure-function tests.

The whole point of Tier 1 is that it is deterministic, stateless, and has no I/O:
given an infant's personalised z-scores it returns an Assessment and the Safety Floor.
These tests exercise it directly with no ONNX, Groq, or Qdrant in sight.
"""
from src.assessment.deviation import DeviationAssessor, DeviationThresholds
from src.assessment.types import AssessmentContext, ConcernLevel


def _ctx(z: dict[str, float]) -> AssessmentContext:
    return AssessmentContext(patient_id="t", z_scores=z, hrv_values={}, detected_events=0)


def test_all_small_deviations_are_green():
    a = DeviationAssessor().assess(_ctx({"rmssd": -0.5, "sdnn": 0.3}))
    assert a.level == ConcernLevel.GREEN
    assert a.source == "deviation"


def test_moderate_deviation_is_yellow():
    a = DeviationAssessor().assess(_ctx({"rmssd": -2.2}))
    assert a.level == ConcernLevel.YELLOW


def test_severe_deviation_is_red():
    a = DeviationAssessor().assess(_ctx({"rmssd": -3.5, "lf_hf_ratio": 2.9}))
    assert a.level == ConcernLevel.RED


def test_risk_is_monotonic_in_max_abs_z():
    risk = lambda z: DeviationAssessor().assess(_ctx({"rmssd": z})).risk
    assert risk(-1.0) < risk(-2.5) < risk(-4.0)


def test_rationale_names_the_top_deviating_feature():
    a = DeviationAssessor().assess(_ctx({"rmssd": -0.2, "lf_hf_ratio": 3.1}))
    assert "lf_hf_ratio" in a.rationale


def test_deterministic_same_input_same_output():
    c = _ctx({"rmssd": -2.0})
    assert DeviationAssessor().assess(c).level == DeviationAssessor().assess(c).level


def test_empty_z_scores_is_green():
    assert DeviationAssessor().assess(_ctx({})).level == ConcernLevel.GREEN


def test_thresholds_are_configurable():
    strict = DeviationAssessor(DeviationThresholds(z_yellow=1.0, z_red=1.5))
    assert strict.assess(_ctx({"rmssd": -1.2})).level == ConcernLevel.YELLOW
    assert strict.assess(_ctx({"rmssd": -1.8})).level == ConcernLevel.RED
