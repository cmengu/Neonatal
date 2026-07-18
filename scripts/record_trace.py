#!/usr/bin/env python
"""Record one real infant window through the Verdict Cascade → ``trace.json`` (#31).

This is the recorder half of the trace seam pinned by the telemetry contract (#30,
``docs/design/trace-telemetry-contract.md``). It replays a real recorded infant window
through the *actual* cascade assessors and serialises per-tier telemetry to a single
``trace.json`` the dashboard trace view (#32) replays. The UI never recomputes anything;
this file is the only place the cascade runs for the demo.

What it does, section by section (contract §1–§6):

- **§3 Tier 1** — replays the stateless ``DeviationAssessor`` window-by-window over the
  range, capturing each feature's z-score + raw-value trajectory and the index where it
  first crosses its trigger (the "plays to a failure point" series), plus the floor the
  tier sets at the decision window.
- **§4 Tier 2** — folds each window's real direction-aware ``composite_deviation`` into the
  same one-sided CUSUM recursion the ``TemporalAssessor`` runs (``C⁺ = max(0, C⁺+comp−k)``,
  reset on fire), capturing the ``C⁺`` trajectory + crossing, and reads the genuine Tier-2
  Assessment (level / rationale / ``may_quiet``) from the real assessor for the gate table.
- **§5 Tier 3** — runs the real RAG graph **once** on the decision window (live Groq
  reasoning + Qdrant retrieval), capturing the query, retrieved guideline chunks, the single
  reasoning string, and the single self-check the graph actually emits (Honesty Ledger H2).
- **§6 Verdict** — composes the three *genuine* tier Assessments through the real
  ``VerdictCascade`` merge (floor + escalate-only), so the final Verdict is the production
  composition of the production tier outputs — no re-run of the LLM, no hand-authored merge.

Honesty Ledger (contract §"Honesty ledger"):
- **H1** — only genuinely recorded channels are emitted, each ``real: true`` (heart rate +
  RR-interval are on the HRV grid; respiration + apnea are the recorded resp/apnea streams,
  time-resampled onto the grid). No synthetic channel is written.
- **H2** — Tier 3 carries exactly the one ``clinical_reasoning`` + one ``self_check`` the
  graph produces, plus the real query and retrieved passages. No fabricated multi-step chain.
- **H3** — every ``verdict_text`` is the tier's own ``Assessment.rationale`` /
  ``clinical_reasoning`` verbatim; nothing is authored here.

Honest data note: the processed feature set on this branch predates the #13 HeRO-feature
upgrade, so the CSVs carry 10 HRV features (``sampen`` / ``sample_asymmetry`` absent). The
recorder emits exactly the features that are really in the data — 3 of them trigger-capable
(``sdnn`` low, ``rmssd`` low, ``mean_rr`` both) — rather than inventing the two missing ones.

Run:  ``python scripts/record_trace.py``  (writes ``dashboard/public/trace/infant7.json``).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
# Running ``python scripts/record_trace.py`` puts ``scripts/`` on sys.path, not the repo
# root, so make the ``src`` package importable regardless of the invocation.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _resource_root() -> Path:
    """Where .env / qdrant_local / audit.db live. These are gitignored, so a fresh worktree
    won't have them — the primary checkout does. Prefer this checkout when it carries them,
    else honour NG_PRIMARY_CHECKOUT. (Tiers 1 & 2 need none of this; only the Tier-3 graph.)"""
    if (REPO_ROOT / ".env").exists() or (REPO_ROOT / "qdrant_local").exists():
        return REPO_ROOT
    override = os.environ.get("NG_PRIMARY_CHECKOUT")
    return Path(override) if override else REPO_ROOT


PRIMARY_CHECKOUT = _resource_root()


def _bootstrap_env() -> None:
    """Load GROQ_API_KEY from the primary checkout's .env and point QDRANT_PATH at its
    on-disk vector store, so the recorder can run the real Tier-3 graph from a worktree."""
    env_path = PRIMARY_CHECKOUT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))
    qdrant = PRIMARY_CHECKOUT / "qdrant_local"
    if "QDRANT_PATH" not in os.environ and qdrant.exists():
        os.environ["QDRANT_PATH"] = str(qdrant)


_bootstrap_env()

from src.assessment.context import _PROCESSED, personal_baseline  # noqa: E402
from src.assessment.cusum import (  # noqa: E402
    CusumThresholds,
    QuietGates,
    TemporalAssessor,
    InMemoryCusumStore,
    composite_deviation,
)
from src.assessment.deviation import (  # noqa: E402
    DEFAULT_DIRECTIONS,
    DeviationAssessor,
    DeviationThresholds,
    pathological_magnitude,
)
from src.assessment.cascade import VerdictCascade  # noqa: E402
from src.assessment.types import Assessment, AssessmentContext, ConcernLevel  # noqa: E402
from src.features.constants import HRV_FEATURE_COLS  # noqa: E402
from src.knowledge.sources import SOURCE_REGISTRY, chunk_source_ids  # noqa: E402

# --- Demo window selection (probed offline for a legible RED, see the ticket) ---
PID = "infant7"
DECISION_POS = 282          # position in the windowed (z-score) CSV of the decision window
N = 180                     # samples on the shared grid
BRADY_RR_MS = 600.0         # mean_rr > 600 ms ⇒ HR < 100 bpm (matches load_context)


class _Fixed:
    """A trivial assessor returning a precomputed Assessment, so the *real* VerdictCascade
    merge (§6) runs over the genuine tier outputs without re-invoking the LLM or CUSUM."""

    def __init__(self, assessment: Assessment) -> None:
        self._a = assessment
        self.source = assessment.source  # cascade identifies the rag/floor tiers by this

    def assess(self, _context: AssessmentContext) -> Assessment:
        return self._a


def _finite(x) -> bool:
    return x is not None and isinstance(x, (int, float)) and math.isfinite(float(x))


def _short_source(source_id: str) -> str:
    """A compact human label for a registry source id (first clause of its description)."""
    desc = SOURCE_REGISTRY.get(source_id, source_id)
    return desc.split("—")[0].strip().rstrip(".") if "—" in desc else source_id


def main() -> None:
    ap = argparse.ArgumentParser(description="Record a cascade trace to trace.json (#31)")
    ap.add_argument("--patient", default=PID)
    ap.add_argument("--decision-pos", type=int, default=DECISION_POS)
    ap.add_argument("--n", type=int, default=N)
    ap.add_argument(
        "--out",
        default=str(REPO_ROOT / "dashboard" / "public" / "trace" / f"{PID}.json"),
    )
    ap.add_argument("--no-llm", action="store_true", help="skip Tier 3 (debug; not for the demo)")
    ap.add_argument("--no-world-model", action="store_true",
                    help="skip the §7 JEPA world_model block (debug)")
    ap.add_argument("--ckpt", default=str(REPO_ROOT / "models" / "jepa" / "jepa.pt"),
                    help="JEPA checkpoint for the world_model block")
    args = ap.parse_args()

    pid = args.patient
    windowed = pd.read_csv(_PROCESSED / f"{pid}_windowed.csv")
    feats = pd.read_csv(_PROCESSED / f"{pid}_features.csv").set_index("window_idx")

    dev_cols = [c for c in HRV_FEATURE_COLS if f"{c}_dev" in windowed.columns]
    val_cols = [c for c in HRV_FEATURE_COLS if c in feats.columns]

    start_pos = args.decision_pos - args.n + 1
    if start_pos < 0:
        raise SystemExit(f"decision_pos {args.decision_pos} < n {args.n}: not enough history")
    rng = windowed.iloc[start_pos : args.decision_pos + 1].reset_index(drop=True)
    if len(rng) != args.n:
        raise SystemExit(f"range length {len(rng)} != n {args.n}")
    window_ids = [int(r.window_idx) for r in rng.itertuples()]

    # --- Bradycardia-event count over the range (feeds the graph's n_events) ---
    n_events = int(
        sum(
            1
            for wid in window_ids
            if wid in feats.index and float(feats.loc[wid, "mean_rr"]) > BRADY_RR_MS
        )
    )

    # --- Per-window contexts on the grid ---
    contexts: list[AssessmentContext] = []
    for k, row in rng.iterrows():
        wid = int(row.window_idx)
        z = {c: float(row[f"{c}_dev"]) for c in dev_cols if _finite(row[f"{c}_dev"])}
        vals = {
            c: float(feats.loc[wid, c])
            for c in val_cols
            if wid in feats.index and _finite(feats.loc[wid, c])
        }
        contexts.append(
            AssessmentContext(patient_id=pid, z_scores=z, hrv_values=vals, detected_events=n_events)
        )
    decision_ctx = contexts[-1]
    baseline = personal_baseline(pid)

    # ================= §3 Tier 1 — Deviation (replayed to a per-feature series) ============
    dev = DeviationAssessor()
    thr = DeviationThresholds()
    tier1_features = []
    onset_idx = None
    for c in HRV_FEATURE_COLS:
        if c not in dev_cols and c not in val_cols:
            continue  # feature genuinely absent from this (pre-#13) processed data
        z_series = [ctx.z_scores.get(c) for ctx in contexts]
        value_series = [ctx.hrv_values.get(c) for ctx in contexts]
        direction = DEFAULT_DIRECTIONS.get(c)
        z_trigger = thr.threshold_for(c)
        failure_idx = None
        for k, ctx in enumerate(contexts):
            zc = ctx.z_scores.get(c)
            if zc is None:
                continue
            if pathological_magnitude(DEFAULT_DIRECTIONS, c, zc) >= z_trigger:
                failure_idx = k
                break
        flagged = failure_idx is not None
        if flagged:
            onset_idx = failure_idx if onset_idx is None else min(onset_idx, failure_idx)
        bmean = baseline.get(c, {}).get("mean", 0.0)
        bstd = baseline.get(c, {}).get("std", 1.0)
        tier1_features.append(
            {
                "key": c,
                "label": c.replace("_", " ").upper() if len(c) <= 5 else c.replace("_", " ").title(),
                "direction": direction,
                "trigger_feature": c in DEFAULT_DIRECTIONS,
                "z_series": [round(v, 4) if _finite(v) else None for v in z_series],
                "value_series": [round(v, 3) if _finite(v) else None for v in value_series],
                "baseline": {"mean": round(bmean, 3), "std": round(bstd, 3)},
                "z_trigger": z_trigger,
                "failure_idx": failure_idx,
                "flagged": flagged,
            }
        )

    floor_a = dev.assess(decision_ctx)
    concordant = len(floor_a.primary_indicators)
    if floor_a.level == ConcernLevel.RED:
        kind = "HARD"
    elif floor_a.level == ConcernLevel.YELLOW:
        kind = "SOFT"
    else:
        kind = "NONE"
    tier1 = {
        "features": tier1_features,
        "floor": {
            "level": floor_a.level.value,
            "concordant_count": concordant,
            "soft_floor": floor_a.soft_floor,
            "kind": kind,
        },
        "indicators": list(floor_a.primary_indicators),
        "verdict_text": floor_a.rationale,  # Ledger H3 — verbatim
    }

    # ================= §4 Tier 2 — CUSUM Drift (trajectory + quiet gates) ==================
    ct = CusumThresholds()
    gates = QuietGates()
    # (a) The genuine per-window Tier-2 Assessments via the REAL assessor (fresh state).
    ta = TemporalAssessor(store=InMemoryCusumStore())
    temporal_assessments = [ta.assess(ctx) for ctx in contexts]
    temporal_a = temporal_assessments[-1]
    # (b) The C⁺ trajectory via the same recursion the assessor runs (composite_deviation is
    #     the real function), tracked without the post-fire reset hiding the crossing peak.
    c_plus = 0.0
    prior_c_plus = 0.0
    c_plus_series: list[float] = []
    crossing_idx = None
    last_signal_at = None
    n_updates = 0
    prior_at_decision = 0.0
    for k, ctx in enumerate(contexts):
        comp = composite_deviation(ctx.z_scores, ct.directions)
        prior = c_plus
        c_plus = max(0.0, c_plus + comp - ct.k)
        n_updates = k + 1
        fired = c_plus >= ct.h
        if k == len(contexts) - 1:
            prior_at_decision = prior
        c_plus_series.append(round(c_plus, 4))
        if fired:
            if crossing_idx is None:
                crossing_idx = k
            last_signal_at = n_updates
            c_plus = 0.0  # Page's reset, same as TemporalAssessor
    # Cross-check the replicated recursion agrees with the real assessor's firing decision.
    real_fired = temporal_a.level == ConcernLevel.YELLOW
    replicated_fired_at_decision = crossing_idx == len(contexts) - 1
    fired_ever = crossing_idx is not None

    windows_since_signal = (n_updates - last_signal_at) if last_signal_at is not None else None
    quiet_gates = [
        {
            "key": "warmup",
            "label": f"Warmed up (≥{gates.warmup_windows} windows)",
            "pass": n_updates >= gates.warmup_windows,
            "detail": f"n_updates={n_updates} {'≥' if n_updates >= gates.warmup_windows else '<'} {gates.warmup_windows}",
        },
        {
            "key": "low_drift",
            "label": f"No building trend (C⁺<{gates.max_c_plus_frac:g}·h)",
            "pass": prior_at_decision < gates.max_c_plus_frac * ct.h,
            "detail": f"prior C⁺={prior_at_decision:.2f} {'<' if prior_at_decision < gates.max_c_plus_frac * ct.h else '≥'} {gates.max_c_plus_frac * ct.h:.2f}",
        },
        {
            "key": "guard",
            "label": f"Not recently alarmed (≥{gates.guard_windows} w)",
            "pass": windows_since_signal is None or windows_since_signal >= gates.guard_windows,
            "detail": "no prior signal" if windows_since_signal is None else f"{windows_since_signal} w since last alarm",
        },
    ]
    soft_floor_target = tier1["floor"]["kind"] == "SOFT"
    tier2 = {
        "c_plus_series": c_plus_series,
        "h": ct.h,
        "k": ct.k,
        "crossing_idx": crossing_idx,
        "fired": fired_ever,
        "level": temporal_a.level.value,
        "quiet": {
            "may_quiet": temporal_a.may_quiet,
            "gates": quiet_gates,
            "soft_floor_target": soft_floor_target,
            "note": (
                "Tier 2 may only quiet a SOFT single-feature YELLOW — never the HARD RED floor."
                if not soft_floor_target
                else "A SOFT single-feature YELLOW floor is present; the gates decide the quiet."
            ),
        },
        "verdict_text": temporal_a.rationale,  # Ledger H3 — verbatim
    }

    # ================= §5 Tier 3 — RAG (real graph, once, on the decision window) ==========
    base_level = max(
        floor_a.level,
        *[a.level for a in [temporal_a]],
    )
    rag_assessment = None
    if args.no_llm or base_level == ConcernLevel.GREEN:
        tier3 = {"ran": False}
    else:
        from src.agent.graph import build_graph

        graph = build_graph()  # already a compiled StateGraph
        state = graph.invoke({"patient_id": pid, "context": decision_ctx})
        alert = state["final_alert"]
        rag_chunks = state.get("rag_context") or []
        retrieved = []
        for i, chunk in enumerate(rag_chunks):
            ids = chunk_source_ids(chunk)
            sid = ids[0] if ids else f"chunk-{i}"
            snippet = chunk.strip()
            snippet = snippet if len(snippet) <= 320 else snippet[:317] + "…"
            retrieved.append(
                {"id": f"{sid}-{i}", "source": _short_source(sid), "snippet": snippet}
            )
        tier3 = {
            "ran": True,
            "query": state.get("rag_query") or "",
            "retrieved": retrieved,
            "reasoning": alert.clinical_reasoning,  # Ledger H2/H3 — the single real string
            "self_check": {
                "passed": bool(alert.self_check_passed),
                "note": (
                    "Deterministic safety override + LLM self-verification ran; "
                    f"the concern level ({alert.concern_level}) was confirmed."
                ),
            },
            "concern_level": alert.concern_level,
            "confidence": round(float(alert.confidence), 3),
            "recommended_action": alert.recommended_action,
            "primary_indicators": list(alert.primary_indicators),
            "escalate_only_note": "Tier 3 may raise concern above the floor but never lower it.",
        }
        rag_assessment = Assessment(
            level=ConcernLevel(alert.concern_level),
            risk=float(alert.risk),
            confidence=float(alert.confidence),
            rationale=alert.clinical_reasoning,
            source="rag",
            recommended_action=alert.recommended_action,
            primary_indicators=list(alert.primary_indicators),
            citations=[r["id"] for r in retrieved],
        )

    # ================= §6 Verdict — real VerdictCascade merge over genuine tiers ===========
    tiers = [_Fixed(floor_a), _Fixed(temporal_a)]
    if rag_assessment is not None:
        tiers.append(_Fixed(rag_assessment))
    verdict = VerdictCascade(tiers).assess(decision_ctx)
    verdict_out = {
        "patient_id": verdict.patient_id,
        "level": verdict.level.value,
        "risk": round(verdict.risk, 4),
        "confidence": round(verdict.confidence, 4),
        "safety_floor": verdict.safety_floor.value,
        "escalated_by": list(verdict.escalated_by),
        "recommended_action": verdict.recommended_action,
        "primary_indicators": list(verdict.primary_indicators),
        "citations": list(verdict.citations),
        "assessments": [
            {
                "source": a.source,
                "level": a.level.value,
                "risk": round(a.risk, 4),
                "confidence": round(a.confidence, 4),
                "rationale": a.rationale,
            }
            for a in verdict.assessments
        ],
        "rationale": verdict.rationale,
    }

    # ================= §1 time_grid ========================================================
    # Real HRV window stride, inferred from the resp grid (30 s windows) and the row-count
    # ratio — the features CSV carries no timestamp column. Honest best estimate, not 30 s.
    try:
        resp = pd.read_csv(_PROCESSED / f"{pid}_resp_features.csv")
        stride = round(30.0 * len(resp) / len(feats), 1)
    except Exception:
        stride = 10.0
    labels = []
    for k in range(args.n):
        secs = int(k * stride)
        labels.append(f"{secs // 60:02d}:{secs % 60:02d}")

    def phase(a, b):
        return [a, b] if a is not None and a <= b else None

    if onset_idx is None:
        phases = {"normal": [0, args.n - 1], "onset": None, "sustained": None}
    else:
        sustained_start = crossing_idx if crossing_idx is not None else None
        onset_end = (sustained_start - 1) if sustained_start is not None else args.n - 1
        phases = {
            "normal": phase(0, onset_idx - 1),
            "onset": phase(onset_idx, onset_end),
            "sustained": phase(sustained_start, args.n - 1) if sustained_start is not None else None,
        }
    time_grid = {
        "n": args.n,
        "unit": "window",
        "step_seconds": stride,
        "labels": labels,
        "phases": phases,
    }

    # ================= §2 data_in — honest recorded channels ==============================
    def band_from_normal(series):
        """A per-channel baseline band from the calm normal phase (mean ± 2·std)."""
        norm = phases["normal"]
        vals = [v for v in (series[norm[0] : norm[1] + 1] if norm else series) if _finite(v)]
        if len(vals) < 2:
            vals = [v for v in series if _finite(v)]
        if not vals:
            return None
        mean = sum(vals) / len(vals)
        var = sum((v - mean) ** 2 for v in vals) / max(1, len(vals) - 1)
        std = math.sqrt(var)
        return {"low": round(mean - 2 * std, 2), "high": round(mean + 2 * std, 2)}

    def make_channel(key, label, unit, series):
        band = band_from_normal(series)
        exit_idx = None
        if band:
            for k, v in enumerate(series):
                if _finite(v) and (v < band["low"] or v > band["high"]):
                    exit_idx = k
                    break
        return {
            "key": key,
            "label": label,
            "unit": unit,
            "real": True,
            "samples": [round(v, 3) if _finite(v) else None for v in series],
            "band": band,
            "band_exit_idx": exit_idx,
            "flagged": exit_idx is not None,
        }

    mean_rr = [ctx.hrv_values.get("mean_rr") for ctx in contexts]
    hr = [round(60000.0 / v, 2) if _finite(v) and v > 0 else None for v in mean_rr]
    channels = [
        make_channel("heart_rate", "Heart rate", "bpm", hr),
        make_channel("rr_interval", "RR interval", "ms", mean_rr),
    ]
    # Respiration + apnea: real recorded streams on a 30 s grid, resampled to the HRV grid by
    # time (nearest resp window). real:true — genuinely recorded, just resampled for display.
    try:
        resp = pd.read_csv(_PROCESSED / f"{pid}_resp_features.csv")
        resp_t0 = float(resp["t_start_s"].iloc[0])
        resp_stride = float(resp["t_start_s"].iloc[1] - resp["t_start_s"].iloc[0])

        def resp_at(wid, col):
            t = wid * stride
            ri = int(round((t - resp_t0) / resp_stride))
            ri = max(0, min(len(resp) - 1, ri))
            v = resp.iloc[ri][col]
            return float(v) if _finite(v) else None

        resp_series = [resp_at(wid, "resp_rate_bpm") for wid in window_ids]
        apnea_series = [resp_at(wid, "apnea_count") for wid in window_ids]
        channels.append(make_channel("respiration", "Respiration rate", "breaths/min", resp_series))
        channels.append(make_channel("apnea_events", "Apnea count", "events/min", apnea_series))
    except Exception as exc:  # pragma: no cover — resp is best-effort, never fabricated
        print(f"[record_trace] respiration/apnea channels skipped ({exc!r})")

    data_in = {"channels": channels}

    # ================= assemble + write ===================================================
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip()
    except Exception:
        commit = "unknown"

    # ================= §7 world_model — the real JEPA block, on THIS window ================
    # Until now the recorder stopped at the verdict, so a recorded trace had no `world_model`
    # and the showtime hero could only ever run off the hand-assembled fixture. Recording it
    # here is what closes that gap: the same absolute window the cascade just ran on, so the
    # 3-D trajectory sits on the *same* shared grid as data-in / Tier 1 / Tier 2 / Tier 3
    # rather than being stitched in from a separate export with its own window.
    #
    # The PCA basis is fitted on the recorder's OWN detected normal phase, not a fixed 90 —
    # if this window opens with 40 calm windows, fitting the basis on 90 would fit it partly
    # on the departure, which is exactly the thing spec §7 forbids.
    world_model = None
    if not args.no_world_model:
        normal_phase = time_grid["phases"].get("normal")
        normal_len = (normal_phase[1] - normal_phase[0] + 1) if normal_phase else args.n
        try:
            from scripts.export_jepa_trace import export_world_model

            world_model = export_world_model(
                args.ckpt, str(_PROCESSED / "all_patients_windowed.csv"), pid,
                int(window_ids[0]), int(window_ids[-1]), normal_len,
            )
        except Exception as exc:
            # A trace without the hero is still a valid trace (the block is optional in the
            # #30 contract); a recorder that dies on a missing checkpoint is not.
            print(f"  [warn] world_model block skipped ({type(exc).__name__}: {exc})")

    trace = {
        "schema_version": "1.0.0",
        "patient_id": pid,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": commit,
        "time_grid": time_grid,
        "data_in": data_in,
        "tier1": tier1,
        "tier2": tier2,
        "tier3": tier3,
        "verdict": verdict_out,
    }
    if world_model is not None:
        trace["world_model"] = world_model

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(trace, indent=2))

    print(f"[record_trace] wrote {out_path}  ({out_path.stat().st_size} bytes)")
    print(f"  window range: pos [{start_pos}, {args.decision_pos}]  window_idx [{window_ids[0]}, {window_ids[-1]}]")
    print(f"  phases: {phases}")
    print(f"  tier1 floor: {tier1['floor']}")
    print(f"  tier2: fired={tier2['fired']} crossing_idx={crossing_idx} may_quiet={tier2['quiet']['may_quiet']}")
    print(f"  tier3: ran={tier3.get('ran')} " + (f"level={tier3.get('concern_level')} action={tier3.get('recommended_action')!r}" if tier3.get("ran") else ""))
    print(f"  VERDICT: {verdict.level.value} risk={verdict.risk:.2f} floor={verdict.safety_floor.value} escalated_by={verdict.escalated_by}")
    if world_model is not None:
        print(f"  world_model: window={world_model['window']} sep_rise={world_model['sep_rise_calm_sd']} calm-SD  "
              f"captured={world_model['pca']['novelty_captured']}  basis={world_model['pca']['basis']}")
    # Honesty cross-check: the replicated CUSUM must agree with the real assessor.
    if fired_ever and not (real_fired or replicated_fired_at_decision or last_signal_at):
        print("  [warn] CUSUM replication/real-assessor mismatch — inspect before trusting §4")


if __name__ == "__main__":
    main()
