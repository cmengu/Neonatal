"""The ONNX→cascade runtime cutover (issue #7).

Locks the post-#7 invariants: the runtime is served by the ``VerdictCascade`` (no ONNX,
no ``risk_score``), the Tier-3 view is deterministic and stateless, and CUSUM composes
exactly once. Uses fake tiers / a fake RAG graph — no Groq, Qdrant, or ONNX.
"""
from __future__ import annotations

from types import SimpleNamespace

from src.agent.state import AssessmentView
from src.assessment.cusum import InMemoryCusumStore
from src.assessment.runtime import build_view, default_cascade
from src.assessment.types import AssessmentContext, ConcernLevel


class _FakeGraph:
    """Stands in for the RAG multi-agent graph; records invocation count."""

    def __init__(self, level: str = "YELLOW") -> None:
        self.calls = 0
        self.level = level

    def invoke(self, state: dict) -> dict:
        self.calls += 1
        return {
            "final_alert": SimpleNamespace(
                concern_level=self.level,
                risk=0.9,
                confidence=0.8,
                clinical_reasoning="fake escalate-only RAG review of the deviation",
            )
        }


def test_build_view_is_deterministic_tier1_and_carries_no_risk_score():
    ctx = AssessmentContext(patient_id="p", z_scores={"sdnn": -3.0, "rmssd": -3.0})
    view = build_view(ctx)
    assert isinstance(view, AssessmentView)
    assert view.level == "RED"  # two concordant pathological features → HARD floor
    assert 0.0 <= view.risk <= 1.0
    assert not hasattr(view, "risk_score")  # the ONNX field is gone


def test_cascade_green_base_short_circuits_rag():
    fg = _FakeGraph("RED")
    cascade = default_cascade(cusum_store=InMemoryCusumStore(), rag_graph=fg)
    verdict = cascade.assess(AssessmentContext(patient_id="calm", z_scores={"sdnn": 0.1}))
    assert verdict.level == ConcernLevel.GREEN
    assert fg.calls == 0  # RAG never invoked on a GREEN base


def test_cascade_rag_is_escalate_only_over_soft_floor():
    fg = _FakeGraph("RED")
    cascade = default_cascade(cusum_store=InMemoryCusumStore(), rag_graph=fg)
    # single pathological feature → SOFT floor YELLOW; RAG (RED) escalates it.
    verdict = cascade.assess(AssessmentContext(patient_id="soft", z_scores={"sdnn": -3.0}))
    assert fg.calls == 1
    assert verdict.level == ConcernLevel.RED
    assert "rag" in verdict.escalated_by


def test_cascade_rag_cannot_lower_the_floor():
    fg = _FakeGraph("GREEN")  # RAG tries to say GREEN...
    cascade = default_cascade(cusum_store=InMemoryCusumStore(), rag_graph=fg)
    # ...but two concordant features set a HARD RED floor the RAG tier may never lower.
    verdict = cascade.assess(
        AssessmentContext(patient_id="hard", z_scores={"sdnn": -3.0, "rmssd": -3.0})
    )
    assert verdict.level == ConcernLevel.RED


def test_cusum_runs_once_per_assess():
    """Tier-2 CUSUM state advances exactly one update per cascade assess (no double-count)."""
    store = InMemoryCusumStore()
    fg = _FakeGraph("GREEN")
    cascade = default_cascade(cusum_store=store, rag_graph=fg)
    ctx = AssessmentContext(patient_id="drift", z_scores={"sdnn": -1.0})
    cascade.assess(ctx)
    assert store.load("drift").n_updates == 1
    cascade.assess(ctx)
    assert store.load("drift").n_updates == 2
