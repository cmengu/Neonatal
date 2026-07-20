"""Tier 2 (learned half) — the observational JepaSurpriseAssessor (#59).

Decision 4 (map #56): the trained JEPA world model becomes a REAL Assessor in the
cascade seam, but strictly *observational* — it may never move the verdict. These
tests pin that contract structurally:

- always GREEN, ``may_quiet=False``, ``soft_floor=False`` — under calm, drift, and
  pathological inputs alike;
- composing it into a ``VerdictCascade`` changes neither the level, the safety
  floor, nor ``escalated_by`` in any floor scenario (GREEN / SOFT YELLOW / HARD RED),
  while its Assessment still rides along in ``verdict.assessments`` for the trace;
- the surprise signal itself is real: per-infant buffered context, horizon-aggregated
  prediction error, self-referenced z → risk that *rises on a regime shift*.

A tiny seeded JEPA keeps the unit tests fast; one integration test exercises the
shipped checkpoint end-to-end when it is present.
"""
from pathlib import Path

import numpy as np
import pytest
import torch

from src.assessment.assessor import Assessor
from src.assessment.cascade import VerdictCascade
from src.assessment.jepa_surprise import DEFAULT_CHECKPOINT, JepaSurpriseAssessor
from src.assessment.types import Assessment, AssessmentContext, ConcernLevel
from src.world_model.jepa import JEPA, JEPAConfig
from src.world_model.jepa_data import FEATURES


def _tiny_model(n_features: int = len(FEATURES)) -> JEPA:
    torch.manual_seed(0)
    return JEPA(
        JEPAConfig(
            n_features=n_features,
            embed_dim=8,
            context_len=4,
            horizon=2,
            n_heads=2,
            encoder_layers=1,
            predictor_layers=1,
            ffn_dim=16,
            dropout=0.0,
        )
    )


@pytest.fixture()
def assessor() -> JepaSurpriseAssessor:
    return JepaSurpriseAssessor(model=_tiny_model())


def _ctx(vec: np.ndarray, pid: str = "p1") -> AssessmentContext:
    z = {f.removesuffix("_dev"): float(v) for f, v in zip(FEATURES, vec)}
    return AssessmentContext(patient_id=pid, z_scores=z, hrv_values={}, detected_events=0)


def _calm_stream(n: int, seed: int = 1) -> np.ndarray:
    """A plausible calm record: small per-infant deviations with noise (never constant)."""
    rng = np.random.default_rng(seed)
    return 0.3 * rng.standard_normal((n, len(FEATURES))).astype(np.float32)


# --- seam + contract -------------------------------------------------------------


def test_implements_assessor_protocol(assessor):
    assert isinstance(assessor, Assessor)


def test_declares_structural_source(assessor):
    # The cascade identifies special tiers via a ``source`` attribute *without invoking
    # them* (the rag short-circuit mechanism); the JEPA tier declares its the same way.
    assert assessor.source == "jepa_surprise"


def test_wrong_feature_count_rejected():
    with pytest.raises(ValueError):
        JepaSurpriseAssessor(model=_tiny_model(n_features=3))


# --- observational invariant: never moves anything -------------------------------


def test_warmup_is_green_and_riskless(assessor):
    a = assessor.assess(_ctx(np.zeros(len(FEATURES))))
    assert a.level is ConcernLevel.GREEN
    assert a.risk == 0.0
    assert a.may_quiet is False
    assert a.soft_floor is False
    assert a.source == "jepa_surprise"
    assert "warm" in a.rationale.lower()


def test_always_green_never_quiets_calm_or_pathological(assessor):
    calm = _calm_stream(30)
    pathological = np.full((30, len(FEATURES)), 6.0, dtype=np.float32)
    for vec in np.concatenate([calm, pathological]):
        a = assessor.assess(_ctx(vec))
        assert a.level is ConcernLevel.GREEN
        assert a.may_quiet is False
        assert a.soft_floor is False
        assert 0.0 <= a.risk <= 1.0


class _FakeFloor:
    """A deviation-tier stand-in that pins the floor scenario under test."""

    def __init__(self, level: ConcernLevel, soft: bool = False) -> None:
        self._level, self._soft = level, soft

    def assess(self, context: AssessmentContext) -> Assessment:
        return Assessment(
            level=self._level,
            risk=0.5,
            confidence=1.0,
            rationale="fake floor",
            source="deviation",
            soft_floor=self._soft,
        )


@pytest.mark.parametrize(
    "floor_level,soft",
    [
        (ConcernLevel.GREEN, False),
        (ConcernLevel.YELLOW, True),   # quietable SOFT floor — jepa must NOT quiet it
        (ConcernLevel.YELLOW, False),  # hard single-tier YELLOW
        (ConcernLevel.RED, False),     # HARD floor
    ],
)
def test_cascade_verdict_unchanged_by_jepa_tier(floor_level, soft):
    stream = _calm_stream(45, seed=7)
    verdicts_with, verdicts_without = [], []
    for tiers, sink in (
        ([_FakeFloor(floor_level, soft)], verdicts_without),
        ([_FakeFloor(floor_level, soft), JepaSurpriseAssessor(model=_tiny_model())], verdicts_with),
    ):
        cascade = VerdictCascade(tiers=tiers)
        for vec in stream:
            sink.append(cascade.assess(_ctx(vec)))
    for vw, vo in zip(verdicts_with, verdicts_without):
        # EVERY clinician-facing field, not just the level. The level is the easy half: the
        # tier pins itself GREEN. The headline is the hard half — it is chosen by
        # ``max(assessments, key=(level, risk))``, so on a calm window a GREEN watcher ties on
        # level and wins on risk, capturing risk/confidence/rationale/action/indicators/
        # citations while leaving the level untouched. Asserting only ``level`` passes straight
        # through that bug; this comparison is what actually pins "observational".
        assert vw.model_dump(exclude={"assessments"}) == vo.model_dump(exclude={"assessments"})
        assert "jepa_surprise" not in vw.escalated_by
    # …but the observational assessment rides in the verdict for the trace/demo.
    assert any(a.source == "jepa_surprise" for a in verdicts_with[-1].assessments)


def test_jepa_tier_never_captures_the_headline_when_its_risk_is_highest(assessor):
    """The regression that ``level``-only assertions miss (#59).

    Drive the watcher's risk above the floor tier's, on a GREEN window where every tier ties
    on level, and demand the Verdict still speak with the deterministic tier's voice.
    """
    floor = _FakeFloor(ConcernLevel.GREEN)  # risk=0.5, rationale="fake floor"
    cascade = VerdictCascade(tiers=[floor, assessor])
    # Warm the buffer + calibration window, then hit it with a regime shift to spike surprise.
    for vec in _calm_stream(40, seed=11):
        cascade.assess(_ctx(vec))
    verdicts = [cascade.assess(_ctx(v)) for v in _calm_stream(12, seed=12) + 6.0]
    jepa_risks = [
        a.risk for v in verdicts for a in v.assessments if a.source == "jepa_surprise"
    ]
    assert max(jepa_risks) > 0.5, "regime shift did not lift surprise above the floor tier's risk"
    for v in verdicts:
        assert v.risk == 0.5 and v.rationale == "fake floor" and v.confidence == 1.0


# --- the signal is real ----------------------------------------------------------


def test_per_infant_buffers_are_isolated(assessor):
    warmup = assessor._need  # Lc + H of the tiny model
    for vec in _calm_stream(warmup + 5, seed=2):
        a_p1 = assessor.assess(_ctx(vec, pid="p1"))
    a_p2 = assessor.assess(_ctx(np.zeros(len(FEATURES)), pid="p2"))
    assert "warm" not in a_p1.rationale.lower()
    assert "warm" in a_p2.rationale.lower()


def test_risk_rises_on_regime_shift(assessor):
    calm = _calm_stream(50, seed=3)
    shift = 5.0 + 0.3 * np.random.default_rng(4).standard_normal((12, len(FEATURES)))
    calm_risks = [assessor.assess(_ctx(v)).risk for v in calm]
    shift_risks = [assessor.assess(_ctx(v.astype(np.float32))).risk for v in shift]
    assert max(shift_risks) > max(calm_risks[-10:])
    assert max(shift_risks) > 0.0


def test_missing_features_read_as_baseline(assessor):
    # A context with no z_scores at all is "at this infant's own normal" (all-zero vector).
    a = assessor.assess(AssessmentContext(patient_id="p9"))
    assert a.level is ConcernLevel.GREEN


def test_nan_inf_and_extremes_are_sanitised(assessor):
    z = {f.removesuffix("_dev"): v for f, v in zip(FEATURES, [float("nan"), float("inf"), 1e9] * 4)}
    for _ in range(assessor._need + 2):
        a = assessor.assess(AssessmentContext(patient_id="p3", z_scores=z))
    assert np.isfinite(a.risk)
    assert 0.0 <= a.risk <= 1.0


# --- shipped checkpoint integration ----------------------------------------------


@pytest.mark.skipif(not Path(DEFAULT_CHECKPOINT).exists(), reason="trained checkpoint absent")
def test_shipped_checkpoint_end_to_end():
    a = JepaSurpriseAssessor()  # loads models/jepa/jepa.pt
    last = None
    for vec in _calm_stream(a._need + 3, seed=5):
        last = a.assess(_ctx(vec, pid="real"))
    assert last.source == "jepa_surprise"
    assert last.level is ConcernLevel.GREEN
    assert "warm" not in last.rationale.lower()
