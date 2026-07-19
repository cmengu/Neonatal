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
*LoRA rows removed in #86 — never measured, and the path is gone. See below.*

### No-LLM Gate (CI-verified, rule-based path)

| Approach | F1 | FNR (RED) | FNR (hard) | Protocol | n |
|----------|----|-----------|------------|----------|---|
| Generalist (Phase 4) | 1.000 | 0.000 | 0.000 | 100% | 30 |
| Multi-agent (Phase 5) | 1.000 | 0.000 | 0.000 | 100% | 30 |

The no-LLM gate is a CI pass/fail check, not a quality measure. All rule-based paths map
`risk_score > 0.70 → RED` deterministically, so F1=1.000 is structurally guaranteed.

### Live-LLM (Groq llama-3.3-70b-versatile) — Primary Quality Metric

| Approach | F1 | FNR (RED) | FNR (hard) | Protocol | Latency p50 | Notes |
|----------|----|-----------|------------|----------|-------------|-------|
| Generalist single-prompt (Phase 4) | 0.533 | 0.000 | 0.000 | 66.7% | ~2s | Baseline |
| Multi-agent, all Groq (Phase 5) | *pending* | *pending* | *pending* | *pending* | ~4s | Run when API restored |

**To fill pending rows:**
```bash
# Multi-agent live-LLM (Phase 5 row):
QDRANT_PATH=qdrant_local python eval/eval_agent.py \
    --agent multi_agent --output results/eval_multiagent_live.json
```

### Phase 6 Success Criteria

| Criterion | Target | Status |
|-----------|--------|--------|
| FIX-10 distribution logging | Present after any retrain | ✅ |
| FIX-11 label gate in notebook | Cell 0 of notebook 05 | ✅ |
| LoRA training data | ≥ 200 examples in data/lora_training/ | ❌ removed (#86) |
| USE_LORA_SIGNAL toggle | Routes to local inference | ❌ removed (#86) |
| Multi-agent live F1 > 0.533 | Positive delta vs generalist | *pending* |
| LoRA F1 ≥ multi-agent F1 | LoRA not worse than Groq specialist | ❌ removed (#86) |
| FNR(RED) = 0.000 all rows | Safety constraint holds | ✅ (no-LLM) |

---

## Phase 7 — FastAPI + Docker + Monitoring

*Recorded 2026-03-22. Production API layer wrapping the Phase 5 multi-agent graph.*

### API Endpoints

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/assess/{patient_id}` | POST | Blocking multi-agent alert with `latency_ms` | ✅ |
| `/assess/{patient_id}/generalist` | POST | Generalist agent for A/B comparison | ✅ |
| `/assess/{patient_id}/stream` | GET | SSE streaming per-specialist progress | ✅ |
| `/patient/{patient_id}/history` | GET | Last N alerts from SQLite audit.db | ✅ |
| `/health` | GET | FIX-12 distribution + FIX-13 chunk count | ✅ |

### Phase 7 Success Criteria

| Feature | Target | Status |
|---------|--------|--------|
| Blocking endpoint | `NeonatalAlert` with `latency_ms` set | ✅ |
| SSE streaming | `text/event-stream`, 200, ≥1 `data:` event | ✅ |
| Patient history | JSON array from SQLite | ✅ |
| Generalist A/B | `NeonatalAlert` from generalist graph | ✅ |
| FIX-12 health | `prediction_distribution_last_100` + `prediction_health` | ✅ |
| FIX-13 health | `qdrant == "ok"` when 34 chunks present | ✅ |
| Docker networked mode | `QDRANT_PATH=""` → `ClinicalKnowledgeBase()` branch | ✅ |
| CI gate regression | `All CI gates passed.` | ✅ |
| Test count | 7 passed (local, excluding Docker parity) | ✅ |

### Infrastructure

| Component | Implementation |
|-----------|---------------|
| API server | FastAPI + Uvicorn (1 worker, process-level singletons) |
| Container | `python:3.11-slim`, `linux/arm64` |
| Services | 4 (neonatalguard-api, qdrant, eval-runner, signal-specialist) |
| KB preload | Lifespan handler — warms SentenceTransformer + Qdrant on startup |
| Tracing | LangSmith via existing `@traceable` decorators (no new instrumentation) |

---

## Removed: Phase-6 LoRA signal specialist (#86)

Every LoRA row above was `*pending*` and now reads *removed*. The adapter was never
trained, so **no measured result was deleted** — only the intent to measure one.

The path is gone rather than gated. It ran: `synthetic_generator.py(sepsis=True,
sepsis_severity=uniform(0.6, 1.0))` → a 230-example training set of which 30 records
(13.0%) carried a `pre_sepsis` label → LoRA fine-tune of Phi-3-mini →
`USE_LORA_SIGNAL=1` loading it as the **Tier 3 signal specialist**, the clinician-facing
tier. Those labels were a number somebody typed. The dataset survey (#73) established
that no public dataset gives this project real sepsis labels on beat-to-beat cardiac
signal, so a synthetic label could never have been checked against one.

Nothing was wrong on the day: the adapter directory did not exist and the flag was
commented out in `.env.example`. It was dormant, not safe — a flag only a careful reader
knows is dangerous is not a safeguard.

What survives is `src/data/synthetic_generator.py`, whose literature-based neonatal HRV
distributions are sound. Its `sepsis`/`sepsis_severity` parameters are replaced by a
`departure={feature: fractional_shift}` argument that names perturbations by
**magnitude, never by disease** — the basis for the detector-characterisation harness
(#83), which measures what the cascade can see and makes no claim about any infant.
