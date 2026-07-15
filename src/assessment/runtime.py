"""The runtime entry point — the Verdict Cascade serves the live verdict (issue #7).

Before #7 the runtime flowed through the ONNX ``NeonatalPipeline``; the cascade was
test-only. This module is the cutover: ``assess_patient`` loads a real patient's context
and runs the full ``VerdictCascade`` — Tier 1 ``DeviationAssessor`` (Safety Floor) + Tier 2
``TemporalAssessor`` (CUSUM Drift) + Tier 3 ``RagVerdictAssessor`` (the guideline-grounded
RAG graph, escalate-only + short-circuited on GREEN). No ONNX, no ``risk_score``.

**Why the cascade, not the bare graph, is the entry (the CUSUM-once invariant).** Tier 2's
CUSUM is *stateful* — each ``assess`` advances persisted per-infant state. It must run
**exactly once per window**. So the cascade composes it once here; the RAG graph (Tier 3),
when it runs, reasons over a **stateless** Tier-1 view (``build_view``) and never touches
CUSUM. That keeps the drift accumulator correct while still letting the LLM tier escalate.
"""
from __future__ import annotations

from src.agent.state import AssessmentView
from src.assessment.cascade import VerdictCascade
from src.assessment.context import load_context, personal_baseline
from src.assessment.cusum import SqliteCusumStore, TemporalAssessor
from src.assessment.deviation import DeviationAssessor
from src.assessment.rag import RagVerdictAssessor
from src.assessment.types import AssessmentContext, Verdict


def default_cascade(cusum_store=None, rag_graph=None) -> VerdictCascade:
    """The production cascade: deterministic floor + CUSUM drift + RAG (escalate-only).

    ``cusum_store`` defaults to the persisted ``SqliteCusumStore`` (``data/audit.db``) so
    drift survives restarts; inject ``InMemoryCusumStore`` / a fake for tests. ``rag_graph``
    is passed through to the RAG tier so tests can inject a fake graph (no Groq/Qdrant).
    """
    return VerdictCascade(
        [
            DeviationAssessor(),
            TemporalAssessor(store=cusum_store or SqliteCusumStore()),
            RagVerdictAssessor(graph=rag_graph),
        ]
    )


def assess_patient(patient_id: str, cascade: VerdictCascade | None = None) -> Verdict:
    """Assess one patient's latest window through the Verdict Cascade → a single Verdict."""
    cascade = cascade if cascade is not None else default_cascade()
    return cascade.assess(load_context(patient_id))


def build_view(context: AssessmentContext) -> AssessmentView:
    """Build the Tier-3 (RAG) input view from a context: the deterministic **Tier-1** level +
    risk plus the personalised deviations. Stateless — deliberately does NOT run Tier-2 CUSUM
    (that composes once at the cascade), so calling this inside the RAG graph is side-effect
    free and cannot double-count drift.
    """
    dev = DeviationAssessor().assess(context)
    return AssessmentView(
        patient_id=context.patient_id,
        level=dev.level.value,
        risk=dev.risk,
        z_scores=dict(context.z_scores),
        hrv_values=dict(context.hrv_values),
        personal_baseline=personal_baseline(context.patient_id),
        n_events=context.detected_events,
    )


def build_view_for_patient(patient_id: str) -> AssessmentView:
    """Convenience: load a real patient's context and build its Tier-3 view."""
    return build_view(load_context(patient_id))


def view_from_state(state: dict) -> AssessmentView:
    """Build the Tier-3 view from the ``AssessmentContext`` the cascade already holds (#24).

    The cascade loads the window once and threads it in under ``state["context"]``; using it
    here deletes Tier 3's second disk read and guarantees the LLM tier reasons over the **same
    window** Tiers 1-2 saw (no divergence if the CSV changed mid-assessment). Standalone callers
    that invoke the graph with only ``patient_id`` (the SSE stream, eval, the A/B generalist)
    have no context to thread, so they fall back to a load — still correct, just not deduped.

    Either way this stays stateless: ``build_view`` runs only Tier 1, never the Tier-2 CUSUM,
    so the CUSUM-once invariant the cascade owns is untouched.
    """
    context = state.get("context")
    if context is not None:
        return build_view(context)
    return build_view_for_patient(state["patient_id"])
