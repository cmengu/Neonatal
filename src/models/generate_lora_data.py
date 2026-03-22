"""Generate LoRA fine-tuning data for the signal specialist.

Produces data/lora_training/signal_train.jsonl — one JSON object per line:
    {"instruction": "...", "input": "<z-score table>", "output": "<SignalAssessment JSON>"}

Data sources:
  1. All 30 eval scenarios (deterministic, reproducible)
  2. ~200 additional synthetic PipelineResults via generate_synthetic_result()

Labels:
  Default (offline): _rule_based_signal() — same logic as EVAL_NO_LLM mode.
  --use-groq: calls Groq API signal assessment (requires GROQ_API_KEY in .env).
              DO NOT USE while Groq API key is exhausted.

Run from repo root:
    python src/models/generate_lora_data.py
    python src/models/generate_lora_data.py --use-groq   # when API restored
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np

from eval.scenarios import SCENARIOS, build_pipeline_result
from src.agent.specialists.signal_agent import _rule_based_signal
from src.agent.schemas import SignalAssessment
from src.data.synthetic_generator import generate_synthetic_result
from src.features.constants import HRV_FEATURE_COLS


_INSTRUCTION = (
    "Classify the neonatal HRV autonomic pattern from these z-score deviations "
    "from this infant's personal baseline. Do NOT recommend clinical actions — "
    "output only the physiological signal assessment."
)


def _result_to_input_str(r) -> str:
    """Format a PipelineResult into the model's input string."""
    z_parts = ", ".join(
        f"{feat} z={r.z_scores.get(feat, 0.0):+.2f}"
        for feat in HRV_FEATURE_COLS
    )
    return (
        f"{z_parts}. "
        f"Risk score {r.risk_score:.2f}. "
        f"Bradycardia events: {len(r.detected_events)}."
    )


def _label_rule_based(r) -> SignalAssessment:
    """Label using the deterministic rule-based signal assessment (offline)."""
    z_vals = [abs(z) for z in r.z_scores.values()]
    max_z = max(z_vals) if z_vals else 0.0
    return _rule_based_signal(r.risk_score, max_z)


def _label_groq(r) -> SignalAssessment:
    """Label using the Groq LLM signal assessment (requires GROQ_API_KEY).

    Only callable when the Groq API key is not exhausted.
    """
    from dotenv import load_dotenv
    load_dotenv()
    from src.agent.graph import _get_groq, _get_kb

    top3 = r.get_top_deviated(3)
    query = (
        "Neonatal HRV autonomic pattern: "
        + ", ".join(f"{d.name} z={d.z_score:+.1f}" for d in top3)
        + f". Risk score {r.risk_score:.2f}. Bradycardia events: {len(r.detected_events)}."
    )
    chunks = _get_kb().query_by_category(query, categories=["hrv_indicators", "sepsis_early_warning"], n=3)
    context = "\n\n".join(chunks)
    z_table = "\n".join(
        f"  {feat}: z={z:+.2f}  (raw={r.hrv_values.get(feat, 0):.1f}ms)"
        for feat, z in r.z_scores.items()
    )
    prompt = (
        f"Patient HRV z-scores:\n{z_table}\n\n"
        f"Retrieved HRV reference:\n{context}\n\n"
        "Classify the autonomic pattern. Output a SignalAssessment."
    )
    return _get_groq().chat.completions.create(
        model="llama-3.3-70b-versatile",
        response_model=SignalAssessment,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_retries=3,
    )


def _make_record(r, label_fn) -> dict:
    """Build one JSONL record from a PipelineResult."""
    assessment: SignalAssessment = label_fn(r)
    return {
        "instruction": _INSTRUCTION,
        "input": _result_to_input_str(r),
        "output": json.dumps({
            "autonomic_pattern": assessment.autonomic_pattern,
            "primary_features": assessment.primary_features,
            "confidence": assessment.confidence,
            "physiological_reasoning": assessment.physiological_reasoning,
        }),
    }


def generate(use_groq: bool = False, n_synthetic: int = 200) -> None:
    """Generate and write signal_train.jsonl."""
    out_dir = REPO_ROOT / "data" / "lora_training"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "signal_train.jsonl"

    label_fn = _label_groq if use_groq else _label_rule_based
    label_source = "groq" if use_groq else "rule_based"
    print(f"Label source: {label_source}")

    records: list[dict] = []

    # Source 1: All 30 eval scenarios (deterministic, covers RED/YELLOW/GREEN/HARD)
    print(f"Adding {len(SCENARIOS)} eval scenarios ...")
    for s in SCENARIOS:
        r = build_pipeline_result(s)
        records.append(_make_record(r, label_fn))

    # Source 2: Synthetic PipelineResults (diverse z-score patterns)
    print(f"Adding {n_synthetic} synthetic examples ...")
    rng = np.random.default_rng(seed=42)
    # Distribution: 40% pre-sepsis, 30% normal, 30% borderline
    n_sepsis     = int(n_synthetic * 0.40)
    n_normal     = int(n_synthetic * 0.30)
    n_borderline = n_synthetic - n_sepsis - n_normal

    for i in range(n_sepsis):
        r = generate_synthetic_result(
            f"synth_sepsis_{i:03d}",
            ga_range="28-32wk",
            sepsis=True,
            sepsis_severity=float(rng.uniform(0.6, 1.0)),
            n_brady_events=int(rng.integers(0, 6)),
        )
        records.append(_make_record(r, label_fn))

    for i in range(n_normal):
        r = generate_synthetic_result(
            f"synth_normal_{i:03d}",
            ga_range="28-32wk",
            sepsis=False,
            n_brady_events=0,
        )
        records.append(_make_record(r, label_fn))

    for i in range(n_borderline):
        # Borderline: mild sepsis severity → risk_score in YELLOW range → indeterminate label
        r = generate_synthetic_result(
            f"synth_border_{i:03d}",
            ga_range="28-32wk",
            sepsis=True,
            sepsis_severity=float(rng.uniform(0.25, 0.50)),
            n_brady_events=int(rng.integers(0, 3)),
        )
        records.append(_make_record(r, label_fn))

    with open(out_path, "w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")

    # Print label distribution
    from collections import Counter
    patterns = Counter(
        json.loads(r["output"])["autonomic_pattern"] for r in records
    )
    print(f"\nWrote {len(records)} records to {out_path}")
    print("Label distribution:")
    for pattern, count in sorted(patterns.items(), key=lambda x: -x[1]):
        print(f"  {pattern}: {count} ({100*count/len(records):.1f}%)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate signal specialist LoRA training data")
    parser.add_argument(
        "--use-groq", action="store_true",
        help="Label with Groq LLM (requires GROQ_API_KEY; DO NOT USE if key exhausted)"
    )
    parser.add_argument(
        "--n-synthetic", type=int, default=200,
        help="Number of synthetic examples to add (default: 200)"
    )
    args = parser.parse_args()
    generate(use_groq=args.use_groq, n_synthetic=args.n_synthetic)
