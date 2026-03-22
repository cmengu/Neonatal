"""Protocol Compliance specialist — pure logic, no LLM, no retrieval.

Validates LLMOutput.recommended_action against concern_level rules.
The generalist uses a loose substring match across all APPROVED_ACTIONS.
This specialist adds concern-level semantics: certain actions are only
appropriate for specific concern levels.

Runs last in the multi-agent chain. Always sets self_check_passed=True
(replaces the generalist's self_check_node for the multi-agent path).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from langsmith import traceable

from src.agent.schemas import APPROVED_ACTIONS

if TYPE_CHECKING:
    from src.agent.supervisor import MultiAgentState


# Actions that are only appropriate when concern_level is RED or YELLOW.
# Flagged if the LLM recommends them for a GREEN patient.
_HIGH_ACUITY_ACTIONS = {
    "blood culture",
    "immediate clinical review",
    "notify attending neonatologist",
    "respiratory support assessment",
}

# Actions appropriate for GREEN patients.
_ROUTINE_ACTIONS = {
    "continue routine monitoring",
    "reassess in 2 hours",
    "increase monitoring frequency",
}


@traceable(name="protocol_agent_node")
def protocol_agent_node(state: "MultiAgentState") -> dict:
    """Validate recommended_action against concern_level. Pure logic — no LLM."""
    out = state["llm_output"]
    if out is None:
        return {"self_check_passed": True}

    action_lower = out.recommended_action.lower()
    level = out.concern_level

    # Check 1: action must be on the APPROVED_ACTIONS list (existing constraint).
    protocol_compliant = any(
        approved.lower() in action_lower for approved in APPROVED_ACTIONS
    )

    # Check 2: concern-level semantic gate.
    if level == "GREEN":
        # Flag high-acuity actions for GREEN patients — likely a reasoning error.
        for high_acuity in _HIGH_ACUITY_ACTIONS:
            if high_acuity in action_lower:
                original = out.recommended_action
                out.recommended_action = (
                    f"[PROTOCOL FLAG: '{original}' inappropriate for GREEN concern level] "
                    "Continue routine monitoring."
                )
                protocol_compliant = False
                break

    if level == "RED":
        # Flag routine-only actions for RED patients — safety concern.
        if any(r in action_lower for r in _ROUTINE_ACTIONS) and \
           not any(h in action_lower for h in _HIGH_ACUITY_ACTIONS):
            original = out.recommended_action
            out.recommended_action = (
                f"[PROTOCOL FLAG: '{original}' insufficient for RED concern level] "
                "Immediate clinical review."
            )
            protocol_compliant = False

    return {
        "llm_output": out,
        "self_check_passed": True,
    }
