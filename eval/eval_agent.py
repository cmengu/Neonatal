"""NeonatalGuard agent eval runner.

Usage:
  python eval/eval_agent.py --no-llm
  python eval/eval_agent.py --no-llm --fail-below-f1 0.80 --fail-above-fnr 0.0
  python eval/eval_agent.py                            # live LLM — requires GROQ_API_KEY
  python eval/eval_agent.py --agent multi_agent        # Phase 6 only

CI invocation (from .github/workflows/eval.yml):
  python eval/eval_agent.py --no-llm --fail-below-f1 0.80 --fail-above-fnr 0.0

Known side effect: assemble_alert_node writes one row to data/audit.db per scenario
(EpisodicMemory.save). Harmless in no-LLM mode (rule-based path ignores past_alerts).
Each scenario has a unique patient_id so cross-scenario history contamination cannot occur.
"""
import json
import os
import sys
import time
import argparse
from pathlib import Path

# Must set EVAL_NO_LLM BEFORE importing src.agent.graph.
# graph.py calls _build_groq_client() at module import time when EVAL_NO_LLM is not set.
# Doing this here (before the REPO_ROOT sys.path insert) is safe because
# os.environ is process-global and does not depend on the import order.
if "--no-llm" in sys.argv:
    os.environ["EVAL_NO_LLM"] = "1"

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
from sklearn.metrics import f1_score

from eval.scenarios import SCENARIOS, inject_scenario, clear_injection

LABELS = ["RED", "YELLOW", "GREEN"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="NeonatalGuard agent eval runner")
    p.add_argument("--no-llm", action="store_true",
                   help="Set EVAL_NO_LLM=1 before importing graph (must also be in sys.argv)")
    p.add_argument("--fail-below-f1",  type=float, default=None, metavar="F",
                   help="Exit 1 if macro F1 < F")
    p.add_argument("--fail-above-fnr", type=float, default=None, metavar="R",
                   help="Exit 1 if FNR(RED) > R")
    p.add_argument("--agent", choices=["agent", "multi_agent"], default="agent",
                   help="Which agent to evaluate (default: agent; multi_agent requires Phase 5)")
    p.add_argument("--output", type=str,
                   default=str(REPO_ROOT / "results" / "eval_agent.json"),
                   help="Output path for JSON results")
    return p.parse_args()


def load_agent(name: str):
    """Import the requested agent graph from src.agent.graph."""
    if name == "agent":
        from src.agent.graph import agent
        return agent
    elif name == "multi_agent":
        try:
            from src.agent.graph import multi_agent
            return multi_agent
        except ImportError:
            sys.exit(
                "ERROR: multi_agent not found in src.agent.graph. "
                "Build Phase 5 first."
            )


def run_eval(run_agent) -> dict:
    """Run all 30 scenarios and collect predictions + latencies."""
    y_true:         list[str]   = []
    y_pred:         list[str]   = []
    protocol_flags: list[bool]  = []
    latencies_ms:   list[float] = []

    for i, scenario in enumerate(SCENARIOS):
        inject_scenario(scenario)
        try:
            t0 = time.perf_counter()
            state = run_agent.invoke({"patient_id": scenario.patient_id})
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            alert = state.get("final_alert")
            if alert is None:
                pred = "ERROR"
                protocol_ok = False
                print(f"  [{i+1:02d}] {scenario.patient_id}: ERROR — final_alert is None in state")
            else:
                pred = alert.concern_level
                protocol_ok = alert.protocol_compliant
                match = "✓" if pred == scenario.expected else "✗"
                print(
                    f"  [{i+1:02d}] {scenario.patient_id}: "
                    f"expected={scenario.expected} got={pred} {match}  "
                    f"{elapsed_ms:.0f}ms"
                )

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0 if "t0" in locals() else 0.0
            pred = "ERROR"
            protocol_ok = False
            print(f"  [{i+1:02d}] {scenario.patient_id}: EXCEPTION — {exc}")

        finally:
            clear_injection()
            y_true.append(scenario.expected)
            y_pred.append(pred)
            protocol_flags.append(protocol_ok)
            latencies_ms.append(elapsed_ms)

    # Macro F1 — only over valid predictions (exclude "ERROR" rows)
    valid_mask  = [p in LABELS for p in y_pred]
    valid_true  = [t for t, ok in zip(y_true,  valid_mask) if ok]
    valid_pred  = [p for p, ok in zip(y_pred,  valid_mask) if ok]
    f1 = float(f1_score(
        valid_true, valid_pred,
        average="macro", labels=LABELS, zero_division=0
    )) if valid_pred else 0.0

    # FNR (RED): missed RED / total RED
    n_red  = sum(1 for t in y_true if t == "RED")
    missed = sum(1 for t, p in zip(y_true, y_pred) if t == "RED" and p != "RED")
    fnr    = missed / n_red if n_red > 0 else 0.0

    # FNR (RED, hard scenarios only) — Phase 5 improvement target
    hard_pairs = [(t, p) for s, t, p in zip(SCENARIOS, y_true, y_pred) if "HARD" in s.patient_id]
    n_hard_red = sum(1 for t, _ in hard_pairs if t == "RED")
    missed_hard_red = sum(1 for t, p in hard_pairs if t == "RED" and p != "RED")
    fnr_hard = missed_hard_red / n_hard_red if n_hard_red > 0 else 0.0

    protocol  = sum(protocol_flags) / len(protocol_flags)
    lat_arr   = sorted(latencies_ms)
    p50       = float(np.percentile(lat_arr, 50)) if lat_arr else 0.0
    p95       = float(np.percentile(lat_arr, 95)) if lat_arr else 0.0
    n_correct = sum(t == p for t, p in zip(y_true, y_pred))

    return {
        "n_scenarios":         len(SCENARIOS),
        "n_correct":           n_correct,
        "f1":                  f1,
        "fnr_red":             fnr,
        "fnr_hard":            fnr_hard,
        "protocol_compliance": protocol,
        "latency_p50_ms":      p50,
        "latency_p95_ms":      p95,
        "no_llm_mode":         os.getenv("EVAL_NO_LLM", "") in {"1", "true", "yes"},
        "y_true":              y_true,
        "y_pred":              y_pred,
    }


def main() -> None:
    args = parse_args()
    mode = "EVAL_NO_LLM=1 (rule-based)" if os.getenv("EVAL_NO_LLM", "") in {"1", "true", "yes"} \
           else "LIVE LLM (Groq)"

    print(f"\nNeonatalGuard Eval — {len(SCENARIOS)} scenarios — mode: {mode}")
    print("-" * 60)

    run_agent = load_agent(args.agent)
    results   = run_eval(run_agent)

    print("-" * 60)
    print(f"F1 (macro):          {results['f1']:.3f}")
    print(f"FNR (RED):           {results['fnr_red']:.3f}")
    print(f"FNR (RED, hard):     {results['fnr_hard']:.3f}")
    print(f"Protocol compliance: {results['protocol_compliance'] * 100:.1f}%")
    print(f"Latency p50 / p95:   {results['latency_p50_ms']:.0f}ms / {results['latency_p95_ms']:.0f}ms")
    print(f"Correct:             {results['n_correct']}/{results['n_scenarios']}")

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
