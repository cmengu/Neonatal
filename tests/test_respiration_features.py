"""Respiration-derived cardiorespiratory feature stream — pure-function tests (issue #3).

Issue #3 turns the PICS respiration channel (currently ignored) into a feature
stream: respiratory rate, respiratory variability, apnea episodes, and the
apnea->bradycardia coupling that heart rate alone cannot express. The feature set
and pathological directions come from the primary-source review in
``docs/research/cardiorespiratory-feature-validation.md`` (resolves research #10).

Like ``test_deviation_assessor.py`` these are deterministic, stateless, I/O-free
tests built on inline synthetic breath/beat arrays. Two facts are load-bearing and
each gets a dedicated guard:

  * **Seconds, not samples.** Breath peaks (``.resp``) and bradycardia onsets
    (``.atr``) live in *different* sample spaces (PICS resp fs is 50 Hz for most
    infants but 500 Hz for infant1; ECG fs is 500 Hz except 250 Hz for infant1/5),
    so everything must be aligned in seconds. ``test_seconds_alignment_*`` pins this.
  * **Apnea is a *banded* pause.** A physiological apnea is ~15-120 s; multi-minute
    "pauses" in this data are sensor dropouts, not apneas, and must not be counted
    (``test_apnea_upper_band_excludes_signal_dropout``).
"""
from pathlib import Path

import numpy as np
import pytest

from src.features.constants import RESP_FEATURE_COLS
from src.features.respiration import (
    APNEA_MAX_PAUSE_S,
    APNEA_MIN_PAUSE_S,
    BREATH_REFRACTORY_S,
    COUPLING_LAG_S,
    apnea_bradycardia_coupling,
    apnea_coincident_flags,
    clean_breath_times,
    compute_respiration_features,
    detect_apnea_episodes,
    event_times_seconds,
    min_heart_rate_bpm,
    respiration_feature_rows,
)

RAW_DIR = (
    Path(__file__).resolve().parent.parent
    / "data" / "raw" / "physionet.org" / "files" / "picsdb" / "1.0.0"
)


# --- sample -> seconds conversion (the fs guard) -------------------------------


def test_event_times_seconds_divides_by_fs():
    # A breath at sample 500 in a 500 Hz record is at t=1.0 s.
    assert event_times_seconds([500, 1000], fs=500) == pytest.approx([1.0, 2.0])
    # The same sample index in a 50 Hz record is a *different* time.
    assert event_times_seconds([500], fs=50) == pytest.approx([10.0])


def test_event_times_seconds_rejects_bad_fs():
    with pytest.raises(ValueError):
        event_times_seconds([1, 2, 3], fs=0)


# --- breath cleaning (refractory merge of double-detections) -------------------


def test_refractory_merge_drops_sub_physiological_peaks():
    # 0.05 s after a breath is 1200/min — an artifact double-detection, dropped.
    cleaned = clean_breath_times([0.0, 0.05, 0.6, 1.2], refractory_s=BREATH_REFRACTORY_S)
    assert cleaned == pytest.approx([0.0, 0.6, 1.2])


def test_cleaning_sorts_and_ignores_nan():
    cleaned = clean_breath_times([2.0, np.nan, 0.0, 1.0])
    assert cleaned == pytest.approx([0.0, 1.0, 2.0])


def test_cleaning_never_creates_or_destroys_a_long_gap():
    # Refractory merge only touches sub-0.2 s spacing; a 20 s apnea gap is untouched.
    cleaned = clean_breath_times([0.0, 0.1, 20.1], refractory_s=0.2)
    assert cleaned == pytest.approx([0.0, 20.1])


# --- apnea detection -----------------------------------------------------------


def test_apnea_detected_on_long_gap():
    # Regular breathing until a single 18 s pause between t=2 and t=20.
    breaths = [0.0, 1.0, 2.0, 20.0, 21.0, 22.0]
    eps = detect_apnea_episodes(breaths, min_pause_s=15.0)
    assert len(eps) == 1
    assert eps[0]["onset_s"] == pytest.approx(2.0)
    assert eps[0]["offset_s"] == pytest.approx(20.0)
    assert eps[0]["duration_s"] == pytest.approx(18.0)


def test_no_apnea_when_breathing_is_regular():
    breaths = np.arange(0.0, 60.0, 0.6)  # ~100/min, no pause
    assert detect_apnea_episodes(breaths, min_pause_s=15.0) == []


def test_apnea_lower_band_is_inclusive_threshold():
    # A gap exactly at the threshold counts; just under it does not.
    assert len(detect_apnea_episodes([0.0, 15.0], min_pause_s=15.0)) == 1
    assert detect_apnea_episodes([0.0, 14.9], min_pause_s=15.0) == []


def test_apnea_upper_band_excludes_signal_dropout():
    # A 15 s pause is an apnea; a 600 s "pause" is a sensor dropout, not an apnea.
    breaths = [0.0, 15.0, 615.0]
    eps = detect_apnea_episodes(
        breaths, min_pause_s=APNEA_MIN_PAUSE_S, max_pause_s=APNEA_MAX_PAUSE_S
    )
    assert len(eps) == 1
    assert eps[0]["duration_s"] == pytest.approx(15.0)


def test_apnea_needs_two_breaths():
    assert detect_apnea_episodes([], min_pause_s=15.0) == []
    assert detect_apnea_episodes([5.0], min_pause_s=15.0) == []


# --- windowed respiration features ---------------------------------------------


def test_feature_keys_match_resp_feature_cols():
    # The single-source-of-truth invariant, mirroring the HRV pipeline.
    feats = compute_respiration_features([0.0, 1.0, 2.0], t_start=0.0, t_end=60.0)
    assert sorted(feats.keys()) == sorted(RESP_FEATURE_COLS)


def test_respiratory_rate_is_breaths_per_minute():
    # 60 breaths spanning a 60 s window -> 60 breaths/min.
    breaths = np.arange(0.0, 60.0, 1.0)
    feats = compute_respiration_features(breaths, t_start=0.0, t_end=60.0)
    assert feats["n_breaths"] == 60
    assert feats["resp_rate_bpm"] == pytest.approx(60.0)


def test_respiratory_variability_zero_for_regular_positive_for_irregular():
    regular = compute_respiration_features(np.arange(0.0, 30.0, 1.0), 0.0, 30.0)
    assert regular["breath_interval_cv"] == pytest.approx(0.0, abs=1e-9)
    irregular = compute_respiration_features([0.0, 0.5, 2.0, 2.3, 5.0], 0.0, 30.0)
    assert irregular["breath_interval_cv"] > 0.0


def test_window_apnea_burden_counts_overlap_seconds():
    # One 18 s apnea (t=2..20); a 60 s window should see all 18 s of it.
    breaths = [0.0, 1.0, 2.0, 20.0, 21.0]
    eps = detect_apnea_episodes(breaths, min_pause_s=15.0)
    feats = compute_respiration_features(breaths, 0.0, 60.0, apnea_episodes=eps)
    assert feats["apnea_count"] == 1
    assert feats["apnea_seconds"] == pytest.approx(18.0)
    assert feats["longest_apnea_s"] == pytest.approx(18.0)


def test_window_apnea_burden_clips_to_window_bounds():
    # Apnea spans t=50..80 but the window ends at 60 -> only 10 s of overlap.
    eps = [{"onset_s": 50.0, "offset_s": 80.0, "duration_s": 30.0}]
    feats = compute_respiration_features([], 0.0, 60.0, apnea_episodes=eps)
    assert feats["apnea_seconds"] == pytest.approx(10.0)


def test_respiration_feature_rows_slide_and_carry_metadata():
    breaths = np.arange(0.0, 120.0, 1.0)
    rows = respiration_feature_rows(
        breaths, record_name="infantX", t0=0.0, t_end=120.0, window_s=60.0, step_s=30.0
    )
    # windows starting at 0,30,60 all fit fully inside [0,120]; 90 would end at 150 (>120)
    assert [r["window_idx"] for r in rows] == [0, 1, 2]
    assert rows[0]["record_name"] == "infantX"
    assert rows[0]["t_start_s"] == pytest.approx(0.0)
    assert rows[0]["t_end_s"] == pytest.approx(60.0)
    assert all(c in rows[0] for c in RESP_FEATURE_COLS)


# --- cardiorespiratory coupling: apnea -> bradycardia --------------------------


def test_apnea_coincident_when_bradycardia_follows_within_lag():
    eps = [{"onset_s": 100.0, "offset_s": 118.0, "duration_s": 18.0}]
    # brady 5 s after the apnea ends -> within COUPLING_LAG_S -> coincident.
    assert apnea_coincident_flags(eps, [123.0], lag_s=COUPLING_LAG_S) == [True]
    # brady far away -> not coincident.
    assert apnea_coincident_flags(eps, [5000.0], lag_s=COUPLING_LAG_S) == [False]


def test_apnea_coincidence_includes_bradycardia_during_the_pause():
    eps = [{"onset_s": 100.0, "offset_s": 118.0, "duration_s": 18.0}]
    assert apnea_coincident_flags(eps, [110.0], lag_s=COUPLING_LAG_S) == [True]


def test_coupling_summary_reports_enrichment_above_chance():
    # Three apneas, each with a brady inside its window; brady onsets are otherwise rare.
    eps = [
        {"onset_s": 100.0, "offset_s": 115.0, "duration_s": 15.0},
        {"onset_s": 500.0, "offset_s": 516.0, "duration_s": 16.0},
        {"onset_s": 900.0, "offset_s": 918.0, "duration_s": 18.0},
    ]
    brady = [116.0, 517.0, 919.0]
    summary = apnea_bradycardia_coupling(eps, brady, total_duration_s=10_000.0)
    assert summary["n_apnea"] == 3
    assert summary["n_coincident"] == 3
    assert summary["coincidence_rate"] == pytest.approx(1.0)
    # 3 coincidences vastly exceed the handful expected if brady were placed at random.
    assert summary["enrichment"] > 5.0


def test_coupling_seconds_alignment_across_sampling_rates():
    # THE fs guard at the coupling layer: a breath at resp-sample 60000 (50 Hz -> 1200 s)
    # and a brady at ecg-sample 600000 (500 Hz -> 1200 s) are the *same instant*. Compared
    # as raw samples they look 540000 apart; compared in seconds they coincide.
    breaths = event_times_seconds([59000, 60000], fs=50)          # 1180 s, 1200 s (20 s apnea)
    brady = event_times_seconds([600000], fs=500)                 # 1200 s
    eps = detect_apnea_episodes(breaths, min_pause_s=15.0)
    assert len(eps) == 1
    assert apnea_coincident_flags(eps, brady, lag_s=COUPLING_LAG_S) == [True]


def test_min_heart_rate_reflects_deceleration_between_beats():
    # A 1.5 s RR gap between beats -> instantaneous HR of 40 bpm (a bradycardia).
    beats = [100.0, 100.4, 101.9, 102.3]  # one 1.5 s gap
    assert min_heart_rate_bpm(beats, 100.0, 103.0) == pytest.approx(40.0)
    # Too few beats in range -> NaN, not a crash.
    assert np.isnan(min_heart_rate_bpm(beats, 200.0, 201.0))


# --- real-data validation: apnea-bradycardia coincidence is observable ---------
#
# Acceptance criterion 3 ("on real data, apnea-bradycardia coincidence is
# observable"). Covers both fs regimes: infant1 (ECG 250 / RESP 500 Hz) and
# infant2 (ECG 500 / RESP 50 Hz). Skips cleanly if the PICS data isn't present.

pytestmark_reason = "PICS raw data not present under data/raw/"


def _load_infant(name: str):
    import wfdb

    ecg_hdr = wfdb.rdheader(str(RAW_DIR / f"{name}_ecg"))
    resp_hdr = wfdb.rdheader(str(RAW_DIR / f"{name}_resp"))
    resp = wfdb.rdann(str(RAW_DIR / f"{name}_resp"), "resp")
    atr = wfdb.rdann(str(RAW_DIR / f"{name}_ecg"), "atr")
    breaths = clean_breath_times(event_times_seconds(resp.sample, resp_hdr.fs))
    brady = event_times_seconds(atr.sample, ecg_hdr.fs)
    duration = resp_hdr.sig_len / resp_hdr.fs
    return breaths, brady, duration


@pytest.mark.skipif(
    not (RAW_DIR / "infant1_resp.resp").exists(), reason=pytestmark_reason
)
@pytest.mark.parametrize("name", ["infant1", "infant2"])
def test_real_apnea_bradycardia_coincidence_is_observable(name):
    breaths, brady, duration = _load_infant(name)
    eps = detect_apnea_episodes(breaths)
    summary = apnea_bradycardia_coupling(eps, brady, total_duration_s=duration)
    assert summary["n_apnea"] > 0, f"{name}: expected apnea episodes in banded range"
    assert summary["n_coincident"] > 0, f"{name}: expected apnea-bradycardia coincidence"
    # Coincidence must beat the random-placement null by a clear margin.
    assert summary["enrichment"] > 2.0
