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

The Safety Floor is **two-level** (ADR-0003 / #14):

- **HARD floor** — RED / ≥2-concordant Tier 1 signals. Un-lowerable by any tier, ever (the
  FNR=0 guarantee).
- **SOFT floor** — a single-feature YELLOW the deviation tier flags (``soft_floor=True``). A
  calibrated, gated **Tier 2** may quiet it to GREEN (``may_quiet=True``) — never the LLM,
  never RED. The quiet is provisional: the deterministic CUSUM re-escalates if the drift
  persists, so a wrong quiet costs bounded delay, never a silent omission (fail-safe defaults
  in the time domain). ADR-0003 also settles #4's fork: Tier 2 does not quiet Tier 3, and
  Tier 3 does not quiet anything — the only quiet in the cascade is Tier 2's quiet of the
  SOFT floor.

The deviation tier speaks to the verdict *only* through the floor; temporal Drift and the
rag tier escalate above it. ``Verdict = max( effective_floor, temporal↑, rag↑ )``.
"""
from __future__ import annotations

from collections.abc import Sequence

from src.assessment.assessor import Assessor, Observational, SoftFloorArbiter
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

    @staticmethod
    def _can_quiet_soft_floor(tier: Assessor) -> bool:
        """Whether ``tier`` *structurally* holds soft-floor-quieting authority (#27).

        The quiet is the one direction (lowering) that must never be granted by an
        untrusted tier, so authority is a capability of the tier object — a
        ``SoftFloorArbiter`` (the calibrated, self-correcting Tier 2 CUSUM), declared at
        class level — not a ``may_quiet`` bool read from any Assessment. This turns the
        ADR-0003 invariant "only Tier 2 may quiet, never the LLM" from a docstring into a
        type property: a rogue tier that sets ``may_quiet`` but does not hold the capability
        is ignored, regardless of tier ordering.
        """
        return isinstance(tier, SoftFloorArbiter) and tier.quiets_soft_floor

    @staticmethod
    def _is_observational(tier: Assessor) -> bool:
        """Whether ``tier`` watches without voting (#59) — see ``Observational``.

        Structural, like the soft-floor capability: read from a class-level attribute, so a
        tier that renounces the vote is excluded from the floor, the level, ``escalated_by``
        *and* the headline regardless of what its Assessment claims. Its Assessment still
        rides in ``Verdict.assessments`` for the trace.
        """
        return isinstance(tier, Observational) and tier.observational

    def assess(self, context: AssessmentContext) -> Verdict:
        # Always-run tiers (Tier 1 + Tier 2). The rag tier is deferred so it can be
        # skipped on a clean window without paying for the LLM.
        base_tiers = [t for t in self._tiers if not self._is_rag(t)]
        rag_tiers = [t for t in self._tiers if self._is_rag(t)]

        # Pair each base assessment with its producing tier so a soft-floor quiet can be
        # honoured *only* from the tier that structurally holds the authority (#27), not from
        # any tier that happens to set ``may_quiet`` on its Assessment.
        base_results: list[tuple[Assessor, Assessment]] = [
            (t, t.assess(context)) for t in base_tiers
        ]
        assessments: list[Assessment] = [a for _t, a in base_results]

        # Observational tiers (#59) watch but never vote: their Assessment stays in
        # ``assessments`` (the trace / demo / future calibration study see every window) but is
        # excluded from *every* verdict computation below — floor, level, escalation, headline.
        # Splitting here, structurally, is what makes "observational" mean observational: the
        # headline is picked by (level, risk), so a GREEN-but-high-risk watcher would otherwise
        # capture the Verdict's risk, confidence and rationale without ever touching its level.
        voting: list[Assessment] = [a for t, a in base_results if not self._is_observational(t)]

        # --- Two-level Safety Floor (ADR-0003 / #14) ---
        floor_assessments = [a for a in voting if a.source == self._floor_source]
        # HARD floor: everything the deviation tier raises that is *not* a quietable SOFT
        # floor (RED / ≥2 concordant). Un-lowerable — the FNR=0 guarantee.
        hard_floor = most_severe(*[a.level for a in floor_assessments if not a.soft_floor])
        # SOFT floor: a single-feature YELLOW the deviation tier flagged as quietable.
        soft_floor_level = most_severe(
            *[a.level for a in floor_assessments if a.soft_floor]
        )
        # A calibrated, gated Tier 2 (never the LLM) may quiet the SOFT floor to GREEN — and only
        # a tier that STRUCTURALLY holds quieting authority (a ``SoftFloorArbiter``) is trusted to
        # grant it. A rogue tier that sets ``may_quiet`` without the capability is ignored (#27).
        gated_quiet = any(
            a.may_quiet
            for tier, a in base_results
            if self._can_quiet_soft_floor(tier) and not self._is_observational(tier)
        )
        soft_contribution = (
            ConcernLevel.GREEN if gated_quiet else soft_floor_level
        )
        effective_floor = most_severe(hard_floor, soft_contribution)

        # Non-floor tiers (temporal Drift, and rag after the short-circuit) may escalate
        # *above* the effective floor; the deviation tier speaks only through the floor.
        non_floor = [a for a in voting if a.source != self._floor_source]
        base_level = most_severe(effective_floor, *[a.level for a in non_floor])

        # Tier 3 short-circuit: skip the LLM entirely when the merged calm case is GREEN.
        # ``base_level`` excludes observational tiers, so a watcher can never provoke LLM spend.
        if rag_tiers and base_level > ConcernLevel.GREEN:
            rag_assessments = [t.assess(context) for t in rag_tiers]
            assessments += rag_assessments
            non_floor += rag_assessments
            voting += rag_assessments

        # Escalate-only: any escalating tier can raise above the floor but never lower it
        # (``most_severe``); the effective floor is the un-lowerable minimum. A quieted SOFT
        # YELLOW settles to GREEN here — but only because a deterministic gated Tier 2, not
        # an LLM, granted it, and the deterministic CUSUM re-escalates if the drift persists.
        level = most_severe(effective_floor, *[a.level for a in non_floor])
        escalated_by = [a.source for a in non_floor if a.level > effective_floor]

        # Headline (risk / rationale / confidence) comes from the most severe *voting*
        # assessment. Observational tiers are excluded: they are GREEN by construction, so on a
        # calm window they would tie every other tier on level and win on risk alone — handing a
        # watcher the clinician-facing rationale. ``or assessments`` keeps a degenerate
        # all-observational cascade from raising on an empty ``max``.
        headline = max(voting or assessments, key=lambda a: (a.level, a.risk))

        return Verdict(
            patient_id=context.patient_id,
            level=level,
            risk=headline.risk,
            confidence=headline.confidence,
            rationale=headline.rationale,
            safety_floor=effective_floor,
            assessments=assessments,
            escalated_by=escalated_by,
            # Surface the headline tier's traceable detail on the Verdict (#23) so a caller
            # reading only the Verdict recovers the action, indicators, and citations without
            # bypassing the cascade. The headline is the most severe assessment — the one whose
            # rationale/risk already drives the Verdict — so its detail is the coherent choice.
            recommended_action=headline.recommended_action,
            primary_indicators=list(headline.primary_indicators),
            citations=list(headline.citations),
        )
