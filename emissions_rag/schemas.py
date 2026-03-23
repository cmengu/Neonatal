"""Pydantic schemas for the Emissions RAG multi-agent system.

ScopeAssessment:  Scope analysis specialist output — Scope 1/2/3 breakdown.
ReductionOutput:  Reduction pathway specialist output — recommended actions.
EmissionsAlert:   Final alert returned by the graph and API.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator


class ScopeAssessment(BaseModel):
    """Structured output of the Scope Analysis specialist."""

    scope_1_tco2e: float
    scope_2_tco2e: float
    scope_3_tco2e: float
    scope_2_method: Literal["market_based", "location_based"]
    primary_sources: list[str]
    hot_spots: list[str]
    emission_intensity: float  # total tCO2e per $M revenue
    sector_delta: float  # % above/below sector average (negative = better)
    reasoning: str

    @field_validator("primary_sources", "hot_spots")
    @classmethod
    def at_least_one(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("must have at least one entry")
        return v


class ReductionOutput(BaseModel):
    """Structured output of the Reduction Pathway specialist."""

    recommended_pathway: str
    near_term_actions: list[str]
    sbti_aligned: bool
    csrd_reportable: bool
    recommended_action: str
    confidence: float
    reasoning: str

    @field_validator("confidence")
    @classmethod
    def confidence_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"confidence {v} out of range [0, 1]")
        return v


class EmissionsAlert(BaseModel):
    """Final emissions assessment for a company — returned by graph and API."""

    company_id: str
    timestamp: datetime
    scope_breakdown: dict[str, float]
    primary_sources: list[str]
    reduction_pathway: str
    sbti_aligned: bool
    csrd_reportable: bool
    recommended_action: str
    confidence: float
    retrieved_context: list[str]
    latency_ms: float | None = None
