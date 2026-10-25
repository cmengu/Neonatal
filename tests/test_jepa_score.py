"""Unit tests for the JEPA scorecard's model-blind math (`src/world_model/jepa_score.py`).

These are the non-circular ground-truth + metric helpers the honest scorecard (#58) and the
demo exporter (#60) both stand on: the rolling deviation magnitude, the departure/calm split,
embedding novelty, and the tie-averaged AUC. They're pure NumPy, so they're tested directly on
synthetic arrays — no model, no data files, fast and deterministic.
"""
import numpy as np
import pytest

from src.world_model.jepa_score import (
    _auc,
    departure_calm_masks,
    deviation_magnitude,
    novelty_from_embeddings,
)


# --- deviation_magnitude ---------------------------------------------------------


def test_deviation_magnitude_roll1_is_rms():
    x = np.array([[3.0, 4.0], [0.0, 0.0], [1.0, 1.0]], dtype=np.float32)
    # roll=1 → no smoothing → sqrt(mean(x^2)) per row
    got = deviation_magnitude(x, roll=1)
    assert got == pytest.approx([np.sqrt(12.5), 0.0, 1.0])


def test_deviation_magnitude_constant_series_is_flat_in_interior():
    x = np.full((80, 4), 0.7, dtype=np.float32)
    d = deviation_magnitude(x, roll=20)
    # sqrt(mean(0.7^2)) = 0.7; the moving average holds it flat in the interior
    # (mode='same' zero-pads, so the outer ~roll windows droop — an expected edge artifact).
    assert d[40] == pytest.approx(0.7, abs=1e-5)
    assert np.allclose(d[20:-20], 0.7, atol=1e-5)


def test_deviation_magnitude_spike_raises_local_average():
    x = np.zeros((60, 3), dtype=np.float32)
    x[30] = 9.0  # one pathological window
    d = deviation_magnitude(x, roll=10)
    assert d[30] > d[0]
    assert d.shape == (60,)  # mode='same' keeps length


# --- departure_calm_masks --------------------------------------------------------


def test_departure_and_calm_are_disjoint_and_ordered():
    rng = np.random.default_rng(0)
    x = rng.standard_normal((400, 10)).astype(np.float32)
    x[300:340] *= 6.0  # a sustained departure episode
    dep, calm, d = departure_calm_masks(x, roll=20, hi_pct=85.0, lo_pct=50.0)
    # a window above the 85th pct can't also be below the 50th
    assert not np.any(dep & calm)
    # the departure windows sit at strictly higher deviation than the calm ones
    assert d[dep].min() > d[calm].max()
    # d is exactly the rolling deviation magnitude
    assert np.allclose(d, deviation_magnitude(x, roll=20))


def test_calm_is_roughly_the_bottom_half():
    rng = np.random.default_rng(1)
    x = rng.standard_normal((1000, 6)).astype(np.float32)
    _, calm, _ = departure_calm_masks(x, roll=20, lo_pct=50.0)
    assert 0.4 < calm.mean() < 0.6  # ~50% by construction


# --- novelty_from_embeddings -----------------------------------------------------


def test_novelty_is_zero_at_the_baseline_mean():
    rng = np.random.default_rng(2)
    baseline = rng.standard_normal((200, 8))
    z = baseline.mean(0, keepdims=True)  # the cloud centre
    for whiten in (True, False):
        nov = novelty_from_embeddings(z, baseline, whiten=whiten)
        assert nov.shape == (1,)
        assert nov[0] == pytest.approx(0.0, abs=1e-6)


def test_novelty_grows_with_distance_from_cloud():
    rng = np.random.default_rng(3)
    baseline = rng.standard_normal((300, 5))
    mu = baseline.mean(0)
    near = (mu + 0.1)[None, :]
    far = (mu + 10.0)[None, :]
    for whiten in (True, False):
        n_near = novelty_from_embeddings(near, baseline, whiten=whiten)[0]
        n_far = novelty_from_embeddings(far, baseline, whiten=whiten)[0]
        assert n_far > n_near >= 0.0


# --- _auc (tie-averaged Mann–Whitney) --------------------------------------------


def test_auc_perfect_separation():
    assert _auc(np.array([3.0, 4.0, 5.0]), np.array([0.0, 1.0, 2.0])) == 1.0
    assert _auc(np.array([0.0, 1.0]), np.array([3.0, 4.0])) == 0.0


def test_auc_ties_are_half():
    # every pos-vs-neg comparison is a tie → 0.5
    assert _auc(np.array([2.0, 2.0]), np.array([2.0])) == pytest.approx(0.5)


def test_auc_mixed_pairs():
    # pos=2 beats neg=1, loses to neg=3 → one win, one loss → 0.5
    assert _auc(np.array([2.0]), np.array([1.0, 3.0])) == pytest.approx(0.5)


def test_auc_ignores_non_finite():
    a = _auc(np.array([3.0, np.nan, 4.0]), np.array([1.0, np.inf, 2.0]))
    # nan/inf dropped → same as the clean perfect-separation case
    assert a == 1.0
