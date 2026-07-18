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

import logging

from src.assessment.cascade import VerdictCascade
from src.assessment.context import load_context, personal_baseline
from src.assessment.cusum import SqliteCusumStore, TemporalAssessor
from src.assessment.deviation import DeviationAssessor
from src.assessment.jepa_surprise import JepaSurpriseAssessor
from src.assessment.rag import RagVerdictAssessor
from src.assessment.types import AssessmentContext, Verdict

logger = logging.getLogger(__name__)


def default_cascade(cusum_store=None, rag_graph=None, jepa=None) -> VerdictCascade:
    """The production cascade: deterministic floor + CUSUM drift + RAG (escalate-only),
    plus the **observational** JEPA world-model tier (#59).

    ``cusum_store`` defaults to the persisted ``SqliteCusumStore`` (``data/audit.db``) so
    drift survives restarts; inject ``InMemoryCusumStore`` / a fake for tests. ``rag_graph``
    is passed through to the RAG tier so tests can inject a fake graph (no Groq/Qdrant).

    **Why the world model ships observational, not voting.** Its onset-anticipation AUC of
    0.758 is held-out and label-free, but it is a 10-infant result with no calibrated alarm
    operating point — and the PICS stream carries no sepsis labels at all, so "departure from
    this infant's learned normal" is the only thing it has ever been scored on. That earns it a
    seat in every Verdict's ``assessments`` (the trace, the demo, and any future calibration
    study now see its Surprise on every window) and nothing more. The ``Observational``
    capability makes that structural: the cascade excludes it from the floor, the composed
    level, ``escalated_by`` and the headline, so wiring it in here cannot change a single
    clinician-facing field.

    **Degradation.** A missing or unreadable checkpoint omits the tier with a warning rather
    than failing the assessment: a watcher that contributes nothing to the verdict by
    construction must never be able to take the safety-critical path down with it. Pass
    ``jepa`` to inject a model (tests) or a pre-built assessor.
    """
    tiers = [
        DeviationAssessor(),
        TemporalAssessor(store=cusum_store or SqliteCusumStore()),
    ]
    observer = jepa if jepa is not None else _load_jepa_tier()
    if observer is not None:
        tiers.append(observer)
    tiers.append(RagVerdictAssessor(graph=rag_graph))
    return VerdictCascade(tiers)


def _load_jepa_tier() -> JepaSurpriseAssessor | None:
    """Build the observational world-model tier, or ``None`` if its checkpoint is unusable."""
    try:
        return JepaSurpriseAssessor()
    except Exception as exc:  # missing / corrupt / shape-mismatched checkpoint
        logger.warning(
            "JEPA observational tier unavailable (%s: %s) — the cascade runs without it; "
            "verdicts are unaffected because the tier never votes.",
            type(exc).__name__,
            exc,
        )
        return None


def assess_patient(patient_id: str, cascade: VerdictCascade | None = None) -> Verdict:
    """Assess one patient's latest window through the Verdict Cascade → a single Verdict."""
    cascade = cascade if cascade is not None else default_cascade()
    return cascade.assess(load_context(patient_id))


def viewed(context: AssessmentContext) -> AssessmentContext:
    """Return the context enriched with its deterministic Tier-1 read — the Tier-3 input.

    Collapses the old ``AssessmentContext`` → ``AssessmentView`` bridge (#28): instead of
    copying the window into a second type, this fills the *same* carrier's derived fields —
    the Tier-1 ``level`` (as a string) / ``risk`` from the stateless ``DeviationAssessor`` and
    the per-infant ``personal_baseline``. Stateless — deliberately does NOT run the Tier-2
    CUSUM (that composes once at the cascade), so calling it inside the RAG graph is
    side-effect free and cannot double-count drift. Returns a copy; the input is left untouched.
    """
    dev = DeviationAssessor().assess(context)
    return context.model_copy(
        update={
            "level": dev.level.value,
            "risk": dev.risk,
            "personal_baseline": personal_baseline(context.patient_id),
        }
    )


def viewed_for_patient(patient_id: str) -> AssessmentContext:
    """Convenience: load a real patient's context and enrich it with the Tier-3 read."""
    return viewed(load_context(patient_id))


def view_from_state(state: dict) -> AssessmentContext:
    """Enrich the Tier-3 input from the ``AssessmentContext`` the cascade already holds (#24).

    The cascade loads the window once and threads it in under ``state["context"]``; using it
    here deletes Tier 3's second disk read and guarantees the LLM tier reasons over the **same
    window** Tiers 1-2 saw (no divergence if the CSV changed mid-assessment). Standalone callers
    that invoke the graph with only ``patient_id`` (the SSE stream, eval, the A/B generalist)
    have no context to thread, so they fall back to a load — still correct, just not deduped.

    Either way this stays stateless: ``viewed`` runs only Tier 1, never the Tier-2 CUSUM,
    so the CUSUM-once invariant the cascade owns is untouched.
    """
    context = state.get("context")
    if context is not None:
        return viewed(context)
    return viewed_for_patient(state["patient_id"])
