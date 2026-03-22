"""Signal Interpretation specialist node.

Physiologically classifies HRV z-score patterns for the multi-agent graph.
Always runs as the first specialist after the supervisor node.

Retrieves from 'hrv_indicators' and 'sepsis_early_warning' KB categories only —
not from bradycardia or intervention chunks. This focus prevents the signal
specialist from conflating autonomic pattern reading with action selection
(the primary cause of YELLOW/GREEN confusion in the generalist).

In EVAL_NO_LLM mode: returns deterministic SignalAssessment from risk_score
and max z-score without any Groq call — CI gate works without API key.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from langsmith import traceable

from src.agent.schemas import SignalAssessment

if TYPE_CHECKING:
    from src.agent.supervisor import MultiAgentState


_SIGNAL_CATEGORIES = ["hrv_indicators", "sepsis_early_warning"]


def _rule_based_signal(risk_score: float, max_z: float) -> SignalAssessment:
    """Deterministic signal assessment for EVAL_NO_LLM mode."""
    if risk_score > 0.70:
        return SignalAssessment(
            autonomic_pattern="pre_sepsis",
            primary_features=["rmssd", "lf_hf_ratio"],
            confidence=0.90,
            physiological_reasoning=(
                f"Rule-based: risk_score={risk_score:.2f} > 0.70, max_z={max_z:.1f}. "
                "Autonomic withdrawal pattern consistent with pre-sepsis HRV signature."
            ),
        )
    if risk_score > 0.40:
        return SignalAssessment(
            autonomic_pattern="indeterminate",
            primary_features=["rmssd"],
            confidence=0.65,
            physiological_reasoning=(
                f"Rule-based: risk_score={risk_score:.2f} in borderline range, max_z={max_z:.1f}. "
                "Pattern indeterminate — clinical context required."
            ),
        )
    return SignalAssessment(
        autonomic_pattern="normal_variation",
        primary_features=["sdnn"],
        confidence=0.85,
        physiological_reasoning=(
            f"Rule-based: risk_score={risk_score:.2f} < 0.40, max_z={max_z:.1f}. "
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
        return {"signal_assessment": _rule_based_signal(r.risk_score, max_z)}

    from src.agent.graph import _get_groq, _get_kb

    top3 = r.get_top_deviated(3)
    query = (
        f"Neonatal HRV autonomic pattern: "
        + ", ".join(f"{d.name} z={d.z_score:+.1f}" for d in top3)
        + f". Risk score {r.risk_score:.2f}. Bradycardia events: {len(r.detected_events)}."
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

    assessment: SignalAssessment = _get_groq().chat.completions.create(
        model="llama-3.3-70b-versatile",
        response_model=SignalAssessment,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_retries=3,
    )
    return {"signal_assessment": assessment}
