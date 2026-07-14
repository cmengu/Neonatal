"""Scenarios for the NeonatalGuard **routing gate** (issue #7).

⚠️ This is a ROUTING / PLUMBING gate, **not** a clinical-accuracy metric. Each scenario
injects fake per-tier ``Assessment`` levels into the real ``VerdictCascade`` and asserts the
*composed* ``Verdict`` level. It verifies the cascade wiring — Safety-Floor composition
(ADR-0001), the HARD/SOFT two-level floor + gated quiet (ADR-0003/#14), Tier-3 escalate-only,
and the GREEN short-circuit (#5) — **not** whether any tier is clinically correct. The old
version derived the expected label from an ONNX ``risk_score`` (circular) and injected a
synthetic ``PipelineResult`` via the ``_SYNTHETIC_RESULT`` env-var pickle; #7 retired both.

Injection is now at the ``Assessor`` seam: a ``FakeAssessor`` per tier (the pattern from
``tests/test_verdict_cascade.py``), so no ONNX, no Groq, no Qdrant, no env-var pickle.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.assessment.cascade import VerdictCascade
from src.assessment.types import Assessment, AssessmentContext, ConcernLevel


class FakeAssessor:
    """A deterministic tier stub — returns a fixed level for a given ``source``.

    Mirrors the ``FakeAssessor`` seam pattern in the unit tests: it lets the eval drive the
    real cascade composition without invoking any tier's real machinery (ONNX/LLM/Qdrant).
    """

    def __init__(
        self,
        source: str,
        level: ConcernLevel,
        *,
        soft_floor: bool = False,
        may_quiet: bool = False,
    ) -> None:
        self.source = source
        self._level = level
        self._soft_floor = soft_floor
        self._may_quiet = may_quiet

    def assess(self, context: AssessmentContext) -> Assessment:
        return Assessment(
            level=self._level,
            risk=1.0 if self._level == ConcernLevel.RED else 0.5,
            confidence=1.0,
            rationale=f"[routing-gate fake] {self.source} → {self._level.value}",
            source=self.source,
            soft_floor=self._soft_floor,
            may_quiet=self._may_quiet,
        )


@dataclass
class Scenario:
    """One routing-gate scenario: the per-tier levels to inject and the expected verdict.

    ``floor``/``temporal``/``rag`` are the levels the (faked) Tier-1/2/3 report; ``expected``
    is the composed ``Verdict`` level the cascade must produce. ``soft_floor``/``may_quiet``
    exercise the ADR-0003 gated-quiet path.
    """

    patient_id: str
    floor: str
    temporal: str
    rag: str
    expected: str
    desc: str
    soft_floor: bool = False
    may_quiet: bool = False


def _lvl(name: str) -> ConcernLevel:
    return ConcernLevel(name)


def build_cascade(s: Scenario) -> VerdictCascade:
    """A cascade wired with this scenario's three fake tiers (deviation / temporal / rag)."""
    return VerdictCascade(
        [
            FakeAssessor("deviation", _lvl(s.floor), soft_floor=s.soft_floor),
            FakeAssessor("temporal", _lvl(s.temporal), may_quiet=s.may_quiet),
            FakeAssessor("rag", _lvl(s.rag)),
        ]
    )


def context_for(s: Scenario) -> AssessmentContext:
    """A minimal context — the fakes ignore its contents; only ``patient_id`` matters."""
    return AssessmentContext(patient_id=s.patient_id)


# 30 scenarios exercising the composition rules. Expected follows the CASCADE RULES, not any
# risk score: verdict = max(effective_floor, temporal↑, rag↑); RAG skipped on a GREEN base;
# HARD floor un-lowerable; SOFT floor quietable only when Tier-2 grants may_quiet.
SCENARIOS: list[Scenario] = [
    # --- RED (8): the HARD floor or an escalating tier drives RED; FNR(RED)=0 by construction.
    Scenario("EVAL-RED-001", "RED", "GREEN", "GREEN", "RED", "HARD floor RED — un-lowerable"),
    Scenario("EVAL-RED-002", "RED", "YELLOW", "GREEN", "RED", "HARD floor RED dominates temporal"),
    Scenario("EVAL-RED-003", "RED", "GREEN", "RED", "RED", "HARD floor RED, RAG concurs"),
    Scenario("EVAL-RED-004", "YELLOW", "GREEN", "RED", "RED", "RAG escalates YELLOW→RED (escalate-only)", soft_floor=True),
    Scenario("EVAL-RED-005", "GREEN", "YELLOW", "RED", "RED", "temporal opens gate, RAG escalates to RED"),
    Scenario("EVAL-RED-006", "RED", "RED", "RED", "RED", "all tiers RED"),
    Scenario("EVAL-RED-007", "YELLOW", "YELLOW", "RED", "RED", "RAG escalation over YELLOW base"),
    Scenario("EVAL-RED-008", "RED", "GREEN", "YELLOW", "RED", "HARD floor RED, RAG cannot lower"),
    # --- YELLOW (8): single-feature SOFT floor or temporal drift, no RED anywhere.
    Scenario("EVAL-YEL-001", "YELLOW", "GREEN", "GREEN", "YELLOW", "SOFT floor YELLOW, no quiet", soft_floor=True),
    Scenario("EVAL-YEL-002", "GREEN", "YELLOW", "GREEN", "YELLOW", "temporal Drift YELLOW"),
    Scenario("EVAL-YEL-003", "YELLOW", "YELLOW", "GREEN", "YELLOW", "floor + temporal both YELLOW", soft_floor=True),
    Scenario("EVAL-YEL-004", "YELLOW", "GREEN", "YELLOW", "YELLOW", "RAG concurs YELLOW", soft_floor=True),
    Scenario("EVAL-YEL-005", "GREEN", "YELLOW", "YELLOW", "YELLOW", "temporal + RAG YELLOW"),
    Scenario("EVAL-YEL-006", "YELLOW", "GREEN", "GREEN", "YELLOW", "SOFT floor, Tier-2 not warmed (no quiet)", soft_floor=True),
    Scenario("EVAL-YEL-007", "GREEN", "YELLOW", "GREEN", "YELLOW", "pure drift YELLOW"),
    Scenario("EVAL-YEL-008", "YELLOW", "YELLOW", "YELLOW", "YELLOW", "all YELLOW", soft_floor=True),
    # --- GREEN (8): clean; RAG must be SHORT-CIRCUITED (never escalates a GREEN base).
    Scenario("EVAL-GRN-001", "GREEN", "GREEN", "GREEN", "GREEN", "all clean — RAG short-circuited"),
    Scenario("EVAL-GRN-002", "GREEN", "GREEN", "RED", "GREEN", "RAG skipped on GREEN base (short-circuit)"),
    Scenario("EVAL-GRN-003", "GREEN", "GREEN", "YELLOW", "GREEN", "RAG skipped on GREEN base"),
    Scenario("EVAL-GRN-004", "GREEN", "GREEN", "GREEN", "GREEN", "clean window"),
    Scenario("EVAL-GRN-005", "YELLOW", "GREEN", "GREEN", "GREEN", "SOFT floor quieted by warmed Tier-2", soft_floor=True, may_quiet=True),
    Scenario("EVAL-GRN-006", "GREEN", "GREEN", "GREEN", "GREEN", "baseline calm"),
    Scenario("EVAL-GRN-007", "YELLOW", "GREEN", "RED", "GREEN", "SOFT floor quieted → GREEN base → RAG short-circuited", soft_floor=True, may_quiet=True),
    Scenario("EVAL-GRN-008", "GREEN", "GREEN", "GREEN", "GREEN", "calm"),
    # --- HARD (6): the discriminating composition edges.
    Scenario("EVAL-HARD-RED-001", "RED", "GREEN", "GREEN", "RED", "HARD RED cannot be quieted"),
    Scenario("EVAL-HARD-RED-002", "YELLOW", "GREEN", "RED", "RED", "escalate-only RAG raises SOFT YELLOW to RED", soft_floor=True),
    Scenario("EVAL-HARD-YEL-001", "YELLOW", "GREEN", "GREEN", "YELLOW", "SOFT floor stands without a quiet grant", soft_floor=True),
    Scenario("EVAL-HARD-YEL-002", "GREEN", "YELLOW", "RED", "RED", "temporal opens gate; RAG escalates"),
    Scenario("EVAL-HARD-GRN-001", "YELLOW", "GREEN", "GREEN", "GREEN", "SOFT floor + warmed Tier-2 quiet → GREEN", soft_floor=True, may_quiet=True),
    Scenario("EVAL-HARD-GRN-002", "GREEN", "GREEN", "YELLOW", "GREEN", "RAG cannot escalate a GREEN base (short-circuit)"),
]
