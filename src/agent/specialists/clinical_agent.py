"""Clinical Reasoning specialist node.

Synthesises pre-interpreted specialist findings into a final clinical decision.
Receives SignalAssessment and optionally BradycardiaAssessment — not raw numbers.
Reasoning like a consultant receiving a handover, not a technician reading sensors.

This is the key improvement over the generalist: the specialist only decides
WHAT TO DO given already-interpreted evidence. It does not also have to interpret
what the z-scores mean — that is signal_agent's job.

Retrieves from 'intervention_thresholds' and 'baseline_interpretation' only.
In EVAL_NO_LLM mode: deterministic LLMOutput from risk_score (same as generalist).
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from langsmith import traceable

from src.agent.schemas import LLMOutput

if TYPE_CHECKING:
    from src.agent.supervisor import MultiAgentState


_CLINICAL_CATEGORIES = ["intervention_thresholds", "baseline_interpretation"]


@traceable(name="clinical_agent_node")
def clinical_agent_node(state: dict) -> dict:
    """Synthesise specialist findings into a structured clinical alert."""
    r = state["pipeline_result"]

    if os.getenv("EVAL_NO_LLM", "").lower() in {"1", "true", "yes"}:
        # Rule-based path — delegates to generalist llm_reasoning_node.
        # Delegation is intentional: llm_reasoning_node only reads pipeline_result,
        # rag_context, and past_alerts — all fields present in MultiAgentState.
        # TypedDict is not enforced at runtime so this is safe.
        from src.agent.graph import llm_reasoning_node
        return llm_reasoning_node(state)

    from src.agent.graph import _get_groq, _get_kb

    sa = state.get("signal_assessment")
    ba = state.get("bradycardia_assessment")
    past = state.get("past_alerts") or []

    signal_summary = (
        f"Signal assessment: pattern={sa.autonomic_pattern}, "
        f"confidence={sa.confidence:.2f}, features={sa.primary_features}\n"
        f"Reasoning: {sa.physiological_reasoning}"
    ) if sa else "Signal assessment: not available."

    brady_summary = (
        f"Bradycardia assessment: classification={ba.classification}, "
        f"clinical_weight={ba.clinical_weight}\nReasoning: {ba.reasoning}"
    ) if ba else "Bradycardia assessment: no events detected."

    episodic = ""
    if past:
        episodic = f"Patient history (last {len(past)} alerts):\n"
        episodic += "\n".join(
            f"  [{a.timestamp[:10]}] {a.concern_level} - {a.top_feature} z={a.top_z_score:.1f}"
            for a in past
        )

    query = (
        f"Intervention decision for neonatal {r.risk_level} risk patient. "
        f"Autonomic pattern: {sa.autonomic_pattern if sa else 'unknown'}. "
        f"Brady events: {len(r.detected_events)}. Risk score: {r.risk_score:.2f}."
    )
    chunks = _get_kb().query_by_category(query, categories=_CLINICAL_CATEGORIES, n=3)
    context = "\n\n".join(chunks)

    prompt = f"""You are a neonatal intensive care clinical decision support consultant.
You receive pre-interpreted specialist findings — not raw numbers.
Your task: determine the concern level and recommend an appropriate clinical action.

ONNX risk score: {r.risk_score:.3f}
{signal_summary}
{brady_summary}
{episodic}

Clinical intervention guidelines:
{context}

Generate a structured neonatal clinical alert. Recommended actions must follow standard NICU protocols."""

    output: LLMOutput = _get_groq().chat.completions.create(
        model="llama-3.3-70b-versatile",
        response_model=LLMOutput,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_retries=3,
    )
    return {"llm_output": output}
