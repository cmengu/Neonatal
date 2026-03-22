# NeonatalGuard — Benchmark Results

---

## Phase 4 — Generalist Baseline

*Recorded 2026-03-22. 30 scenarios (24 clean + 6 hard mixed-signal).*

### Agent Eval

| Metric | No-LLM (rule-based) | Live LLM (Groq llama-3.3-70b) |
|--------|---------------------|-------------------------------|
| F1 (macro) | 1.000 | 0.533 |
| FNR (RED) | 0.000 | 0.000 |
| FNR (RED, hard scenarios) | 0.000 | 0.000 |
| Protocol compliance | 1.000 | 0.667 |
| Latency p50 / p95 | 688ms / 3292ms | — |
| Scenarios run | 30 | 30 |

**Interpretation:** No-LLM F1=1.000 is the guaranteed CI baseline — the rule-based path maps `risk_score > 0.70 → RED` directly. Live-LLM F1=0.533 reflects YELLOW↔GREEN confusion: the generalist conflates signal interpretation with action selection in a single prompt. FNR(RED)=0.000 in both modes — the safety constraint holds. Protocol compliance of 0.667 reflects both parse failures and lack of concern-level awareness in action validation.

### RAG Retrieval

| Metric | Vector-only | Hybrid + Rerank | Delta |
|--------|-------------|-----------------|-------|
| MRR@3 | 0.793 | 0.960 | +0.167 |
| Recall@3 | 92.0% | 100.0% | +8.0pp |

Hybrid (dense + TF-IDF sparse + FlashRank rerank) achieves perfect Recall@3. The two queries vector-only missed were a bradycardia event-count query and an intervention-threshold query with a specific PPV statistic — exact numeric terms that BM25 caught and semantic embeddings missed.

---

## Phase 5 — Multi-Agent (Specialist Routing)

*Recorded 2026-03-22. Same 30 scenarios.*
*Architecture: supervisor → signal specialist → [brady conditional] → clinical specialist → protocol specialist → assemble.*

### Agent Eval (no-LLM gate)

| Metric | Generalist (Phase 4) | Multi-Agent (Phase 5) | Delta |
|--------|---------------------|-----------------------|-------|
| F1 (macro, no-LLM) | 1.000 | 1.000 | 0.000 |
| FNR (RED) | 0.000 | 0.000 | 0.000 |
| FNR (RED, hard scenarios) | 0.000 | 0.000 | 0.000 |
| Protocol compliance | 1.000 | 1.000 | 0.000 |
| Latency p50 / p95 | 688ms / 3292ms | 11ms / 14ms | — |
| Scenarios run | 30 | 30 | — |

**Latency note:** Multi-agent p50=11ms vs generalist p50=688ms in no-LLM mode because the multi-agent rule-based path skips the Qdrant KB retrieval (specialist nodes return deterministically without calling `query_by_category()`). In live-LLM mode both will be network-bound on Groq latency.

### Agent Eval (live LLM)

| Metric | Generalist (Phase 4) | Multi-Agent (Phase 5) | Delta |
|--------|---------------------|-----------------------|-------|
| F1 (macro) | 0.533 | *pending* | — |
| FNR (RED) | 0.000 | *pending* | — |
| FNR (RED, hard scenarios) | 0.000 | *pending* | — |
| Protocol compliance | 0.667 | *pending* | — |

*Run `QDRANT_PATH=qdrant_local python eval/eval_agent.py --agent multi_agent --output results/eval_multiagent_live.json` to populate.*

---

## Safety Constraint

**FNR(RED) must remain 0.000 in all future phases.** A missed RED is a patient safety event. This constraint has held across all Phase 4 and Phase 5 no-LLM evaluations.

## Phase 5 Improvement Claim Requirements

A Phase 5 live-LLM result is an improvement over Phase 4 if and only if:
1. FNR(RED) remains 0.000
2. Hard-scenario FNR(RED) ≤ 0.000 (Phase 4 live-LLM value)
3. Overall F1 (live LLM) > 0.533 (Phase 4 live-LLM value)

---

## Phase 6 — Three-Way Comparison

*Phase 6 recorded 2026-03-22. Groq API key exhausted — live-LLM rows pending key restoration.*
*LoRA adapter pending training run in `notebooks/05_signal_specialist_lora.ipynb`.*

### No-LLM Gate (CI-verified, rule-based path)

| Approach | F1 | FNR (RED) | FNR (hard) | Protocol | n |
|----------|----|-----------|------------|----------|---|
| Generalist (Phase 4) | 1.000 | 0.000 | 0.000 | 100% | 30 |
| Multi-agent (Phase 5) | 1.000 | 0.000 | 0.000 | 100% | 30 |
| Multi-agent + LoRA signal (Phase 6) | *pending* | *pending* | *pending* | *pending* | — |

The no-LLM gate is a CI pass/fail check, not a quality measure. All rule-based paths map
`risk_score > 0.70 → RED` deterministically, so F1=1.000 is structurally guaranteed.

### Live-LLM (Groq llama-3.3-70b-versatile) — Primary Quality Metric

| Approach | F1 | FNR (RED) | FNR (hard) | Protocol | Latency p50 | Notes |
|----------|----|-----------|------------|----------|-------------|-------|
| Generalist single-prompt (Phase 4) | 0.533 | 0.000 | 0.000 | 66.7% | ~2s | Baseline |
| Multi-agent, all Groq (Phase 5) | *pending* | *pending* | *pending* | *pending* | ~4s | Run when API restored |
| Multi-agent + LoRA signal (Phase 6) | *pending* | *pending* | *pending* | *pending* | ~0.5s signal | Run after LoRA training |

**To fill pending rows:**
```bash
# Multi-agent live-LLM (Phase 5 row):
QDRANT_PATH=qdrant_local python eval/eval_agent.py \
    --agent multi_agent --output results/eval_multiagent_live.json

# Multi-agent + LoRA signal (Phase 6 row):
USE_LORA_SIGNAL=1 QDRANT_PATH=qdrant_local python eval/eval_agent.py \
    --agent multi_agent --output results/eval_lora.json
```

### Phase 6 Success Criteria

| Criterion | Target | Status |
|-----------|--------|--------|
| FIX-10 distribution logging | Present after any retrain | ✅ |
| FIX-11 label gate in notebook | Cell 0 of notebook 05 | ✅ |
| LoRA training data | ≥ 200 examples in data/lora_training/ | ✅ |
| USE_LORA_SIGNAL toggle | Routes to local inference | ✅ |
| Multi-agent live F1 > 0.533 | Positive delta vs generalist | *pending* |
| LoRA F1 ≥ multi-agent F1 | LoRA not worse than Groq specialist | *pending* |
| FNR(RED) = 0.000 all rows | Safety constraint holds | ✅ (no-LLM) |
