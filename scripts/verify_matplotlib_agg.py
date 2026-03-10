#!/usr/bin/env python3
"""Quick verification that matplotlib.use('Agg') prevents blocking. Runs in ~5–30s."""
import os
os.environ["MPLBACKEND"] = "Agg"
_cwd = os.path.dirname(os.path.abspath(__file__))
os.environ["MPLCONFIGDIR"] = os.path.join(_cwd, "..", ".mpl_config")
# Avoid matplotlib font crash on macOS (KeyError '_items' / slow system_profiler)
os.environ["PATH"] = "/usr/bin:/bin:/usr/local/bin"
import matplotlib
matplotlib.use("Agg")
import neurokit2 as nk
import numpy as np

# Use simulated ECG — random noise yields too few peaks and NaN
sig = nk.ecg_simulate(duration=5, sampling_rate=500, heart_rate=80)
try:
    signals, info = nk.ecg_process(sig, sampling_rate=500)
    n_peaks = len(info["ECG_R_Peaks"])
    print(f"OK: ecg_process completed without blocking (got {n_peaks} peaks)")
except Exception as e:
    print(f"FAIL: {e}")
    raise SystemExit(1)
