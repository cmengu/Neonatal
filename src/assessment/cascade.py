"""The Verdict Cascade — the one place the verdict policy lives.

Runs the tiers, takes the Safety Floor from the deviation tier, and merges into a
single Verdict. Per ADR-0001 the Verdict is never below the floor.

Composition (ADR-0001): the verdict is never below the Safety Floor (Tier 1's
deterministic minimum), and any tier may escalate above it. As of #4 the second tier
is real — the deterministic CUSUM ``TemporalAssessor`` (``source="temporal"``) — so a
gradual Drift now escalates the verdict even when no single window trips the floor.

Tier 3 (RAG / LLM, ``source="rag"``) is governed by two extra rules, added in #5:

- **Escalate-only** — a ``rag`` Assessment may raise the verdict above the merged
  Tier 1 + Tier 2 level, but may *never* lower it. ADR-0003 settles the fork #4 left
  open: Tier 2 does not quiet Tier 3, and Tier 3 never quiets anything — the only quiet
  in the cascade is Tier 2's gated quiet of the SOFT floor (#14). An LLM is never trusted
  to talk clinical concern down.
- **Short-circuit** — the expensive LLM tier is skipped entirely when the merged
  Tier 1 + Tier 2 level is GREEN (the common calm case), so it never runs on a clean
  window. The cascade identifies the rag tier structurally, via its ``source`` attribute,
  so it can skip it *without invoking it*.

The floor rule encodes the *safe* half of ADR-0001's asymmetric de-escalation: a temporal
Assessment *below* the floor is clamped up to it. The two-level (HARD/SOFT) floor and Tier
2's gated quiet-to-GREEN of a SOFT single-feature YELLOW are ADR-0003 / #14, not here.
"""
from __future__ import annotations

from collections.abc import Sequence

from src.assessment.assessor import Assessor
from src.assessment.types import Assessment, AssessmentContext, ConcernLevel, Verdict, most_severe

RAG_SOURCE = "rag"


class VerdictCascade:
    """Composes tier Assessments into one Verdict under the Safety Floor rule."""

    def __init__(
        self,
        tiers: Sequence[Assessor],
        floor_source: str = "deviation",
        rag_source: str = RAG_SOURCE,
    ) -> None:
        if not tiers:
            raise ValueError("VerdictCascade needs at least one tier")
        self._tiers = list(tiers)
        self._floor_source = floor_source
        self._rag_source = rag_source

    def _is_rag(self, tier: Assessor) -> bool:
        """Identify the escalate-only, skippable Tier 3 *without* invoking it.

        Reads an optional ``source`` attribute on the tier object; a tier that doesn't
        declare one is treated as an always-run tier (backward-compatible).
        """
        return getattr(tier, "source", None) == self._rag_source

    def assess(self, context: AssessmentContext) -> Verdict:
        # Always-run tiers (Tier 1 + Tier 2). The rag tier is deferred so it can be
        # skipped on a clean window without paying for the LLM.
        base_tiers = [t for t in self._tiers if not self._is_rag(t)]
        rag_tiers = [t for t in self._tiers if self._is_rag(t)]

        assessments: list[Assessment] = [t.assess(context) for t in base_tiers]

        # Safety Floor: the deterministic minimum from the deviation tier.
        floor = most_severe(
            *[a.level for a in assessments if a.source == self._floor_source]
        )
        # Merged Tier 1 + Tier 2 level — never below the floor.
        base_level = most_severe(*[a.level for a in assessments], floor)

        # Tier 3 short-circuit: skip the LLM entirely when the calm case is GREEN.
        if rag_tiers and base_level > ConcernLevel.GREEN:
            assessments += [t.assess(context) for t in rag_tiers]

        # Escalate-only: any rag level below base_level is discarded by ``most_severe``
        # (it can raise, never lower). The floor stays un-lowerable by construction.
        level = most_severe(*[a.level for a in assessments], floor)
        escalated_by = [a.source for a in assessments if a.level > floor]

        # Headline (risk / rationale / confidence) comes from the most severe assessment.
        headline = max(assessments, key=lambda a: (a.level, a.risk))

        return Verdict(
            patient_id=context.patient_id,
            level=level,
            risk=headline.risk,
            confidence=headline.confidence,
            rationale=headline.rationale,
            safety_floor=floor,
            assessments=assessments,
            escalated_by=escalated_by,
        )
