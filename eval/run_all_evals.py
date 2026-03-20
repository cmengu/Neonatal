"""Run the full Phase 4 eval suite: agent (no-LLM) + RAG retrieval.

Agent eval uses EVAL_NO_LLM=1 (rule-based path, zero API cost).
RAG eval uses on-disk Qdrant at QDRANT_PATH (default: qdrant_local/).

Usage:
  QDRANT_PATH=qdrant_local python eval/run_all_evals.py
"""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS   = REPO_ROOT / "results"


def run_subprocess(script: str, extra_args: list[str], label: str) -> int:
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print("=" * 60)
    cmd = [sys.executable, script] + extra_args
    result = subprocess.run(cmd, cwd=str(REPO_ROOT))
    return result.returncode


def print_summary() -> None:
    print(f"\n{'=' * 60}")
    print("  PHASE 4 EVAL SUMMARY")
    print("=" * 60)

    agent_path = RESULTS / "eval_agent.json"
    if agent_path.exists():
        r = json.loads(agent_path.read_text())
        mode = "no-LLM" if r.get("no_llm_mode") else "live-LLM"
        print(
            f"Agent ({mode}):  "
            f"F1={r['f1']:.3f}  "
            f"FNR(RED)={r['fnr_red']:.3f}  "
            f"Protocol={r['protocol_compliance'] * 100:.1f}%  "
            f"p50={r['latency_p50_ms']:.0f}ms"
        )
    else:
        print("Agent eval:  results/eval_agent.json not found")

    retrieval_path = RESULTS / "eval_retrieval.json"
    if retrieval_path.exists():
        r = json.loads(retrieval_path.read_text())
        delta = r['mrr_delta']
        sign = "+" if delta >= 0 else ""
        print(
            f"RAG:          "
            f"MRR@3 vector={r['mrr_vector']:.3f}  "
            f"hybrid={r['mrr_hybrid']:.3f}  "
            f"delta={sign}{delta:.3f}"
        )
    else:
        print("RAG eval:    results/eval_retrieval.json not found")


def main() -> None:
    qdrant_path = os.getenv("QDRANT_PATH", str(REPO_ROOT / "qdrant_local"))
    os.environ["QDRANT_PATH"] = qdrant_path

    rc_agent = run_subprocess(
        "eval/eval_agent.py",
        ["--no-llm"],
        "Agent Eval (EVAL_NO_LLM=1 — rule-based path)",
    )
    rc_retrieval = run_subprocess(
        "eval/eval_retrieval.py",
        [],
        "RAG Retrieval Eval (MRR@3 vector vs hybrid+rerank)",
    )

    print_summary()
    sys.exit(max(rc_agent, rc_retrieval))


if __name__ == "__main__":
    main()
