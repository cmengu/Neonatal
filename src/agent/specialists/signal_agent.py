"""Signal Interpretation specialist node.

Physiologically classifies HRV z-score patterns for the multi-agent graph.
Always runs as the first specialist after the supervisor node.

Retrieves from 'hrv_indicators' and 'sepsis_early_warning' KB categories only —
not from bradycardia or intervention chunks. This focus prevents the signal
specialist from conflating autonomic pattern reading with action selection
(the primary cause of YELLOW/GREEN confusion in the generalist).

In EVAL_NO_LLM mode: returns deterministic SignalAssessment from risk_score
and max z-score without any Groq call — CI gate works without API key.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from langsmith import traceable

from src.agent.schemas import SignalAssessment

if TYPE_CHECKING:
    from src.agent.supervisor import MultiAgentState


_SIGNAL_CATEGORIES = ["hrv_indicators", "sepsis_early_warning"]

# Module-level LoRA model singleton — loaded lazily on first call when USE_LORA_SIGNAL=1.
# None until _get_lora_model() is first called; then cached for the process lifetime.
_LORA_MODEL = None
_LORA_TOKENIZER = None


def _get_lora_model():
    """Lazily load the fine-tuned Phi-3-mini + LoRA adapter.

    Loads once per process; subsequent calls reuse the cached tuple.
    Requires USE_LORA_SIGNAL=1 and models/exports/signal_specialist_lora/ to exist.
    Device priority: MPS (Apple Silicon) → CPU.
    """
    global _LORA_MODEL, _LORA_TOKENIZER
    if _LORA_MODEL is not None:
        return _LORA_MODEL, _LORA_TOKENIZER

    import torch
    from pathlib import Path
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    REPO_ROOT   = Path(__file__).resolve().parent.parent.parent
    ADAPTER_DIR = str(REPO_ROOT / "models" / "exports" / "signal_specialist_lora")
    BASE_MODEL  = "microsoft/Phi-3-mini-4k-instruct"
    DEVICE      = "mps" if torch.backends.mps.is_available() else "cpu"
    DTYPE       = torch.float16

    tokenizer = AutoTokenizer.from_pretrained(ADAPTER_DIR, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    base = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL, torch_dtype=DTYPE, trust_remote_code=True, device_map=DEVICE
    )
    model = PeftModel.from_pretrained(base, ADAPTER_DIR)
    model.eval()

    _LORA_MODEL, _LORA_TOKENIZER = model, tokenizer
    return _LORA_MODEL, _LORA_TOKENIZER


def _lora_signal_inference(r) -> "SignalAssessment":
    """Run local LoRA adapter inference and parse output as SignalAssessment.

    Falls back to _rule_based_signal() if JSON parsing fails — never crashes.

    Parameters
    ----------
    r : PipelineResult — used for z-score input and rule-based fallback.
    """
    import json
    import torch

    instruction = (
        "Classify the neonatal HRV autonomic pattern from these z-score deviations "
        "from this infant's personal baseline. Do NOT recommend clinical actions."
    )
    z_parts = ", ".join(
        f"{feat} z={r.z_scores.get(feat, 0.0):+.2f}"
        for feat in r.z_scores
    )
    input_text = (
        f"{z_parts}. "
        f"Risk score {r.risk_score:.2f}. "
        f"Bradycardia events: {len(r.detected_events)}."
    )
    prompt = (
        f"### Instruction:\n{instruction}\n\n"
        f"### Input:\n{input_text}\n\n"
        f"### Output:\n"
    )

    model, tokenizer = _get_lora_model()
    device = next(model.parameters()).device
    inputs = tokenizer(prompt, return_tensors="pt").to(device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=256,
            do_sample=False,
            pad_token_id=tokenizer.pad_token_id,
        )

    decoded = tokenizer.decode(
        outputs[0][inputs["input_ids"].shape[1]:],
        skip_special_tokens=True,
    ).strip()

    # Parse JSON from generated output; fallback to rule-based on failure.
    try:
        j_start = decoded.find("{")
        j_end   = decoded.rfind("}") + 1
        if j_start == -1 or j_end <= 0:
            raise ValueError("No JSON object in output")
        parsed = json.loads(decoded[j_start:j_end])
        return SignalAssessment(**parsed)
    except Exception:
        # Fallback: rule-based rather than crashing the pipeline.
        z_vals = [abs(z) for z in r.z_scores.values()]
        max_z  = max(z_vals) if z_vals else 0.0
        return _rule_based_signal(r.risk_score, max_z)


def _rule_based_signal(risk_score: float, max_z: float) -> SignalAssessment:
    """Deterministic signal assessment for EVAL_NO_LLM mode."""
    if risk_score > 0.70:
        return SignalAssessment(
            autonomic_pattern="pre_sepsis",
            primary_features=["rmssd", "lf_hf_ratio"],
            confidence=0.90,
            physiological_reasoning=(
                f"Rule-based: risk_score={risk_score:.2f} > 0.70, max_z={max_z:.1f}. "
                "Autonomic withdrawal pattern consistent with pre-sepsis HRV signature."
            ),
        )
    if risk_score > 0.40:
        return SignalAssessment(
            autonomic_pattern="indeterminate",
            primary_features=["rmssd"],
            confidence=0.65,
            physiological_reasoning=(
                f"Rule-based: risk_score={risk_score:.2f} in borderline range, max_z={max_z:.1f}. "
                "Pattern indeterminate — clinical context required."
            ),
        )
    return SignalAssessment(
        autonomic_pattern="normal_variation",
        primary_features=["sdnn"],
        confidence=0.85,
        physiological_reasoning=(
            f"Rule-based: risk_score={risk_score:.2f} < 0.40, max_z={max_z:.1f}. "
            "HRV deviations within expected normal variation range."
        ),
    )


@traceable(name="signal_agent_node")
def signal_agent_node(state: dict) -> dict:
    """Classify autonomic pattern from HRV z-scores. Always runs first."""
    r = state["pipeline_result"]
    z_vals = [abs(z) for z in r.z_scores.values()]
    max_z = max(z_vals) if z_vals else 0.0

    if os.getenv("EVAL_NO_LLM", "").lower() in {"1", "true", "yes"}:
        return {"signal_assessment": _rule_based_signal(r.risk_score, max_z)}

    # USE_LORA_SIGNAL: route to local Phi-3-mini LoRA adapter (no Groq call).
    # Priority: EVAL_NO_LLM (CI, rule-based) > USE_LORA_SIGNAL (LoRA) > default (Groq).
    if os.getenv("USE_LORA_SIGNAL", "").lower() in {"1", "true", "yes"}:
        return {"signal_assessment": _lora_signal_inference(r)}

    from src.agent.graph import _get_groq, _get_kb

    top3 = r.get_top_deviated(3)
    query = (
        f"Neonatal HRV autonomic pattern: "
        + ", ".join(f"{d.name} z={d.z_score:+.1f}" for d in top3)
        + f". Risk score {r.risk_score:.2f}. Bradycardia events: {len(r.detected_events)}."
    )
    chunks = _get_kb().query_by_category(query, categories=_SIGNAL_CATEGORIES, n=3)
    context = "\n\n".join(chunks)

    z_table = "\n".join(
        f"  {feat}: z={z:+.2f}  (raw={r.hrv_values.get(feat, 0):.1f}ms)"
        for feat, z in r.z_scores.items()
    )

    prompt = f"""You are a neonatal HRV signal analyst. Your ONLY task is to classify
the physiological meaning of these z-score deviations from this infant's personal baseline.
Do NOT recommend clinical actions — that is a separate agent's responsibility.

Patient HRV z-scores (personal baseline deviation):
{z_table}

Retrieved HRV reference knowledge:
{context}

Classify the autonomic pattern and identify which features drove your assessment.
Output a SignalAssessment."""

    assessment: SignalAssessment = _get_groq().chat.completions.create(
        model="llama-3.3-70b-versatile",
        response_model=SignalAssessment,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_retries=3,
    )
    return {"signal_assessment": assessment}
