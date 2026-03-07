#!/usr/bin/env python3
"""Verify notebooks 01 & 02 pipeline with neurokit2 simulated data. No matplotlib."""
import neurokit2 as nk
import numpy as np
import pandas as pd
from scipy.signal import butter, filtfilt
import os

# Simulated data (notebook 01)
ecg_raw = nk.ecg_simulate(duration=60, sampling_rate=500)
fs = 500
print("Notebook 01 simulation: OK")
print(f"  ECG: {len(ecg_raw)} samples, std={ecg_raw.std():.4f}")

# Bandpass (notebook 02)
def bandpass_filter(signal, lowcut=0.5, highcut=40, fs=500, order=4):
    nyq = 0.5 * fs
    b, a = butter(order, [lowcut / nyq, highcut / nyq], btype="band")
    return filtfilt(b, a, signal)

ecg_f = bandpass_filter(ecg_raw, fs=fs)
_, info = nk.ecg_peaks(ecg_f, sampling_rate=fs)
rpeaks = info["ECG_R_Peaks"]
bpm = len(rpeaks) / (60 / 60)
print(f"  R-peaks: {len(rpeaks)}, bpm={bpm:.1f}")

# RR + ectopic
def filter_ectopic_beats(rr_ms, threshold_pct=0.20):
    rr = np.array(rr_ms, dtype=float)
    median_rr = np.median(rr)
    deviation = np.abs(rr - median_rr) / median_rr
    mask = deviation <= threshold_pct
    return rr[mask], mask

rr = np.diff(rpeaks) / fs * 1000
rr_clean, mask = filter_ectopic_beats(rr)
print(f"  RR: mean={rr_clean.mean():.1f}ms, removed {(~mask).sum()} ectopics")

os.makedirs("data/processed", exist_ok=True)
pd.DataFrame({"rr_ms": rr_clean}).to_csv("data/processed/simulated_1_rr_clean.csv", index=False)
print("  Saved simulated_1_rr_clean.csv")

# All 10 infants
for i in range(1, 11):
    ecg = nk.ecg_simulate(duration=60, sampling_rate=500, heart_rate=120 + 6 * i)
    ecg_f = bandpass_filter(ecg, fs=fs)
    _, info = nk.ecg_peaks(ecg_f, sampling_rate=fs)
    rp = info["ECG_R_Peaks"]
    rr = np.diff(rp) / fs * 1000
    rr_c, m = filter_ectopic_beats(rr)
    pd.DataFrame({"rr_ms": rr_c}).to_csv(f"data/processed/simulated_{i}_rr_clean.csv", index=False)

n_csv = len([f for f in os.listdir("data/processed") if f.endswith(".csv")])
print(f"Notebook 02 pipeline: OK, {n_csv} CSVs in data/processed/")

# Step 7 verification
df = pd.read_csv("data/processed/simulated_1_rr_clean.csv")
print(f"Step 7 check: Rows={len(df)}, Mean RR={df.rr_ms.mean():.1f}ms, NaNs={df.rr_ms.isna().sum()}")
