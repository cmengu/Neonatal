"""RagVerdictAssessor (#5) — the Tier 3 seam, tested with a fake graph.

The point of the seam: Tier 3 is exercised like any other Assessor without touching
Groq / Qdrant / ONNX. Here a fake graph stands in for ``multi_agent``.
"""
from types import SimpleNamespace

from src.assessment.rag import RagVerdictAssessor
from src.assessment.types import AssessmentContext, ConcernLevel


class FakeGraph:
    """Stands in for the compiled ``multi_agent`` LangGraph: ``invoke`` → state dict."""

    def __init__(self, alert):
        self._alert = alert
        self.invoked_with = None

    def invoke(self, state):
        self.invoked_with = state
        return {"final_alert": self._alert}


def _alert(
    concern="YELLOW", risk=0.62, confidence=0.8, reasoning="reduced RMSSD vs baseline",
    recommended_action="Increase monitoring frequency",
    primary_indicators=("rmssd", "sdnn"),
    retrieved_context=("NICE NG195 §1.7 — sepsis risk factors",),
):
    # Mimics the fields RagVerdictAssessor reads off a NeonatalAlert.
    return SimpleNamespace(
        concern_level=concern, risk=risk, confidence=confidence,
        clinical_reasoning=reasoning,
        recommended_action=recommended_action,
        primary_indicators=list(primary_indicators),
        retrieved_context=list(retrieved_context),
    )


def test_maps_neonatal_alert_to_assessment():
    graph = FakeGraph(_alert(concern="RED", risk=0.9, confidence=0.85, reasoning="apnoeic bradycardia"))
    a = RagVerdictAssessor(graph=graph).assess(AssessmentContext(patient_id="infant3"))
    assert a.level == ConcernLevel.RED
    assert a.risk == 0.9
    assert a.confidence == 0.85
    assert a.rationale == "apnoeic bradycardia"
    assert a.source == "rag"


def test_carries_action_indicators_and_citations_through_the_seam():
    # #23: the seam must stop collapsing away the very fields the API bypassed it to recover.
    graph = FakeGraph(_alert(
        recommended_action="Blood culture and CBC with differential",
        primary_indicators=("sampen", "sample_asymmetry"),
        retrieved_context=("AAP/COFN preterm sepsis pathway", "HeRO HRC adjunct note"),
    ))
    a = RagVerdictAssessor(graph=graph).assess(AssessmentContext(patient_id="infant9"))
    assert a.recommended_action == "Blood culture and CBC with differential"
    assert a.primary_indicators == ["sampen", "sample_asymmetry"]
    assert a.citations == ["AAP/COFN preterm sepsis pathway", "HeRO HRC adjunct note"]


def test_passes_patient_id_to_the_graph():
    graph = FakeGraph(_alert())
    RagVerdictAssessor(graph=graph).assess(AssessmentContext(patient_id="infant7"))
    assert graph.invoked_with == {"patient_id": "infant7"}


def test_source_attribute_is_readable_without_invoking():
    # The cascade reads .source to skip Tier 3 without running it — so it must exist on
    # the class/instance, not only inside a produced Assessment.
    assert RagVerdictAssessor.source == "rag"
    assert getattr(RagVerdictAssessor(graph=FakeGraph(_alert())), "source", None) == "rag"


def test_satisfies_the_assessor_protocol():
    from src.assessment.assessor import Assessor
    assert isinstance(RagVerdictAssessor(graph=FakeGraph(_alert())), Assessor)
