"""24-scenario eval suite for NeonatalGuard.

Each Scenario maps to a deterministic PipelineResult injected into the
LangGraph agent via the _SYNTHETIC_RESULT env var mechanism in graph.py.

RED   scenarios: risk_score > 0.70 — rule-based path returns RED unconditionally.
YELLOW scenarios: risk_score 0.41–0.69 — rule-based path returns YELLOW.
GREEN  scenarios: risk_score ≤ 0.40 — rule-based path returns GREEN.

In EVAL_NO_LLM=1 mode, llm_reasoning_node returns concern_level = r.risk_level
(derived from risk_score via level_from_score). FNR=0.000 is guaranteed for RED.
"""
from __future__ import annotations

import os
import pickle
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.features.constants import HRV_FEATURE_COLS
from src.pipeline.result import BradycardiaEvent, PipelineResult

# Fixed 28-32wk premature neonate baseline used for all 24 scenarios.
# Scenario z_scores are deviations FROM these values.
# Sources: Fyfe 2003, Longin 2005 — same as synthetic_generator.py.
_BASELINE_MEANS: dict[str, float] = {
    "mean_rr":   432.0, "sdnn":   18.0, "rmssd":  12.0, "pnn50":    2.5,
    "lf_hf_ratio": 1.5,
    "rr_ms_min": 380.0, "rr_ms_max": 490.0,
    "rr_ms_25%": 422.0, "rr_ms_50%": 432.0, "rr_ms_75%": 442.0,
}
_BASELINE_STDS: dict[str, float] = {
    "mean_rr":    30.0, "sdnn":   6.0, "rmssd":   4.0, "pnn50":   1.2,
    "lf_hf_ratio": 0.5,
    "rr_ms_min":  28.0, "rr_ms_max":  35.0,
    "rr_ms_25%":  24.0, "rr_ms_50%":  28.0, "rr_ms_75%": 24.0,
}


@dataclass
class Scenario:
    """One eval scenario — defines a PipelineResult and its expected classification."""
    patient_id: str
    risk_score: float
    z_scores: dict[str, float]      # Key deviating features only; remaining default to 0.0
    n_brady: int
    expected: Literal["RED", "YELLOW", "GREEN"]
    desc: str


def build_pipeline_result(s: Scenario) -> PipelineResult:
    """Construct a PipelineResult from a Scenario using the fixed 28-32wk baseline."""
    full_z = {feat: s.z_scores.get(feat, 0.0) for feat in HRV_FEATURE_COLS}
    hrv_values = {
        feat: _BASELINE_MEANS[feat] + full_z[feat] * _BASELINE_STDS[feat]
        for feat in HRV_FEATURE_COLS
    }
    personal_baseline = {
        feat: {"mean": _BASELINE_MEANS[feat], "std": _BASELINE_STDS[feat]}
        for feat in HRV_FEATURE_COLS
    }
    events = [
        BradycardiaEvent(timestamp_idx=i * 100, rr_interval_ms=620.0, duration_beats=1)
        for i in range(s.n_brady)
    ]
    return PipelineResult(
        patient_id=s.patient_id,
        risk_score=s.risk_score,
        risk_level=PipelineResult.level_from_score(s.risk_score),
        z_scores=full_z,
        hrv_values=hrv_values,
        personal_baseline=personal_baseline,
        detected_events=events,
    )


def inject_scenario(s: Scenario) -> None:
    """Serialise PipelineResult to hex and set _SYNTHETIC_RESULT env var for graph.py."""
    result = build_pipeline_result(s)
    os.environ["_SYNTHETIC_RESULT"] = pickle.dumps(result).hex()


def clear_injection() -> None:
    """Remove _SYNTHETIC_RESULT so the next invocation uses the real pipeline."""
    os.environ.pop("_SYNTHETIC_RESULT", None)


# fmt: off
SCENARIOS: list[Scenario] = [
    # RED (8) — risk_score > 0.70. Rule-based path returns RED. FNR=0.000 guaranteed.
    Scenario("EVAL-RED-001", 0.87, {"rmssd": -3.2, "lf_hf_ratio": +2.9, "pnn50": -2.7, "sdnn": -1.8}, 3, "RED",    "Classic pre-sepsis HRV signature"),
    Scenario("EVAL-RED-002", 0.82, {"rmssd": -2.8, "lf_hf_ratio": +2.5, "pnn50": -2.4, "sdnn": -2.1}, 2, "RED",    "Moderate pre-sepsis with 2 brady events"),
    Scenario("EVAL-RED-003", 0.91, {"rmssd": -3.8, "lf_hf_ratio": +3.3, "pnn50": -3.1, "sdnn": -2.6}, 5, "RED",    "Severe HRV suppression"),
    Scenario("EVAL-RED-004", 0.75, {"rmssd": -2.1, "lf_hf_ratio": +2.2, "pnn50": -1.9, "sdnn": -1.5}, 1, "RED",    "Borderline RED — just above threshold"),
    Scenario("EVAL-RED-005", 0.93, {"rmssd": -4.1, "lf_hf_ratio": +3.8, "pnn50": -3.5, "sdnn": -3.0}, 6, "RED",    "Critical — extreme HRV collapse"),
    Scenario("EVAL-RED-006", 0.79, {"rmssd": -2.5, "lf_hf_ratio": +2.0, "pnn50": -2.2, "sdnn": -1.7}, 0, "RED",    "RED without brady events — pure HRV signal"),
    Scenario("EVAL-RED-007", 0.85, {"rmssd": -3.0, "lf_hf_ratio": +2.7, "pnn50": -2.5, "sdnn": -2.0}, 4, "RED",    "Multiple brady events"),
    Scenario("EVAL-RED-008", 0.88, {"rmssd": -3.5, "lf_hf_ratio": +1.8, "pnn50": -2.8, "sdnn": -2.4}, 2, "RED",    "Dominant rmssd/pnn50 suppression"),
    # YELLOW (8) — risk_score 0.41–0.69
    Scenario("EVAL-YEL-001", 0.58, {"rmssd": -1.5, "lf_hf_ratio": +1.3, "pnn50": -1.2, "sdnn": -0.8}, 1, "YELLOW", "Moderate concern — borderline features"),
    Scenario("EVAL-YEL-002", 0.65, {"rmssd": -1.8, "lf_hf_ratio": +1.6, "pnn50": -1.5, "sdnn": -1.1}, 1, "YELLOW", "Upper YELLOW — close to RED threshold"),
    Scenario("EVAL-YEL-003", 0.42, {"rmssd": -0.9, "lf_hf_ratio": +0.8, "pnn50": -0.7, "sdnn": -0.5}, 0, "YELLOW", "Lower YELLOW — mild deviations"),
    Scenario("EVAL-YEL-004", 0.61, {"rmssd": -1.6, "lf_hf_ratio": +1.4, "pnn50": -1.3, "sdnn": -0.9}, 2, "YELLOW", "YELLOW with brady events"),
    Scenario("EVAL-YEL-005", 0.53, {"rmssd": -1.2, "lf_hf_ratio": +1.5, "pnn50": -1.0, "sdnn": -0.7}, 0, "YELLOW", "Sympathetic dominance"),
    Scenario("EVAL-YEL-006", 0.48, {"rmssd": -1.0, "lf_hf_ratio": +1.1, "pnn50": -0.9, "sdnn": -0.6}, 1, "YELLOW", "Low YELLOW — one isolated event"),
    Scenario("EVAL-YEL-007", 0.67, {"rmssd": -2.0, "lf_hf_ratio": +1.7, "pnn50": -1.7, "sdnn": -1.3}, 0, "YELLOW", "High YELLOW — elevated LF/HF"),
    Scenario("EVAL-YEL-008", 0.55, {"rmssd": -1.4, "lf_hf_ratio": +1.2, "pnn50": -1.1, "sdnn": -0.8}, 1, "YELLOW", "Mixed moderate signals"),
    # GREEN (8) — risk_score ≤ 0.40
    Scenario("EVAL-GRN-001", 0.12, {"rmssd": +0.3, "lf_hf_ratio": -0.2, "pnn50": +0.2, "sdnn": +0.1}, 0, "GREEN",  "Normal baseline — healthy variation"),
    Scenario("EVAL-GRN-002", 0.08, {"rmssd": +0.5, "lf_hf_ratio": -0.4, "pnn50": +0.4, "sdnn": +0.2}, 0, "GREEN",  "Very low risk — all features normal"),
    Scenario("EVAL-GRN-003", 0.22, {"rmssd": -0.4, "lf_hf_ratio": +0.3, "pnn50": -0.3, "sdnn": -0.2}, 0, "GREEN",  "Mild asymmetry but GREEN"),
    Scenario("EVAL-GRN-004", 0.18, {"rmssd": +0.2, "lf_hf_ratio": -0.1, "pnn50": +0.1, "sdnn":  0.0}, 0, "GREEN",  "Near-perfect baseline"),
    Scenario("EVAL-GRN-005", 0.35, {"rmssd": -0.7, "lf_hf_ratio": +0.6, "pnn50": -0.6, "sdnn": -0.4}, 0, "GREEN",  "Upper GREEN — mild trend, no alarm"),
    Scenario("EVAL-GRN-006", 0.15, {"rmssd": +0.4, "lf_hf_ratio": -0.3, "pnn50": +0.3, "sdnn": +0.2}, 0, "GREEN",  "Stable — positive HRV trend"),
    Scenario("EVAL-GRN-007", 0.28, {"rmssd": -0.5, "lf_hf_ratio": +0.4, "pnn50": -0.4, "sdnn": -0.3}, 0, "GREEN",  "Minor deviation — routine monitoring"),
    Scenario("EVAL-GRN-008", 0.38, {"rmssd": -0.8, "lf_hf_ratio": +0.7, "pnn50": -0.6, "sdnn": -0.4}, 0, "GREEN",  "Borderline GREEN — just below threshold"),
]
# fmt: on

assert len(SCENARIOS) == 24, f"Expected 24 scenarios, got {len(SCENARIOS)}"
assert sum(1 for s in SCENARIOS if s.expected == "RED")    == 8
assert sum(1 for s in SCENARIOS if s.expected == "YELLOW") == 8
assert sum(1 for s in SCENARIOS if s.expected == "GREEN")  == 8
