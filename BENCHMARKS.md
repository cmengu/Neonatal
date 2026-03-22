# NeonatalGuard — Generalist Baseline Benchmarks

*Phase 4 baseline — recorded 2026-03-22.*
*Phase 5 multi-agent results will be added as a new section below.*
*Hard-scenario FNR is the primary Phase 5 improvement target.*

---

## Eval Suite: 30 Scenarios (24 clean + 6 hard mixed-signal)

| Metric | No-LLM (rule-based) | Live LLM (Groq generalist) |
|--------|---------------------|---------------------------|
| F1 (macro) | 1.000 | 0.533 |
| FNR (RED) | 0.000 | 0.000 |
| FNR (RED, hard scenarios only) | 0.000 | 0.000 |
| Protocol compliance | 1.000 | 0.667 |
| Scenarios run | 30 | 30 |

## RAG Retrieval

| Metric | Vector-only | Hybrid + Rerank | Delta |
|--------|-------------|-----------------|-------|
| MRR@3 | 0.793 | 0.960 | +0.167 |
| Recall@3 | 92.0% | 100.0% | — |

---

## Notes

- **FNR(RED) must remain 0.000 in all future phases.** A missed RED is a patient safety event.
- **Hard-scenario FNR** is the primary target for Phase 5. The signal specialist is
  expected to reduce this on mixed-signal cases.
- **Live LLM F1** reflects the generalist's YELLOW/GREEN distinction quality.
  The clinical reasoning specialist targets improvement here.

## Phase 5 Improvement Claim Requirements

A Phase 5 multi-agent result is an improvement if and only if:
1. FNR(RED) remains 0.000
2. Hard-scenario FNR(RED) ≤ Phase 4 live-LLM value (0.000)
3. Overall F1 (live LLM) > Phase 4 live-LLM value (0.533)
