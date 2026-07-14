"""Unit tests for the per-infant Surprise forecaster (issue #6).

Covers the two properties the research gate makes load-bearing: (1) Surprise is a
per-window NLL that *rises* when a window departs from the infant's learned dynamics, and
(2) fitting is strictly per-infant (no shared state across ``fit`` calls).
"""
from __future__ import annotations

import numpy as np
import pytest

from src.world_model.forecaster import (
    FORECAST_FEATURES,
    PerInfantForecaster,
)


def _stationary_stream(n: int, d: int, seed: int) -> np.ndarray:
    """A calm AR(1) stream: each feature reverts to 0 with small innovations."""
    rng = np.random.default_rng(seed)
    x = np.zeros((n, d))
    for t in range(1, n):
        x[t] = 0.5 * x[t - 1] + rng.normal(0.0, 0.3, size=d)
    return x


def test_fit_returns_per_infant_params_of_right_shape():
    d = len(FORECAST_FEATURES)
    f = PerInfantForecaster()
    params = f.fit(_stationary_stream(500, d, seed=1))
    assert params.a_matrix.shape == (d, d)
    assert params.intercept.shape == (d,)
    assert params.cov.shape == (d, d)
    assert params.dim == d
    assert params.n_train == 500


def test_fit_rejects_too_few_windows():
    d = len(FORECAST_FEATURES)
    f = PerInfantForecaster()
    with pytest.raises(ValueError):
        f.fit(np.zeros((d, d)))  # fewer than d+2 rows


def test_surprise_rises_on_departure_from_learned_normal():
    """A window far outside the infant's learned dynamics is more surprising than a calm one."""
    d = len(FORECAST_FEATURES)
    f = PerInfantForecaster()
    stream = _stationary_stream(800, d, seed=2)
    params = f.fit(stream)

    # A typical calm transition (near the infant's baseline).
    calm_prev = np.zeros(d)
    calm_cur = np.zeros(d)
    calm = f.surprise(params, calm_prev, calm_cur)

    # A large multivariate excursion the model never saw.
    shock_cur = np.full(d, 6.0)
    shock = f.surprise(params, calm_prev, shock_cur)

    assert shock > calm
    # The excursion should be many nats more surprising, not marginally.
    assert shock - calm > 10.0


def test_surprise_stream_has_nan_head_and_finite_tail():
    d = len(FORECAST_FEATURES)
    f = PerInfantForecaster()
    stream = _stationary_stream(300, d, seed=3)
    params = f.fit(stream)
    s = f.surprise_stream(params, stream)
    assert s.shape == (300,)
    assert np.isnan(s[0])
    assert np.all(np.isfinite(s[1:]))


def test_fit_is_per_infant_no_shared_state():
    """Two different infants fit two different models — nothing is shared across fits."""
    d = len(FORECAST_FEATURES)
    f = PerInfantForecaster()
    p1 = f.fit(_stationary_stream(400, d, seed=10))
    p2 = f.fit(_stationary_stream(400, d, seed=999))
    # Different data → different fitted dynamics.
    assert not np.allclose(p1.a_matrix, p2.a_matrix)
    # Re-fitting infant 1 reproduces infant 1 exactly (deterministic, order-independent).
    p1_again = f.fit(_stationary_stream(400, d, seed=10))
    assert np.allclose(p1.a_matrix, p1_again.a_matrix)
    assert np.allclose(p1.cov, p1_again.cov)


def test_nonfinite_inputs_are_handled():
    d = len(FORECAST_FEATURES)
    f = PerInfantForecaster()
    stream = _stationary_stream(200, d, seed=4)
    stream[50] = np.nan  # a dropout window
    params = f.fit(stream)  # must not raise
    assert np.isfinite(params.logdet)
    s = f.surprise(params, np.full(d, np.nan), np.zeros(d))
    assert np.isfinite(s)
