"""Tests for the detector-characterisation harness (#83).

Follows the cascade tests' stance: assert what the harness *measures*, never how it
composes a stream internally. The properties asserted here are the ones that would make a
published number wrong if they broke — a departure pushing the reassuring way, a delay
being averaged over runs that fired before onset, ARL0 improving when it should worsen.
"""
from __future__ import annotations

import numpy as np
import pytest

from src.assessment.cusum import CusumThresholds, composite_deviation
from src.assessment.deviation import DEFAULT_DIRECTIONS
from src.assessment.types import ConcernLevel
from src.characterisation.harness import (
    SECONDS_PER_WINDOW,
    VARIABILITY_COLLAPSE,
    Departure,
    RunResult,
    detection_delay,
    false_alarm_rate,
    run_cascade,
    run_tier2,
    sensitivity_floor,
    synthesise_stream,
)


class TestDeparture:
    def test_rejects_features_that_cannot_trigger(self):
        """A departure in a display-only feature is invisible by construction, so measuring
        against it would report a floor that says nothing about the detector."""
        with pytest.raises(ValueError, match="not trigger-capable"):
            Departure(magnitude_z=1.0, onset_window=0, features=("pnn50",)).validate()

    def test_rejects_negative_ramp(self):
        with pytest.raises(ValueError, match="ramp_windows"):
            Departure(magnitude_z=1.0, onset_window=0, ramp_windows=-1).validate()

    def test_step_departure_is_zero_before_onset_and_full_after(self):
        d = Departure(magnitude_z=1.5, onset_window=10)
        assert d.shift_at(9) == 0.0
        assert d.shift_at(10) == 1.5
        assert d.shift_at(999) == 1.5

    def test_ramp_reaches_full_magnitude_and_saturates(self):
        d = Departure(magnitude_z=2.0, onset_window=10, ramp_windows=4)
        assert d.shift_at(9) == 0.0
        assert d.shift_at(10) == pytest.approx(0.5)
        assert d.shift_at(13) == pytest.approx(2.0)
        assert d.shift_at(50) == pytest.approx(2.0)


class TestStream:
    def test_departure_pushes_every_feature_the_pathological_way(self):
        """magnitude_z must always mean 'how abnormal', never 'how positive' — otherwise a
        departure in a high-only feature would be injected as an improvement."""
        big = 6.0
        s = synthesise_stream(
            40,
            Departure(magnitude_z=big, onset_window=0,
                      features=("sdnn", "rmssd", "sampen", "sample_asymmetry")),
            noise_sd=0.01,
            seed=3,
        )
        z = s[5].z_scores
        assert z["sdnn"] < 0 and z["rmssd"] < 0 and z["sampen"] < 0  # low-is-pathological
        assert z["sample_asymmetry"] > 0                             # high-is-pathological

    def test_in_control_stream_is_centred_on_zero(self):
        s = synthesise_stream(4000, None, seed=11)
        for f in DEFAULT_DIRECTIONS:
            vals = [c.z_scores[f] for c in s]
            assert abs(float(np.mean(vals))) < 0.1

    def test_is_deterministic_in_seed(self):
        a = synthesise_stream(50, Departure(1.0, 10), seed=5)
        b = synthesise_stream(50, Departure(1.0, 10), seed=5)
        assert [c.z_scores for c in a] == [c.z_scores for c in b]

    def test_in_control_composite_is_positive_not_zero(self):
        """The fact that makes k=0.5 marginal: the CUSUM's input is rectified, so pure
        noise has a strictly positive mean that k must clear."""
        s = synthesise_stream(4000, None, seed=7)
        mean_composite = float(np.mean([composite_deviation(c.z_scores) for c in s]))
        analytic = (4 * (1 / np.sqrt(2 * np.pi)) + np.sqrt(2 / np.pi)) / 5
        assert mean_composite == pytest.approx(analytic, abs=0.03)
        assert mean_composite > 0.4


class TestRunResult:
    def test_delay_is_none_when_fired_before_onset(self):
        """A signal before the departure exists is a false alarm. Counting it as a
        negative-delay detection would flatter the detector."""
        r = RunResult(fired_at=5, n_windows=100, departure_onset=50)
        assert r.delay_windows is None
        assert r.delay_seconds is None
        assert r.detected is True  # it did fire — just not at the departure

    def test_delay_converts_to_seconds(self):
        r = RunResult(fired_at=60, n_windows=100, departure_onset=50)
        assert r.delay_windows == 10
        assert r.delay_seconds == pytest.approx(10 * SECONDS_PER_WINDOW)


class TestDetection:
    def test_large_sustained_departure_is_detected(self):
        s = synthesise_stream(400, Departure(magnitude_z=2.0, onset_window=100), seed=1)
        r = run_tier2(s, departure_onset=100)
        assert r.detected
        assert r.delay_windows is not None and r.delay_windows < 30

    def test_in_control_stream_rarely_fires_quickly(self):
        s = synthesise_stream(200, None, seed=2)
        r = run_tier2(s)
        assert r.fired_at is None or r.fired_at > 20

    def test_bigger_departures_are_detected_faster(self):
        small = detection_delay(0.5, n_replicates=40, n_windows=2000)
        large = detection_delay(2.0, n_replicates=40, n_windows=2000)
        assert large["median_delay_windows"] < small["median_delay_windows"]

    def test_ramped_departure_is_slower_than_a_step(self):
        step = detection_delay(1.5, n_replicates=40, ramp_windows=0, n_windows=2000)
        ramp = detection_delay(1.5, n_replicates=40, ramp_windows=60, n_windows=2000)
        assert ramp["median_delay_windows"] > step["median_delay_windows"]


class TestFalseAlarms:
    def test_raising_k_lengthens_arl0(self):
        """The core of the #84 finding: k must clear the rectified noise floor (~0.474).
        Below it the accumulator drifts up on noise alone; above it, it mean-reverts."""
        low = false_alarm_rate(n_replicates=20, n_windows=2000,
                               thresholds=CusumThresholds(k=0.25, h=5.0))
        cur = false_alarm_rate(n_replicates=20, n_windows=2000,
                               thresholds=CusumThresholds(k=0.5, h=5.0))
        assert low["arl0_windows"] < cur["arl0_windows"]
        assert low["false_alarms_per_patient_day"] > cur["false_alarms_per_patient_day"]

    def test_raising_h_lengthens_arl0(self):
        lo = false_alarm_rate(n_replicates=20, n_windows=2000,
                              thresholds=CusumThresholds(k=0.5, h=3.0))
        hi = false_alarm_rate(n_replicates=20, n_windows=2000,
                              thresholds=CusumThresholds(k=0.5, h=6.0))
        assert hi["arl0_windows"] > lo["arl0_windows"]

    def test_reports_censoring_rather_than_dropping_it(self):
        """Runs that never fire must be counted, or ARL0 is biased downward — the
        direction that makes the detector look better than it is."""
        r = false_alarm_rate(n_replicates=10, n_windows=200,
                             thresholds=CusumThresholds(k=0.9, h=8.0))
        assert r["censored_fraction"] > 0.0
        assert "caveat" in r and "OPTIMISTIC" in r["caveat"]


class TestSensitivityFloor:
    def test_requires_a_time_budget(self):
        with pytest.raises(TypeError):
            sensitivity_floor()  # type: ignore[call-arg]

    def test_tighter_budget_raises_the_floor(self):
        loose = sensitivity_floor(within_windows=200, magnitudes=(0.5, 1.0, 2.0),
                                  n_replicates=30, n_windows=2000)
        tight = sensitivity_floor(within_windows=6, magnitudes=(0.5, 1.0, 2.0),
                                  n_replicates=30, n_windows=2000)
        assert loose["sensitivity_floor_z"] <= tight["sensitivity_floor_z"]


class TestCascadeComposition:
    def test_tier1_alone_fires_on_noise_far_sooner_than_tier2(self):
        """Tier 1 is memoryless: with 5 trigger-capable features under noise, some feature
        clears z=2.0 pathologically within a few windows. That is exactly why a
        single-feature floor is SOFT and Tier 2 is the tier allowed to quiet it."""
        s = synthesise_stream(300, None, seed=4)
        cascade = run_cascade(s)
        tier2 = run_tier2(s)
        assert cascade.fired_at is not None
        assert tier2.fired_at is None or cascade.fired_at < tier2.fired_at

    def test_cascade_never_returns_an_unknown_level(self):
        s = synthesise_stream(120, Departure(1.0, 40), seed=6)
        assert set(run_cascade(s).levels) <= set(ConcernLevel)
