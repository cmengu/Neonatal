"""NeonatalGuard **routing-gate** runner (issue #7).

⚠️ ROUTING / PLUMBING gate — NOT a clinical-accuracy metric. It drives the real
``VerdictCascade`` with fake per-tier ``Assessor``s (``eval/scenarios.py``) and checks the
composed ``Verdict`` level against the cascade rules (Safety Floor, escalate-only, GREEN
short-circuit, ADR-0003 gated quiet). The old runner invoked the LangGraph agent with an
ONNX-derived ``risk_score`` injected via ``_SYNTHETIC_RESULT`` — #7 retired both, so there is
no ONNX, no Groq, no Qdrant, and no env-var pickle here.

Usage:
  python eval/eval_agent.py --fail-below-f1 0.80 --fail-above-fnr 0.0
  python eval/eval_agent.py --no-llm ...    # --no-llm accepted (no-op) for CI compatibility

CI invocation (.github/workflows/eval.yml):
  python eval/eval_agent.py --no-llm --fail-below-f1 0.80 --fail-above-fnr 0.0
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
from sklearn.metrics import f1_score

from eval.scenarios import SCENARIOS, build_cascade, context_for

LABELS = ["RED", "YELLOW", "GREEN"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="NeonatalGuard cascade routing-gate runner")
    p.add_argument("--no-llm", action="store_true",
                   help="Accepted for CI compatibility; the routing gate never calls an LLM.")
    p.add_argument("--fail-below-f1", type=float, default=None, metavar="F",
                   help="Exit 1 if macro F1 < F")
    p.add_argument("--fail-above-fnr", type=float, default=None, metavar="R",
                   help="Exit 1 if FNR(RED) > R")
    p.add_argument("--output", type=str,
                   default=str(REPO_ROOT / "results" / "eval_agent.json"),
                   help="Output path for JSON results")
    return p.parse_args()


def run_eval() -> dict:
    """Compose every scenario through the real cascade and collect predicted verdict levels."""
    y_true: list[str] = []
    y_pred: list[str] = []
    latencies_ms: list[float] = []

    for i, s in enumerate(SCENARIOS):
        try:
            t0 = time.perf_counter()
            verdict = build_cascade(s).assess(context_for(s))
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            pred = verdict.level.value
            match = "✓" if pred == s.expected else "✗"
            print(f"  [{i+1:02d}] {s.patient_id}: expected={s.expected} got={pred} {match}  {elapsed_ms:.1f}ms")
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0 if "t0" in locals() else 0.0
            pred = "ERROR"
            print(f"  [{i+1:02d}] {s.patient_id}: EXCEPTION — {exc}")
        finally:
            y_true.append(s.expected)
            y_pred.append(pred)
            latencies_ms.append(elapsed_ms)

    valid = [p in LABELS for p in y_pred]
    vt = [t for t, ok in zip(y_true, valid) if ok]
    vp = [p for p, ok in zip(y_pred, valid) if ok]
    f1 = float(f1_score(vt, vp, average="macro", labels=LABELS, zero_division=0)) if vp else 0.0

    n_red = sum(1 for t in y_true if t == "RED")
    missed = sum(1 for t, p in zip(y_true, y_pred) if t == "RED" and p != "RED")
    fnr = missed / n_red if n_red > 0 else 0.0

    hard = [(t, p) for s, t, p in zip(SCENARIOS, y_true, y_pred) if "HARD" in s.patient_id]
    n_hard_red = sum(1 for t, _ in hard if t == "RED")
    missed_hard_red = sum(1 for t, p in hard if t == "RED" and p != "RED")
    fnr_hard = missed_hard_red / n_hard_red if n_hard_red > 0 else 0.0

    lat = sorted(latencies_ms)
    return {
        "gate_type": "routing/plumbing (cascade composition) — NOT clinical accuracy",
        "n_scenarios": len(SCENARIOS),
        "n_correct": sum(t == p for t, p in zip(y_true, y_pred)),
        "f1": f1,
        "fnr_red": fnr,
        "fnr_hard": fnr_hard,
        "latency_p50_ms": float(np.percentile(lat, 50)) if lat else 0.0,
        "latency_p95_ms": float(np.percentile(lat, 95)) if lat else 0.0,
        "y_true": y_true,
        "y_pred": y_pred,
    }


def main() -> None:
    args = parse_args()
    print(f"\nNeonatalGuard Routing Gate — {len(SCENARIOS)} scenarios (cascade composition)")
    print("  NOTE: plumbing/routing gate, NOT a clinical-accuracy metric.")
    print("-" * 60)

    results = run_eval()

    print("-" * 60)
    print(f"F1 (macro):        {results['f1']:.3f}")
    print(f"FNR (RED):         {results['fnr_red']:.3f}")
    print(f"FNR (RED, hard):   {results['fnr_hard']:.3f}")
    print(f"Latency p50 / p95: {results['latency_p50_ms']:.1f}ms / {results['latency_p95_ms']:.1f}ms")
    print(f"Correct:           {results['n_correct']}/{results['n_scenarios']}")

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults → {out_path}")

    failed = False
    if args.fail_below_f1 is not None and results["f1"] < args.fail_below_f1:
        print(f"\nCI FAIL: F1={results['f1']:.3f} < threshold {args.fail_below_f1:.3f}")
        failed = True
    if args.fail_above_fnr is not None and results["fnr_red"] > args.fail_above_fnr:
        print(f"\nCI FAIL: FNR(RED)={results['fnr_red']:.3f} > threshold {args.fail_above_fnr:.3f}")
        failed = True

    if failed:
        sys.exit(1)
    print("All CI gates passed.")


if __name__ == "__main__":
    main()
