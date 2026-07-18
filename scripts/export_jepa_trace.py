"""Export the REAL JEPA world-model trajectory for the demo window → trace `world_model` block.

Ticket #60 (map #56): the demo's 3-D embedding hero and its Surprise warp must be driven by
the *actual* trained model on the *actual* recorded infant window — not a hand-drawn curve.
This script runs the shipped checkpoint (`models/jepa/jepa.pt`) over infant7's stream, slices
the scenario window (`[2740, 2919]`), and emits a JSON block that:

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

Two further honesty notes, both learned the hard way:

- **The window is selected, not typical.** Across 2 308 candidate 180-window slices that open
  calm, the median novelty rise is 0.08 calm-SD — most of the record simply has nothing to show.
  The shipped window sits near the 99th percentile. That is legitimate for a *case study* and
  dishonest as a summary, so the caption says so and the cohort-wide onset-anticipation AUC
  remains the actual claim.
- **The window changed when the data was fixed.** The original `[1240, 1419]` was chosen on the
  pre-#18 stream. After the bradycardia data-integrity fix its opening phase is no longer calm
  and its separation collapses from 1.56 to 0.41 calm-SD. Re-run this script after any change
  to the feature pipeline; the numbers here are downstream of it.

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


# Fewest points that may define the 3-D basis. Below this the top-3 SVD is rank-deficient or
# wildly unstable, so the basis is fitted on the infant's whole calm cloud instead (still
# label-free, still never the departure). Chosen as a floor on "enough windows to have a
# direction at all", not a statistical guarantee — 3 axes in 48 dims is under-determined either
# way, which is what ``novelty_captured`` reports.
MIN_BASIS_POINTS = 24


def _complete_basis(comps: np.ndarray, var: np.ndarray, dim: int, n: int = 3):
    """Pad a rank-deficient basis out to ``n`` orthonormal rows, with 0.0 variance.

    A window that opens with 2 calm samples yields a rank-1 SVD, so ``vt[:3]`` returns a
    (2, D) array — and every downstream ``pca3`` silently becomes 2-D, which the trace
    contract declares as a 3-tuple and the 3-D hero reads as ``undefined`` on the z axis.
    Padding with genuinely orthogonal directions carrying an honest 0.0 keeps the shape
    contract while making the emptiness visible rather than hiding it.
    """
    extra: list[np.ndarray] = []
    for e in np.eye(dim):
        v = e - comps.T @ (comps @ e) if len(comps) else e.copy()
        for u in extra:
            v = v - u * float(u @ v)
        norm = float(np.linalg.norm(v))
        if norm > 1e-6:
            extra.append(v / norm)
        if len(comps) + len(extra) >= n:
            break
    comps = np.vstack([comps, np.array(extra)])[:n] if extra else comps[:n]
    var = np.concatenate([var, np.zeros(n - len(var))])[:n]
    return comps, var


def _pca_fit(embeddings: np.ndarray, n_components: int = 3):
    """Top-3 PCA basis of ``embeddings`` (N, D). Returns (mean (D,), components (3, D),
    variance_explained (3,)). Fitted on whatever slice is passed — here, the normal phase.

    Always returns exactly ``n_components`` orthonormal rows: see ``_complete_basis``.
    """
    mu = embeddings.mean(axis=0)
    centered = embeddings - mu
    # SVD is the numerically stable PCA; right-singular vectors are the principal axes.
    _, s, vt = np.linalg.svd(centered, full_matrices=False)
    total_var = float(np.sum(s**2)) or 1.0
    comps, var = vt[:n_components], (s[:n_components] ** 2) / total_var
    if comps.shape[0] < n_components:
        comps, var = _complete_basis(comps, var, embeddings.shape[1], n_components)
    return mu, comps, var


def _project(embeddings: np.ndarray, mu: np.ndarray, comps: np.ndarray) -> np.ndarray:
    """Project (N, D) embeddings onto the 3 principal axes → (N, 3)."""
    return (embeddings - mu) @ comps.T


def _whiten_fit(calm: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Whitening transform of the calm cloud: ``(x - mu) @ W`` is isotropic on calm.

    This is the metric the novelty read-out already uses (Mahalanobis = Euclidean distance
    *after* whitening). Fitted on the calm cloud only — no departure windows — so it is the
    same defensible, label-free basis choice as the raw PCA, just expressed in the geometry
    the model actually measures in.
    """
    mu = calm.mean(axis=0)
    cov = np.cov((calm - mu).T) + 1e-6 * np.eye(calm.shape[1])
    evals, evecs = np.linalg.eigh(cov)
    return mu, evecs @ np.diag(1.0 / np.sqrt(np.maximum(evals, 1e-12))) @ evecs.T


def _captured_fraction(centered: np.ndarray, comps: np.ndarray) -> float:
    """Median share of each point's distance-from-normal that the 3 plotted axes carry.

    The honest headline for the *picture* (distinct from ``variance_explained``, which
    describes the basis rather than the departure): if this reads 0.55, then a viewer watching
    the dot move is seeing 55% of the displacement the model responds to, and 45% is happening
    in directions the screen cannot show.
    """
    full = np.linalg.norm(centered, axis=1)
    shown = np.linalg.norm(centered @ comps.T, axis=1)
    return float(np.median(shown / np.maximum(full, 1e-12)))


def _caption(fitted_on: str, basis: str, captured: float) -> str:
    """The text painted on the panel — every caveat the picture needs, in one place.

    Assembled rather than interpolated inline because each clause is conditional and the
    disclosures (what the axes can show, that the window is selected) must survive *every*
    branch: a caption that silently drops them on one code path is worse than none.
    """
    where = (
        "this infant's normal phase only"
        if fitted_on == "normal"
        else "this infant's whole calm baseline (this window opens too briefly calm to define axes)"
    )
    whitened = (
        " and whitened by the calm covariance, so on-screen distance from the cloud is the "
        "Mahalanobis novelty the model actually reports"
        if basis == "whitened"
        else ""
    )
    return (
        f"Principal components of the JEPA target-encoder embedding, fitted on {where}{whitened}. "
        f"These 3 axes carry {captured * 100:.0f}% of the departure; the rest moves in directions "
        "the screen cannot show. The trajectory's distance from the learned-normal cloud and its "
        "predictive surprise are real model outputs; the axes carry no accuracy score. This is a "
        "selected example window, not a typical one — the model's actual claim is the pooled "
        "onset-anticipation AUC across the whole cohort."
    )


def export_world_model(
    ckpt: str,
    csv_path: str,
    infant: str,
    w0: int,
    w1: int,
    normal_len: int,
    roll: int = 20,
    lo_pct: float = 50.0,
    basis: str = "raw",
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

    # --- 3-D basis, fitted on the NORMAL PHASE of the demo window only (spec §7) ---
    #
    # Two defensible bases, both label-free (neither is ever fitted on the departure):
    #
    #   "raw"      — PCA of the embeddings as they are (the default, and the spec §7 choice).
    #   "whitened" — PCA in the space the novelty read-out measures in (Mahalanobis = Euclidean
    #                after whitening by the calm covariance), so on-screen distance from the
    #                cloud centre *is* the reported statistic.
    #
    # Whitening looks like the obvious fix for the flat-looking hero and it is NOT. Measured on
    # both candidate demo windows (same checkpoint, same corrected data):
    #
    #     window          basis      sep_rise   visible_sep   novelty_captured
    #     [1240,1419]     raw          0.406       0.402            0.61
    #     [1240,1419]     whitened     0.406       0.978            0.34
    #     [2740,2919]     raw          1.312       0.207            0.64
    #     [2740,2919]     whitened     1.312       0.159            0.33
    #
    # Whitening more than doubles the visible drift on one window and *shrinks* it on the other,
    # so "it makes the demo pop" is a property of the window, not of the transform — adopting it
    # on that evidence would be fitting the basis to the example. And it consistently halves
    # ``novelty_captured``: whitening spreads the departure over more directions, so three axes
    # show less of it. Raw stays the default because it is the more faithful projection; the
    # option is kept so the comparison stays reproducible rather than folklore.
    #
    # The real lesson is in the last two rows: the window with by far the strongest true signal
    # (sep_rise 1.31) has the *weakest* visible drift (0.21). No 3-axis linear projection
    # recovers this departure — it is genuinely diffuse across the 48 dims. That is why the hero
    # drives its drama from novelty/surprise and reports ``novelty_captured`` rather than
    # pretending the dot's position carries the finding.
    normal_abs = [w0 + i for i in range(min(normal_len, n))]
    if basis == "whitened":
        mu_c, wmat = _whiten_fit(calm_embeddings)
        Zb = (Z - mu_c) @ wmat
        cloud_src_all = (calm_embeddings - mu_c) @ wmat
    else:
        Zb = Z
        cloud_src_all = calm_embeddings
    normal_embeddings = np.array([Zb[zpos[t]] for t in normal_abs])
    # A recorded window need not open calm — the recorder's own window [113,292] opens with a
    # 2-window normal phase, which cannot define three axes. Fall back to the infant's whole
    # calm cloud: still fitted with no label and never on the departure, just on a bigger
    # sample of "this infant's normal" than this particular window happens to contain.
    if len(normal_embeddings) >= MIN_BASIS_POINTS:
        basis_src, fitted_on = normal_embeddings, "normal"
    else:
        basis_src, fitted_on = cloud_src_all, "calm_cloud"
    mu, comps, var_explained = _pca_fit(basis_src)
    # How much of the departure the screen can actually show (see _captured_fraction).
    demo_centered = np.array([Zb[zpos[w0 + i]] for i in range(n)]) - mu
    captured = _captured_fraction(demo_centered, comps)

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
        emb = Zb[zpos[abs_w]]
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
    if len(cloud_src_all) > CLOUD_SAMPLE:
        pick = np.linspace(0, len(cloud_src_all) - 1, CLOUD_SAMPLE).astype(int)
        cloud_src = cloud_src_all[pick]
    else:
        cloud_src = cloud_src_all
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
            "fitted_on": fitted_on,
            "basis": basis,
            "variance_explained": [round(float(v), 4) for v in var_explained],
            # The honest number for the *picture*: the median share of each window's
            # distance-from-normal that these 3 axes carry. ``variance_explained`` describes
            # the basis; this describes how much of the departure a viewer can actually see.
            "novelty_captured": round(captured, 4),
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
        "caption": _caption(fitted_on, basis, captured),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="models/jepa/jepa.pt")
    ap.add_argument("--data", default="data/processed/all_patients_windowed.csv")
    ap.add_argument("--infant", default="infant7")
    # Demo window re-selected on the #18-corrected data (see docs/research/world-model-jepa-result.md):
    # the previous [1240, 1419] was chosen on the pre-fix stream, where it opened calm. It no longer
    # does, and its separation collapses to 0.41 calm-SD. [2740, 2919] is this infant's strongest
    # remaining departure that still opens calm — a selected case study, disclosed as such.
    ap.add_argument("--w0", type=int, default=2740)
    ap.add_argument("--w1", type=int, default=2919)
    ap.add_argument("--normal-len", type=int, default=DEFAULT_NORMAL_LEN)
    ap.add_argument("--basis", choices=("raw", "whitened"), default="raw",
                    help="raw (default) is the more faithful projection; see export_world_model")
    ap.add_argument("--out", default="dashboard/lib/world-model-infant7.json")
    args = ap.parse_args()

    block = export_world_model(
        args.ckpt, args.data, args.infant, args.w0, args.w1, args.normal_len,
        basis=args.basis,
    )
    out = REPO_ROOT / args.out
    out.write_text(json.dumps(block, indent=2) + "\n")
    print(f"wrote {out}")
    print(
        f"  n={len(block['trajectory'])}  embed_dim={block['embed_dim']}  "
        f"var_explained={block['pca']['variance_explained']}"
    )
    print(
        f"  novelty sep_rise={block['sep_rise_calm_sd']} calm-SD  basis={block['pca']['basis']}  captured={block['pca']['novelty_captured']}  "
        f"pca_visible_sep={block['pca_visible_sep']}  cloud_edge_p95={block['novelty_baseline_p95']}  "
        f"cloud_pts={len(block['normal_cloud'])}"
    )


if __name__ == "__main__":
    main()
