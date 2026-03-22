"""Pydantic schemas for the NeonatalGuard LangGraph agent.

LLMOutput:  Strict schema that every LLM response must conform to.
            Pydantic validators enforce clinical constraints so malformed or
            clinically unsafe LLM output is caught before the alert is finalised.

NeonatalAlert:  The final alert object persisted to SQLite and returned by the graph.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator


APPROVED_ACTIONS = [
    "Immediate clinical review",
    "Blood culture and CBC with differential",
    "Temperature and perfusion monitoring",
    "Continue routine monitoring",
    "Reassess in 2 hours",
    "Notify attending neonatologist",
    "Increase monitoring frequency to every 15 minutes",
    "Respiratory support assessment",
]


class LLMOutput(BaseModel):
    concern_level: Literal["RED", "YELLOW", "GREEN"]
    primary_indicators: list[str]
    clinical_reasoning: str
    recommended_action: str
    confidence: float

    @field_validator("confidence")
    @classmethod
    def confidence_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"confidence {v} must be between 0.0 and 1.0")
        return v

    @field_validator("primary_indicators")
    @classmethod
    def at_least_one_indicator(cls, v: list[str]) -> list[str]:
        if len(v) < 1:
            raise ValueError("must provide at least one primary indicator")
        return v[:3]

    @field_validator("clinical_reasoning")
    @classmethod
    def reasoning_substantive(cls, v: str) -> str:
        if len(v.strip()) < 30:
            raise ValueError("clinical_reasoning too short - LLM may have failed")
        return v

    @model_validator(mode="after")
    def enforce_protocol_compliance(self) -> "LLMOutput":
        """Flag any action not on the approved NICU protocol list rather than rejecting it,
        so a non-compliant LLM response is surfaced rather than causing a hard error."""
        compliant = any(
            approved.lower() in self.recommended_action.lower()
            for approved in APPROVED_ACTIONS
        )
        if not compliant:
            original = self.recommended_action
            self.recommended_action = (
                f"[PROTOCOL FLAG: non-standard action '{original}'] "
                "Notify attending neonatologist for immediate review."
            )
        return self


class NeonatalAlert(BaseModel):
    patient_id: str
    timestamp: datetime
    concern_level: Literal["RED", "YELLOW", "GREEN"]
    risk_score: float
    primary_indicators: list[str]
    clinical_reasoning: str
    recommended_action: str
    confidence: float
    retrieved_context: list[str]
    self_check_passed: bool
    protocol_compliant: bool
    past_similar_events: int
    latency_ms: float | None = None


class SignalAssessment(BaseModel):
    """Structured output of the Signal Interpretation specialist.

    autonomic_pattern: Physiological classification of the HRV z-score pattern.
    primary_features:  Which HRV features drove the classification.
    confidence:        0.0–1.0 specialist confidence.
    physiological_reasoning: At least 30 chars of reasoning.
    """

    autonomic_pattern: Literal[
        "pre_sepsis",
        "bradycardia_reflex",
        "normal_variation",
        "indeterminate",
    ]
    primary_features: list[str]
    confidence: float
    physiological_reasoning: str

    @field_validator("confidence")
    @classmethod
    def confidence_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"confidence {v} out of range [0, 1]")
        return v

    @field_validator("primary_features")
    @classmethod
    def at_least_one(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("primary_features must contain at least one feature")
        return v[:3]

    @field_validator("physiological_reasoning")
    @classmethod
    def reasoning_substantive(cls, v: str) -> str:
        if len(v.strip()) < 30:
            raise ValueError("physiological_reasoning too short — LLM may have failed")
        return v


class BradycardiaAssessment(BaseModel):
    """Structured output of the Bradycardia Classification specialist.

    classification: Clinical category of the bradycardia pattern.
    clinical_weight: Low/medium/high importance relative to HRV findings.
    reasoning: Free-text clinical reasoning.
    """

    classification: Literal[
        "isolated_reflex",
        "recurrent_without_suppression",
        "recurrent_with_suppression",
        "cluster",
        "apnoeic",
        "none",
    ]
    clinical_weight: Literal["low", "medium", "high"]
    reasoning: str
