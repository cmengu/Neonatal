"""Tier 1 DeviationAssessor — pure-function tests.

The whole point of Tier 1 is that it is deterministic, stateless, and has no I/O:
given an infant's personalised z-scores it returns an Assessment and the Safety Floor.
These tests exercise it directly with no ONNX, Groq, or Qdrant in sight.

Per issue #8 the rule is *direction-aware* (only a deviation in the pathological
direction counts) and *concordance-gated* (one feature caps at YELLOW; two concordant
features are needed for RED). The per-feature directions and the removed features come
from the primary-source review in docs/research/hrv-features-neonatal-validity.md.
"""
from src.assessment.deviation import DeviationAssessor, DeviationThresholds
from src.assessment.types import AssessmentContext, ConcernLevel


def _ctx(z: dict[str, float]) -> AssessmentContext:
    return AssessmentContext(patient_id="t", z_scores=z, hrv_values={}, detected_events=0)


# --- floor behaviour that survives the #8 change -------------------------------


def test_all_small_deviations_are_green():
    a = DeviationAssessor().assess(_ctx({"rmssd": -0.5, "sdnn": 0.3}))
    assert a.level == ConcernLevel.GREEN
    assert a.source == "deviation"


def test_single_moderate_pathological_deviation_is_yellow():
    a = DeviationAssessor().assess(_ctx({"rmssd": -2.2}))
    assert a.level == ConcernLevel.YELLOW


def test_empty_z_scores_is_green():
    assert DeviationAssessor().assess(_ctx({})).level == ConcernLevel.GREEN


def test_deterministic_same_input_same_output():
    c = _ctx({"rmssd": -2.0})
    assert DeviationAssessor().assess(c).level == DeviationAssessor().assess(c).level


def test_risk_is_monotonic_in_pathological_magnitude():
    risk = lambda z: DeviationAssessor().assess(_ctx({"rmssd": z})).risk  # noqa: E731
    assert risk(-1.0) < risk(-2.5) < risk(-4.0)


# --- #8: direction-awareness ---------------------------------------------------


def test_high_variability_outlier_is_reassuring_not_concerning():
    # sdnn is low-only: a *high*-variability outlier is generally reassuring, not a risk.
    a = DeviationAssessor().assess(_ctx({"sdnn": 4.0}))
    assert a.level == ConcernLevel.GREEN


def test_low_variability_deviation_is_red_eligible():
    # A collapse in variability is the sepsis signature — it counts (RED-eligible), but a
    # single feature alone caps at YELLOW.
    a = DeviationAssessor().assess(_ctx({"sdnn": -4.0}))
    assert a.level == ConcernLevel.YELLOW


def test_high_only_feature_triggers_up_not_down():
    # rr_ms_max encodes the deceleration tail: long RR (high) is pathological, short is not.
    assert DeviationAssessor().assess(_ctx({"rr_ms_max": 4.0})).level == ConcernLevel.YELLOW
    assert DeviationAssessor().assess(_ctx({"rr_ms_max": -4.0})).level == ConcernLevel.GREEN


def test_mean_rr_is_two_sided():
    # mean_rr is genuinely bidirectional (tachycardia = low RR, or bradycardia/decel = high RR).
    assert DeviationAssessor().assess(_ctx({"mean_rr": 4.0})).level == ConcernLevel.YELLOW
    assert DeviationAssessor().assess(_ctx({"mean_rr": -4.0})).level == ConcernLevel.YELLOW


# --- #8: concordance -----------------------------------------------------------


def test_single_pathological_feature_caps_at_yellow():
    # Even an extreme single feature does not reach RED on its own.
    assert DeviationAssessor().assess(_ctx({"sdnn": -6.0})).level == ConcernLevel.YELLOW


def test_two_concordant_low_features_reach_red():
    a = DeviationAssessor().assess(_ctx({"sdnn": -2.4, "rmssd": -3.5}))
    assert a.level == ConcernLevel.RED


def test_variability_collapse_plus_deceleration_tail_is_concordant_red():
    # Low variability (low sdnn) + the deceleration tail (high rr_ms_max) are the two
    # halves of the same sepsis signature — concordant on the pathology, so RED.
    a = DeviationAssessor().assess(_ctx({"sdnn": -2.5, "rr_ms_max": 3.0}))
    assert a.level == ConcernLevel.RED


# --- #8: feature cleanup -------------------------------------------------------


def test_lf_hf_ratio_alone_does_not_fire_red():
    # lf_hf_ratio is removed from the trigger set (adult bands, contested construct).
    assert DeviationAssessor().assess(_ctx({"lf_hf_ratio": 5.0})).level == ConcernLevel.GREEN


def test_removed_features_do_not_trigger_even_in_pairs():
    # rr_ms_min, rr_ms_50%, pnn50 are display-only, not triggers — even two is still GREEN.
    a = DeviationAssessor().assess(_ctx({"rr_ms_min": -5.0, "rr_ms_50%": 4.0, "pnn50": -5.0}))
    assert a.level == ConcernLevel.GREEN


def test_removed_feature_does_not_promote_a_single_valid_feature_to_red():
    # The original direction-blind bug: rmssd (valid) + lf_hf_ratio (removed) must NOT be RED.
    a = DeviationAssessor().assess(_ctx({"rmssd": -3.5, "lf_hf_ratio": 2.9}))
    assert a.level == ConcernLevel.YELLOW


# --- #8: honest rationale ------------------------------------------------------


def test_rationale_names_a_triggered_pathological_feature():
    a = DeviationAssessor().assess(_ctx({"rmssd": -3.0}))
    assert "rmssd" in a.rationale


def test_rationale_is_honest_about_being_a_triage_threshold():
    a = DeviationAssessor().assess(_ctx({"sdnn": -2.5, "rmssd": -2.5}))
    r = a.rationale.lower()
    assert "triage" in r or "spc" in r
    assert "not a validated clinical cutoff" in r


# --- #8: adjustability (per-feature / per-direction thresholds) -----------------


def test_per_feature_threshold_override():
    lenient = DeviationThresholds(per_feature={"rmssd": 1.0})
    # rmssd at z=-1.2 is inside the default 2.0 (GREEN) but past a 1.0 override (YELLOW).
    assert DeviationAssessor().assess(_ctx({"rmssd": -1.2})).level == ConcernLevel.GREEN
    assert DeviationAssessor(lenient).assess(_ctx({"rmssd": -1.2})).level == ConcernLevel.YELLOW


def test_global_trigger_threshold_is_adjustable():
    strict = DeviationThresholds(z_trigger=1.0)
    # two concordant features just past a stricter 1.0 trigger reach RED.
    a = DeviationAssessor(strict).assess(_ctx({"sdnn": -1.2, "rmssd": -1.3}))
    assert a.level == ConcernLevel.RED
