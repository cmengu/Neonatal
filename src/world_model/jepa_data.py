"""Data plumbing for the JEPA world model.

Reads ``data/processed/all_patients_windowed.csv`` — the per-infant **personalised-deviation**
feature stream (already z-scored against each infant's own baseline, so 0 = "this infant's
normal") plus the bradycardia ``label`` column. Turns each infant's ordered window sequence
into ``(context, full)`` training pairs: ``context`` = ``Lc`` past windows the encoder sees,
``full`` = those windows plus the ``H`` future windows whose embeddings the predictor must hit.

No cross-infant leakage in a *sample* — every window in a pair comes from one infant's
contiguous stream. (The model is trained across infants, unlike the strictly per-infant VAR
forecaster; that is the point of a learned representation — it shares structure across babies
while the *trajectory* it produces is still infant-specific.)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset

# Order must match the columns emitted below; the 10 `_dev` HRV features.
FEATURES: tuple[str, ...] = (
    "mean_rr_dev",
    "sdnn_dev",
    "rmssd_dev",
    "pnn50_dev",
    "lf_hf_ratio_dev",
    "rr_ms_min_dev",
    "rr_ms_max_dev",
    "rr_ms_25%_dev",
    "rr_ms_50%_dev",
    "rr_ms_75%_dev",
)

# Personalised deviations are ~unit scale but can spike; clip so one pathological window can't
# dominate the batch statistics the VICReg terms are computed from. Public because every
# consumer feeding the model at inference (jepa_score, the JepaSurpriseAssessor) must
# sanitise identically to training.
CLIP = 8.0


def load_infant_sequences(
    csv_path: str,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Return ``{infant: (T, F) features}`` and ``{infant: (T,) label}`` in window order."""
    df = pd.read_csv(csv_path)
    df = df.sort_values(["record_name", "window_idx"])
    feats: dict[str, np.ndarray] = {}
    labels: dict[str, np.ndarray] = {}
    for name, g in df.groupby("record_name"):
        x = g[list(FEATURES)].to_numpy(dtype=np.float32)
        x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
        x = np.clip(x, -CLIP, CLIP)
        feats[str(name)] = x
        labels[str(name)] = (
            g["label"].to_numpy(dtype=np.int64)
            if "label" in g.columns
            else np.zeros(len(g), dtype=np.int64)
        )
    return feats, labels


class JEPADataset(Dataset):
    """Sliding ``(context, full)`` windows over the per-infant sequences.

    ``stride`` controls overlap between successive training samples; smaller = more samples,
    more overlap. Each item is ``(context (Lc, F), full (Lc+H, F))`` as float tensors.
    """

    def __init__(
        self,
        sequences: dict[str, np.ndarray],
        context_len: int,
        horizon: int,
        stride: int = 4,
    ) -> None:
        self.context_len = context_len
        self.horizon = horizon
        self.seq_len = context_len + horizon
        self.arrays: list[np.ndarray] = []
        self.index: list[tuple[int, int]] = []  # (array_idx, start)
        for arr in sequences.values():
            if len(arr) < self.seq_len:
                continue
            ai = len(self.arrays)
            self.arrays.append(arr)
            last_start = len(arr) - self.seq_len
            for start in range(0, last_start + 1, stride):
                self.index.append((ai, start))

    def __len__(self) -> int:
        return len(self.index)

    def __getitem__(self, i: int) -> tuple[torch.Tensor, torch.Tensor]:
        ai, start = self.index[i]
        seq = self.arrays[ai][start : start + self.seq_len]
        full = torch.from_numpy(np.ascontiguousarray(seq))
        context = full[: self.context_len]
        return context, full
