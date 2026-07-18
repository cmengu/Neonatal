"""Candidate C — concern level has one home (the Verdict Cascade), not the graph.

`self_check_node` used to own verdict *policy*: a deterministic RED override on a stale
ONNX-era threshold (`risk > 0.8 and max_z > 3.0`) and an LLM self-check that could revise
the level down. Both are retired — the graph emits reasoning only; the Safety Floor and the
escalate-only rule live solely in `src/assessment/cascade.py`. These tests pin that the node
no longer touches the concern level, so the "level decided in ≥4 places" duplication is gone.
"""
import os

os.environ.setdefault("EVAL_NO_LLM", "1")
os.environ.setdefault("QDRANT_PATH", "qdrant_local")

from src.agent.graph import self_check_node
from src.agent.schemas import LLMOutput
from src.agent.state import AssessmentView


def _view(level: str, risk: float, z_scores: dict[str, float]) -> AssessmentView:
    return AssessmentView(
        patient_id="infant_test",
        level=level,
        risk=risk,
        z_scores=z_scores,
        hrv_values={},
    )


def _llm_output(level: str) -> LLMOutput:
    return LLMOutput(
        concern_level=level,
        primary_indicators=["sdnn"],
        clinical_reasoning="Deterministic Tier-1 read over the patient's own baseline deviations.",
        recommended_action="Continue routine monitoring",
        confidence=0.9,
    )


def test_self_check_does_not_escalate_on_stale_threshold():
    """The retired stale floor would have forced RED here (risk > 0.8, max_z > 3.0);
    now the node leaves the LLM's level untouched — escalation is the cascade's job."""
    out = _llm_output("GREEN")
    state = {
        "llm_output": out,
        "pipeline_result": _view("RED", risk=0.95, z_scores={"sdnn": -4.0, "sample_asymmetry": 3.5}),
    }

    result = self_check_node(state)

    # The node reports the self-check ran but never rewrites the level.
    assert result == {"self_check_passed": True}
    # It did not mutate the LLMOutput object in place either.
    assert out.concern_level == "GREEN"
    assert "OVERRIDDEN" not in out.clinical_reasoning


def test_self_check_does_not_lower_level():
    """A RED from the LLM is not talked down by the graph — an LLM never lowers concern
    (ADR-0001/0003); only the calibrated cascade may quiet, never here."""
    out = _llm_output("RED")
    state = {
        "llm_output": out,
        "pipeline_result": _view("GREEN", risk=0.1, z_scores={"sdnn": 0.2}),
    }

    result = self_check_node(state)

    assert result == {"self_check_passed": True}
    assert out.concern_level == "RED"
