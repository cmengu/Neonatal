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
