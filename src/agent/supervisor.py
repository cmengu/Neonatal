"""Multi-agent supervisor graph for NeonatalGuard Phase 5.

Replaces the single 6-node generalist graph with a 7-node supervisor
routing through four specialist subgraphs:

  supervisor → signal → [brady (conditional)] → clinical → protocol → assemble_multi

Bradycardia specialist runs when: len(detected_events) > 0 OR max_z > 2.0.
All other nodes always run.

The generalist `agent` object in graph.py is unchanged — this graph is exported
as `multi_agent` alongside it for side-by-side eval comparison.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional, TypedDict

from langgraph.graph import END, StateGraph
from langsmith import traceable

from src.agent.memory import EpisodicMemory, PastAlert
from src.agent.schemas import BradycardiaAssessment, LLMOutput, NeonatalAlert, SignalAssessment
from src.agent.specialists.brady_agent import brady_agent_node
from src.agent.specialists.clinical_agent import clinical_agent_node
from src.agent.specialists.protocol_agent import protocol_agent_node
from src.agent.specialists.signal_agent import signal_agent_node
from src.pipeline.result import PipelineResult


class MultiAgentState(TypedDict):
    """State schema for the multi-agent graph."""

    patient_id: str
    pipeline_result: Optional[PipelineResult]
    run_brady: Optional[bool]  # routing flag set by supervisor_node
    rag_context: Optional[list[str]]  # kept for compat with assemble_alert_node
    signal_assessment: Optional[SignalAssessment]
    bradycardia_assessment: Optional[BradycardiaAssessment]
    past_alerts: Optional[list[PastAlert]]
    llm_output: Optional[LLMOutput]
    self_check_passed: Optional[bool]
    final_alert: Optional[NeonatalAlert]
    error: Optional[str]


@traceable(name="supervisor_node")
def supervisor_node(state: dict) -> dict:
    """Run the ONNX pipeline and determine specialist routing.

    Sets run_brady=True if bradycardia events present OR any z-score abs > 2.0.
    This mirrors the project plan routing logic exactly.
    """
    synthetic = os.environ.get("_SYNTHETIC_RESULT")
    if synthetic:
        import pickle
        try:
            result = pickle.loads(bytes.fromhex(synthetic))
        except Exception as exc:
            raise RuntimeError(f"_SYNTHETIC_RESULT could not be deserialised: {exc}") from exc
    else:
        from src.pipeline.runner import NeonatalPipeline
        result = NeonatalPipeline().run(state["patient_id"])

    max_z = max(abs(z) for z in result.z_scores.values()) if result.z_scores else 0.0
    run_brady = len(result.detected_events) > 0 or max_z > 2.0
    past = EpisodicMemory().get_recent(state["patient_id"], n=7)

    return {
        "pipeline_result": result,
        "run_brady": run_brady,
        "past_alerts": past,
        "rag_context": [],  # filled by specialists; kept for NeonatalAlert compat
    }


def _route_brady(state: dict) -> str:
    """Conditional edge: route to brady specialist or skip directly to clinical."""
    return "brady" if state.get("run_brady") else "clinical"


@traceable(name="assemble_multi_node")
def assemble_multi_node(state: dict) -> dict:
    """Assemble the final NeonatalAlert and persist with specialist outputs to audit.db."""
    result = state["pipeline_result"]
    llm_out = state["llm_output"]
    sa = state.get("signal_assessment")
    ba = state.get("bradycardia_assessment")

    top_one = result.get_top_deviated(1)
    top_feature_name = top_one[0].name if top_one else "none"
    top_feature_z = top_one[0].z_score if top_one else 0.0

    alert = NeonatalAlert(
        patient_id=result.patient_id,
        timestamp=datetime.now(),
        concern_level=llm_out.concern_level,
        risk_score=result.risk_score,
        primary_indicators=llm_out.primary_indicators,
        clinical_reasoning=llm_out.clinical_reasoning,
        recommended_action=llm_out.recommended_action,
        confidence=llm_out.confidence,
        retrieved_context=state.get("rag_context") or [],
        self_check_passed=state.get("self_check_passed", True),
        protocol_compliant="PROTOCOL FLAG" not in llm_out.recommended_action,
        past_similar_events=len(state.get("past_alerts") or []),
        z_scores=result.z_scores,
    )

    EpisodicMemory().save(
        alert,
        top_feature_name,
        top_feature_z,
        z_scores=result.z_scores,
        hrv_values=result.hrv_values,
        signal_pattern=sa.autonomic_pattern if sa else None,
        signal_confidence=sa.confidence if sa else None,
        brady_classification=ba.classification if ba else None,
        brady_weight=ba.clinical_weight if ba else None,
        agent_version="multi_agent",
    )
    return {"final_alert": alert}


def build_multi_agent_graph():
    """Compile the 7-node multi-agent supervisor graph."""
    g = StateGraph(MultiAgentState)

    g.add_node("supervisor", supervisor_node)
    g.add_node("signal", signal_agent_node)
    g.add_node("brady", brady_agent_node)
    g.add_node("clinical", clinical_agent_node)
    g.add_node("protocol", protocol_agent_node)
    g.add_node("assemble_multi", assemble_multi_node)

    g.set_entry_point("supervisor")
    g.add_edge("supervisor", "signal")
    g.add_conditional_edges("signal", _route_brady, {"brady": "brady", "clinical": "clinical"})
    g.add_edge("brady", "clinical")
    g.add_edge("clinical", "protocol")
    g.add_edge("protocol", "assemble_multi")
    g.add_edge("assemble_multi", END)

    return g.compile()
