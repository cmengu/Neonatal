"""Bradycardia Classification specialist node.

Classifies the clinical significance of detected bradycardia events.
Runs conditionally: only when len(detected_events) > 0 OR max_z > 2.0.

Retrieves from 'bradycardia_patterns' KB category only — isolating bradycardia
clinical knowledge from HRV spectral analysis. The generalist mixes both in one
prompt, causing confusion on cases where brady pattern and HRV signals disagree.

In EVAL_NO_LLM mode: deterministic classification from event count.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from langsmith import traceable

from src.agent.schemas import BradycardiaAssessment

if TYPE_CHECKING:
    from src.agent.supervisor import MultiAgentState


_BRADY_CATEGORIES = ["bradycardia_patterns"]


def _rule_based_brady(n_events: int) -> BradycardiaAssessment:
    """Deterministic bradycardia classification for EVAL_NO_LLM mode."""
    if n_events == 0:
        return BradycardiaAssessment(
            classification="none",
            clinical_weight="low",
            reasoning="No bradycardia events detected in last 6h.",
        )
    if n_events >= 4:
        return BradycardiaAssessment(
            classification="cluster",
            clinical_weight="high",
            reasoning=f"Rule-based: {n_events} events — cluster pattern, high clinical weight.",
        )
    if n_events >= 2:
        return BradycardiaAssessment(
            classification="recurrent_without_suppression",
            clinical_weight="medium",
            reasoning=f"Rule-based: {n_events} events — recurrent pattern without clear HRV suppression.",
        )
    return BradycardiaAssessment(
        classification="isolated_reflex",
        clinical_weight="low",
        reasoning=f"Rule-based: {n_events} event — isolated, likely reflex bradycardia.",
    )


@traceable(name="brady_agent_node")
def brady_agent_node(state: "MultiAgentState") -> dict:
    """Classify bradycardia event pattern. Runs only when events present or max_z > 2.0."""
    r = state["pipeline_result"]
    n_events = len(r.detected_events)

    if os.getenv("EVAL_NO_LLM", "").lower() in {"1", "true", "yes"}:
        return {"bradycardia_assessment": _rule_based_brady(n_events)}

    from src.agent.graph import _get_groq, _get_kb

    signal_ctx = ""
    sa = state.get("signal_assessment")
    if sa:
        signal_ctx = (
            f"\nSignal assessment from HRV specialist: "
            f"pattern={sa.autonomic_pattern}, confidence={sa.confidence:.2f}\n"
        )

    query = (
        f"Bradycardia events: {n_events} in last 6h. "
        f"Risk score {r.risk_score:.2f}. "
        + ", ".join(
            f"{d.name} z={d.z_score:+.1f}"
            for d in r.get_top_deviated(3)
        )
    )
    chunks = _get_kb().query_by_category(query, categories=_BRADY_CATEGORIES, n=2)
    context = "\n\n".join(chunks)

    prompt = f"""You are a neonatal bradycardia classification specialist.
Your ONLY task is to classify the clinical significance of these bradycardia events.
Do NOT recommend clinical actions.

Bradycardia events last 6h: {n_events}
{signal_ctx}
Retrieved bradycardia reference:
{context}

Classify the bradycardia pattern and assign clinical weight. Output a BradycardiaAssessment."""

    assessment: BradycardiaAssessment = _get_groq().chat.completions.create(
        model="llama-3.3-70b-versatile",
        response_model=BradycardiaAssessment,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_retries=3,
    )
    return {"bradycardia_assessment": assessment}
