"""Tier 3 — the RAG Assessor (#5).

Wraps the existing multi-agent LangGraph (``src.agent.graph.multi_agent`` — supervisor +
specialists + hybrid RAG) behind the ``Assessor`` seam, so the guideline-grounded rationale
becomes one more Assessment the ``VerdictCascade`` composes.

Two cascade-level rules govern this tier (enforced in ``cascade.py``, not here):
- **escalate-only** — it may raise concern but never lower it (ADR-0001 / ADR-0003); and
- **short-circuit** — it is skipped entirely on a clean GREEN window.

The cascade identifies this tier by its ``source`` attribute (``"rag"``) so it can skip the
expensive LLM without invoking it. The graph is injectable so the seam is testable with a
fake — no Groq / Qdrant / ONNX in unit tests.

Guideline grounding (see ``docs/research/rag-guideline-grounding-neonatal-sepsis.md``): the
wrapped graph's clinical vocabulary and actions are grounded in NICE NG195 + AAP/COFN preterm;
the HRV→risk inference is grounded only by HeRO/HRC *as an adjunct*, never a diagnosis. Tier 3's
honest output is a retrieved, cited, escalate-only prompt for clinician review.
"""
from __future__ import annotations

from typing import Any

from src.assessment.types import Assessment, AssessmentContext, ConcernLevel


class RagVerdictAssessor:
    """Adapts the multi-agent RAG graph to the ``Assessor`` Protocol (``source="rag"``)."""

    #: Read by ``VerdictCascade`` to identify this tier as escalate-only + skippable
    #: *without* invoking it. Must stay in sync with ``cascade.RAG_SOURCE``.
    source = "rag"

    def __init__(self, graph: Any | None = None) -> None:
        # Lazily bound: importing ``multi_agent`` pulls in Groq/Qdrant, so defer it until
        # the tier actually runs (and let tests inject a fake graph instead).
        self._graph = graph

    def _get_graph(self) -> Any:
        if self._graph is None:
            from src.agent.graph import multi_agent

            self._graph = multi_agent
        return self._graph

    def assess(self, context: AssessmentContext) -> Assessment:
        state = self._get_graph().invoke({"patient_id": context.patient_id})
        alert = state["final_alert"]
        return Assessment(
            level=ConcernLevel(alert.concern_level),
            risk=alert.risk_score,
            confidence=alert.confidence,
            rationale=alert.clinical_reasoning,
            source=self.source,
        )
