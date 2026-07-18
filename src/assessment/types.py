"""The currency of the Verdict Cascade — the types every tier and caller shares.

See CONTEXT.md for the domain definitions of ConcernLevel, Assessment, Verdict, and
AssessmentContext. ConcernLevel is deliberately ordered by *severity* (not
alphabetically) so the Safety Floor can be computed with ``max``.
"""
from __future__ import annotations

from enum import Enum
from functools import total_ordering
from typing import Literal

from pydantic import BaseModel, Field


@total_ordering
class ConcernLevel(Enum):
    """Triage severity of an Assessment or Verdict, ordered GREEN < YELLOW < RED.

    A plain Enum (not a str-mixin) so our severity ordering isn't shadowed by
    lexicographic string comparison. Serialises to its value ("RED", ...) under
    Pydantic ``model_dump(mode="json")``.
    """

    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"

    @property
    def _severity(self) -> int:
        return {"GREEN": 0, "YELLOW": 1, "RED": 2}[self.value]

    def __lt__(self, other: object) -> bool:
        if isinstance(other, ConcernLevel):
            return self._severity < other._severity
        return NotImplemented


def most_severe(*levels: ConcernLevel, default: ConcernLevel = ConcernLevel.GREEN) -> ConcernLevel:
    """Return the highest-severity level, or ``default`` if none are given."""
    return max(levels, default=default)


class FeatureDeviation(BaseModel):
    """Single HRV feature with its current value and z-score from personal baseline."""

    name: str
    value: float
    z_score: float
    baseline_mean: float
    baseline_std: float


class AssessmentContext(BaseModel):
    """The one carrier for a single physiological window (#28 — collapsed the former
    ``AssessmentContext`` / ``AssessmentView`` twins into one type).

    Two roles, one type:

    - **Tier input** — the raw personalised window a tier assesses. Tier 1 (Deviation)
      reads only ``z_scores``; later tiers add window history / CUSUM state. The derived
      fields below are *not* required to assess: a bare ``AssessmentContext(patient_id=...)``
      is a valid input, and the tiers ignore ``level`` / ``risk`` / ``personal_baseline``.
    - **Tier-3 view** — the enriched read the RAG graph reasons over: the same window plus
      the *deterministic Tier-1* concern level/risk and the per-infant baseline. These are
      derived (a tier produces the level *from* the window, so they cannot be required on the
      input without circularity) — hence optional, populated by ``runtime.viewed`` before the
      graph runs. This replaces the separate ``AssessmentView`` type + ``build_view`` bridge.

    ``level`` is the stateless Tier-1 concern level as a **string** ("RED"/"YELLOW"/"GREEN")
    — the currency the RAG prompts and ``LLMOutput`` already speak; ``risk`` is the Tier-1
    abnormality-departure magnitude, NOT the retired ONNX probability (ADR-0002). The
    authoritative verdict is still the cascade's composed ``Verdict``; this carrier is only
    the Tier-3 input, so it deliberately does not run the stateful CUSUM.
    """

    patient_id: str
    z_scores: dict[str, float] = Field(default_factory=dict)
    hrv_values: dict[str, float] = Field(default_factory=dict)
    # ``n_events``: count of bradycardia-suggestive windows (mean_rr > 600 ms ⇒ HR < 100).
    # Was ``detected_events`` on the old context / ``n_events`` on the old view — one name now.
    n_events: int = 0
    # --- Derived Tier-1 read (the former AssessmentView fields; optional, see class docstring) ---
    level: Literal["RED", "YELLOW", "GREEN"] | None = None
    risk: float = 0.0
    personal_baseline: dict[str, dict[str, float]] = Field(default_factory=dict)

    def get_top_deviated(self, n: int = 3) -> list[FeatureDeviation]:
        """Return the ``n`` features with the highest absolute z-score deviation."""
        deviations = [
            FeatureDeviation(
                name=feat,
                value=self.hrv_values.get(feat, 0.0),
                z_score=z,
                baseline_mean=self.personal_baseline.get(feat, {}).get("mean", 0.0),
                baseline_std=self.personal_baseline.get(feat, {}).get("std", 1.0),
            )
            for feat, z in self.z_scores.items()
        ]
        return sorted(deviations, key=lambda d: abs(d.z_score), reverse=True)[:n]


class Assessment(BaseModel):
    """One tier's judgement — the uniform currency every Assessor emits."""

    level: ConcernLevel
    risk: float
    confidence: float
    rationale: str
    source: str  # which tier produced it: "deviation" | "temporal" | "rag"
    # --- Two-level Safety Floor composition signals (ADR-0003 / #14) ---
    # ``soft_floor``: Tier 1 sets this on a *single-feature* YELLOW — the quietable SOFT
    # floor. RED / ≥2-concordant (the HARD floor) and GREEN leave it False.
    soft_floor: bool = False
    # ``may_quiet``: the calibrated deterministic Tier 2 (CUSUM) sets this when its gates
    # (warmed-up + low accumulated drift + not-recently-alarmed) permit quieting a SOFT
    # floor to GREEN this window. Only a tier that owns auditable, self-correcting state
    # ever sets it — never the LLM. The cascade grants the quiet iff both are present.
    may_quiet: bool = False
    # --- Traceable clinical detail (#23) ---
    # The actionable, human-facing detail a tier can carry alongside its concern level, so
    # the ``Assessor`` seam stops discarding the very fields the API used to bypass the
    # cascade to recover (recommended action, indicators, citations). All optional: a
    # deterministic tier populates what it can (Tier 1 names its deviating features), the
    # rag tier carries all three, and a tier with nothing to add leaves them empty.
    # ``recommended_action``: the guideline-grounded next step (rag tier; None otherwise).
    recommended_action: str | None = None
    # ``primary_indicators``: the features / observations that drove this tier's level.
    primary_indicators: list[str] = Field(default_factory=list)
    # ``citations``: traceable retrieved-guideline references backing the rationale (rag tier).
    citations: list[str] = Field(default_factory=list)


class Verdict(BaseModel):
    """The single merged judgement the clinician sees, plus the trail that produced it."""

    patient_id: str
    level: ConcernLevel
    risk: float
    confidence: float
    rationale: str
    safety_floor: ConcernLevel
    assessments: list[Assessment]
    escalated_by: list[str] = Field(default_factory=list)
    # --- Traceable clinical detail (#23) ---
    # Lifted from the headline Assessment so a caller reading only the Verdict still gets the
    # recommended action, the indicators behind the level, and the guideline citations — the
    # three things ``POST /assess`` used to bypass the cascade (running the bare LLM graph) to
    # recover. With them on the Verdict, the narrow seam no longer invites its own bypass.
    recommended_action: str | None = None
    primary_indicators: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
