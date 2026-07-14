"""The per-infant forecaster — the learned half of Tier 2 (issue #6).

**Surprise**, formally, is the per-window negative log-likelihood of the next window
under the infant's *own* fitted model (research gate
``docs/research/world-model-surprise-validation.md``):

>   ``Surprise_i(t) = −log p(x_t | x_<t, θ_i)``

Per the gate's "start linear" mandate we fit a **VAR(1)** — a first-order vector
autoregression — by ordinary least squares on the infant's own personalised-deviation
stream, and read Surprise off in closed form as the normalised one-step-ahead innovation:

>   ``e_t = x_t − (A x_{t-1} + c)``            (the prediction error / innovation)
>   ``Surprise_i(t) = ½( e_tᵀ Σ⁻¹ e_t + log|2πΣ| )``   (Gaussian NLL of that innovation)

The Mahalanobis term ``e_tᵀ Σ⁻¹ e_t`` is the auditable heart of it: how many
covariance-scaled SD the window departs from what the infant's own dynamics predicted.

**Why linear, why per-infant** (both mandated by the gate, both load-bearing):

- *Per-infant, no shared population weights.* ``fit`` sees one infant's stream and returns
  that infant's ``θ_i``. This is the label-scarcity-robust replacement for the supervised
  ONNX classifier that scored at-random on held-out infants (ADR-0002). Nothing here is
  trained across infants.
- *Linear (VAR/Kalman), not neural.* On 10 infants a high-capacity model memorises; a
  VAR(1) innovation is inspectable, cheap, and contamination-resistant. Escalate to neural
  only if the linear LOIO test is promising (it is a *spike*).

**Two-sidedness is deliberate and defensible here.** Unlike the Tier-1 ``abs(z)`` critique
(#8), Surprise is NLL against a *learned model of this infant's normal*, so it rises for a
departure in *either* direction — a window that becomes anomalously *regular* is still
surprising to a model that learned this infant's normal irregularity (gate §4.3). The
*sign and lead time* of Surprise on our bradycardia target are an empirical question the
LOIO test answers — not an assumption baked in here.

Pure numpy: no I/O, no pandas, no sklearn. The LOIO harness (``loio.py``) and the runtime
assessor (``src.assessment.surprise``) both build on this.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

# The forecaster's feature vector: the personalised-deviation (``_dev``) form of the five
# physiologically-meaningful HRV features #8 kept as floor triggers (sdnn/rmssd collapse =
# the sepsis variability signature; rr_ms_max/rr_ms_75% = the deceleration tail; mean_rr =
# tachy/brady). The contested / floor-effect / display-only features #8 dropped from the
# trigger set (lf_hf_ratio, rr_ms_min, rr_ms_50%, rr_ms_25%, pnn50) are excluded here too:
# adding degenerate columns only destabilises the covariance without adding signal. This is
# the same "keep the validated features" discipline as Tier 1, one config tuple.
FORECAST_FEATURES: tuple[str, ...] = (
    "mean_rr_dev",
    "sdnn_dev",
    "rmssd_dev",
    "rr_ms_max_dev",
    "rr_ms_75%_dev",
)

# Ridge added to the residual covariance diagonal before inversion. Keeps Σ invertible when
# a feature is near-constant for an infant and de-sensitises the Mahalanobis term to a
# single collapsing direction. Small relative to the unit-ish scale of z-score deviations.
_DEFAULT_RIDGE = 1e-3

_LOG_2PI = math.log(2.0 * math.pi)


@dataclass(frozen=True)
class ForecasterParams:
    """A single infant's fitted world model ``θ_i`` — everything ``surprise`` needs.

    Frozen and self-contained so it round-trips cleanly through a state store (the runtime
    assessor persists it per infant, mirroring the CUSUM store pattern). ``cov_inv`` and
    ``logdet`` are precomputed at fit time so scoring a window is a couple of matmuls.
    """

    features: tuple[str, ...]
    a_matrix: np.ndarray  # (d, d) VAR(1) coefficient — next window from the previous one
    intercept: np.ndarray  # (d,) VAR(1) intercept
    cov: np.ndarray  # (d, d) residual (innovation) covariance, ridge-regularised
    cov_inv: np.ndarray  # (d, d) precomputed Σ⁻¹
    logdet: float  # log|Σ| (of the ridge-regularised Σ)
    n_train: int  # windows the fit consumed (a warm-up / trust signal)

    @property
    def dim(self) -> int:
        return len(self.features)


def _clean_matrix(x: np.ndarray) -> np.ndarray:
    """Replace non-finite entries with 0.0 (the per-infant z-score mean).

    ``_dev`` columns are already personalised z-scores, so 0 is the infant's own baseline —
    the least-surprising fill for a missing/degenerate window, and it keeps the VAR design
    matrix full-height rather than punching holes in the autoregressive lag structure.
    """
    return np.nan_to_num(np.asarray(x, dtype=float), nan=0.0, posinf=0.0, neginf=0.0)


class PerInfantForecaster:
    """Fits one infant's VAR(1) world model and scores per-window Surprise (NLL).

    Stateless across infants by construction: ``fit`` takes exactly one infant's ordered
    window matrix and returns that infant's ``ForecasterParams``. There is no cross-infant
    state, no shared weights — the gate's hard requirement.
    """

    def __init__(
        self,
        features: Sequence[str] = FORECAST_FEATURES,
        ridge: float = _DEFAULT_RIDGE,
    ) -> None:
        self.features = tuple(features)
        self.ridge = ridge

    def fit(self, x: np.ndarray) -> ForecasterParams:
        """Fit VAR(1) ``x_t = A x_{t-1} + c + e_t`` by OLS on one infant's stream.

        ``x`` is ``(T, d)`` — ``T`` windows in temporal order, ``d = len(features)`` columns
        in ``self.features`` order. Needs at least ``d + 2`` windows to identify ``A``.
        """
        x = _clean_matrix(x)
        if x.ndim != 2 or x.shape[1] != len(self.features):
            raise ValueError(
                f"expected (T, {len(self.features)}) matrix, got {x.shape}"
            )
        t, d = x.shape
        if t < d + 2:
            raise ValueError(
                f"need at least {d + 2} windows to fit VAR(1) on {d} features, got {t}"
            )

        prev = x[:-1]  # (T-1, d) — the lag-1 regressors
        nxt = x[1:]  # (T-1, d) — the targets
        # Design matrix with an intercept column: [prev | 1].
        design = np.hstack([prev, np.ones((prev.shape[0], 1))])  # (T-1, d+1)
        # OLS for every target column at once: beta is (d+1, d).
        beta, *_ = np.linalg.lstsq(design, nxt, rcond=None)
        a_matrix = beta[:d].T  # (d, d)
        intercept = beta[d]  # (d,)

        resid = nxt - design @ beta  # (T-1, d) innovations
        # Residual covariance, ridge-regularised so it inverts even when a feature is
        # near-constant for this infant.
        cov = np.cov(resid, rowvar=False)
        cov = np.atleast_2d(cov) + self.ridge * np.eye(d)
        cov_inv = np.linalg.inv(cov)
        sign, logabsdet = np.linalg.slogdet(cov)
        if sign <= 0:
            # Ridge should prevent this; fall back to the diagonal if a pathological input
            # still yields a non-positive-definite Σ.
            cov = np.diag(np.diag(cov))
            cov_inv = np.linalg.inv(cov)
            _, logabsdet = np.linalg.slogdet(cov)

        return ForecasterParams(
            features=self.features,
            a_matrix=a_matrix,
            intercept=intercept,
            cov=cov,
            cov_inv=cov_inv,
            logdet=float(logabsdet),
            n_train=t,
        )

    @staticmethod
    def surprise(params: ForecasterParams, x_prev: np.ndarray, x_cur: np.ndarray) -> float:
        """Per-window Surprise: the Gaussian NLL of the one-step-ahead innovation.

        ``Surprise = ½( eᵀ Σ⁻¹ e + log|Σ| + d·log 2π )`` where ``e = x_cur − (A x_prev + c)``.
        A non-negative-ish number (the constant ``½(log|Σ| + d·log2π)`` may be negative, but
        differences and the Mahalanobis core are what carry signal). Higher = more surprising.
        """
        x_prev = _clean_matrix(x_prev).reshape(-1)
        x_cur = _clean_matrix(x_cur).reshape(-1)
        e = x_cur - (params.a_matrix @ x_prev + params.intercept)
        maha = float(e @ params.cov_inv @ e)
        return 0.5 * (maha + params.logdet + params.dim * _LOG_2PI)

    def surprise_stream(self, params: ForecasterParams, x: np.ndarray) -> np.ndarray:
        """Surprise for every window in ``x`` (``(T, d)``), as a length-``T`` array.

        Element 0 is ``nan`` (no predecessor to forecast from); element ``t`` is the NLL of
        window ``t`` given window ``t-1``. This is the raw signal the LOIO test aligns to the
        annotated bradycardia events, and the runtime assessor scores one window at a time.
        """
        x = _clean_matrix(x)
        t = x.shape[0]
        out = np.full(t, np.nan, dtype=float)
        for i in range(1, t):
            out[i] = self.surprise(params, x[i - 1], x[i])
        return out
