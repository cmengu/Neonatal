"""NeonatalGuard LangGraph agent — 2-node starter graph.

This starter graph wires:
  pipeline -> assemble

It exists to prove state passing and memory persistence work correctly
before the RAG + LLM nodes are added in Step 3.4.

assemble_alert_node uses a rule-based stub so no Groq calls are made here.
"""
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, TypedDict

from langgraph.graph import END, StateGraph

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.agent.memory import EpisodicMemory, PastAlert
from src.agent.schemas import LLMOutput, NeonatalAlert
from src.pipeline.result import PipelineResult
from src.pipeline.runner import NeonatalPipeline


class AgentState(TypedDict):
    patient_id: str
    pipeline_result: Optional[PipelineResult]
    rag_context: Optional[list[str]]
    rag_query: Optional[str]
    past_alerts: Optional[list[PastAlert]]
    llm_output: Optional[LLMOutput]
    self_check_passed: Optional[bool]
    final_alert: Optional[NeonatalAlert]
    error: Optional[str]


def run_pipeline_node(state: AgentState) -> dict:
    """Run the ONNX pipeline for the given patient and load recent alert history."""
    # Support injected synthetic PipelineResult for deterministic offline evals.
    synthetic = os.environ.get("_SYNTHETIC_RESULT")
    if synthetic:
        import pickle
        result = pickle.loads(bytes.fromhex(synthetic))
    else:
        result = NeonatalPipeline().run(state["patient_id"])
    past = EpisodicMemory().get_recent(state["patient_id"], n=7)
    return {"pipeline_result": result, "past_alerts": past}


def assemble_alert_node(state: AgentState) -> dict:
    """Assemble and persist a NeonatalAlert.

    In the starter graph there is no llm_output, so a rule-based stub is used.
    Step 3.4 replaces this with a version that reads from llm_output.
    """
    result = state.get("pipeline_result")
    if not result:
        raise RuntimeError("PipelineResult is missing in assemble node")

    top = result.get_top_deviated(3)
    indicators = [d.name for d in top]
    # Reasoning string is deliberately long enough to pass the >=30 char validator.
    reasoning = f"Starter graph summary: risk_score={result.risk_score:.2f} with {len(indicators)} indicators."

    top_one = result.get_top_deviated(1)
    top_feature_name = top_one[0].name if top_one else "none"
    top_feature_z = top_one[0].z_score if top_one else 0.0

    alert = NeonatalAlert(
        patient_id=result.patient_id,
        timestamp=datetime.now(),
        concern_level=result.risk_level,
        risk_score=result.risk_score,
        primary_indicators=indicators,
        clinical_reasoning=reasoning,
        recommended_action="Continue routine monitoring",
        confidence=0.5,
        retrieved_context=[],
        self_check_passed=True,
        protocol_compliant=True,
        past_similar_events=len(state.get("past_alerts") or []),
    )

    EpisodicMemory().save(alert, top_feature_name, top_feature_z)
    return {"final_alert": alert}


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("pipeline", run_pipeline_node)
    g.add_node("assemble", assemble_alert_node)
    g.set_entry_point("pipeline")
    g.add_edge("pipeline", "assemble")
    g.add_edge("assemble", END)
    return g.compile()


agent = build_graph()
