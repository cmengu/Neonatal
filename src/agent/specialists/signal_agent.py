"""Signal Interpretation specialist node.

Physiologically classifies HRV z-score patterns for the multi-agent graph.
Always runs as the first specialist after the supervisor node.

Retrieves from 'hrv_indicators' and 'sepsis_early_warning' KB categories only —
not from bradycardia or intervention chunks. This focus prevents the signal
specialist from conflating autonomic pattern reading with action selection
(the primary cause of YELLOW/GREEN confusion in the generalist).

In EVAL_NO_LLM mode: returns deterministic SignalAssessment from risk_score
and max z-score without any LLM call — CI gate works without API key.

Removed in #86 — do not reinstate: a ``USE_LORA_SIGNAL=1`` route once pointed this
specialist at a local Phi-3-mini LoRA adapter. That adapter was fine-tuned on a
training set that was 40% synthetic "sepsis" cases whose labels came from a
``sepsis_severity`` float drawn from ``uniform(0.6, 1.0)`` — a number somebody
typed, not an outcome anyone adjudicated. The adapter was never trained and every
LoRA row in BENCHMARKS.md is still *pending*, so nothing measured is lost. The
whole chain is gone rather than gated: a flag only a careful reader knows is
dangerous is not a safeguard (D13). If a local signal model is ever wanted, it
must be trained on labels from outside this repo.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from langsmith import traceable

from src.agent.schemas import SignalAssessment

if TYPE_CHECKING:
    from src.agent.supervisor import MultiAgentState


_SIGNAL_CATEGORIES = ["hrv_indicators", "sepsis_early_warning"]


def _rule_based_signal(level: str, max_z: float) -> SignalAssessment:
    """Deterministic signal assessment for EVAL_NO_LLM mode.

    Post-#7 this routes on the deterministic Tier-1 concern ``level`` (the retired ONNX
    ``risk_score`` bands are gone), mapping RED→abnormal_hrc, YELLOW→indeterminate,
    GREEN→normal_variation.
    """
    if level == "RED":
        return SignalAssessment(
            autonomic_pattern="abnormal_hrc",
            primary_features=["rmssd", "sdnn"],
            confidence=0.90,
            physiological_reasoning=(
                f"Rule-based: Tier-1 level=RED, max_z={max_z:.1f}. "
                "Autonomic withdrawal pattern — abnormal heart-rate characteristics "
                "(increased risk); an adjunct risk signal, not a sepsis diagnosis."
            ),
        )
    if level == "YELLOW":
        return SignalAssessment(
            autonomic_pattern="indeterminate",
            primary_features=["rmssd"],
            confidence=0.65,
            physiological_reasoning=(
                f"Rule-based: Tier-1 level=YELLOW (borderline), max_z={max_z:.1f}. "
                "Pattern indeterminate — clinical context required."
            ),
        )
    return SignalAssessment(
        autonomic_pattern="normal_variation",
        primary_features=["sdnn"],
        confidence=0.85,
        physiological_reasoning=(
            f"Rule-based: Tier-1 level=GREEN, max_z={max_z:.1f}. "
            "HRV deviations within expected normal variation range."
        ),
    )


@traceable(name="signal_agent_node")
def signal_agent_node(state: dict) -> dict:
    """Classify autonomic pattern from HRV z-scores. Always runs first."""
    r = state["pipeline_result"]
    z_vals = [abs(z) for z in r.z_scores.values()]
    max_z = max(z_vals) if z_vals else 0.0

    if os.getenv("EVAL_NO_LLM", "").lower() in {"1", "true", "yes"}:
        return {"signal_assessment": _rule_based_signal(r.level, max_z)}

    from src.agent.graph import LLM_MAX_TOKENS, LLM_MODEL, _get_kb, _get_llm

    top3 = r.get_top_deviated(3)
    query = (
        f"Neonatal HRV autonomic pattern: "
        + ", ".join(f"{d.name} z={d.z_score:+.1f}" for d in top3)
        + f". Deterministic risk {r.risk:.2f}. Bradycardia events: {r.n_events}."
    )
    chunks = _get_kb().query_by_category(query, categories=_SIGNAL_CATEGORIES, n=3)
    context = "\n\n".join(chunks)

    z_table = "\n".join(
        f"  {feat}: z={z:+.2f}  (raw={r.hrv_values.get(feat, 0):.1f}ms)"
        for feat, z in r.z_scores.items()
    )

    prompt = f"""You are a neonatal HRV signal analyst. Your ONLY task is to classify
the physiological meaning of these z-score deviations from this infant's personal baseline.
Do NOT recommend clinical actions — that is a separate agent's responsibility.

Patient HRV z-scores (personal baseline deviation):
{z_table}

Retrieved HRV reference knowledge:
{context}

Classify the autonomic pattern and identify which features drove your assessment.
Output a SignalAssessment."""

    assessment: SignalAssessment = _get_llm().chat.completions.create(
        model=LLM_MODEL,
        response_model=SignalAssessment,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=LLM_MAX_TOKENS,
        max_retries=3,
    )
    return {"signal_assessment": assessment}
