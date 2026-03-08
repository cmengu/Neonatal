# src/features/hrv.py
"""
HRV (heart rate variability) feature encoding for neonatal sepsis pipeline.

Adapted from acampillos/sepsis-prediction preprocessing/util.py.
Input: 1D numpy array of RR intervals (ms). Output: flat dict of statistical features.
"""
import pandas as pd
import numpy as np


def get_serie_describe(rr_intervals):
    """
    Encode a window of RR intervals as statistical features.

    Takes a 1D numpy array of RR intervals (ms), wraps in DataFrame,
    computes describe() stats, and returns a flat dictionary keyed as
    'rr_ms_mean', 'rr_ms_std', etc. Adapted from acampillos/sepsis-prediction.

    Parameters
    ----------
    rr_intervals : np.ndarray
        1D array of RR intervals in milliseconds (ectopic beats already removed).

    Returns
    -------
    dict
        Flat dictionary: 'rr_ms_mean', 'rr_ms_std', 'rr_ms_min', 'rr_ms_max',
        'rr_ms_25%', 'rr_ms_50%', 'rr_ms_75%'

    Raises
    ------
    ValueError
        If rr_intervals is empty (caller must ensure len > 0).
    """
    if len(rr_intervals) == 0:
        raise ValueError("rr_intervals cannot be empty")
    serie = pd.DataFrame({"rr_ms": rr_intervals})
    serie_describe = serie.describe().transpose().drop(columns=["count"])

    values = dict()
    for index, row in serie_describe.iterrows():
        for col in row.index:
            values[f"{index}_{col}"] = row[col]
    return values


def get_window_features(rr_intervals, record_name, window_idx):
    """
    Encode a window of RR intervals with record metadata for feature matrix rows.

    Parameters
    ----------
    rr_intervals : np.ndarray
        1D array of RR intervals in milliseconds for this window.
    record_name : str
        Infant record identifier (e.g. 'simulated_1', 'infant1').
    window_idx : int
        Index of the window within the recording.

    Returns
    -------
    dict
        Feature dictionary with record_name, window_idx, plus statistical features.
    """
    features = get_serie_describe(rr_intervals)
    features["record_name"] = record_name
    features["window_idx"] = window_idx
    return features
