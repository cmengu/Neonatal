"""Unit tests for the LOIO evaluation core (issue #6).

These pin the mechanics (roles, AUC, lead time, pooling) on synthetic labels/surprise so
the headline number the ticket reports is trustworthy independent of the real data.
"""
from __future__ import annotations

import numpy as np

from src.world_model.loio import (
    auc,
    evaluate_infant,
    event_onsets,
    lead_times,
    peri_event_trace,
    summarise,
    window_roles,
)


def test_event_onsets_marks_rising_edges_only():
    labels = np.array([0, 0, 1, 0, 0, 1, 1, 0])
    # index 2 is an onset; index 5 is an onset; index 6 is a continuation, not a new onset.
    assert event_onsets(labels).tolist() == [2, 5]


def test_window_roles_lead_and_baseline_are_disjoint_and_correct():
    labels = np.zeros(100, dtype=int)
    labels[50] = 1
    is_lead, is_baseline = window_roles(labels, lead=5, guard=10)
    assert is_lead[45:50].all()  # the 5 windows before onset
    assert not is_lead[50]  # the event window itself is not a lead window
    assert not is_baseline[40:61].any()  # guard neighbourhood excluded from baseline
    assert is_baseline[0]  # far-from-event window is baseline
    assert not (is_lead & is_baseline).any()  # disjoint


def test_auc_perfect_and_chance():
    assert auc(np.array([3.0, 4.0, 5.0]), np.array([0.0, 1.0, 2.0])) == 1.0
    assert auc(np.array([1.0, 2.0]), np.array([1.0, 2.0])) == 0.5  # identical → ties → 0.5
    assert np.isnan(auc(np.array([]), np.array([1.0])))


def test_lead_times_counts_contiguous_pre_onset_rise():
    surprise = np.zeros(60)
    # onset at 30; make the 3 windows just before it elevated (>2 SD over baseline 0/1).
    surprise[27:30] = 10.0
    labels = np.zeros(60, dtype=int)
    labels[30] = 1
    lt = lead_times(surprise, labels, baseline_mean=0.0, baseline_std=1.0, lookback=20)
    assert lt == [3]


def test_lead_times_ignores_non_contiguous_rise():
    surprise = np.zeros(60)
    surprise[25] = 10.0  # a spike, but a gap before onset breaks contiguity
    labels = np.zeros(60, dtype=int)
    labels[30] = 1
    lt = lead_times(surprise, labels, baseline_mean=0.0, baseline_std=1.0, lookback=20)
    assert lt == []  # window 29 is not elevated → no contiguous run


def test_evaluate_infant_detects_a_planted_lead_rise():
    """A stream where Surprise reliably spikes before events should score AUC well > 0.5."""
    rng = np.random.default_rng(0)
    n = 2000
    surprise = rng.normal(0.0, 1.0, size=n)
    labels = np.zeros(n, dtype=int)
    for o in range(200, n - 200, 300):
        labels[o] = 1
        surprise[o - 5 : o] += 6.0  # plant a strong lead-window rise
    res = evaluate_infant("infantX", surprise, labels, lead=5, guard=30)
    assert res.auc > 0.9
    assert res.n_events == len(range(200, n - 200, 300))
    assert len(res.lead_time_windows) >= 1


def test_summarise_pools_across_infants():
    rng = np.random.default_rng(1)

    def make(seed_shift):
        n = 1500
        s = rng.normal(0.0, 1.0, size=n)
        labels = np.zeros(n, dtype=int)
        for o in range(200, n - 200, 300):
            labels[o] = 1
            s[o - 5 : o] += 5.0
        return evaluate_infant(f"i{seed_shift}", s, labels, lead=5, guard=30)

    summary = summarise([make(0), make(1), make(2)])
    assert summary.n_infants == 3
    assert summary.pooled_auc > 0.8
    assert 0.0 <= summary.mean_infant_auc <= 1.0
    assert summary.total_events > 0


def test_peri_event_trace_peaks_before_onset():
    n = 1500
    surprise = np.zeros(n)
    labels = np.zeros(n, dtype=int)
    for o in range(200, n - 200, 300):
        labels[o] = 1
        surprise[o - 3 : o] = 8.0
    trace = peri_event_trace(surprise, labels, baseline_mean=0.0, baseline_std=1.0, half=10)
    assert trace.shape == (21,)
    # The pre-onset positions (indices 7,8,9 = offsets -3,-2,-1) should exceed far-left calm.
    assert np.nanmean(trace[7:10]) > np.nanmean(trace[0:3])
