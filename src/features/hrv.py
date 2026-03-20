"""
HRV feature extraction for neonatal sepsis pipeline.

Computes time-domain and frequency-domain HRV metrics from windowed RR intervals.
Time-domain:       mean_rr, sdnn, rmssd, pnn50
Frequency-domain:  lf_hf_ratio  (Welch PSD, LF 0.04–0.15 Hz / HF 0.15–0.40 Hz)
Statistical:       rr_ms_min, rr_ms_max, rr_ms_25%, rr_ms_50%, rr_ms_75%

The authoritative ordered column name list is in ``src.features.constants.HRV_FEATURE_COLS``.
The keys returned by ``compute_hrv_features()`` must stay in sync with that list.
"""
import numpy as np
from scipy import signal, interpolate
from scipy.integrate import trapezoid as _trapz  # np.trapz removed in NumPy 2.0


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


def compute_hrv_features(rr_ms: np.ndarray) -> dict:
    """
    Compute all HRV features from a 1D array of RR intervals (ms).

    Returns a flat dict with keys:
      mean_rr, sdnn, rmssd, pnn50, lf_hf_ratio,
      rr_ms_min, rr_ms_max, rr_ms_25%, rr_ms_50%, rr_ms_75%

    Parameters
    ----------
    rr_ms : np.ndarray
        1D array of RR intervals in milliseconds. Must be non-empty.

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

    return {
        "mean_rr":     mean_rr,
        "sdnn":        sdnn,
        "rmssd":       rmssd,
        "pnn50":       pnn50,
        "lf_hf_ratio": lf_hf,
        "rr_ms_min":   float(np.min(rr)),
        "rr_ms_max":   float(np.max(rr)),
        "rr_ms_25%":   float(np.percentile(rr, 25)),
        "rr_ms_50%":   float(np.percentile(rr, 50)),
        "rr_ms_75%":   float(np.percentile(rr, 75)),
    }


def get_window_features(rr_intervals: np.ndarray, record_name: str, window_idx: int) -> dict:
    """
    Encode a window of RR intervals with record metadata for feature matrix rows.

    Signature is intentionally unchanged from the original implementation so that
    run_nb03.py requires no import update.

    Parameters
    ----------
    rr_intervals : np.ndarray
        1D array of RR intervals in milliseconds for this window.
    record_name : str
        Infant record identifier (e.g. 'infant1').
    window_idx : int
        Index of this window within the recording.

    Returns
    -------
    dict
        Feature dict with record_name, window_idx, plus all keys from compute_hrv_features().
    """
    features = compute_hrv_features(rr_intervals)
    features["record_name"] = record_name
    features["window_idx"]  = window_idx
    return features
