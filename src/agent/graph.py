"""NeonatalGuard LangGraph agent — full 6-node graph.

Node flow:
  pipeline -> build_query -> retrieve -> reason -> self_check -> assemble

Key design decisions:
- _is_eval_mode() is called per-node (not cached at import time), so tests that set
  os.environ["EVAL_NO_LLM"] = "1" programmatically after import are respected.
- _build_groq_client() raises RuntimeError on missing/placeholder key rather than
  silently falling through to rule-based mode in production.
- retrieve_context_node uses local on-disk Qdrant (qdrant_local/) by default,
  overridable via QDRANT_PATH env var for Docker/remote deployments.
- All six node functions are decorated with @traceable for LangSmith observability.
"""
import os
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional, TypedDict

import instructor
from dotenv import load_dotenv
from groq import Groq
from langgraph.graph import END, StateGraph
from langsmith import traceable
from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

from src.agent.memory import EpisodicMemory, PastAlert
from src.agent.schemas import LLMOutput, NeonatalAlert
from src.knowledge.knowledge_base import ClinicalKnowledgeBase
from src.pipeline.result import PipelineResult
from src.pipeline.runner import NeonatalPipeline

load_dotenv()


def _is_eval_mode() -> bool:
    """Per-call eval-mode check so programmatic os.environ changes in tests are respected.

    Checking at call-time (rather than storing a module-level boolean) means that
    Phase 4 test code that does os.environ["EVAL_NO_LLM"] = "1" after importing
    this module will correctly gate every Groq call.
    """
    return os.getenv("EVAL_NO_LLM", "").lower() in {"1", "true", "yes"}


def _build_groq_client():
    """Construct the Instructor-wrapped Groq client.

    Fails closed: if GROQ_API_KEY is missing or still the placeholder value,
    raises RuntimeError rather than returning None and silently falling back to
    rule-based output.
    """
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key or api_key == "your_groq_api_key_here":
        raise RuntimeError(
            "GROQ_API_KEY is missing or still set to the placeholder value. "
            "Set a real key in .env or export EVAL_NO_LLM=1 for non-LLM mode."
        )
    return instructor.from_groq(Groq(api_key=api_key), mode=instructor.Mode.JSON)


# Groq client initialised at import time for production efficiency.
# Per-call _is_eval_mode() checks inside each node still gate every API call,
# so setting EVAL_NO_LLM after import works correctly in programmatic tests.
_GROQ = None if _is_eval_mode() else _build_groq_client()

# ClinicalKnowledgeBase singleton — initialised once on first retrieve_context_node call.
# On-disk Qdrant uses an exclusive file lock; recreating the client on every invoke()
# triggers "Storage folder already accessed" when 24 scenarios run in a tight loop.
# Caching also avoids reloading the 90 MB SentenceTransformer model on each call.
_KB: ClinicalKnowledgeBase | None = None


def _get_groq():
    """Return the Groq client, initialising lazily if the module was first imported
    in eval mode and is now being used in live mode within the same process."""
    global _GROQ
    if _GROQ is None:
        _GROQ = _build_groq_client()
    return _GROQ


def _get_kb() -> ClinicalKnowledgeBase:
    """Return the ClinicalKnowledgeBase singleton, initialising on first call.

    Singleton avoids reloading the 90 MB SentenceTransformer + reopening the
    on-disk Qdrant file lock on every retrieve_context_node invocation.
    QDRANT_PATH is read once at first call; subsequent calls reuse the same client.
    """
    global _KB
    if _KB is None:
        _KB = ClinicalKnowledgeBase(
            path=os.getenv("QDRANT_PATH", str(REPO_ROOT / "qdrant_local"))
        )
    return _KB


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


class Verify(BaseModel):
    """Schema for the LLM self-check verification call."""

    confirmed: bool
    revised_concern_level: Literal["RED", "YELLOW", "GREEN"]
    reason: str


@traceable(name="run_pipeline_node")
def run_pipeline_node(state: AgentState) -> dict:
    """Run the ONNX pipeline and load recent alert history for the patient."""
    # Support injected synthetic PipelineResult for deterministic offline evals.
    synthetic = os.environ.get("_SYNTHETIC_RESULT")
    if synthetic:
        import pickle
        try:
            result = pickle.loads(bytes.fromhex(synthetic))
        except (ValueError, Exception) as exc:
            raise RuntimeError(
                f"_SYNTHETIC_RESULT could not be deserialised: {exc}"
            ) from exc
    else:
        result = NeonatalPipeline().run(state["patient_id"])

    past = EpisodicMemory().get_recent(state["patient_id"], n=7)
    return {"pipeline_result": result, "past_alerts": past}


@traceable(name="build_rag_query_node")
def build_rag_query_node(state: AgentState) -> dict:
    """Build a free-text RAG query from the top deviating HRV features."""
    r = state["pipeline_result"]
    top3 = r.get_top_deviated(3)
    query = (
        f"Premature neonate, {r.risk_level} risk. "
        f"HRV deviations from personal baseline: "
        + ", ".join(f"{d.name} z={d.z_score:+.1f}" for d in top3)
        + f". Bradycardia events: {len(r.detected_events)} in last 6h. "
        + f"Risk score: {r.risk_score:.2f}."
    )
    return {"rag_query": query}


@traceable(name="retrieve_context_node")
def retrieve_context_node(state: AgentState) -> dict:
    """Retrieve top-3 clinical knowledge chunks via hybrid dense+sparse search.

    Uses the on-disk Qdrant store at qdrant_local/ by default.
    Override with QDRANT_PATH env var for Docker/remote Qdrant.
    The KB singleton (_get_kb) is initialised once per process to avoid
    reloading the SentenceTransformer model and reopening the Qdrant file lock.
    """
    context = _get_kb().query(
        state["rag_query"],
        n=3,
        risk_tier=state["pipeline_result"].risk_level,
    )
    return {"rag_context": context}


@traceable(name="llm_reasoning_node")
def llm_reasoning_node(state: AgentState) -> dict:
    """Call Groq to produce a structured LLMOutput, or fall back to rule-based output.

    The rule-based path is active when EVAL_NO_LLM is set at call time.
    Checked via _is_eval_mode() — not a module-level constant — so programmatic
    env var changes in Phase 4 tests are respected.
    """
    r = state["pipeline_result"]

    if _is_eval_mode():
        return {
            "llm_output": LLMOutput(
                concern_level=r.risk_level,
                primary_indicators=[d.name for d in r.get_top_deviated(3)] or ["unknown"],
                clinical_reasoning=(
                    f"Rule-based fallback: ONNX risk score {r.risk_score:.2f}, "
                    f"{len(r.detected_events)} bradycardia events, and structured HRV deviations from baseline."
                ),
                recommended_action=(
                    "Immediate clinical review"
                    if r.risk_level == "RED"
                    else "Reassess in 2 hours"
                    if r.risk_level == "YELLOW"
                    else "Continue routine monitoring"
                ),
                confidence=0.90 if r.risk_level == "RED" else 0.75 if r.risk_level == "YELLOW" else 0.90,
            )
        }

    context = "\n\n".join(state["rag_context"] or [])
    past = state.get("past_alerts") or []

    episodic = ""
    if past:
        episodic = "Patient history (last {} alerts):\n".format(len(past))
        episodic += "\n".join(
            f"  [{a.timestamp[:10]}] {a.concern_level} - {a.top_feature} z={a.top_z_score:.1f}"
            for a in past
        )

    prompt = f"""You are a clinical decision support system for neonatal intensive care.

Patient: {r.patient_id}
ONNX risk score: {r.risk_score:.3f}

HRV z-scores (deviation from THIS PATIENT's personal baseline):
{chr(10).join(f"  {feat}: z={z:+.2f}  (actual={r.hrv_values.get(feat, 0):.1f}ms, baseline_mean={r.personal_baseline.get(feat, {}).get('mean', 0):.1f}ms)" for feat, z in r.z_scores.items())}

Bradycardia events last 6h: {len(r.detected_events)}

{episodic}

Retrieved clinical context:
{context}

Generate a structured neonatal clinical alert. Be specific about which HRV values are abnormal and why. Recommended actions must follow standard NICU protocols."""

    output: LLMOutput = _get_groq().chat.completions.create(
        model="llama-3.3-70b-versatile",
        response_model=LLMOutput,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_retries=3,
    )
    return {"llm_output": output}


@traceable(name="self_check_node")
def self_check_node(state: AgentState) -> dict:
    """Apply deterministic safety overrides and optionally ask the LLM to verify itself.

    Deterministic override: if ONNX risk > 0.8 AND max z-score > 3.0 AND the LLM
    returned anything below RED, escalate to RED unconditionally.

    LLM self-check: ask Groq to confirm or revise the concern level when
    confidence < 0.7 or the level is YELLOW (borderline cases).
    Skipped in eval mode.
    """
    out = state["llm_output"]
    r = state["pipeline_result"]
    z_vals = [abs(z) for z in r.z_scores.values()]
    max_z = max(z_vals) if z_vals else 0.0

    # Deterministic safety net — always runs regardless of eval mode.
    if r.risk_score > 0.8 and max_z > 3.0 and out.concern_level != "RED":
        out.concern_level = "RED"
        out.confidence = max(out.confidence, 0.85)
        out.clinical_reasoning += " [OVERRIDDEN: rule-based RED threshold triggered]"

    if (not _is_eval_mode()) and (out.confidence < 0.7 or out.concern_level == "YELLOW"):
        v: Verify = _get_groq().chat.completions.create(
            model="llama-3.3-70b-versatile",
            response_model=Verify,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Review neonatal alert: level={out.concern_level}, "
                        f"confidence={out.confidence:.2f}, risk_score={r.risk_score:.2f}, "
                        f"max_z_score={max_z:.1f}. "
                        "Is the concern level correct? "
                        "Reply with confirmed (true/false), revised_concern_level, and reason."
                    ),
                }
            ],
            temperature=0.1,
        )
        if not v.confirmed:
            out.concern_level = v.revised_concern_level

    return {"llm_output": out, "self_check_passed": True}


@traceable(name="assemble_alert_node")
def assemble_alert_node(state: AgentState) -> dict:
    """Assemble the final NeonatalAlert from graph state and persist to audit log."""
    result = state["pipeline_result"]
    llm_out = state["llm_output"]

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
    )

    EpisodicMemory().save(alert, top_feature_name, top_feature_z)
    return {"final_alert": alert}


def build_graph():
    """Compile the full 6-node LangGraph agent."""
    g = StateGraph(AgentState)
    g.add_node("pipeline", run_pipeline_node)
    g.add_node("build_query", build_rag_query_node)
    g.add_node("retrieve", retrieve_context_node)
    g.add_node("reason", llm_reasoning_node)
    g.add_node("self_check", self_check_node)
    g.add_node("assemble", assemble_alert_node)
    g.set_entry_point("pipeline")
    g.add_edge("pipeline", "build_query")
    g.add_edge("build_query", "retrieve")
    g.add_edge("retrieve", "reason")
    g.add_edge("reason", "self_check")
    g.add_edge("self_check", "assemble")
    g.add_edge("assemble", END)
    return g.compile()


agent = build_graph()
