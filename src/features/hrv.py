"""
HRV feature extraction for neonatal sepsis pipeline.

Computes time-domain and frequency-domain HRV metrics from windowed RR intervals.
Time-domain:       mean_rr, sdnn, rmssd, pnn50
Frequency-domain:  lf_hf_ratio  (Welch PSD, LF 0.04–0.15 Hz / HF 0.15–0.40 Hz)
Statistical:       rr_ms_min, rr_ms_max, rr_ms_25%, rr_ms_50%, rr_ms_75%
Nonlinear (#13):   sampen           — sample entropy, the HeRO irregularity measure
Histogram (#13):   sample_asymmetry — R2/R1 deceleration-burden statistic

``sampen`` and ``sample_asymmetry`` are the two neonatally-validated HeRO
discriminators added in issue #13 (research gate:
docs/research/cardiorespiratory-feature-validation.md, issue #10). They replace
the crude RR-tail proxies (``rr_ms_max``/``rr_ms_75%``) as Tier-1 triggers.

The authoritative ordered column name list is in ``src.features.constants.HRV_FEATURE_COLS``.
The keys returned by ``compute_hrv_features()`` must stay in sync with that list.
"""
import numpy as np
from scipy import signal, interpolate
from scipy.integrate import trapezoid as _trapz  # np.trapz removed in NumPy 2.0
from scipy.spatial import cKDTree

# --- SampEn parameters ---------------------------------------------------------
# Neonatal defaults from the #10 research gate: m=3 (Lake 2002, PMID 12185014),
# r=0.2×SD (Richman & Moorman 2000, PMID 10843903; PhysioNet ``sampen``). The
# *window length* N≈4096 (~20–25 min) lives with the pipeline that supplies
# ``rr_entropy`` (scripts/run_nb03.py), because SampEn slides "per the existing
# Tier-1 cadence" — the window is long, the step stays the fast HRV step.
# [UNVERIFIED] exact r/N from the neonatal primary (paywalled); relax r upward
# for short/noisy windows. These are tunable, not primary-verified constants.
SAMPEN_M = 3
SAMPEN_R_FACTOR = 0.2
_SAMPEN_ARTIFACT_FRAC = 0.20  # reject beats >20% from the local median (dropped/ectopic)
_SAMPEN_DETREND_WIN = 15      # moving-average baseline window (beats)


def _compute_lf_hf(rr_ms: np.ndarray, fs_resample: float = 4.0) -> float:
    """
    Compute LF/HF power ratio from RR intervals (ms).

    Resamples the RR series onto a uniform 4 Hz grid using linear interpolation,
    then estimates PSD via Welch's method and integrates over LF and HF bands.
    Returns 1.0 (neutral) for windows too short for reliable estimation (< 20 beats).

    Parameters
    ----------
    rr_ms : np.ndarray
        1D array of RR intervals in milliseconds.
    fs_resample : float
        Target uniform sampling frequency in Hz (default 4 Hz per HRV guidelines).

    Returns
    -------
    float
        LF power / HF power ratio. Returns 1.0 if window is too short.
    """
    rr = np.asarray(rr_ms, dtype=np.float64)
    if len(rr) < 20:
        return 1.0

    # Build cumulative time axis (seconds), starting at t=0 for the first beat
    t_rr = np.cumsum(rr / 1000.0)
    t_rr = np.insert(t_rr, 0, 0.0)[:-1]

    # Uniform time grid at fs_resample Hz
    t_uniform = np.arange(t_rr[0], t_rr[-1], 1.0 / fs_resample)
    if len(t_uniform) < 16:
        return 1.0

    # Clamp to edge values instead of extrapolating — t_uniform ends at t_rr[-1]
    # (exclusive via np.arange) so out-of-bounds is rare, but linear extrapolation
    # on a non-monotone RR signal could produce negative values at the boundary.
    # Note: t_uniform stops at t_rr[-1] (start of last beat), so the last rr[-1] ms
    # of signal are not interpolated — a ~2% loss for a 50-beat window at 400 ms avg.
    f_interp = interpolate.interp1d(
        t_rr, rr, kind="linear", bounds_error=False, fill_value=(rr[0], rr[-1])
    )
    rr_uniform = f_interp(t_uniform)
    rr_uniform = rr_uniform - rr_uniform.mean()  # remove DC offset before Welch

    nperseg = min(len(rr_uniform), 256)
    freqs, psd = signal.welch(rr_uniform, fs=fs_resample, nperseg=nperseg)

    lf_mask = (freqs >= 0.04) & (freqs < 0.15)
    hf_mask = (freqs >= 0.15) & (freqs < 0.40)

    lf_power = float(_trapz(psd[lf_mask], freqs[lf_mask])) if lf_mask.any() else 0.0
    hf_power = float(_trapz(psd[hf_mask], freqs[hf_mask])) if hf_mask.any() else 0.0

    return float(lf_power / max(hf_power, 1e-9))


def _causal_rolling_median(x: np.ndarray, win: int) -> np.ndarray:
    """Causal rolling median: ``out[i] = median(x[max(0, i-win) : i+1])``.

    Replaces the per-sample Python loop (the dominant SampEn cost once the pair
    count is vectorised, issue #45) with a strided window-view median for the
    steady state, computing only the first ``win`` expanding-window medians in
    Python. Bit-identical to the loop it replaces — the ``_preprocess`` golden
    test pins this.
    """
    n = len(x)
    out = np.empty(n, dtype=np.float64)
    head = min(win, n)
    for i in range(head):  # expanding window x[0:i+1] until the window fills
        out[i] = np.median(x[: i + 1])
    if win < n:  # steady state: fixed window of win+1 samples ending at i
        windows = np.lib.stride_tricks.sliding_window_view(x, win + 1)  # (n-win, win+1)
        out[win:] = np.median(windows, axis=1)
    return out


def _preprocess_for_entropy(rr_ms: np.ndarray) -> np.ndarray:
    """Artifact-reject then detrend an RR series before computing SampEn.

    Entropy "inevitably falls in any record with spikes" — a missed or ectopic
    beat masquerades as structure and craters SampEn — so rejection is mandatory,
    not optional (Lake 2002, PMID 12185014; HeRO methods per Moorman 2011,
    PMID 22026974). Steps: drop non-finite values, reject beats that deviate
    >20% from the local median of the surrounding window, then remove a slow
    baseline (subtract a moving average) so ``r`` scales to the fluctuations,
    not the trend.
    """
    x = np.asarray(rr_ms, dtype=np.float64)
    x = x[np.isfinite(x)]
    if len(x) < 5:
        return x

    win = min(_SAMPEN_DETREND_WIN, len(x))
    local_med = _causal_rolling_median(x, win)
    keep = np.abs(x - local_med) <= _SAMPEN_ARTIFACT_FRAC * local_med
    x = x[keep]
    if len(x) < 5:
        return x

    # Detrend: subtract a centred moving-average baseline (edge-padded).
    kernel = np.ones(win) / win
    baseline = np.convolve(np.pad(x, win // 2, mode="edge"), kernel, mode="valid")
    baseline = baseline[: len(x)]
    return x - baseline


def _count_close_pairs(templates: np.ndarray, r: float) -> int:
    """Count unordered template pairs (i<j, no self-match) within Chebyshev distance ``r``.

    The original SampEn scan is O(n²) with a Python row-loop — ~7 s on a 4096-beat
    window (issue #45). A materialised-broadcast version is still O(n²) and
    memory-bound, so it wins nothing. Instead we index the templates in a KD-tree
    and count neighbours under the Chebyshev (``p=∞``) metric — O(n log n) build,
    and sparse for the small SampEn tolerance (``r = 0.2·SD``), so the count is
    fast. ``count_neighbors`` returns ordered pairs *including* the diagonal
    (every point matches itself, distance 0 ≤ r), so the unordered no-self count
    is ``(total − n) / 2`` — the same integer the row-loop produced (same
    templates, same ``≤ r``); the equivalence tests pin this bit-for-bit.
    """
    n = len(templates)
    if n < 2:
        return 0
    tree = cKDTree(np.ascontiguousarray(templates))
    total = int(tree.count_neighbors(tree, r, p=np.inf))  # ordered pairs incl. self, dist ≤ r
    return (total - n) // 2


def _sampen(rr_ms: np.ndarray, m: int = SAMPEN_M, r_factor: float = SAMPEN_R_FACTOR) -> float:
    """Sample entropy of an RR series (ms). Returns NaN when uncomputable.

    SampEn = −ln( A / B ) where B is the number of matching template pairs of
    length ``m`` and A of length ``m+1``, using the Chebyshev (max) distance and
    a tolerance ``r = r_factor × SD`` of the *detrended* series, counted without
    self-matches (Richman & Moorman 2000, PMID 10843903). Falls toward regularity
    — the direction that precedes sepsis in the neonatal RR domain (Lake 2002).

    NaN (never a fabricated value) when the series is too short, degenerate
    (r≈0), or produces no matches at length m/m+1 (entropy undefined).
    """
    x = _preprocess_for_entropy(rr_ms)
    n = len(x)
    if n < m + 2:
        return float("nan")

    r = r_factor * np.std(x, ddof=1)
    if not np.isfinite(r) or r <= 0:
        return float("nan")

    def _count_matches(mm: int) -> int:
        # Number of i<j template pairs within Chebyshev distance r (no self-match).
        templates = np.lib.stride_tricks.sliding_window_view(x, mm)
        return _count_close_pairs(templates, r)

    b = _count_matches(m)
    a = _count_matches(m + 1)
    if b == 0 or a == 0:
        return float("nan")
    return float(-np.log(a / b))


def _sample_asymmetry(rr_ms: np.ndarray) -> float:
    """Sample asymmetry (R2/R1) of the RR histogram. Returns NaN when uncomputable.

    Sign convention (PINNED — the #13 [UNVERIFIED] flag): computed on **RR** with
    the Kovatchev R2/R1 convention about the median. Values above the median are
    long RR / **decelerations (R2)**; below are short RR / **accelerations (R1)**.
    A deceleration-heavy histogram gives R2 > R1 → ratio **> 1**; the value
    **rises** before sepsis (~3.3 → 4.2), so it wires as a **high-only** trigger
    (Kovatchev 2003, PMID 12930915; Moorman 2011, PMID 22026974).
    """
    x = np.asarray(rr_ms, dtype=np.float64)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 3:
        return float("nan")

    dev = x - np.median(x)
    r1 = float(np.sum(dev[dev < 0] ** 2) / n)  # accelerations (short RR, below median)
    r2 = float(np.sum(dev[dev > 0] ** 2) / n)  # decelerations (long RR, above median)
    if r1 <= 0:
        return float("nan")
    return r2 / r1


def compute_hrv_features(rr_ms: np.ndarray, rr_entropy: np.ndarray | None = None) -> dict:
    """
    Compute all HRV features from a 1D array of RR intervals (ms).

    Returns a flat dict with keys:
      mean_rr, sdnn, rmssd, pnn50, lf_hf_ratio,
      rr_ms_min, rr_ms_max, rr_ms_25%, rr_ms_50%, rr_ms_75%,
      sampen, sample_asymmetry

    Parameters
    ----------
    rr_ms : np.ndarray
        1D array of RR intervals in milliseconds for this window. Must be non-empty.
        All statistics except ``sampen`` are computed on this window.
    rr_entropy : np.ndarray, optional
        The (typically longer, ~4096-interval / ~20–25 min) trailing RR series over
        which ``sampen`` is computed — SampEn needs far more beats than the ~50-beat
        HRV window to be stable, so the pipeline slides a long window "per the existing
        Tier-1 cadence" (issue #13; docs/research/cardiorespiratory-feature-validation.md).
        When ``None``, SampEn falls back to ``rr_ms``; when too short it is NaN
        (cold-start), which the direction-aware floor treats as non-triggering.

    Raises
    ------
    ValueError
        If rr_ms is empty.
    """
    rr = np.asarray(rr_ms, dtype=np.float64)
    n = len(rr)
    if n == 0:
        raise ValueError("rr_ms cannot be empty")

    mean_rr = float(np.mean(rr))
    sdnn    = float(np.std(rr, ddof=1)) if n > 1 else 0.0
    rmssd   = float(np.sqrt(np.mean(np.diff(rr) ** 2))) if n > 1 else 0.0
    pnn50   = float(np.sum(np.abs(np.diff(rr)) > 50) / max(n - 1, 1) * 100) if n > 1 else 0.0
    lf_hf   = _compute_lf_hf(rr)

    entropy_src = rr if rr_entropy is None else np.asarray(rr_entropy, dtype=np.float64)

    return {
        "mean_rr":          mean_rr,
        "sdnn":             sdnn,
        "rmssd":            rmssd,
        "pnn50":            pnn50,
        "lf_hf_ratio":      lf_hf,
        "rr_ms_min":        float(np.min(rr)),
        "rr_ms_max":        float(np.max(rr)),
        "rr_ms_25%":        float(np.percentile(rr, 25)),
        "rr_ms_50%":        float(np.percentile(rr, 50)),
        "rr_ms_75%":        float(np.percentile(rr, 75)),
        "sampen":           _sampen(entropy_src),
        "sample_asymmetry": _sample_asymmetry(rr),
    }


def get_window_features(
    rr_intervals: np.ndarray,
    record_name: str,
    window_idx: int,
    rr_entropy: np.ndarray | None = None,
) -> dict:
    """
    Encode a window of RR intervals with record metadata for feature matrix rows.

    Parameters
    ----------
    rr_intervals : np.ndarray
        1D array of RR intervals in milliseconds for this window.
    record_name : str
        Infant record identifier (e.g. 'infant1').
    window_idx : int
        Index of this window within the recording.
    rr_entropy : np.ndarray, optional
        The trailing long window over which ``sampen`` is computed (issue #13). See
        ``compute_hrv_features``. When ``None``, SampEn falls back to ``rr_intervals``.

    Returns
    -------
    dict
        Feature dict with record_name, window_idx, plus all keys from compute_hrv_features().
    """
    features = compute_hrv_features(rr_intervals, rr_entropy=rr_entropy)
    features["record_name"] = record_name
    features["window_idx"]  = window_idx
    return features
