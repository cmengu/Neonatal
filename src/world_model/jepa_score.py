"""Honest scorecard for the JEPA world model (map #56, ticket #58).

Two families of number, both designed to be **non-circular** and reproducible — the honesty
bar (owner's instruction) forbids overfitting-to-look-good, so every "deterioration" label
here comes from a signal the JEPA never sees at train time, not from the JEPA's own output.

**Ground truth for "departure from normal" is independent of the model.** We use the raw
personalised-deviation magnitude ``||x_dev||`` (the same physiological-departure notion Tier 1's
floor triggers and Tier 2's CUSUM half act on) — a rolling excursion of that signal marks a
*sustained* departure. Whether the JEPA's *learned* embedding-novelty and *predictive surprise*
rise on those independently-marked episodes is then a fair question, not a tautology.

Metrics:

- ``window_separation`` — the **demo metric**. On one infant + window, how far (in baseline-SD)
  the embedding drifts from its own first-third baseline cloud, and whether surprise rises.
  Reproduces the handoff's §2 table.
- ``departure_auc`` — the **cohort metric**. Per infant, standardised to its own calm baseline
  and pooled held-out: AUC of JEPA surprise / embedding-novelty separating sustained-departure
  windows from calm windows. Reported next to the VAR(1) baseline on the *identical* protocol,
  so "the learned model beats / matches the linear one" is an apples-to-apples claim.

Batched on MPS/CPU. Pure inference — loads a checkpoint, never trains.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch

from src.world_model.jepa import JEPA, load_checkpoint
from src.world_model.jepa_data import FEATURES, load_infant_sequences


# ----------------------------------------------------------------------------------------
# Independent (model-blind) deterioration signal
# ----------------------------------------------------------------------------------------
def deviation_magnitude(x: np.ndarray, roll: int = 20) -> np.ndarray:
    """Rolling mean of the personalised-deviation magnitude ``||x_dev||`` — the model-blind
    "how far is this infant from its own normal" signal Tier 1/CUSUM already trust.

    ``x`` is ``(T, F)`` personalised-deviation features. Returns ``(T,)``.
    """
    mag = np.sqrt(np.mean(np.square(x), axis=1))
    if roll <= 1:
        return mag
    k = np.ones(roll) / roll
    return np.convolve(mag, k, mode="same")


def departure_calm_masks(
    x: np.ndarray, roll: int = 20, hi_pct: float = 85.0, lo_pct: float = 50.0
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Split windows into *departure* (rolling ``||x_dev||`` above ``hi_pct``) and *calm*
    (below ``lo_pct``) by this infant's own percentiles. Returns ``(departure, calm, d)``.
    """
    d = deviation_magnitude(x, roll=roll)
    hi = np.percentile(d, hi_pct)
    lo = np.percentile(d, lo_pct)
    return d >= hi, d <= lo, d


# ----------------------------------------------------------------------------------------
# JEPA inference streams (batched)
# ----------------------------------------------------------------------------------------
@torch.no_grad()
def embed_stream(model: JEPA, x: np.ndarray, device: torch.device, ctx: int | None = None,
                 batch: int = 512) -> tuple[np.ndarray, np.ndarray]:
    """Per-window embedding of the state ending at each ``t``.

    For every ``t`` we encode the block ``x[t-ctx+1 : t+1]`` and take the last token's
    embedding from the stable target encoder. ``ctx`` defaults to ``seq_len`` to match the
    handoff's §2 reproduction. Returns ``(t_index (N,), embeddings (N, D))``.
    """
    cfg = model.cfg
    ctx = ctx or cfg.seq_len
    xt = torch.tensor(x, dtype=torch.float32)
    T = xt.shape[0]
    ts = np.arange(ctx - 1, T)
    blocks = torch.stack([xt[t - ctx + 1 : t + 1] for t in ts])  # (N, ctx, F)
    out = []
    for i in range(0, len(blocks), batch):
        b = blocks[i : i + batch].to(device)
        z = model.encode(b)[:, -1, :]  # (b, D)
        out.append(z.cpu().numpy())
    return ts, np.concatenate(out, axis=0)


@torch.no_grad()
def surprise_stream(model: JEPA, x: np.ndarray, device: torch.device,
                    batch: int = 512, horizon: bool = False) -> tuple[np.ndarray, np.ndarray]:
    """Per-window JEPA surprise (predicted-vs-true latent error).

    ``horizon=False`` → single +1-step error ``predict_surprise(x[t-Lc:t], x[t])``.
    ``horizon=True``  → error aggregated over the full ``H``-window horizon
    ``surprise_horizon(x[t-Lc:t], x[t:t+H])`` (method #4 — anticipates regime change).
    Returns ``(t_index (N,), surprise (N,))``.
    """
    cfg = model.cfg
    Lc, H = cfg.context_len, cfg.horizon
    xt = torch.tensor(x, dtype=torch.float32)
    T = xt.shape[0]
    hi = T - H if horizon else T
    ts = np.arange(Lc, hi)
    ctxs = torch.stack([xt[t - Lc : t] for t in ts])       # (N, Lc, F)
    if horizon:
        futs = torch.stack([xt[t : t + H] for t in ts])    # (N, H, F)
    else:
        futs = torch.stack([xt[t : t + 1] for t in ts])    # (N, 1, F)
    out = []
    for i in range(0, len(ctxs), batch):
        c = ctxs[i : i + batch].to(device)
        n = futs[i : i + batch].to(device)
        s = model.surprise_horizon(c, n) if horizon else model.predict_surprise(c, n)
        out.append(s.cpu().numpy())
    return ts, np.concatenate(out, axis=0)


def novelty_from_embeddings(z: np.ndarray, baseline: np.ndarray, whiten: bool = True) -> np.ndarray:
    """Per-window novelty = distance of each embedding from a *baseline* latent cloud.

    ``whiten=True`` → Mahalanobis against the baseline covariance (per-infant whitening,
    handoff method #2); else per-dim z-distance. ``baseline`` is ``(M, D)`` calm embeddings.
    """
    mu = baseline.mean(0)
    if whiten:
        cov = np.cov(baseline, rowvar=False) + 1e-3 * np.eye(baseline.shape[1])
        prec = np.linalg.inv(cov)
        diff = z - mu
        return np.sqrt(np.einsum("nd,de,ne->n", diff, prec, diff) / z.shape[1])
    sd = baseline.std(0) + 1e-6
    return np.sqrt(np.mean(((z - mu) / sd) ** 2, axis=1))


# ----------------------------------------------------------------------------------------
# Metric A — demo-window separation (reproduces handoff §2)
# ----------------------------------------------------------------------------------------
@dataclass
class WindowScore:
    infant: str
    w0: int
    w1: int
    sep_rise: float           # median(last third) − median(first third) of novelty, in baseline SD
    sep_max: float            # peak novelty in the window
    surprise_rise: float
    dev_rise: float           # independent ground-truth: rise in raw ||x_dev|| (grounds "deterioration")


def window_separation(model: JEPA, x: np.ndarray, w0: int, w1: int, device: torch.device,
                      infant: str = "?", whiten: bool = False) -> WindowScore:
    """Embedding-separation on ``[w0, w1]`` vs that window's own first-third baseline."""
    ts_z, Z = embed_stream(model, x, device)
    ts_s, S = surprise_stream(model, x, device)
    zpos = {int(t): i for i, t in enumerate(ts_z)}
    spos = {int(t): i for i, t in enumerate(ts_s)}
    idx = [t for t in range(w0, w1 + 1) if t in zpos and t in spos]
    z = np.array([Z[zpos[t]] for t in idx])
    s = np.array([S[spos[t]] for t in idx])
    third = max(1, len(z) // 3)
    nov = novelty_from_embeddings(z, z[:third], whiten=whiten)
    dev = deviation_magnitude(x, roll=20)[np.array(idx)]
    return WindowScore(
        infant=infant, w0=w0, w1=w1,
        sep_rise=float(np.median(nov[-third:]) - np.median(nov[:third])),
        sep_max=float(nov.max()),
        surprise_rise=float(np.median(s[-third:]) - np.median(s[:third])),
        dev_rise=float(np.median(dev[-third:]) - np.median(dev[:third])),
    )


@dataclass
class DemoTrajectory:
    """The honest "leaves the cloud" trajectory for one infant window (for #60 export + demo)."""

    infant: str
    w0: int
    w1: int
    t: np.ndarray            # window indices
    novelty: np.ndarray      # per-window Mahalanobis distance from the infant's FULL calm cloud
    surprise: np.ndarray     # per-window horizon-aggregated JEPA surprise (z vs calm)
    dev: np.ndarray          # independent ground-truth ||x_dev|| (grounds "deterioration")
    baseline_p95: float      # 95th-pct novelty over the infant's calm windows (the "cloud edge")
    sep_rise: float          # median(last third) − median(first third), in calm-SD units


def demo_trajectory(model: JEPA, x: np.ndarray, w0: int, w1: int, device: torch.device,
                    infant: str = "?", roll: int = 20, lo_pct: float = 50.0) -> DemoTrajectory:
    """Novelty/surprise trajectory across ``[w0, w1]`` vs the infant's **full calm baseline**.

    Unlike ``window_separation`` (which whitens against the window's own 60-window first third —
    small-sample Mahalanobis inflates that), the baseline here is *every* calm window in the
    record (rolling ``||x_dev||`` below ``lo_pct``), so the covariance is well-estimated and the
    "how far outside this infant's normal cloud" number is honest.
    """
    ts_z, Z = embed_stream(model, x, device)
    ts_s, S = surprise_stream(model, x, device, horizon=True)
    _, calm, dev_full = departure_calm_masks(x, roll=roll, lo_pct=lo_pct)

    calm_z = Z[np.array([i for i, t in enumerate(ts_z) if calm[t]])]
    nov_all = novelty_from_embeddings(Z, calm_z, whiten=True)         # over all t in ts_z
    calm_nov = nov_all[np.array([i for i, t in enumerate(ts_z) if calm[t]])]
    baseline_p95 = float(np.percentile(calm_nov, 95))

    # standardise surprise to calm
    calm_s = S[np.array([i for i, t in enumerate(ts_s) if calm[t]])]
    s_mu, s_sd = float(calm_s.mean()), float(calm_s.std() + 1e-9)

    zpos = {int(t): i for i, t in enumerate(ts_z)}
    spos = {int(t): i for i, t in enumerate(ts_s)}
    idx = [t for t in range(w0, w1 + 1) if t in zpos and t in spos]
    nov = np.array([nov_all[zpos[t]] for t in idx])
    surp = np.array([(S[spos[t]] - s_mu) / s_sd for t in idx])
    dev = dev_full[np.array(idx)]
    third = max(1, len(nov) // 3)
    calm_sd = float(calm_nov.std() + 1e-9)
    sep_rise = float((np.median(nov[-third:]) - np.median(nov[:third])) / calm_sd)
    return DemoTrajectory(infant, w0, w1, np.array(idx), nov, surp, dev, baseline_p95, sep_rise)


# ----------------------------------------------------------------------------------------
# Metric C — cohort departure-vs-calm AUC (held-out, non-circular), JEPA vs VAR
# ----------------------------------------------------------------------------------------
def _auc(pos: np.ndarray, neg: np.ndarray) -> float:
    pos = pos[np.isfinite(pos)]; neg = neg[np.isfinite(neg)]
    if pos.size == 0 or neg.size == 0:
        return float("nan")
    allv = np.concatenate([pos, neg])
    order = np.argsort(allv, kind="mergesort")
    ranks = np.empty(allv.size); ranks[order] = np.arange(1, allv.size + 1)
    # average ties
    _, inv, cnt = np.unique(allv, return_inverse=True, return_counts=True)
    csum = np.cumsum(cnt); starts = csum - cnt
    avg = (starts + csum + 1) / 2.0
    ranks = avg[inv]
    u = ranks[: pos.size].sum() - pos.size * (pos.size + 1) / 2.0
    return float(u / (pos.size * neg.size))


@dataclass
class DepartureResult:
    pooled_auc_surprise: float
    pooled_auc_novelty: float
    pooled_auc_var: float
    per_infant: dict


def departure_auc(model: JEPA, csv_path: str, device: torch.device,
                  roll: int = 20, hi_pct: float = 85.0, lo_pct: float = 50.0,
                  whiten: bool = True, surp_horizon: bool = False) -> DepartureResult:
    """Held-out AUC: does JEPA surprise / embedding-novelty separate *sustained-departure*
    windows (top-``hi_pct`` rolling ``||x_dev||``) from *calm* windows (bottom-``lo_pct``)?

    Standardised per infant to its own calm windows, then pooled. The VAR(1) forecaster is
    scored on the identical split as the honest linear reference.
    """
    from src.world_model.forecaster import FORECAST_FEATURES, PerInfantForecaster

    seqs, _ = load_infant_sequences(csv_path)
    var = PerInfantForecaster()
    fidx = [FEATURES.index(f) for f in FORECAST_FEATURES]  # VAR uses a subset of the columns

    p_surp, n_surp, p_nov, n_nov, p_var, n_var = ([] for _ in range(6))
    per = {}
    for infant, x in seqs.items():
        dep, calm, _ = departure_calm_masks(x, roll=roll, hi_pct=hi_pct, lo_pct=lo_pct)

        ts_s, S = surprise_stream(model, x, device, horizon=surp_horizon)
        ts_z, Z = embed_stream(model, x, device)
        # VAR surprise on its feature subset
        vparams = var.fit(x[:, fidx])
        Vs = var.surprise_stream(vparams, x[:, fidx])

        def split(stream_ts, stream_vals):
            pos_i = np.array([i for i, t in enumerate(stream_ts) if dep[t]])
            neg_i = np.array([i for i, t in enumerate(stream_ts) if calm[t]])
            pv = stream_vals[pos_i] if pos_i.size else np.array([])
            nv = stream_vals[neg_i] if neg_i.size else np.array([])
            # nan-safe standardisation: the VAR stream carries a nan at index 0 (no
            # predecessor); plain mean/std would nan-poison the whole infant.
            finite = nv[np.isfinite(nv)]
            m, sd = (finite.mean(), finite.std() + 1e-9) if finite.size else (0.0, 1.0)
            return (pv - m) / sd, (nv - m) / sd

        calm_idx_z = np.array([i for i, t in enumerate(ts_z) if calm[t]])
        nov = novelty_from_embeddings(Z, Z[calm_idx_z], whiten=whiten)

        sp, sn = split(ts_s, S)
        np_, nn = split(ts_z, nov)
        # VAR stream is length T with nan at 0; align by window index
        var_ts = np.arange(len(x))
        vp, vn = split(var_ts, Vs)

        p_surp.append(sp); n_surp.append(sn)
        p_nov.append(np_); n_nov.append(nn)
        p_var.append(vp); n_var.append(vn)
        per[infant] = {
            "auc_surprise": _auc(sp, sn),
            "auc_novelty": _auc(np_, nn),
            "auc_var": _auc(vp, vn),
            "n_departure": int(dep.sum()), "n_calm": int(calm.sum()),
        }

    cat = lambda L: np.concatenate([a for a in L if a.size])
    return DepartureResult(
        pooled_auc_surprise=_auc(cat(p_surp), cat(n_surp)),
        pooled_auc_novelty=_auc(cat(p_nov), cat(n_nov)),
        pooled_auc_var=_auc(cat(p_var), cat(n_var)),
        per_infant=per,
    )


def onset_anticipation_auc(model: JEPA, csv_path: str, device: torch.device,
                           roll: int = 20, hi_pct: float = 85.0,
                           lead: int = 5, guard: int = 30, whiten: bool = True,
                           surp_horizon: bool = True) -> dict:
    """The **anticipation** metric — the non-circular, temporal claim a world model earns.

    Ground truth is honest and in-repo: a *departure onset* = the rolling ``||x_dev||`` signal
    (which the JEPA never sees as a label) crossing its ``hi_pct`` percentile from below. We
    then reuse the *validated* ``loio.py`` machinery (window roles, Mann–Whitney AUC, per-infant
    standardisation, pooling) to ask: does JEPA novelty / surprise rise in the ``lead`` windows
    **before** an onset, vs calm baseline? This sidesteps the #18 brady-label confound entirely
    and tests lead-time, not just concurrent level.
    """
    from src.world_model.loio import evaluate_infant, summarise

    seqs, _ = load_infant_sequences(csv_path)
    res_nov, res_surp = [], []
    for infant, x in seqs.items():
        d = deviation_magnitude(x, roll=roll)
        above = (d >= np.percentile(d, hi_pct)).astype(int)
        onset_labels = np.zeros(len(x), dtype=int)
        onsets = np.flatnonzero((above == 1) & (np.concatenate([[0], above[:-1]]) == 0))
        onset_labels[onsets] = 1

        ts_z, Z = embed_stream(model, x, device)
        ts_s, S = surprise_stream(model, x, device, horizon=surp_horizon)
        calm = d <= np.percentile(d, 50.0)
        nov = novelty_from_embeddings(Z, Z[np.array([i for i, t in enumerate(ts_z) if calm[t]])],
                                      whiten=whiten)
        # pad streams to length T aligned by window index (nan where undefined)
        nov_full = np.full(len(x), np.nan); nov_full[ts_z] = nov
        surp_full = np.full(len(x), np.nan); surp_full[ts_s] = S
        res_nov.append(evaluate_infant(infant, nov_full, onset_labels, lead=lead, guard=guard))
        res_surp.append(evaluate_infant(infant, surp_full, onset_labels, lead=lead, guard=guard))

    sn, ss = summarise(res_nov), summarise(res_surp)
    return {
        "novelty_pooled_auc": round(sn.pooled_auc, 3),
        "novelty_median_infant_auc": round(sn.median_infant_auc, 3),
        "surprise_pooled_auc": round(ss.pooled_auc, 3),
        "surprise_median_infant_auc": round(ss.median_infant_auc, 3),
        "total_onsets": sn.total_events,
        "lead": lead, "guard": guard,
    }


def pick_device() -> torch.device:
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="models/jepa/jepa.pt")
    ap.add_argument("--data", default="data/processed/all_patients_windowed.csv")
    ap.add_argument("--infant", default="infant7")
    ap.add_argument("--windows", default="1240:1419,2098:2277,113:292")
    ap.add_argument("--whiten", action="store_true", help="Mahalanobis novelty (per-infant whitening)")
    ap.add_argument("--surp-horizon", action="store_true", help="horizon-aggregated surprise (method #4)")
    args = ap.parse_args()

    device = pick_device()
    model = load_checkpoint(args.ckpt).to(device)
    model.eval()
    seqs, _ = load_infant_sequences(args.data)

    print(f"# scorecard  ckpt={args.ckpt}  device={device}  whiten={args.whiten}")
    print(f"# cfg: D={model.cfg.embed_dim} Lc={model.cfg.context_len} H={model.cfg.horizon}\n")

    print("== Metric A — demo-window embedding separation ==")
    print(f"{'infant':8} {'window':13} {'sep_rise':>9} {'sep_max':>8} {'surp_rise':>10} {'dev_rise':>9}")
    x = seqs[args.infant]
    for spec in args.windows.split(","):
        w0, w1 = (int(v) for v in spec.split(":"))
        r = window_separation(model, x, w0, w1, device, infant=args.infant, whiten=args.whiten)
        print(f"{r.infant:8} [{r.w0:4d},{r.w1:4d}] {r.sep_rise:9.3f} {r.sep_max:8.3f} "
              f"{r.surprise_rise:10.4f} {r.dev_rise:9.3f}")

    print("\n== Metric C — cohort departure-vs-calm AUC (held-out, JEPA vs VAR) ==")
    dr = departure_auc(model, args.data, device, whiten=args.whiten, surp_horizon=args.surp_horizon)
    print(f"pooled AUC  surprise={dr.pooled_auc_surprise:.3f}  novelty={dr.pooled_auc_novelty:.3f}  "
          f"VAR(baseline)={dr.pooled_auc_var:.3f}")
    aucs_s = np.array([v["auc_surprise"] for v in dr.per_infant.values()])
    aucs_n = np.array([v["auc_novelty"] for v in dr.per_infant.values()])
    aucs_v = np.array([v["auc_var"] for v in dr.per_infant.values()])
    print(f"mean per-infant  surprise={np.nanmean(aucs_s):.3f}  novelty={np.nanmean(aucs_n):.3f}  "
          f"VAR={np.nanmean(aucs_v):.3f}")


if __name__ == "__main__":
    main()
