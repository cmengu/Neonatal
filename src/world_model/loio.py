"""Leave-one-infant-out (LOIO) validation of the Surprise signal (issue #6).

The gating question the research gate (``world-model-surprise-validation.md``) sets for
issue #6: *does Surprise rise in the lead window before the annotated bradycardia events on
held-out infants?* This module is the pure, testable core that answers it; ``scripts/
run_world_model_loio.py`` supplies the data I/O and the plot.

**What "leave-one-infant-out" means for a per-infant self-supervised model.** The models
share no weights (``forecaster.py``): each infant's ``θ_i`` is fit on that infant's stream
alone. So the contamination LOIO normally guards against — one subject's data leaking into
another's fit — *cannot happen here by construction*. What LOIO still buys, and what we
report, is that **no infant informs another's score or any shared decision threshold**:
each infant's Surprise is standardised against *its own* baseline, and the pooled AUC is a
held-out aggregate in which every infant is scored only by its own model. Hyper-parameters
(``lead``/``guard`` window counts) are fixed a priori from the gate (Gee 2016 ~80–116 s
lead), never tuned on the infants they are tested on.

**The test.** For each infant we label every window's *role* relative to its bradycardia
annotations:

- **lead** — the ``lead`` windows immediately *before* an event onset (the pre-event lead
  window Surprise should rise in);
- **baseline** — windows far (``guard``) from any event (the calm reference);
- everything else (the event windows themselves, and the ``guard`` neighbourhood) is
  excluded from the discrimination so we measure *anticipation*, not *coincidence*.

Surprise's ability to separate lead from baseline is summarised by the AUC (Mann–Whitney).
We also report the per-event **lead time** — how many windows before onset Surprise first
rises above the infant's own baseline — and a peri-event trace for the plot.

**Bradycardia viability ≠ sepsis validation** (gate §3): passing this licenses "the
per-infant model carries lead-time signal on our own data", not "Surprise detects sepsis".
Pure numpy; no I/O.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# A priori hyper-parameters, fixed from the research gate — NOT tuned on the test infants.
# ``lead`` windows before an onset are the pre-event window Surprise should rise in; Gee
# 2016 anticipates bradycardia ~80–116 s ahead, and the beat-based windows are ~tens of
# seconds each, so a handful of windows spans that horizon. ``guard`` keeps baseline
# windows clear of any event neighbourhood so we measure anticipation, not the event itself.
DEFAULT_LEAD = 5
DEFAULT_GUARD = 30
# SD above the infant's own baseline mean at which Surprise counts as "risen", for the
# per-event lead-time measurement. 2 SD ≈ the conventional excursion threshold.
DEFAULT_RISE_SD = 2.0


def event_onsets(labels: np.ndarray) -> np.ndarray:
    """Indices where a bradycardia event *begins* (a 0→1 transition, or an initial 1).

    The PICS annotations flag each event as an isolated window, but we treat it as a run
    boundary so the test is robust if a future stream marks multi-window events.
    """
    labels = np.asarray(labels).astype(int)
    if labels.size == 0:
        return np.array([], dtype=int)
    prev = np.concatenate([[0], labels[:-1]])
    return np.flatnonzero((labels == 1) & (prev == 0))


def window_roles(
    labels: np.ndarray, lead: int = DEFAULT_LEAD, guard: int = DEFAULT_GUARD
) -> tuple[np.ndarray, np.ndarray]:
    """Classify every window as lead / baseline (booleans), given the event labels.

    - *lead*: the ``lead`` windows immediately before an onset, provided they are not
      themselves labelled events.
    - *baseline*: windows at least ``guard`` away from *every* onset (before or after) and
      not labelled — the calm reference. ``guard >= lead`` so lead and baseline never
      overlap.
    Windows that are neither (event windows, and the guard neighbourhood) are excluded.
    """
    labels = np.asarray(labels).astype(int)
    n = labels.size
    onsets = event_onsets(labels)

    is_lead = np.zeros(n, dtype=bool)
    for o in onsets:
        lo = max(0, o - lead)
        is_lead[lo:o] = True
    is_lead &= labels == 0  # never call an event window a lead window

    near_event = np.zeros(n, dtype=bool)
    for o in onsets:
        lo = max(0, o - guard)
        hi = min(n, o + guard + 1)
        near_event[lo:hi] = True
    is_baseline = (~near_event) & (labels == 0)

    return is_lead, is_baseline


def auc(pos: np.ndarray, neg: np.ndarray) -> float:
    """AUC of positives over negatives via the Mann–Whitney U statistic (rank-based).

    Returns 0.5 for no separation, 1.0 if every positive outranks every negative. NaN if
    either group is empty. Ties contribute 0.5, matching the trapezoidal ROC AUC.
    """
    pos = np.asarray(pos, dtype=float)
    neg = np.asarray(neg, dtype=float)
    pos = pos[np.isfinite(pos)]
    neg = neg[np.isfinite(neg)]
    if pos.size == 0 or neg.size == 0:
        return float("nan")
    all_vals = np.concatenate([pos, neg])
    ranks = _rankdata(all_vals)
    rank_pos_sum = ranks[: pos.size].sum()
    u = rank_pos_sum - pos.size * (pos.size + 1) / 2.0
    return float(u / (pos.size * neg.size))


def _rankdata(a: np.ndarray) -> np.ndarray:
    """Average ranks (1-based), ties averaged — a dependency-free ``scipy.stats.rankdata``."""
    a = np.asarray(a, dtype=float)
    order = np.argsort(a, kind="mergesort")
    ranks = np.empty(a.size, dtype=float)
    sorted_a = a[order]
    i = 0
    while i < a.size:
        j = i
        while j + 1 < a.size and sorted_a[j + 1] == sorted_a[i]:
            j += 1
        avg = (i + j) / 2.0 + 1.0  # 1-based average rank for the tie block
        ranks[order[i : j + 1]] = avg
        i = j + 1
    return ranks


def lead_times(
    surprise: np.ndarray,
    labels: np.ndarray,
    baseline_mean: float,
    baseline_std: float,
    lookback: int = DEFAULT_GUARD,
    rise_sd: float = DEFAULT_RISE_SD,
) -> list[int]:
    """Per-event lead time (in windows) — how far before onset Surprise first rises.

    For each onset, scan back up to ``lookback`` windows and return the earliest contiguous
    window (counting back from the onset) at which Surprise exceeds
    ``baseline_mean + rise_sd·baseline_std``. Events with no pre-onset rise contribute
    nothing (an honest miss, not a zero). Returned in windows; the caller converts to
    seconds with the per-infant window hop.
    """
    surprise = np.asarray(surprise, dtype=float)
    threshold = baseline_mean + rise_sd * baseline_std
    out: list[int] = []
    for o in event_onsets(labels):
        lead = 0
        for back in range(1, lookback + 1):
            idx = o - back
            if idx < 0 or not np.isfinite(surprise[idx]):
                break
            if surprise[idx] > threshold:
                lead = back
            else:
                break  # only count the *contiguous* run of elevation before onset
        if lead > 0:
            out.append(lead)
    return out


@dataclass(frozen=True)
class InfantResult:
    """One held-out infant's LOIO result."""

    patient_id: str
    auc: float
    n_lead: int
    n_baseline: int
    n_events: int
    baseline_mean: float
    baseline_std: float
    # within-infant-standardised surprise for the two groups (for pooling across infants)
    lead_z: np.ndarray
    baseline_z: np.ndarray
    lead_time_windows: list[int]


def evaluate_infant(
    patient_id: str,
    surprise: np.ndarray,
    labels: np.ndarray,
    lead: int = DEFAULT_LEAD,
    guard: int = DEFAULT_GUARD,
    rise_sd: float = DEFAULT_RISE_SD,
) -> InfantResult:
    """Score one infant: fit-free — takes its precomputed Surprise stream + labels.

    Standardises Surprise against the infant's *own* baseline (mean/SD over baseline
    windows) so per-infant scores are comparable when pooled, then computes the lead-vs-
    baseline AUC and the per-event lead times.
    """
    surprise = np.asarray(surprise, dtype=float)
    labels = np.asarray(labels).astype(int)
    is_lead, is_baseline = window_roles(labels, lead=lead, guard=guard)

    base_vals = surprise[is_baseline]
    base_vals = base_vals[np.isfinite(base_vals)]
    base_mean = float(np.mean(base_vals)) if base_vals.size else 0.0
    base_std = float(np.std(base_vals)) if base_vals.size else 1.0
    if base_std == 0.0:
        base_std = 1.0

    lead_vals = surprise[is_lead]
    lead_vals = lead_vals[np.isfinite(lead_vals)]

    a = auc(lead_vals, base_vals)
    lead_z = (lead_vals - base_mean) / base_std
    baseline_z = (base_vals - base_mean) / base_std

    return InfantResult(
        patient_id=patient_id,
        auc=a,
        n_lead=int(lead_vals.size),
        n_baseline=int(base_vals.size),
        n_events=int(event_onsets(labels).size),
        baseline_mean=base_mean,
        baseline_std=base_std,
        lead_z=lead_z,
        baseline_z=baseline_z,
        lead_time_windows=lead_times(
            surprise, labels, base_mean, base_std, lookback=guard, rise_sd=rise_sd
        ),
    )


@dataclass(frozen=True)
class LoioSummary:
    """The pooled, held-out headline the ticket asks for — the number."""

    pooled_auc: float
    mean_infant_auc: float
    median_infant_auc: float
    n_infants: int
    total_events: int
    total_lead_windows: int
    total_baseline_windows: int
    lead_time_windows: list[int]
    per_infant: list[InfantResult]


def summarise(results: list[InfantResult]) -> LoioSummary:
    """Pool per-infant results into the LOIO headline.

    ``pooled_auc`` concatenates every infant's within-infant-standardised lead and baseline
    Surprise and takes one AUC — a held-out aggregate (each infant scored only by its own
    model, standardised to its own baseline). ``mean/median_infant_auc`` summarise the
    distribution of per-infant AUCs so a single infant cannot dominate the headline.
    """
    valid = [r for r in results if np.isfinite(r.auc)]
    pooled_lead = np.concatenate([r.lead_z for r in results]) if results else np.array([])
    pooled_base = (
        np.concatenate([r.baseline_z for r in results]) if results else np.array([])
    )
    infant_aucs = np.array([r.auc for r in valid], dtype=float)
    all_lead_times = [w for r in results for w in r.lead_time_windows]
    return LoioSummary(
        pooled_auc=auc(pooled_lead, pooled_base),
        mean_infant_auc=float(np.mean(infant_aucs)) if infant_aucs.size else float("nan"),
        median_infant_auc=float(np.median(infant_aucs)) if infant_aucs.size else float("nan"),
        n_infants=len(results),
        total_events=sum(r.n_events for r in results),
        total_lead_windows=sum(r.n_lead for r in results),
        total_baseline_windows=sum(r.n_baseline for r in results),
        lead_time_windows=all_lead_times,
        per_infant=results,
    )


def peri_event_trace(
    surprise: np.ndarray,
    labels: np.ndarray,
    baseline_mean: float,
    baseline_std: float,
    half: int = DEFAULT_GUARD,
) -> np.ndarray:
    """Mean within-infant-standardised Surprise in a ``[-half, +half]`` window around each
    onset, for the peri-event plot. Returns a length-``2·half+1`` array (index ``half`` =
    onset); positions with no data are ``nan``.
    """
    surprise = np.asarray(surprise, dtype=float)
    z = (surprise - baseline_mean) / (baseline_std or 1.0)
    n = z.size
    width = 2 * half + 1
    acc = np.full((0, width), np.nan)
    rows = []
    for o in event_onsets(labels):
        seg = np.full(width, np.nan)
        for k in range(-half, half + 1):
            idx = o + k
            if 0 <= idx < n:
                seg[k + half] = z[idx]
        rows.append(seg)
    if rows:
        acc = np.vstack(rows)
    return np.nanmean(acc, axis=0) if acc.size else np.full(width, np.nan)
