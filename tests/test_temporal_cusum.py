"""Tier 2 (deterministic half) — the CUSUM Drift detector.

Issue #4. The TemporalAssessor accumulates a one-sided CUSUM over a single
*direction-aware composite* of the infant's personalised deviations, so a sustained
sub-threshold drift that never trips Tier 1's instantaneous floor still integrates to
a Drift alarm. Grounded in docs/research/cusum-drift-and-composition-validation.md
(k=0.5, h=5 z-units, target δ=1 SD sustained, one-sided in the pathological direction).

Design note (the fork resolved in #4): ONE CUSUM on a composite, not five parallel
per-feature CUSUMs — parallel one-sided CUSUMs reintroduce the max|z| multiplicity
inflation #8 removed from Tier 1. The composite reuses Tier 1's DEFAULT_DIRECTIONS, so
reassuring deviations contribute 0.
"""
import pytest

from src.assessment.cusum import (
    CusumThresholds,
    InMemoryCusumStore,
    SqliteCusumStore,
    TemporalAssessor,
    composite_deviation,
)
from src.assessment.types import AssessmentContext, ConcernLevel


def _ctx(z: dict[str, float]) -> AssessmentContext:
    return AssessmentContext(patient_id="t", z_scores=z, hrv_values={})


# --- the composite is direction-aware (reuses Tier 1's map) ---------------------


def test_composite_ignores_reassuring_deviations():
    # sdnn is low-only: a *high*-variability reading is reassuring -> contributes 0.
    assert composite_deviation({"sdnn": 4.0}) == 0.0


def test_composite_counts_pathological_direction():
    # sdnn low is pathological; a single feature -> mean over the one present feature.
    assert composite_deviation({"sdnn": -3.0}) == pytest.approx(3.0)


def test_composite_is_mean_over_direction_features_present():
    # two pathological features -> their mean magnitude, not the max (no multiplicity).
    assert composite_deviation({"sdnn": -2.0, "rmssd": -4.0}) == pytest.approx(3.0)


def test_composite_empty_is_zero():
    assert composite_deviation({}) == 0.0


# --- defaults match the research gate ------------------------------------------


def test_default_thresholds_match_research():
    t = CusumThresholds()
    assert t.k == 0.5
    assert t.h == 5.0


# --- a calm stream never fires --------------------------------------------------


def test_flat_normal_stream_stays_green():
    a = TemporalAssessor()
    for _ in range(50):
        result = a.assess(_ctx({"sdnn": 0.1, "rmssd": -0.2, "mean_rr": 0.0}))
    assert result.level == ConcernLevel.GREEN
    assert result.source == "temporal"


def test_reassuring_drift_never_fires():
    # sustained HIGH variability (reassuring) must not accumulate a Drift alarm.
    a = TemporalAssessor()
    for _ in range(60):
        result = a.assess(_ctx({"sdnn": 3.0, "rmssd": 3.0}))
    assert result.level == ConcernLevel.GREEN


# --- the core promise: drift escalates before any single window trips the floor --


def _first_fire_window(assessor: TemporalAssessor, ctx: AssessmentContext, n: int = 200) -> int | None:
    for i in range(n):
        if assessor.assess(ctx).level != ConcernLevel.GREEN:
            return i
    return None


def test_sustained_subfloor_drift_eventually_fires():
    # Each window sits at -1.5 SD on two features: below Tier 1's |z|>=2 floor, so no
    # single window trips the instantaneous gate, but the drift accumulates to a Drift.
    a = TemporalAssessor()
    fired = _first_fire_window(a, _ctx({"sdnn": -1.5, "rmssd": -1.5}))
    assert fired is not None


def test_drift_escalates_while_deviation_floor_stays_green():
    from src.assessment.deviation import DeviationAssessor

    drift_ctx = _ctx({"sdnn": -1.5, "rmssd": -1.5})  # composite 1.5; no feature >= 2
    # Tier 1 floor never fires on this window (nothing reaches |z|>=2).
    assert DeviationAssessor().assess(drift_ctx).level == ConcernLevel.GREEN
    # Tier 2 does, given enough sustained windows.
    assert _first_fire_window(TemporalAssessor(), drift_ctx) is not None


def test_a_faster_threshold_fires_sooner():
    slow = TemporalAssessor(thresholds=CusumThresholds(h=5.0))
    fast = TemporalAssessor(thresholds=CusumThresholds(h=2.0))
    ctx = _ctx({"sdnn": -1.5, "rmssd": -1.5})
    assert _first_fire_window(fast, ctx) < _first_fire_window(slow, ctx)


# --- determinism ----------------------------------------------------------------


def test_same_sequence_same_escalation_point():
    ctx = _ctx({"sdnn": -1.5, "rmssd": -1.4})
    a1 = _first_fire_window(TemporalAssessor(), ctx)
    a2 = _first_fire_window(TemporalAssessor(), ctx)
    assert a1 == a2 and a1 is not None


# --- reset after a signal -------------------------------------------------------


def test_accumulator_resets_after_firing():
    # After a fire, one calm window should show a low (reset-derived) risk, not a
    # still-saturated one.
    a = TemporalAssessor(thresholds=CusumThresholds(h=2.0))
    ctx = _ctx({"sdnn": -1.5, "rmssd": -1.5})
    # push until it fires
    fired_at = _first_fire_window(a, ctx)
    assert fired_at is not None
    calm = a.assess(_ctx({"sdnn": 0.0, "rmssd": 0.0}))
    assert calm.level == ConcernLevel.GREEN
    assert calm.risk < 0.5  # reset, not still pinned near 1.0


# --- persistence survives a restart (the AC) -----------------------------------


def test_cusum_state_persists_across_restart(tmp_path):
    db = str(tmp_path / "audit.db")
    ctx = _ctx({"sdnn": -1.2, "rmssd": -1.2})

    # A single continuous run: how many windows to fire?
    continuous = TemporalAssessor(store=SqliteCusumStore(str(tmp_path / "cont.db")))
    continuous_fire = _first_fire_window(continuous, ctx)
    assert continuous_fire is not None

    # A split run over the *same* db, dropping the assessor+store midway (a "restart").
    half = continuous_fire // 2
    first = TemporalAssessor(store=SqliteCusumStore(db))
    for _ in range(half):
        assert first.assess(ctx).level == ConcernLevel.GREEN

    # Fresh assessor + fresh store on the same db == restart; state must survive.
    resumed = TemporalAssessor(store=SqliteCusumStore(db))
    fired_offset = _first_fire_window(resumed, ctx)
    assert fired_offset is not None
    # Continuous fire == windows before restart + windows after; state carried over.
    assert half + fired_offset == continuous_fire


def test_rationale_distinguishes_first_from_recurring_drift():
    # last_signal_at is load-bearing: a repeat Drift reads the prior signal window.
    a = TemporalAssessor(thresholds=CusumThresholds(h=2.0))
    ctx = _ctx({"sdnn": -1.5, "rmssd": -1.5})
    fires = [a.assess(ctx) for _ in range(12)]
    fired = [f for f in fires if f.level != ConcernLevel.GREEN]
    assert len(fired) >= 2
    assert "first sustained Drift" in fired[0].rationale
    assert "recurring Drift" in fired[1].rationale


def test_in_memory_store_is_isolated_per_patient():
    store = InMemoryCusumStore()
    a = TemporalAssessor(store=store, thresholds=CusumThresholds(h=2.0))
    # Patient p1 drifts; p2 stays calm on the same assessor/store.
    for _ in range(10):
        a.assess(AssessmentContext(patient_id="p1", z_scores={"sdnn": -1.5, "rmssd": -1.5}))
    p2 = a.assess(AssessmentContext(patient_id="p2", z_scores={"sdnn": -1.5, "rmssd": -1.5}))
    # p2's first window alone cannot have accumulated p1's evidence.
    assert p2.level == ConcernLevel.GREEN


# --- #14: the SOFT-floor quiet grant (may_quiet gates) -------------------------

from src.assessment.cusum import QuietGates


def _calm():
    return _ctx({"sdnn": 0.0, "rmssd": 0.0})  # composite 0


def test_may_quiet_false_before_warmup():
    a = TemporalAssessor()  # default gates: warmup=20
    r = None
    for _ in range(19):
        r = a.assess(_calm())
    assert r.level == ConcernLevel.GREEN and r.may_quiet is False


def test_may_quiet_true_once_warmed_calm_and_not_alarmed():
    a = TemporalAssessor()
    for _ in range(20):
        r = a.assess(_calm())
    assert r.may_quiet is True


def test_may_quiet_false_with_a_building_trend():
    # Warmed + calm, then a window arriving on top of an already-built prior C⁺ is not quietable.
    a = TemporalAssessor()
    for _ in range(20):
        a.assess(_calm())
    a.assess(_ctx({"sdnn": -3.0}))  # composite 3.0 → prior C⁺ now ~2.5 (> 0.25·h)
    r = a.assess(_ctx({"sdnn": -1.0}))  # arrives on a built-up trend → no quiet
    assert r.level == ConcernLevel.GREEN and r.may_quiet is False


def test_may_quiet_false_right_after_an_alarm_then_true_after_the_guard():
    a = TemporalAssessor()  # h=5, guard=20, warmup=20
    for _ in range(20):
        a.assess(_calm())
    fired = False
    for _ in range(12):
        r = a.assess(_ctx({"sdnn": -1.5, "rmssd": -1.5}))
        if r.level == ConcernLevel.YELLOW:
            fired = True
            break
    assert fired
    r = a.assess(_calm())            # one window after the alarm: recently-alarmed
    assert r.may_quiet is False
    for _ in range(20):              # let the guard window elapse (calm)
        r = a.assess(_calm())
    assert r.may_quiet is True
