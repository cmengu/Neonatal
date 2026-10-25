"""The ONNX→cascade runtime cutover (issue #7).

Locks the post-#7 invariants: the runtime is served by the ``VerdictCascade`` (no ONNX,
no ``risk_score``), the Tier-3 view is deterministic and stateless, and CUSUM composes
exactly once. Uses fake tiers / a fake RAG graph — no Groq, Qdrant, or ONNX.
"""
from __future__ import annotations

from types import SimpleNamespace

from src.assessment.cusum import InMemoryCusumStore
from src.assessment.runtime import default_cascade, viewed
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
                recommended_action="Notify attending neonatologist",
                primary_indicators=["rmssd"],
                retrieved_context=["NICE NG195 — fake citation"],
            )
        }


def test_viewed_is_deterministic_tier1_and_carries_no_risk_score():
    # #28: the Tier-3 read is the *same* AssessmentContext carrier, enriched in place —
    # not a second AssessmentView type. viewed() fills the deterministic Tier-1 level/risk.
    ctx = AssessmentContext(patient_id="p", z_scores={"sdnn": -3.0, "rmssd": -3.0})
    view = viewed(ctx)
    assert isinstance(view, AssessmentContext)
    assert view.level == "RED"  # two concordant pathological features → HARD floor
    assert 0.0 <= view.risk <= 1.0
    assert not hasattr(view, "risk_score")  # the ONNX field is gone
    # The input is left untouched — enrichment returns a copy.
    assert ctx.level is None


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


def test_view_from_state_uses_injected_context_without_a_disk_read():
    # #24: a threaded AssessmentContext drives the Tier-3 view — the window is NOT re-read from
    # disk. z-scores that exist nowhere on disk still surface, proving Tier 3 sees exactly the
    # window Tiers 1-2 saw (no divergence if the CSV changed mid-assessment).
    from src.assessment.runtime import view_from_state

    ctx = AssessmentContext(
        patient_id="synthetic-not-on-disk", z_scores={"rmssd": -2.7, "sdnn": -2.3}
    )
    view = view_from_state({"patient_id": ctx.patient_id, "context": ctx})
    assert view.patient_id == "synthetic-not-on-disk"
    assert view.z_scores == {"rmssd": -2.7, "sdnn": -2.3}


def test_view_from_state_falls_back_to_load_when_no_context(monkeypatch):
    # Standalone callers (SSE stream / eval / A-B generalist) invoke the graph with only a
    # patient_id — no context to thread — so the view is loaded by patient_id, still correct.
    import src.assessment.runtime as rt

    seen = {}
    monkeypatch.setattr(
        rt, "viewed_for_patient",
        lambda pid: seen.__setitem__("pid", pid) or "LOADED_VIEW",
    )
    assert rt.view_from_state({"patient_id": "infant1"}) == "LOADED_VIEW"
    assert seen["pid"] == "infant1"
