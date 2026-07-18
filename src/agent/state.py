"""Deprecated shim — the per-window carrier collapsed into one type (#28).

The RAG graph used to reason over an ``AssessmentView`` that was a second model of the
same physiological window as ``AssessmentContext`` (z-scores, HRV values, event count),
enriched with the deterministic Tier-1 read (level, risk, baseline). Candidate G collapsed
the twins: there is now a single carrier, ``src.assessment.types.AssessmentContext``, which
carries the raw window *and* the optional derived Tier-1 read. ``runtime.viewed`` enriches a
context with that read in place of the old ``build_view`` bridge.

This module re-exports the unified names so existing imports keep working. ``AssessmentView``
remains only as a **deprecated alias** of ``AssessmentContext``; prefer importing
``AssessmentContext`` / ``FeatureDeviation`` directly from ``src.assessment.types``.
"""
from __future__ import annotations

from src.assessment.types import AssessmentContext, FeatureDeviation

# Deprecated alias (#28): the Tier-3 "view" is now just the enriched AssessmentContext.
AssessmentView = AssessmentContext

__all__ = ["AssessmentContext", "AssessmentView", "FeatureDeviation"]
