"""The Assessor seam — the single interface every tier implements.

A ``Protocol`` (structural typing) means anything with an ``assess`` method of the
right shape is an Assessor: the three real tiers, and any fake a test injects. This
is the seam the whole architecture turns on — one interface, tested from both sides.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.assessment.types import Assessment, AssessmentContext


@runtime_checkable
class Assessor(Protocol):
    """Produces an Assessment from the current evidence. The tiers are its adapters."""

    def assess(self, context: AssessmentContext) -> Assessment: ...


@runtime_checkable
class SoftFloorArbiter(Protocol):
    """A tier structurally authorised to quiet a SOFT single-feature Safety Floor (ADR-0003).

    The two-level floor lets a *single-feature* YELLOW (the quietable SOFT floor) be lowered to
    GREEN — but only by a calibrated, auditable, self-correcting tier, **never** by the LLM. That
    authority is a **capability of the tier**, declared once at class level, not a per-window
    ``may_quiet`` bool that any tier could set on its Assessment. The ``VerdictCascade`` honours
    ``may_quiet`` *only* from a tier holding this capability — so "only the deterministic Tier 2
    may quiet, never the LLM" is enforced by type, not by a docstring or the luck of tier ordering.
    A rogue tier (a future RAG that sets ``may_quiet``) cannot quiet the floor: claiming the
    authority means declaring ``quiets_soft_floor = True`` at class level, a reviewable act.

    Composition note: this is a marker capability layered *on top of* ``Assessor`` — an arbiter is
    still an ordinary tier whose ``assess`` returns the ``may_quiet`` decision for the window; the
    capability only governs whether that decision is trusted.
    """

    #: Declared ``True`` by the (single) tier permitted to quiet the SOFT floor — the calibrated,
    #: gated Tier 2 CUSUM. Absent / False on every other tier (Tier 1 floor, the RAG/LLM Tier 3).
    quiets_soft_floor: bool


@runtime_checkable
class Observational(Protocol):
    """A tier that *watches* the stream but never speaks for the Verdict (#59).

    The mirror image of ``SoftFloorArbiter``: where that capability *grants* a narrow
    authority, this one **renounces** all of it. An observational tier's Assessment rides in
    ``Verdict.assessments`` — so the trace, the demo, and any later calibration study see its
    signal on every window — but the cascade excludes it from the Safety Floor, the composed
    level, ``escalated_by``, and the headline. It cannot raise a verdict, lower one, or colour
    the rationale a clinician reads.

    **Why this is a cascade-enforced capability and not a tier-side promise.** The JEPA
    Surprise tier already pins ``level=GREEN`` and ``may_quiet=False`` itself, which keeps it
    out of the *level*. That is not enough: the headline is chosen by
    ``max(assessments, key=(level, risk))``, so a GREEN tier reporting a high ``risk`` silently
    captures the Verdict's ``risk``, ``confidence``, ``rationale``, ``recommended_action``,
    ``primary_indicators`` and ``citations`` — every human-facing field except the level. A
    learned tier that renounces the wheel must not keep its hand on the dashboard. Declaring
    the capability at class level makes "this tier is observational" a reviewable act, and
    makes the guarantee hold even if the tier's own discipline regresses.
    """

    #: Declared ``True`` by a tier that contributes signal for the trace but never votes.
    observational: bool
