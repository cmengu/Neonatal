"""Export the REAL JEPA world-model trajectory for the demo window → trace `world_model` block.

Ticket #60 (map #56): the demo's 3-D embedding hero and its Surprise warp must be driven by
the *actual* trained model on the *actual* recorded infant window — not a hand-drawn curve.
This script runs the shipped checkpoint (`models/jepa/jepa.pt`) over infant7's stream, slices
the locked scenario window (`[1240, 1419]`, spec §1), and emits a JSON block that:

- aligns to the #30 **shared time grid** (index ``i`` ↔ absolute window ``w0 + i``), so every
  point sits on the same clock as data-in / Tier 1 / Tier 2 / Tier 3;
- carries each window's **PCA→3-D** projection of the target-encoder embedding, the basis
  **fitted on the normal phase only** (spec §7 — defensible axes, not fit on the departure);
- carries **novelty** (Mahalanobis distance from this infant's learned-normal cloud) and the
  **Surprise** series (horizon-aggregated latent error, z-scored to calm) — the two signals the
  #58 scorecard validated;
- includes a **normal-cloud** sample (calm embeddings in the PCA basis) + the cloud-edge p95, so
  the front-end can draw the cluster and ripple the warp against a real reference.

Honesty: the ground truth for "calm" is the model-blind rolling ``||x_dev||`` (the same signal
Tier 1/CUSUM trust), never a label — identical protocol to `jepa_score.demo_trajectory`. The
caption written into the block says exactly what the axes are; no accuracy number is painted on.

    PYTHONPATH=. python3 scripts/export_jepa_trace.py         # writes dashboard/lib/world-model-infant7.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from src.world_model.jepa import load_checkpoint
from src.world_model.jepa_score import (
    departure_calm_masks,
    embed_stream,
    novelty_from_embeddings,
    pick_device,
    surprise_stream,
)
from src.world_model.jepa_data import load_infant_sequences

REPO_ROOT = Path(__file__).resolve().parent.parent
# Normal-phase length inside the demo window (shared-grid [0, NORMAL_LEN) = pre-onset).
# Matches the trace time_grid phases in dashboard/lib/mock-trace.ts (onset at window 90).
DEFAULT_NORMAL_LEN = 90
# Cap on calm points drawn as the 3-D "normal cloud" — enough for a soft cluster, not bloat.
CLOUD_SAMPLE = 400


def _pca_fit(embeddings: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Top-3 PCA basis of ``embeddings`` (N, D). Returns (mean (D,), components (3, D),
    variance_explained (3,)). Fitted on whatever slice is passed — here, the normal phase."""
    mu = embeddings.mean(axis=0)
    centered = embeddings - mu
    # SVD is the numerically stable PCA; right-singular vectors are the principal axes.
    _, s, vt = np.linalg.svd(centered, full_matrices=False)
    total_var = float(np.sum(s**2)) or 1.0
    return mu, vt[:3], (s[:3] ** 2) / total_var


def _project(embeddings: np.ndarray, mu: np.ndarray, comps: np.ndarray) -> np.ndarray:
    """Project (N, D) embeddings onto the 3 principal axes → (N, 3)."""
    return (embeddings - mu) @ comps.T


def export_world_model(
    ckpt: str,
    csv_path: str,
    infant: str,
    w0: int,
    w1: int,
    normal_len: int,
    roll: int = 20,
    lo_pct: float = 50.0,
) -> dict:
    device = pick_device()
    model = load_checkpoint(ckpt).to(device)
    model.eval()
    seqs, _ = load_infant_sequences(csv_path)
    if infant not in seqs:
        raise SystemExit(f"{infant} not in {csv_path} (have {sorted(seqs)})")
    x = seqs[infant]
    n = w1 - w0 + 1

    # --- real model streams over the whole record, indexed by absolute window ---
    ts_z, Z = embed_stream(model, x, device)
    ts_s, S = surprise_stream(model, x, device, horizon=True)
    zpos = {int(t): i for i, t in enumerate(ts_z)}
    spos = {int(t): i for i, t in enumerate(ts_s)}

    missing_z = [w0 + i for i in range(n) if (w0 + i) not in zpos]
    if missing_z:
        raise SystemExit(f"no embedding for windows {missing_z[:5]}… — window too near record start")

    # --- model-blind calm cloud (same ground truth as the scorecard) ---
    _, calm, _ = departure_calm_masks(x, roll=roll, lo_pct=lo_pct)
    calm_z_idx = np.array([i for i, t in enumerate(ts_z) if calm[int(t)]])
    calm_embeddings = Z[calm_z_idx]  # (M, D) — well-estimated covariance for Mahalanobis

    # --- PCA basis fitted on the NORMAL PHASE of the demo window only (spec §7) ---
    normal_abs = [w0 + i for i in range(min(normal_len, n))]
    normal_embeddings = np.array([Z[zpos[t]] for t in normal_abs])
    mu, comps, var_explained = _pca_fit(normal_embeddings)

    # --- novelty over all windows vs the full calm cloud; cloud-edge p95 ---
    nov_all = novelty_from_embeddings(Z, calm_embeddings, whiten=True)  # aligned to ts_z
    calm_novelty = nov_all[calm_z_idx]
    baseline_p95 = float(np.percentile(calm_novelty, 95))
    calm_sd = float(calm_novelty.std() + 1e-9)

    # --- surprise standardised to this infant's calm distribution ---
    calm_s_idx = np.array([i for i, t in enumerate(ts_s) if calm[int(t)]])
    calm_s = S[calm_s_idx]
    s_mu, s_sd = float(calm_s.mean()), float(calm_s.std() + 1e-9)

    # --- per-window trajectory on the shared grid ---
    trajectory = []
    novelty_window: list[float] = []
    surprise_window: list[float] = []
    for i in range(n):
        abs_w = w0 + i
        emb = Z[zpos[abs_w]]
        pca3 = _project(emb[None, :], mu, comps)[0]
        novelty = float(nov_all[zpos[abs_w]])
        # last H windows of the record can lack a horizon surprise; forward-fill honestly
        surprise = float((S[spos[abs_w]] - s_mu) / s_sd) if abs_w in spos else (
            surprise_window[-1] if surprise_window else 0.0
        )
        trajectory.append(
            {
                "idx": i,
                "pca3": [round(float(v), 4) for v in pca3],
                "novelty": round(novelty, 4),
                "surprise": round(surprise, 4),
            }
        )
        novelty_window.append(novelty)
        surprise_window.append(surprise)

    # --- normal-cloud sample projected into the PCA basis (evenly subsampled) ---
    if len(calm_embeddings) > CLOUD_SAMPLE:
        pick = np.linspace(0, len(calm_embeddings) - 1, CLOUD_SAMPLE).astype(int)
        cloud_src = calm_embeddings[pick]
    else:
        cloud_src = calm_embeddings
    cloud3 = _project(cloud_src, mu, comps)

    # --- honest separation summary (median last third − first third, in calm-SD) ---
    third = max(1, n // 3)
    sep_rise_calm_sd = float(
        (np.median(novelty_window[-third:]) - np.median(novelty_window[:third])) / calm_sd
    )
    # 3-D visible separation: how far the trajectory travels in the PCA basis vs calm spread
    cloud_spread = float(np.linalg.norm(cloud3.std(axis=0)) + 1e-9)
    traj3 = np.array([t["pca3"] for t in trajectory])
    pca_sep = float(np.linalg.norm(np.median(traj3[-third:], axis=0)
                                   - np.median(traj3[:third], axis=0)) / cloud_spread)

    return {
        "real": True,
        "infant": infant,
        "window": [w0, w1],
        "embed_dim": int(model.cfg.embed_dim),
        "pca": {
            "fitted_on": "normal",
            "variance_explained": [round(float(v), 4) for v in var_explained],
            "axis_labels": ["PC1", "PC2", "PC3"],
        },
        "trajectory": trajectory,
        "normal_cloud": [[round(float(v), 4) for v in p] for p in cloud3],
        "novelty_baseline_p95": round(baseline_p95, 4),
        "surprise": {
            "series": [round(v, 4) for v in surprise_window],
            "calm_mean": round(s_mu, 6),
            "calm_std": round(s_sd, 6),
        },
        "sep_rise_calm_sd": round(sep_rise_calm_sd, 3),
        "pca_visible_sep": round(pca_sep, 3),
        "caption": (
            "Principal components of the JEPA target-encoder embedding, fitted on this infant's "
            "normal phase. The trajectory's distance from the learned-normal cloud (Mahalanobis) "
            "and its predictive surprise are the real model outputs; the axes carry no accuracy score."
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="models/jepa/jepa.pt")
    ap.add_argument("--data", default="data/processed/all_patients_windowed.csv")
    ap.add_argument("--infant", default="infant7")
    ap.add_argument("--w0", type=int, default=1240)
    ap.add_argument("--w1", type=int, default=1419)
    ap.add_argument("--normal-len", type=int, default=DEFAULT_NORMAL_LEN)
    ap.add_argument("--out", default="dashboard/lib/world-model-infant7.json")
    args = ap.parse_args()

    block = export_world_model(
        args.ckpt, args.data, args.infant, args.w0, args.w1, args.normal_len
    )
    out = REPO_ROOT / args.out
    out.write_text(json.dumps(block, indent=2) + "\n")
    print(f"wrote {out}")
    print(
        f"  n={len(block['trajectory'])}  embed_dim={block['embed_dim']}  "
        f"var_explained={block['pca']['variance_explained']}"
    )
    print(
        f"  novelty sep_rise={block['sep_rise_calm_sd']} calm-SD  "
        f"pca_visible_sep={block['pca_visible_sep']}  cloud_edge_p95={block['novelty_baseline_p95']}  "
        f"cloud_pts={len(block['normal_cloud'])}"
    )


if __name__ == "__main__":
    main()
