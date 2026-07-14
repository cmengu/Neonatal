"""Respiration-derived cardiorespiratory features for the neonatal-sepsis pipeline.

Issue #3. The PICS respiration channel (``.resp`` = "automatically detected
respiration peaks") is the second non-invasive signal the world model needs. This
module turns the breath-peak stream into a feature stream — respiratory rate,
respiratory variability, and apnea episodes — and quantifies the apnea->bradycardia
coupling that heart rate alone cannot express. It is pure numpy: no I/O, no wfdb
(the runner ``scripts/run_respiration.py`` reads the WFDB records and calls in here),
mirroring ``src.features.hrv``.

Feature set and pathological directions are grounded in the primary-source review
``docs/research/cardiorespiratory-feature-validation.md`` (resolves research #10):

  * **Apnea burden.** Central apnea (pauses >= ~15-20 s) is detectable from the
    respiration waveform and *increases* in the 1-2 days before late-onset sepsis;
    the apnea->bradycardia link is the classic apnea-of-prematurity coupling
    (Pre-Vent, J Pediatr 2024, PMID 38570031; Vergales 2014, PMID 23592319;
    Fairchild 2016 part 1, PMID 26959485).
  * **Respiratory-rate variability / instability.** Breathing becomes more unstable
    before sepsis (Joshi 2020, PMID 31295130; Pre-Vent, PMID 38570031). All
    computable respiration features move *up* toward the pathological state.
  * **SpO2 gap.** Intermittent hypoxemia — the single strongest predictor in
    ventilated infants — needs SpO2, which PICS does not have; it is recorded as an
    explicit gap, not proxied (Pre-Vent, PMID 38570031).

Two facts drive the design and each is a named constant below:

  * **Align in seconds, never in samples.** PICS sampling frequencies are
    heterogeneous — respiration is 50 Hz for most infants but 500 Hz for infant1,
    and ECG is 500 Hz except 250 Hz for infant1/5. Breath peaks and bradycardia
    onsets therefore live in different sample spaces; ``event_times_seconds`` is the
    single door that converts to a common seconds timeline before anything is compared.
  * **Apnea is a *banded* pause.** A physiological apnea is bounded above: a
    multi-minute "pause" in this data is a sensor dropout, not an apnea, and would
    otherwise dominate the counts. ``APNEA_MAX_PAUSE_S`` is a data-quality gate
    (the review stresses that artifact rejection "is not optional"), not a clinical
    threshold.

The ordered output column list is ``src.features.constants.RESP_FEATURE_COLS``; the
keys returned by ``compute_respiration_features`` must stay in sync with it.
"""
from __future__ import annotations

import numpy as np

# Drop breath peaks spaced closer than this — 0.2 s is a 300/min ceiling, above any
# real neonatal respiratory rate, so a sub-refractory peak is a detector
# double-count, not a breath. Never merges across an apnea gap.
BREATH_REFRACTORY_S = 0.2

# Apnea plausibility band. Lower bound: Pre-Vent/clinical apnea is a pause of
# >= ~15-20 s (PMID 38570031; Vergales 2014 PMID 23592319 uses >=10 s *with*
# brady/desat). Upper bound: a data-quality gate — pauses beyond ~2 min are sensor
# dropouts (this cohort has "gaps" of thousands of seconds), not survivable apneas.
APNEA_MIN_PAUSE_S = 15.0
APNEA_MAX_PAUSE_S = 120.0

# A bradycardia counts as coupled to an apnea if its onset falls within the apnea or
# within COUPLING_LAG_S after it — the apnea-bradycardia-desaturation timing of
# prematurity, where the bradycardia follows the pause by seconds to tens of seconds.
COUPLING_LAG_S = 30.0


def event_times_seconds(samples, fs: float) -> np.ndarray:
    """
    Convert WFDB annotation sample indices to a seconds timeline.

    This is the single conversion point that lets breath peaks (respiration record)
    and bradycardia onsets/beats (ECG record) be compared, because the two records
    are sampled at *different* frequencies (see module docstring).

    Parameters
    ----------
    samples : array-like
        Annotation sample indices within a single WFDB record.
    fs : float
        That record's sampling frequency in Hz (read from its header, never assumed).

    Returns
    -------
    np.ndarray
        Event times in seconds from the record start.

    Raises
    ------
    ValueError
        If ``fs`` is missing or non-positive.
    """
    if fs is None or fs <= 0:
        raise ValueError(f"fs must be a positive sampling frequency, got {fs!r}")
    return np.asarray(samples, dtype=np.float64) / float(fs)


def clean_breath_times(
    breath_times_s, refractory_s: float = BREATH_REFRACTORY_S
) -> np.ndarray:
    """
    Sort breath-peak times and drop sub-refractory double-detections.

    Peaks spaced closer than ``refractory_s`` are collapsed to the first of the run.
    Because ``refractory_s`` (0.2 s) is far below the apnea threshold, this never
    creates or removes an apnea gap — it only cleans respiratory-rate/variability.

    Parameters
    ----------
    breath_times_s : array-like
        Breath-peak times in seconds. NaNs are ignored.
    refractory_s : float
        Minimum spacing between kept breaths.

    Returns
    -------
    np.ndarray
        Sorted, de-duplicated breath times in seconds.
    """
    t = np.asarray(breath_times_s, dtype=np.float64)
    t = np.sort(t[~np.isnan(t)])
    if len(t) == 0:
        return t
    kept = [t[0]]
    for x in t[1:]:
        if x - kept[-1] >= refractory_s:
            kept.append(x)
    return np.asarray(kept, dtype=np.float64)


def detect_apnea_episodes(
    breath_times_s,
    min_pause_s: float = APNEA_MIN_PAUSE_S,
    max_pause_s: float = APNEA_MAX_PAUSE_S,
) -> list[dict]:
    """
    Find apnea episodes as breath-to-breath gaps within the plausibility band.

    An episode is a gap ``g`` between consecutive breaths with
    ``min_pause_s <= g <= max_pause_s``. Gaps above ``max_pause_s`` are treated as
    signal dropouts and excluded (see ``APNEA_MAX_PAUSE_S``).

    Parameters
    ----------
    breath_times_s : array-like
        Cleaned breath-peak times in seconds (ascending).
    min_pause_s, max_pause_s : float
        Inclusive lower/upper bounds of the apnea band.

    Returns
    -------
    list[dict]
        One dict per episode with ``onset_s`` (last breath before the pause),
        ``offset_s`` (first breath after it), and ``duration_s`` (the gap).
    """
    t = np.asarray(breath_times_s, dtype=np.float64)
    if len(t) < 2:
        return []
    gaps = np.diff(t)
    episodes = []
    for i, g in enumerate(gaps):
        if min_pause_s <= g <= max_pause_s:
            episodes.append(
                {
                    "onset_s": float(t[i]),
                    "offset_s": float(t[i + 1]),
                    "duration_s": float(g),
                }
            )
    return episodes


def compute_respiration_features(
    breath_times_s, t_start: float, t_end: float, apnea_episodes: list[dict] | None = None
) -> dict:
    """
    Compute respiration features over the window ``[t_start, t_end)``.

    Returns exactly the keys in ``src.features.constants.RESP_FEATURE_COLS``.
    Respiratory rate and variability are count/CV of the breaths inside the window;
    apnea burden is the overlap of ``apnea_episodes`` with the window (episodes are
    detected once per record and passed in, so a long apnea is attributed to every
    window it spans).

    Parameters
    ----------
    breath_times_s : array-like
        Cleaned breath-peak times in seconds for the whole record.
    t_start, t_end : float
        Window bounds in seconds (half-open ``[t_start, t_end)``).
    apnea_episodes : list[dict] | None
        Episodes from ``detect_apnea_episodes``. If None, apnea burden is zero
        (respiratory-rate/variability are still computed).

    Returns
    -------
    dict
        Flat feature dict keyed by ``RESP_FEATURE_COLS``.
    """
    t = np.asarray(breath_times_s, dtype=np.float64)
    in_window = t[(t >= t_start) & (t < t_end)]
    duration = float(t_end - t_start)
    n_breaths = int(in_window.size)

    resp_rate = float(n_breaths / duration * 60.0) if duration > 0 else 0.0

    # Variability needs at least two inter-breath intervals (three breaths); with a
    # single interval the sample SD (ddof=1) is undefined, so report 0 (no observable
    # variability) rather than NaN.
    intervals = np.diff(in_window)
    if intervals.size >= 2:
        mean_interval = float(intervals.mean())
        cv = float(intervals.std(ddof=1) / mean_interval) if mean_interval > 0 else 0.0
    else:
        cv = 0.0

    apnea_count = 0
    apnea_seconds = 0.0
    longest_apnea = 0.0
    for episode in apnea_episodes or []:
        overlap = min(episode["offset_s"], t_end) - max(episode["onset_s"], t_start)
        if overlap > 0:
            apnea_count += 1
            apnea_seconds += overlap
            longest_apnea = max(longest_apnea, overlap)

    return {
        "resp_rate_bpm": resp_rate,
        "breath_interval_cv": cv,
        "n_breaths": n_breaths,
        "apnea_count": apnea_count,
        "apnea_seconds": float(apnea_seconds),
        "longest_apnea_s": float(longest_apnea),
    }


def respiration_feature_rows(
    breath_times_s,
    record_name: str,
    t0: float | None = None,
    t_end: float | None = None,
    window_s: float = 60.0,
    step_s: float = 30.0,
    apnea_episodes: list[dict] | None = None,
) -> list[dict]:
    """
    Slide a fixed-time window over the record and emit one feature row per window.

    Unlike the beat-indexed HRV windows (which cannot be mapped back to wall-clock
    time — the cleaned RR series drops the gaps), the respiration stream is windowed
    on the absolute seconds timeline, so each row carries ``t_start_s``/``t_end_s``
    for later time-alignment with any other channel.

    Parameters
    ----------
    breath_times_s : array-like
        Cleaned breath-peak times in seconds.
    record_name : str
        Infant record identifier (e.g. ``"infant1"``).
    t0, t_end : float | None
        Window grid start/end in seconds; default to the first/last breath.
    window_s, step_s : float
        Window length and step (default 60 s window, 30 s step = 50% overlap).
    apnea_episodes : list[dict] | None
        Precomputed episodes; detected from ``breath_times_s`` if None.

    Returns
    -------
    list[dict]
        Rows with ``record_name, window_idx, t_start_s, t_end_s`` plus
        ``RESP_FEATURE_COLS``. Empty if there are no breaths.
    """
    t = np.asarray(breath_times_s, dtype=np.float64)
    if t.size == 0:
        return []
    if t0 is None:
        t0 = float(t.min())
    if t_end is None:
        t_end = float(t.max())
    if apnea_episodes is None:
        apnea_episodes = detect_apnea_episodes(t)

    rows = []
    window_idx = 0
    start = t0
    while start + window_s <= t_end:
        features = compute_respiration_features(t, start, start + window_s, apnea_episodes)
        features["record_name"] = record_name
        features["window_idx"] = window_idx
        features["t_start_s"] = float(start)
        features["t_end_s"] = float(start + window_s)
        rows.append(features)
        start += step_s
        window_idx += 1
    return rows


def apnea_coincident_flags(
    apnea_episodes: list[dict], brady_onsets_s, lag_s: float = COUPLING_LAG_S
) -> list[bool]:
    """
    For each apnea episode, whether a bradycardia onset falls within its coupling window.

    The coupling window is ``[onset_s, offset_s + lag_s]`` — a bradycardia occurring
    *during* the pause or shortly after it (apnea preceding/overlapping bradycardia).

    Parameters
    ----------
    apnea_episodes : list[dict]
        Episodes from ``detect_apnea_episodes``.
    brady_onsets_s : array-like
        Bradycardia onset times in seconds (from the ECG ``.atr`` reference).
    lag_s : float
        Post-apnea window in which a bradycardia still counts as coupled.

    Returns
    -------
    list[bool]
        One flag per episode, in order.
    """
    brady = np.asarray(brady_onsets_s, dtype=np.float64)
    flags = []
    for episode in apnea_episodes:
        low = episode["onset_s"]
        high = episode["offset_s"] + lag_s
        flags.append(bool(np.any((brady >= low) & (brady <= high))))
    return flags


def min_heart_rate_bpm(beat_times_s, t_low: float, t_high: float) -> float:
    """
    Instantaneous heart-rate nadir between beats in ``[t_low, t_high]``, in bpm.

    This is the beat-side of the cardiorespiratory coupling feature: it aligns the
    breath-derived apnea window against the ECG beats to expose the bradycardia that
    heart rate alone (a window mean) would average away. The nadir is
    ``60 / max_RR`` over the beats in range.

    Parameters
    ----------
    beat_times_s : array-like
        R-peak times in seconds (from the ECG ``.qrsc`` reference).
    t_low, t_high : float
        Time bounds in seconds (inclusive).

    Returns
    -------
    float
        Minimum instantaneous HR in bpm, or NaN if fewer than two beats are in range.
    """
    beats = np.asarray(beat_times_s, dtype=np.float64)
    segment = beats[(beats >= t_low) & (beats <= t_high)]
    if segment.size < 2:
        return float("nan")
    max_rr = float(np.diff(segment).max())
    return float(60.0 / max_rr) if max_rr > 0 else float("nan")


def apnea_bradycardia_coupling(
    apnea_episodes: list[dict],
    brady_onsets_s,
    total_duration_s: float,
    lag_s: float = COUPLING_LAG_S,
) -> dict:
    """
    Summarise apnea->bradycardia coupling and test it against a random-placement null.

    Reports how many apnea episodes have a coincident bradycardia and how many would
    be expected if the same number of bradycardias were scattered uniformly over the
    record. ``enrichment`` = observed / expected is the effect size; >> 1 means the
    coupling is real, not an artifact of two busy event streams overlapping by chance.

    The null models each episode's coupling window independently: for a window of
    width ``w`` in a record of length ``T`` with ``n`` bradycardias placed at random,
    the chance that at least one lands in it is ``1 - (1 - w/T)**n``; the expected
    coincident count is the sum of those probabilities.

    Parameters
    ----------
    apnea_episodes : list[dict]
        Episodes from ``detect_apnea_episodes``.
    brady_onsets_s : array-like
        Bradycardia onset times in seconds.
    total_duration_s : float
        Record duration in seconds (the null's ``T``).
    lag_s : float
        Post-apnea coupling window (see ``apnea_coincident_flags``).

    Returns
    -------
    dict
        ``n_apnea, n_bradycardia, n_coincident, coincidence_rate,
        expected_by_chance, enrichment``.
    """
    brady = np.asarray(brady_onsets_s, dtype=np.float64)
    n_apnea = len(apnea_episodes)
    n_brady = int(brady.size)

    flags = apnea_coincident_flags(apnea_episodes, brady, lag_s)
    n_coincident = int(np.sum(flags))

    expected = 0.0
    if total_duration_s > 0 and n_brady > 0:
        for episode in apnea_episodes:
            width = (episode["offset_s"] - episode["onset_s"]) + lag_s
            p_hit = 1.0 - (1.0 - min(width / total_duration_s, 1.0)) ** n_brady
            expected += p_hit

    enrichment = float(n_coincident / expected) if expected > 0 else float("nan")

    return {
        "n_apnea": n_apnea,
        "n_bradycardia": n_brady,
        "n_coincident": n_coincident,
        "coincidence_rate": float(n_coincident / n_apnea) if n_apnea else 0.0,
        "expected_by_chance": float(expected),
        "enrichment": enrichment,
    }
