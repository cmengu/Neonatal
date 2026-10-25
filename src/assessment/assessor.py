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
