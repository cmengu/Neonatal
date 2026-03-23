# NeonatalGuard — Unified Gameplan: Phase 4 Onwards
*Integrates architecture plan + post-mortem hardening fixes into one cohesive plan.*
*Version 4.0 — March 2026*

---

## How to read this document

Every phase has three sections:

- **What it builds** — architecture goals from the gameplan
- **Hardening fixes** — post-mortem-derived correctness/safety tasks integrated into the phase
- **Success criteria** — gates that must pass before moving forward

Fix priority levels:
- 🔴 BLOCKING — silent wrong outputs if missing. Must pass before the phase ends.
- 🟡 IMPORTANT — degrades debuggability or comparison validity. Must pass before the phase it blocks.
- 🟢 GOOD PRACTICE — operational hygiene. Must pass before Phase 7 (production).

Fix numbering is preserved from the post-mortem document for traceability.

---

## Revised Phase Map

```
Phase 4  — Eval framework + CI + pre-flight hardening   [baseline numbers on generalist]
Phase 5  — Multi-agent architecture + audit hardening   [supervisor + 4 specialists]
Phase 6  — Eval re-run + fine-tuning + training safety  [multi-agent vs generalist delta + LoRA]
Phase 7  — FastAPI + Docker + LangSmith + monitoring    [production wrap]
Phase 8  — Emissions RAG bridge                         [Unravel Carbon domain]
```

**Total estimate:** ~22 days of engineering
**Phases 4–6** = Razer screen pass (evals, multi-agent, fine-tuning)
**Phases 4–7** = Unravel screen pass (full production system)
**Phase 8**    = Unravel domain gap closed

---

## Phase 4 — Eval Framework + CI + Pre-Flight Hardening

**Goal:** Establish a concrete, trustworthy baseline on the generalist agent.
Every future improvement is measured against these numbers. The hardening fixes
in this phase exist because if the baseline is computed on wrong inputs or with
wrong feature order, the entire generalist vs multi-agent comparison is
meaningless.

**Time estimate:** 3.5 days (original 2.5 + 1 day for hardening fixes)

**Why before multi-agent:** Without baseline numbers you are building specialist
agents blind. The eval tells you exactly which scenario types the generalist
fails on, so Phase 5 is a targeted fix, not speculative architecture. Without
the hardening fixes, those baseline numbers may be silently wrong.

---

### 4.1 — Pre-flight: Run these three checks before writing any new code

If any of these fails, fix it before touching Phase 4 architecture.

```bash
# FIX-1: Verify feature order is consistent right now
python -c "
import pandas as pd
from src.features.constants import HRV_FEATURE_COLS
df = pd.read_csv('data/processed/combined_features_labelled.csv')
actual = df[HRV_FEATURE_COLS].columns.tolist()
assert actual == list(HRV_FEATURE_COLS), f'ORDER MISMATCH: {actual}'
print('FIX-1 OK: feature order consistent')
"

# FIX-3: Check dependency versions are pinned
python -c "
reqs = open('requirements.txt').read()
for pkg in ['flashrank', 'qdrant-client', 'sentence-transformers']:
    if f'{pkg}>=' in reqs or f'{pkg}~=' in reqs:
        print(f'WARNING: {pkg} uses range version — should be pinned with ==')
    elif f'{pkg}==' in reqs:
        print(f'OK: {pkg} is pinned')
    else:
        print(f'MISSING: {pkg} not in requirements.txt')
"

# FIX-4: Count current hard scenarios (expect 0 before this phase)
python -c "
from eval.scenarios import SCENARIOS
hard = [s for s in SCENARIOS if 'HARD' in s.patient_id]
print(f'Hard scenarios: {len(hard)} (target: >= 6 by end of Phase 4)')
print('Add FIX-4 hard scenarios as part of Phase 4 eval build.')
"
```

---

### 4.2 — FIX-1 🔴 Feature order assertion in `train_classifier.py`

**What post-mortem it addresses:** Silent data corruption — feature names
match but column order silently differs between training and inference.
Every prediction is wrong but no error is raised.

**Where it goes:** `src/models/train_classifier.py`, immediately before `clf.fit()`.

```python
# Add after loading the dataframe, before X = df[HRV_FEATURE_COLS].values
actual_cols = df[HRV_FEATURE_COLS].columns.tolist()
assert actual_cols == list(HRV_FEATURE_COLS), (
    f"Column order mismatch between HRV_FEATURE_COLS and CSV.\n"
    f"  Expected: {list(HRV_FEATURE_COLS)}\n"
    f"  Got:      {actual_cols}\n"
    f"  The ONNX model uses positional features — order must be identical."
)
logging.info("Feature order verified: %s", actual_cols)
```

**Why now:** The ONNX model is already trained and exported. If you retrain
in Phase 6 (LoRA comparison requires rerunning baseline), this assertion must
be present or the retrained model may silently use a different feature order
than the exported ONNX.

**Verification:**
```bash
python -c "
import pandas as pd
from src.features.constants import HRV_FEATURE_COLS
df = pd.read_csv('data/processed/combined_features_labelled.csv')
actual = df[HRV_FEATURE_COLS].columns.tolist()
assert actual == list(HRV_FEATURE_COLS), f'ORDER MISMATCH: {actual}'
print('PASS: feature order matches HRV_FEATURE_COLS')
print('Order:', actual)
"
```

---

### 4.3 — FIX-2 🔴 Input logging in `audit.db`

**What post-mortem it addresses:** End-to-end input logging gap. Every
post-mortem where a model was silently wrong for weeks includes the line
"we did not have access to the actual model inputs at inference time."
Currently `audit.db` stores alert outputs but not what the model saw.

**Where it goes:** `src/agent/memory.py`

```python
# In _init_schema(), replace the CREATE TABLE statement:
conn.execute("""
    CREATE TABLE IF NOT EXISTS alert_history (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id      TEXT,
        timestamp       TEXT,
        concern_level   TEXT,
        risk_score      REAL,
        top_feature     TEXT,
        top_z_score     REAL,
        z_scores_json   TEXT,    -- JSON blob of full z_scores dict
        hrv_values_json TEXT     -- JSON blob of full hrv_values dict
    )
""")

# In save(), update the INSERT:
import json
conn.execute("""
    INSERT INTO alert_history
    (patient_id, timestamp, concern_level, risk_score,
     top_feature, top_z_score, z_scores_json, hrv_values_json)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", (
    alert.patient_id,
    alert.timestamp.isoformat(),
    alert.concern_level,
    alert.risk_score,
    top_feature,
    top_z,
    json.dumps(alert_z_scores),
    json.dumps(alert_hrv_values),
))
```

**Update `assemble_alert_node` in `graph.py` to pass inputs to save:**
```python
EpisodicMemory().save(
    alert,
    top_feature_name,
    top_feature_z,
    z_scores=result.z_scores,
    hrv_values=result.hrv_values,
)
```

**Why now:** Phase 5 multi-agent adds specialist agents whose outputs feed
into clinical reasoning. If a specialist produces a wrong `SignalAssessment`,
you need to trace it back to the z-scores it received. Without input logging
you cannot do this.

**Verification:**
```bash
python -c "
import sqlite3, json
conn = sqlite3.connect('data/audit.db')
row = conn.execute('SELECT z_scores_json, hrv_values_json FROM alert_history LIMIT 1').fetchone()
if row:
    z = json.loads(row[0])
    h = json.loads(row[1])
    assert len(z) == 10, f'Expected 10 z-scores, got {len(z)}'
    assert len(h) == 10, f'Expected 10 hrv values, got {len(h)}'
    print('PASS: input logging working, 10 features stored per alert')
else:
    print('No rows yet — run the agent once then re-run this check')
"
```

---

### 4.4 — FIX-3 🔴 Pin exact dependency versions in `requirements.txt`

**What post-mortem it addresses:** Dependency version drift. The FlashRank
`r["text"]` vs `r.text` issue was caught in plan review — in production it
would have been a silent runtime crash.

```bash
# Check your exact installed versions right now:
pip show flashrank qdrant-client sentence-transformers skl2onnx | grep -E "^Name:|^Version:"
```

Then replace ranges with exact pins:
```
# Before (bad — allows silent API changes):
flashrank>=0.2.0
qdrant-client>=1.7
sentence-transformers>=2.0

# After (good — locked to verified versions):
flashrank==0.2.10
qdrant-client==1.7.3
sentence-transformers==2.7.0
skl2onnx==1.16.0
```

**Add a dependency API test:**
```python
# tests/test_dependency_apis.py
def test_flashrank_returns_dict_with_text_key():
    """Verify flashrank API contract — r['text'] not r.text."""
    from flashrank import Ranker, RerankRequest
    ranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2")
    results = ranker.rerank(RerankRequest(
        query="RMSSD neonatal sepsis",
        passages=[{"id": "1", "text": "RMSSD measures short-term HRV in premature neonates."}]
    ))
    assert isinstance(results[0], dict), \
        f"flashrank API changed — results[0] is {type(results[0])}, not dict"
    assert "text" in results[0], \
        f"flashrank API changed — 'text' key missing from result dict"

def test_onnx_output_format():
    """Verify ONNX output[1] is ndarray with shape (n, 2) when zipmap=False."""
    import numpy as np
    import onnxruntime as ort
    sess = ort.InferenceSession("models/exports/neonatalguard_v1.onnx")
    dummy = np.random.randn(3, 10).astype("float32")
    out = sess.run(None, {"hrv_features": dummy})
    assert isinstance(out[1], np.ndarray), \
        f"ONNX output[1] type changed: {type(out[1])}"
    assert out[1].shape == (3, 2), \
        f"ONNX output[1] shape changed: {out[1].shape}"
```

**Why now:** Phase 5 adds more dependencies (instructor, groq, langgraph).
Each is a new version drift risk. Lock everything before adding more.

---

### 4.5 — FIX-4 🟡 Mixed-signal hard scenarios in eval suite

**What post-mortem it addresses:** Evaluation-production gap. The initial 24
scenarios all have clean signals — multiple features deviating in the same
direction simultaneously. Real neonates are messier. A comparison measured
only on clean signals will show a smaller delta than the real clinical
improvement.

**Where it goes:** `eval/scenarios.py` — add 6 hard scenarios after the existing
24. Update the assertion from `== 24` to `== 30`.

```python
# HARD scenarios (6) — mixed signals, real clinical ambiguity
Scenario("EVAL-HARD-RED-001", 0.75,
    {"rmssd": -2.8, "lf_hf_ratio": +0.3, "pnn50": -2.5, "sdnn": -2.2},
    n_brady=0, expected="RED",
    desc="RED — RMSSD+SDNN+pNN50 suppressed but LF/HF normal. No brady events."),

Scenario("EVAL-HARD-RED-002", 0.71,
    {"rmssd": -1.2, "lf_hf_ratio": +3.1, "pnn50": -0.8, "sdnn": -0.6},
    n_brady=4, expected="RED",
    desc="RED — dominant LF/HF shift with brady events, mild RMSSD change"),

Scenario("EVAL-HARD-YEL-001", 0.55,
    {"rmssd": -2.1, "lf_hf_ratio": -0.4, "pnn50": -1.9, "sdnn": +0.3},
    n_brady=0, expected="YELLOW",
    desc="YELLOW — RMSSD+pNN50 declining but LF/HF improving. Contradictory."),

Scenario("EVAL-HARD-YEL-002", 0.48,
    {"rmssd": +0.2, "lf_hf_ratio": +2.4, "pnn50": +0.1, "sdnn": -0.3},
    n_brady=3, expected="YELLOW",
    desc="YELLOW — isolated LF/HF elevation with brady, other HRV features normal"),

Scenario("EVAL-HARD-GRN-001", 0.35,
    {"rmssd": -1.8, "lf_hf_ratio": +1.5, "pnn50": -1.6, "sdnn": -1.4},
    n_brady=0, expected="GREEN",
    desc="GREEN — looks like YELLOW but risk_score low. Tests against false positives."),

Scenario("EVAL-HARD-GRN-002", 0.28,
    {"rmssd": -0.9, "lf_hf_ratio": +0.8, "pnn50": +1.2, "sdnn": -0.7},
    n_brady=1, expected="GREEN",
    desc="GREEN — mixed directions, single brady, low overall risk"),

# Update assertions:
assert len(SCENARIOS) == 30
assert sum(1 for s in SCENARIOS if s.expected == "RED")    == 10
assert sum(1 for s in SCENARIOS if s.expected == "YELLOW") == 10
assert sum(1 for s in SCENARIOS if s.expected == "GREEN")  == 10
```

**Why now:** These scenarios need to be in the Phase 4 baseline run so you have
the generalist's performance on hard cases documented. When Phase 5 multi-agent
improves on these cases, you need a baseline to compare against.

---

### 4.6 — FIX-5 🟡 Baseline skew assertion in `runner.py`

**What post-mortem it addresses:** Training-serving skew. The plan documents
that `runner.py` uses LOOKBACK=10 to match `run_nb04.py`. There is a comment.
There is no runtime enforcement. Comments about invariants are not enforced
invariants.

**Where it goes:** `src/pipeline/runner.py`, after computing `personal_baseline`
and `z_scores`.

```python
import math
_skew_warnings = []
for feat in self._feature_cols:
    if feat not in z_scores:
        continue
    stored_z   = z_scores[feat]
    x          = hrv_values[feat]
    mean       = personal_baseline[feat]["mean"]
    std        = personal_baseline[feat]["std"]
    recomputed = (x - mean) / std

    if not math.isfinite(stored_z) or not math.isfinite(recomputed):
        continue
    if abs(recomputed - stored_z) > 0.5:
        _skew_warnings.append(
            f"{feat}: stored_z={stored_z:.3f} recomputed={recomputed:.3f} "
            f"diff={abs(recomputed-stored_z):.3f}"
        )

if _skew_warnings:
    import logging as _log
    _log.warning(
        "Baseline skew detected for %s — runner.py and run_nb04.py "
        "may be using different lookback windows:\n%s",
        patient_id,
        "\n".join(_skew_warnings)
    )
    # Raise only if ALL features are skewed (structural bug):
    if len(_skew_warnings) == len(self._feature_cols):
        raise RuntimeError(
            f"All features show baseline skew for {patient_id}. "
            "Check _LOOKBACK constant matches run_nb04.py LOOKBACK."
        )
```

**Why now:** Phase 5's signal specialist reasons from z-scores. If those
z-scores are wrong due to baseline skew, the specialist produces wrong
`SignalAssessment` objects with no visibility into why.

---

### 4.7 — Eval framework architecture

**30-scenario eval suite** — 10 RED, 10 YELLOW, 10 GREEN (8 clean + 2 hard per class
from FIX-4 above). Each scenario injects a synthetic `PipelineResult` into the
graph via `_SYNTHETIC_RESULT` env var, bypassing the real ECG pipeline.

**Metrics reported:**
- F1 (macro) — overall classification quality
- FNR (RED) — false negative rate on critical alerts. Must be 0.000. A missed
  RED in a NICU is a patient safety event.
- FNR by scenario type (clean vs hard) — shows where generalist struggles
- Protocol compliance % — what fraction of alerts use approved actions
- Mean latency p50 / p95 — per-run timing from LangSmith traces

**Scenario design (critical detail):**
RED scenarios must have `risk_score > 0.70` so the rule-based path in
`llm_reasoning_node` correctly returns RED without an LLM call.

```python
SCENARIOS = [
  # RED (8 clean) — risk_score > 0.70 in all cases
  Scenario("EVAL-RED-001", risk_score=0.87,
           z_scores={"rmssd": -3.2, "lf_hf_ratio": +2.9, "pnn50": -2.7, "sdnn": -1.8},
           n_brady=3, expected="RED", desc="Classic pre-sepsis signature"),
  # ... 7 more RED clean

  # YELLOW (8 clean) — risk_score 0.41–0.69
  Scenario("EVAL-YEL-001", risk_score=0.58, ..., expected="YELLOW"),
  # ... 7 more YELLOW clean

  # GREEN (8 clean) — risk_score < 0.40
  Scenario("EVAL-GRN-001", risk_score=0.12, ..., expected="GREEN"),
  # ... 7 more GREEN clean

  # HARD scenarios from FIX-4 — 2 per class
  # (defined above in section 4.5)
]
```

**GitHub Actions CI workflow:**
```yaml
name: NeonatalGuard Eval CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.12"}
      - run: pip install -r requirements.txt
      - name: Run dependency API tests
        run: pytest tests/test_dependency_apis.py -v   # from FIX-3
      - name: Run eval suite (no-LLM)
        env:
          QDRANT_PATH: qdrant_local
        run: python eval/eval_agent.py --no-llm --fail-below-f1 0.80 --fail-above-fnr 0.0
      - uses: actions/upload-artifact@v4
        with:
          name: eval-${{ github.sha }}
          path: results/eval_*.json
      - if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            const r = JSON.parse(require('fs').readFileSync('results/eval_agent.json'))
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner, repo: context.repo.repo,
              body: `## Eval\nF1: ${r.f1.toFixed(3)} | FNR(RED): ${r.fnr.toFixed(3)} | Protocol: ${(r.protocol_compliance*100).toFixed(1)}%\nHard-scenario FNR: ${r.fnr_hard.toFixed(3)}`
            })
```

**RAG eval:** 25 ground-truth query/chunk pairs. Reports MRR@3 for vector-only
vs hybrid+rerank. Include 5 numeric queries (e.g. "RMSSD 21ms") to show hybrid
BM25 advantage over pure vector.

---

### 4.8 — Files Phase 4 creates or modifies

```
eval/
  scenarios.py          — 30 Scenario dataclasses (24 clean + 6 hard)
  eval_agent.py         — runner: inject synthetic → invoke graph → compute metrics
  eval_retrieval.py     — RAG eval: 25 ground-truth pairs, MRR@3
  run_all_evals.py      — runs both evals, writes results/

results/
  eval_agent.json       — {f1, fnr, fnr_hard, protocol_compliance, n_scenarios}
  eval_retrieval.json   — {mrr_vector, mrr_hybrid, recall_vector, recall_hybrid}

tests/
  test_dependency_apis.py   — FIX-3 API contract tests

.github/workflows/
  eval.yml              — CI: checkout → dep tests → eval_agent --no-llm → gate

src/models/
  train_classifier.py   — FIX-1 feature order assertion added

src/agent/
  memory.py             — FIX-2 input logging (z_scores_json, hrv_values_json)
  graph.py              — FIX-2 assemble_alert_node updated to pass inputs

src/pipeline/
  runner.py             — FIX-5 baseline skew warning added

requirements.txt        — FIX-3 exact version pins
```

---

### 4.9 — Phase 4 success criteria

| Metric | Target | Why |
|---|---|---|
| FIX-1 verification passes | ✅ | Feature order consistent |
| FIX-2 verification passes | ✅ | Input logging active |
| FIX-3 all packages pinned | ✅ | No version drift risk |
| FIX-3 API tests pass | ✅ | Contracts verified |
| FIX-5 no skew warnings | ✅ | Baseline lookback consistent |
| FNR (RED), --no-llm | 0.000 | Safety — no missed critical alerts |
| F1 (macro), --no-llm | >= 0.80 | Rule-based path should easily achieve this |
| FNR on hard scenarios | Documented | Baseline for Phase 5/6 comparison |
| FNR (RED), live LLM | Documented | Generalist baseline |
| F1 (macro), live LLM | Documented | Generalist baseline |
| MRR@3 hybrid vs vector | Hybrid >= +0.05 delta | Validates hybrid retrieval |
| CI runtime | < 60 seconds | Practical for every-commit runs |

**Write the live-LLM numbers into `BENCHMARKS.md` immediately after running.**
These are your generalist baseline. Phase 6 will show the delta. Include a
separate row for hard-scenario performance.

---

## Phase 5 — Multi-Agent Architecture + Audit Hardening

**Goal:** Replace the single generalist agent with a supervisor routing to four
specialist subgraphs. Each specialist has a narrower prompt, targeted retrieval,
and measurably better performance on its specific task — especially on the
hard mixed-signal scenarios added in Phase 4.

**Time estimate:** 4.5 days (original 3.5 + 1 day for hardening fixes)

**Depends on:** Phase 4 baseline numbers. The hard-scenario FNR numbers from
Phase 4 tell you exactly what the signal specialist needs to be good at.

---

### 5.1 — Architecture overview

```
PipelineResult
      │
      ▼
 Supervisor node
  │
  ├──► Signal Interpretation Agent   (always runs)
  │    └── retrieves from: hrv_indicators, sepsis_early_warning chunks
  │
  ├──► Bradycardia Agent             (runs if events > 0 OR max_z > 2.0)
  │    └── retrieves from: bradycardia_patterns chunks
  │
  ├──► Clinical Reasoning Agent      (always runs, waits for both above)
  │    └── retrieves from: intervention_thresholds, baseline_interpretation
  │
  └──► Protocol Compliance Agent     (always runs last)
       └── no retrieval — uses APPROVED_ACTIONS list only
            │
            ▼
       NeonatalAlert
```

Each specialist is its own `StateGraph` compiled separately. The supervisor
is the outer graph that routes between them using conditional edges.

---

### 5.2 — Why four specialists and not more or fewer

**Signal Interpretation** is separated because HRV pattern reading is a distinct
skill from clinical decision-making. The generalist mixes them in one prompt.
A specialist that only asks "what do these z-scores mean physiologically"
produces sharper signal assessments — especially on the hard mixed-signal
scenarios where the generalist conflates signal interpretation with action
selection.

**Bradycardia** is separated because bradycardia interpretation requires different
clinical knowledge than HRV spectral analysis. A specialist asks "is this
isolated reflex bradycardia or pathological dysregulation" — categorically
different from spectral analysis.

**Clinical Reasoning** is separated so it receives already-interpreted findings,
not raw numbers. It reasons like a consultant receiving a handover, not a
technician reading sensors. This is the key improvement for hard scenarios
where the generalist is confused by contradictory signals.

**Protocol Compliance** is separated from clinical reasoning entirely. A proper
specialist can reason about whether a recommendation is appropriate given the
specific concern level, gestational age, and patient history — not just a
Pydantic string-match.

---

### 5.3 — Supervisor routing logic

```python
def route_after_supervisor(state: MultiAgentState) -> list[str]:
    """
    Signal agent always runs.
    Bradycardia agent runs if events present OR any z-score crosses threshold.
    """
    routes = ["signal_agent"]
    r = state["pipeline_result"]
    max_z = max(abs(z) for z in r.z_scores.values()) if r.z_scores else 0.0
    if len(r.detected_events) > 0 or max_z > 2.0:
        routes.append("bradycardia_agent")
    return routes
```

This is LangGraph's `send` pattern — parallel specialist invocation when both
are needed. Clinical reasoning waits for both specialists. Protocol agent waits
for clinical reasoning.

---

### 5.4 — Per-specialist prompt design

**Signal Interpretation Agent:**
```
You are a neonatal HRV signal analyst. Your only job is to interpret
what these z-score deviations mean physiologically.

Patient personal baseline z-scores:
{z_scores_formatted}

Retrieved HRV reference:
{hrv_chunks}  ← from hrv_indicators + sepsis_early_warning only

Output: SignalAssessment(
    autonomic_pattern: "pre_sepsis" | "bradycardia_reflex" | "normal_variation" | "indeterminate",
    primary_features: list[str],
    confidence: float,
    physiological_reasoning: str
)
```

**Bradycardia Agent:**
```
You are a neonatal bradycardia classification specialist.

Bradycardia events: {n_events} in last 6h
Event details: {event_list}
HRV context from signal agent: {signal_assessment}

Retrieved bradycardia patterns:
{bradycardia_chunks}

Output: BradycardiaAssessment(
    classification: "isolated_reflex" | "recurrent_without_suppression" |
                    "recurrent_with_suppression" | "cluster" | "apnoeic",
    clinical_weight: "low" | "medium" | "high",
    reasoning: str
)
```

**Clinical Reasoning Agent:**
```
You are a neonatal intensive care clinical decision support system.
You receive interpreted findings, not raw numbers.

Signal assessment: {signal_assessment}
Bradycardia assessment: {bradycardia_assessment}  ← may be None
Patient history: {episodic_context}
Intervention guidelines:
{intervention_chunks}

Output: LLMOutput (existing schema)
```

**Protocol Compliance Agent — pure logic, no LLM:**
```python
def protocol_agent_node(state):
    action = state["llm_output"].recommended_action
    level  = state["llm_output"].concern_level
    # Validates action is appropriate for concern level.
    # e.g. GREEN + "Blood culture" = protocol mismatch
    # Returns corrected action or flags for human review.
```

---

### 5.5 — New Pydantic schemas

```python
# src/agent/schemas.py

class SignalAssessment(BaseModel):
    autonomic_pattern: Literal[
        "pre_sepsis", "bradycardia_reflex",
        "normal_variation", "indeterminate"
    ]
    primary_features: list[str]
    confidence: float
    physiological_reasoning: str

    @field_validator("physiological_reasoning")
    @classmethod
    def reasoning_substantive(cls, v):
        if len(v.strip()) < 30:
            raise ValueError("physiological_reasoning too short")
        return v

class BradycardiaAssessment(BaseModel):
    classification: Literal[
        "isolated_reflex", "recurrent_without_suppression",
        "recurrent_with_suppression", "cluster", "apnoeic", "none"
    ]
    clinical_weight: Literal["low", "medium", "high"]
    reasoning: str
```

---

### 5.6 — Multi-agent state schema

```python
class MultiAgentState(TypedDict):
    patient_id:              str
    pipeline_result:         Optional[PipelineResult]
    rag_query_signal:        Optional[str]
    rag_query_brady:         Optional[str]
    rag_context_signal:      Optional[list[str]]
    rag_context_brady:       Optional[list[str]]
    rag_context_clinical:    Optional[list[str]]
    signal_assessment:       Optional[SignalAssessment]
    bradycardia_assessment:  Optional[BradycardiaAssessment]
    past_alerts:             Optional[list[PastAlert]]
    llm_output:              Optional[LLMOutput]
    self_check_passed:       Optional[bool]
    final_alert:             Optional[NeonatalAlert]
    error:                   Optional[str]
```

---

### 5.7 — FIX-6 🔴 Schema version tracking in `audit.db`

**What post-mortem it addresses:** Schema version drift. Phase 5 adds
`SignalAssessment` and `BradycardiaAssessment` — new information that should be
logged. If the schema changes without versioning, the `PastAlert(*row)` positional
row unpacking in `get_recent()` silently returns wrong values.

**Where it goes:** `src/agent/memory.py`

```python
# In _init_schema(), add alongside the existing table:
conn.execute("""
    CREATE TABLE IF NOT EXISTS schema_meta (
        key   TEXT PRIMARY KEY,
        value TEXT
    )
""")
existing = conn.execute(
    "SELECT value FROM schema_meta WHERE key='version'"
).fetchone()
if not existing:
    conn.execute(
        "INSERT INTO schema_meta (key, value) VALUES ('version', '2.0')"
    )

def _check_schema_version(self):
    with sqlite3.connect(self.db_path) as conn:
        row = conn.execute(
            "SELECT value FROM schema_meta WHERE key='version'"
        ).fetchone()
        if not row:
            raise RuntimeError(
                "audit.db has no schema_meta table. "
                "Run: python scripts/migrate_audit_db.py"
            )
        if row[0] != "2.0":
            raise RuntimeError(
                f"audit.db schema version {row[0]} != expected 2.0. "
                "Run migration script before proceeding."
            )
```

**Migration script** for existing Phase 3/4 databases:
```python
# scripts/migrate_audit_db.py
import sqlite3
from pathlib import Path

db = Path("data/audit.db")
with sqlite3.connect(db) as conn:
    existing = [r[1] for r in conn.execute("PRAGMA table_info(alert_history)")]
    for col, coltype in [
        ("z_scores_json",       "TEXT"),
        ("hrv_values_json",     "TEXT"),
        ("signal_pattern",      "TEXT"),
        ("signal_confidence",   "REAL"),
        ("brady_classification","TEXT"),
        ("brady_weight",        "TEXT"),
        ("agent_version",       "TEXT"),
    ]:
        if col not in existing:
            conn.execute(f"ALTER TABLE alert_history ADD COLUMN {col} {coltype}")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT)
    """)
    conn.execute(
        "INSERT OR REPLACE INTO schema_meta (key, value) VALUES ('version', '2.0')"
    )
print("Migration complete: audit.db is now schema version 2.0")
```

---

### 5.8 — FIX-7 🟡 Specialist output logging in `audit.db`

**What post-mortem it addresses:** End-to-end traceability for multi-agent
failures. If the clinical reasoning agent produces a wrong alert, you need to
know what the signal specialist told it. Without logging specialist outputs,
debugging multi-agent failures is impossible.

**Phase 5 full schema** (extends FIX-2 columns added in Phase 4):

```sql
CREATE TABLE IF NOT EXISTS alert_history (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id           TEXT,
    timestamp            TEXT,
    concern_level        TEXT,
    risk_score           REAL,
    top_feature          TEXT,
    top_z_score          REAL,
    z_scores_json        TEXT,    -- FIX-2
    hrv_values_json      TEXT,    -- FIX-2
    signal_pattern       TEXT,    -- FIX-7: SignalAssessment.autonomic_pattern
    signal_confidence    REAL,    -- FIX-7: SignalAssessment.confidence
    brady_classification TEXT,    -- FIX-7: BradycardiaAssessment.classification
    brady_weight         TEXT,    -- FIX-7: BradycardiaAssessment.clinical_weight
    agent_version        TEXT     -- FIX-7: "generalist" | "multi_agent"
)
```

**Note:** The `agent_version` column is important — when running A/B evals in
Phase 6, you can query the audit log to compare specialist output quality
across both agents on the same patients.

---

### 5.9 — FIX-8 🟡 Cross-agent baseline eval in CI

**What post-mortem it addresses:** Evaluation-production gap — both agents must
be measured on identical inputs. The `--agent` flag supports this but CI only
runs the generalist. Phase 5 adds a CI step that runs both and writes a
comparison to `results/eval_comparison.json`.

**Add to `.github/workflows/eval.yml` after Phase 5 is merged:**
```yaml
- name: Run multi-agent eval (no-LLM)
  env:
    QDRANT_PATH: qdrant_local
  run: >
    python eval/eval_agent.py
    --agent multi_agent
    --no-llm
    --fail-below-f1 0.85
    --fail-above-fnr 0.0
    --output results/eval_multiagent.json

- name: Compare generalist vs multi-agent
  run: |
    python -c "
    import json
    g = json.load(open('results/eval_agent.json'))
    m = json.load(open('results/eval_multiagent.json'))
    delta_f1      = m['f1'] - g['f1']
    delta_fnr     = m['fnr_red'] - g['fnr_red']
    delta_fnr_hard = m['fnr_hard'] - g['fnr_hard']
    print(f'F1 delta:       {delta_f1:+.3f}')
    print(f'FNR delta:      {delta_fnr:+.3f}')
    print(f'Hard-FNR delta: {delta_fnr_hard:+.3f}')
    assert delta_fnr <= 0, f'Multi-agent FNR WORSE than generalist: {delta_fnr:+.3f}'
    assert delta_fnr_hard <= 0, f'Multi-agent hard-scenario FNR WORSE: {delta_fnr_hard:+.3f}'
    print('CI PASS: multi-agent FNR not worse than generalist on either clean or hard scenarios')
    "
```

**Note:** F1 improvement is not a hard gate. FNR and hard-scenario FNR must not
regress. Those are the hard constraints.

---

### 5.10 — FIX-9 🟡 Qdrant mode parity test

**What post-mortem it addresses:** The plan switches between local path mode and
networked mode depending on Docker state. There is no test that verifies both
modes return identical results. If they differ, the agent produces different
outputs in development vs production silently.

```python
# tests/test_qdrant_parity.py
"""Run manually after Docker is restored:
  docker compose up qdrant -d
  python tests/test_qdrant_parity.py
"""
from src.knowledge.knowledge_base import ClinicalKnowledgeBase

TEST_QUERIES = [
    "RMSSD declining sepsis premature neonate",
    "bradycardia cluster three episodes 60 minutes",
    "personalised baseline LOOKBACK rolling window",
]

def test_parity():
    kb_local  = ClinicalKnowledgeBase(path="qdrant_local")
    kb_remote = ClinicalKnowledgeBase(host="localhost", port=6333)

    for query in TEST_QUERIES:
        local_results  = kb_local.query(query, n=3)
        remote_results = kb_remote.query(query, n=3)
        assert local_results == remote_results, (
            f"Parity failure for query: '{query}'\n"
            f"  Local:  {[r[:60] for r in local_results]}\n"
            f"  Remote: {[r[:60] for r in remote_results]}"
        )
    print("PASS: local-path and networked Qdrant return identical results")

if __name__ == "__main__":
    test_parity()
```

---

### 5.11 — Backward compatibility

The Phase 3 `agent` object in `graph.py` must still work for Phase 4 evals.
Phase 5 adds `multi_agent` alongside it. The eval runner supports both via
`--agent` flag.

```python
# src/agent/graph.py after Phase 5
from src.agent.supervisor import build_multi_agent_graph

agent       = build_graph()             # Phase 3 generalist — kept for baseline
multi_agent = build_multi_agent_graph() # Phase 5 multi-agent
```

---

### 5.12 — Files Phase 5 creates or modifies

```
src/agent/
  schemas.py            — add SignalAssessment, BradycardiaAssessment
  supervisor.py         — outer graph with routing logic
  graph.py              — imports supervisor, exposes multi_agent
  memory.py             — FIX-6 schema versioning, FIX-7 specialist logging
  specialists/
    __init__.py
    signal_agent.py     — SignalInterpretationAgent (StateGraph)
    brady_agent.py      — BradycardiaAgent (StateGraph)
    clinical_agent.py   — ClinicalReasoningAgent (StateGraph)
    protocol_agent.py   — ProtocolComplianceAgent (pure logic)

src/knowledge/
  knowledge_base.py     — add query_by_category(category: str) method

scripts/
  migrate_audit_db.py   — FIX-6 migration for Phase 3/4 databases

tests/
  test_qdrant_parity.py — FIX-9 parity test (manual, not CI)

.github/workflows/
  eval.yml              — FIX-8 cross-agent comparison step added
```

---

### 5.13 — Phase 5 success criteria

| Metric | Target | Why |
|---|---|---|
| schema_meta version == "2.0" | ✅ | FIX-6 schema version in place |
| Specialist outputs in audit.db | ✅ | FIX-7 logging active |
| CI cross-agent comparison passes | ✅ | FIX-8 no FNR regression |
| Multi-agent FNR (RED) | 0.000 | Same safety bar as generalist |
| Multi-agent hard-scenario FNR | <= generalist hard FNR | Key improvement |
| Multi-agent F1 vs generalist | >= +0.05 delta | Measurably better |
| Signal assessment accuracy | >= 80% correct autonomic_pattern | Specialist doing its job |
| Protocol compliance | >= 95% | Compliance agent working |
| Phase 4 CI still passing | ✅ | Backward compat maintained |

---

## Phase 6 — Eval Re-run + LoRA Fine-Tuning + Training Safety

**Goal:** Produce the three-way comparison table that goes in the paper.
Measure generalist vs multi-agent vs multi-agent with fine-tuned signal specialist.

**Time estimate:** 3.5 days (original 3 + 0.5 day for training safety fixes)

**Depends on:** Phase 5 multi-agent working.

---

### 6.1 — FIX-10 🟡 Training data distribution logging in `train_classifier.py`

**What post-mortem it addresses:** If you retrain in Phase 6 (LoRA comparison
requires a fresh baseline), there is currently no record of class distribution
per patient or feature statistics at training time. This makes it impossible to
diagnose why a retrained model behaves differently.

**Where it goes:** `src/models/train_classifier.py`, after data loading.

```python
logging.info("=== Training Data Distribution ===")
logging.info("Total rows: %d | Positive: %d (%.3f%%)",
    len(df), df[LABEL_COL].sum(), 100 * df[LABEL_COL].mean())

logging.info("Per-patient distribution:")
for pid, group in df.groupby("record_name"):
    pos = int(group[LABEL_COL].sum())
    n   = len(group)
    logging.info("  %-12s %d/%d pos (%.2f%%)", pid, pos, n, 100*pos/n)

logging.info("Feature statistics (mean ± std):")
for feat in HRV_FEATURE_COLS:
    logging.info("  %-20s %.3f ± %.3f",
        feat, df[feat].mean(), df[feat].std())

# Write machine-readable alongside AUC-PR:
with open(LOGS_DIR / "train_classifier.log", "a") as f:
    f.write(f"n_total: {len(df)}\n")
    f.write(f"n_positive: {int(df[LABEL_COL].sum())}\n")
    f.write(f"pos_rate: {df[LABEL_COL].mean():.6f}\n")
    for feat in HRV_FEATURE_COLS:
        f.write(f"feature_{feat}_mean: {df[feat].mean():.4f}\n")
        f.write(f"feature_{feat}_std:  {df[feat].std():.4f}\n")
```

---

### 6.2 — FIX-11 🟡 LoRA training data label validation gate

**What post-mortem it addresses:** A fine-tuned model trained on wrong labels
produces confident wrong outputs — worse than no fine-tuning at all. Labels need
human sign-off before training begins.

**Where it goes:** `notebooks/05_signal_specialist_lora.ipynb`, mandatory cell
before the training cell.

```python
# Cell N — MUST RUN before training cell
import pandas as pd
train_df = pd.read_json("data/lora_training/signal_train.jsonl", lines=True)

print("Label distribution:")
print(train_df["output"].apply(lambda x: eval(x)["autonomic_pattern"]).value_counts())

print("\n10 random samples for manual review:")
for _, row in train_df.sample(10, random_state=42).iterrows():
    print(f"\nInput: {row['input']}")
    print(f"Label: {eval(row['output'])['autonomic_pattern']}")
    print(f"Reasoning: {eval(row['output'])['physiological_reasoning'][:100]}")

# Check for class imbalance — warn if any class < 15% of training data
pattern_counts = train_df["output"].apply(
    lambda x: eval(x)["autonomic_pattern"]
).value_counts(normalize=True)
for pattern, pct in pattern_counts.items():
    if pct < 0.15:
        print(f"WARNING: '{pattern}' is underrepresented ({pct:.1%}) — model may underperform on this class")

# Hard gate: require manual confirmation
confirmed = input("\nHave you reviewed the labels and class balance? Type 'yes' to proceed: ")
assert confirmed.strip().lower() == "yes", "Training aborted — labels not confirmed"
print("Labels confirmed. Proceeding to training.")
```

---

### 6.3 — Part A: Eval re-run (0.5 days)

Run Phase 4 eval suite against the multi-agent. Write to
`results/eval_multiagent.json`. Update `BENCHMARKS.md` with the delta.

```bash
python eval/eval_agent.py \
  --agent multi_agent \
  --fail-below-f1 0.85 \
  --fail-above-fnr 0.0 \
  --output results/eval_multiagent.json
```

The eval runner `--agent` flag switches between `agent` and `multi_agent` from
`src/agent/graph.py`. Everything else is identical — same 30 scenarios, same
metrics.

---

### 6.4 — Part B: LoRA fine-tuning for signal specialist (2.5 days)

**Base model:** `microsoft/Phi-3-mini-4k-instruct` (3.8B parameters).
Runs on M2 MacBook Air with 4-bit quantisation via QLoRA.

**Training data:** For each of the 30 eval scenarios, generate signal assessment
ground truth labels from the large Groq LLM (verified by FIX-11 gate above).
Augment with 200+ additional synthetic HRV windows from `synthetic_generator.py`.

**Training format:**
```json
{
  "instruction": "Classify this neonatal HRV pattern...",
  "input": "rmssd z=-3.1, lf_hf_ratio z=+2.8, pnn50 z=-2.5, sdnn z=-1.8",
  "output": "{\"autonomic_pattern\": \"pre_sepsis\", \"primary_features\": [\"rmssd\", \"lf_hf_ratio\"], ...}"
}
```

**Training setup:**
```python
# notebooks/05_signal_specialist_lora.ipynb
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, BitsAndBytesConfig

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4"
)

lora_config = LoraConfig(
    r=16,
    lora_alpha=32,
    target_modules=["q_proj", "v_proj"],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM"
)
```

**What to measure after fine-tuning:**
- Signal assessment accuracy (autonomic_pattern) vs Groq specialist
- Hard-scenario accuracy specifically — this is where LoRA training on
  mixed-signal examples should show the biggest gain
- Latency: fine-tuned local inference vs Groq API call
- End-to-end agent F1 and FNR with fine-tuned specialist vs Groq specialist

---

### 6.5 — The three-way comparison table

| Approach | F1 | FNR | Hard-FNR | Latency | Protocol | Notes |
|---|---|---|---|---|---|---|
| Generalist single agent | X.XXX | 0.000 | X.XXX | ~2s | ~85% | Phase 4 baseline |
| Multi-agent (all Groq) | X.XXX | 0.000 | X.XXX | ~4s | ~96% | Phase 5 result |
| Multi-agent (LoRA signal + Groq reasoning) | X.XXX | 0.000 | X.XXX | ~1.8s | ~96% | Phase 6 result |

The Hard-FNR column is the new addition from the integrated plan — it shows that
the multi-agent and LoRA specialist improvements are specifically meaningful on
ambiguous clinical cases, not just easy clean-signal scenarios.

**DSPy mention (even if not built):** DSPy compiles prompts automatically by
optimising against a labelled eval set. The Phase 4/5 eval suite is exactly the
kind of labelled set DSPy needs. Relevant as future work in the paper discussion.

---

### 6.6 — Files Phase 6 creates or modifies

```
notebooks/
  05_signal_specialist_lora.ipynb   — QLoRA training (FIX-11 gate cell included)
  06_fine_tune_comparison.ipynb     — three-way comparison plots

models/exports/
  signal_specialist_lora/           — fine-tuned adapter weights

src/models/
  train_classifier.py               — FIX-10 distribution logging added

src/agent/specialists/
  signal_agent.py                   — updated: flag for local LoRA vs Groq

eval/
  eval_agent.py                     — updated: --agent flag for generalist vs multi

results/
  eval_multiagent.json
  eval_lora.json

BENCHMARKS.md                       — three-way comparison table with Hard-FNR column
```

---

### 6.7 — Phase 6 success criteria

| Metric | Target |
|---|---|
| FIX-10 distribution log present | ✅ after any retrain |
| FIX-11 label gate passed | ✅ before training |
| Three-way comparison table complete | All three rows have real numbers |
| Hard-scenario FNR column filled | All three rows |
| LoRA inference latency | <= 0.5s per signal assessment |
| Multi-agent F1 > generalist F1 | Positive delta |
| All CI checks still passing | No regression |

---

## Phase 7 — FastAPI + Docker + LangSmith + Production Monitoring

**Goal:** `docker compose up` starts everything. One HTTP call runs the full
multi-agent pipeline. SSE streaming shows per-specialist progress. LangSmith
traces every specialist separately. Production monitoring catches silent failures
before they become patient safety events.

**Time estimate:** 3 days (original 2.5 + 0.5 day for monitoring fixes)

**Depends on:** Phase 5 multi-agent. Phase 6 LoRA is optional.

---

### 7.1 — API design

Two endpoints. Both call `multi_agent`, not the generalist.

**Blocking endpoint:**
```
POST /assess/{patient_id}
→ NeonatalAlert JSON
```

**Streaming SSE endpoint:**
```
GET /assess/{patient_id}/stream

data: {"stage": "pipeline",    "status": "running"}
data: {"stage": "pipeline",    "status": "done", "risk_score": 0.84, "risk_level": "RED"}
data: {"stage": "signal",      "status": "running"}
data: {"stage": "signal",      "status": "done", "pattern": "pre_sepsis", "confidence": 0.91}
data: {"stage": "bradycardia", "status": "running"}
data: {"stage": "bradycardia", "status": "done", "classification": "recurrent_with_suppression"}
data: {"stage": "reasoning",   "status": "running"}
data: {"stage": "reasoning",   "status": "done"}
data: {"stage": "complete",    "alert": {...full NeonatalAlert...}}
```

The clinician sees the system's reasoning unfold — signal assessment first, then
bradycardia classification, then synthesis. Each stage completing is actionable
information before the final alert arrives.

**Additional endpoints:**
```
GET  /patient/{patient_id}/history         → last N alerts from SQLite
GET  /health                               → full system status (extended in FIX-12/13)
POST /assess/{patient_id}/generalist       → run generalist agent (A/B comparison)
```

---

### 7.2 — LangSmith observability with per-specialist spans

```
Run: assess/infant1
├── supervisor_node          (2ms)
├── signal_agent             (340ms)
│   ├── build_signal_query   (1ms)
│   ├── retrieve_hrv_chunks  (45ms)
│   └── llm_signal_reason    (290ms)   ← or local LoRA: 80ms
├── bradycardia_agent        (280ms)
│   ├── build_brady_query    (1ms)
│   ├── retrieve_brady_chunks(42ms)
│   └── llm_brady_classify   (235ms)
├── clinical_reasoning_agent (680ms)
│   ├── retrieve_clinical    (44ms)
│   └── llm_clinical_reason  (630ms)
├── protocol_agent           (3ms)
└── assemble_alert           (2ms)
```

Cost per run is now trackable per specialist. If signal specialist is LoRA-local,
that shows as zero API cost in LangSmith.

---

### 7.3 — FIX-12 🟢 Prediction distribution monitoring in health endpoint

**What post-mortem it addresses:** If a bug causes all patients to receive RED
alerts, nothing in the current system raises an alarm until a human notices.

**Where it goes:** `api/main.py`

```python
@app.get("/health")
async def health():
    try:
        kb = ClinicalKnowledgeBase(path=os.getenv("QDRANT_PATH", "qdrant_local"))
        doc_count = kb.client.count("clinical_knowledge").count
        qdrant_ok = True
    except Exception:
        doc_count = 0
        qdrant_ok = False

    # FIX-12: prediction distribution from last 100 alerts
    try:
        import sqlite3, json
        with sqlite3.connect("data/audit.db") as conn:
            rows = conn.execute("""
                SELECT concern_level, COUNT(*) as n
                FROM (
                    SELECT concern_level FROM alert_history
                    ORDER BY timestamp DESC LIMIT 100
                )
                GROUP BY concern_level
            """).fetchall()
            dist = {row[0]: row[1] for row in rows}
            total = sum(dist.values())
            red_rate = dist.get("RED", 0) / max(total, 1)
            # Historical base rate ~0.4% — 20% = 50x elevated
            prediction_health = "ok" if red_rate < 0.20 else "elevated_red_rate"

            # Also check for complete suppression (all GREEN when RED expected)
            green_rate = dist.get("GREEN", 0) / max(total, 1)
            if green_rate > 0.95:
                prediction_health = "suppressed_alerts_possible"
    except Exception:
        dist = {}
        prediction_health = "unknown"

    return {
        "status": "ok",
        "qdrant": qdrant_status,           # from FIX-13 below
        "knowledge_base_docs": doc_count,
        "prediction_distribution_last_100": dist,
        "prediction_health": prediction_health,
        "schema_version": "2.0",
        "retrieval": "hybrid_dense_sparse_rrf_reranked",
        "guardrails": "instructor_pydantic_v2",
        "episodic_memory": "sqlite_v2.0",
    }
```

---

### 7.4 — FIX-13 🟢 Chunk count verification in health endpoint

**What post-mortem it addresses:** The KB is verified once during build but never
at runtime. If the Qdrant collection is partially corrupted or rebuilt with wrong
chunk count, queries degrade silently.

```python
# In health endpoint, extend Qdrant check:
EXPECTED_CHUNK_COUNT = 34  # update if KB is rebuilt with more chunks

if doc_count != EXPECTED_CHUNK_COUNT:
    qdrant_status = f"wrong_chunk_count_{doc_count}_expected_{EXPECTED_CHUNK_COUNT}"
else:
    qdrant_status = "ok"
```

---

### 7.5 — FIX-14 🟢 Docker migration test for Qdrant

**What post-mortem it addresses:** When Docker is restored, the switch from
`qdrant_local/` to networked Qdrant needs to be validated before production.

```bash
# Phase 7 pre-flight — run before starting full docker compose:
docker compose up qdrant -d
sleep 5

# FIX-9 parity test — verifies both modes return identical results
python tests/test_qdrant_parity.py

# Then switch graph to networked mode:
# In retrieve_context_node and all specialist retrieve nodes, change:
#   ClinicalKnowledgeBase(path=os.getenv("QDRANT_PATH", str(REPO_ROOT / "qdrant_local")))
# to:
#   ClinicalKnowledgeBase()  # uses QDRANT_HOST and QDRANT_PORT from .env
# Set in .env: QDRANT_HOST=qdrant, QDRANT_PORT=6333
# The path= vs host= toggle is already built into ClinicalKnowledgeBase.__init__
```

---

### 7.6 — Docker: four services

```yaml
services:
  neonatalguard-api:
    build: .
    ports: ["8000:8000"]
    env_file: .env
    volumes: ["./data:/app/data"]
    depends_on: [qdrant]
    platform: linux/arm64

  qdrant:
    image: qdrant/qdrant:latest
    ports: ["6333:6333"]
    volumes: ["qdrant_data:/qdrant/storage"]
    platform: linux/arm64

  eval-runner:
    build: .
    command: python eval/run_all_evals.py --agent multi_agent
    depends_on: [neonatalguard-api, qdrant]
    profiles: ["eval"]

  signal-specialist:
    image: ollama/ollama
    volumes: ["./models/exports/signal_specialist_lora:/models"]
    profiles: ["lora"]
    platform: linux/arm64

volumes:
  qdrant_data:
```

---

### 7.7 — Files Phase 7 creates or modifies

```
api/
  main.py               — FastAPI: blocking + SSE + history + health (FIX-12/13)

Dockerfile
docker-compose.yml      — 4-service compose

src/agent/
  supervisor.py         — @traceable decorators on all specialist calls

scripts/
  pre_flight.sh         — FIX-14 parity test + docker startup sequence
```

---

### 7.8 — Phase 7 success criteria

| Metric | Target |
|---|---|
| FIX-12 health endpoint returns distribution | ✅ |
| FIX-13 chunk count verified at runtime | ✅ |
| FIX-14 parity test passes pre-docker | ✅ |
| `docker compose up` starts clean | All services healthy |
| `POST /assess/infant1` returns NeonatalAlert | < 5s end-to-end |
| `GET /assess/infant1/stream` streams all 7 events | Verified with curl |
| LangSmith trace shows per-specialist spans | Visible in dashboard |
| Health endpoint flags elevated RED rate correctly | Tested with injected bad data |
| `docker compose --profile eval up` runs eval suite | CI-equivalent in Docker |

---

## Phase 8 — Emissions RAG Bridge

**Goal:** Close the Unravel Carbon domain gap. Demonstrate that the same
multi-agent architecture applies to sustainability analysis.

**Time estimate:** 1.5 days
**Depends on:** Phase 5 (specialist pattern), Phase 7 (API pattern)

---

### 8.1 — Architecture mapping

| NeonatalGuard | Emissions RAG |
|---|---|
| ONNX risk classifier | Emission intensity calculator (rules-based) |
| Personalised HRV baseline | Per-company emission baseline vs sector |
| Signal interpretation specialist | Scope analysis specialist (Scope 1/2/3 decomposition) |
| Clinical reasoning specialist | Reduction pathway specialist |
| Protocol compliance | GHG Protocol / SBTi compliance validator |
| `NeonatalAlert` | `EmissionsAlert` |
| audit.db agent_version field | Records which pipeline generated the assessment |

---

### 8.2 — Knowledge base (30 GHG Protocol chunks)

```
emissions_rag/data/ghg_protocol/
  scope_definitions.txt
  scope2_methods.txt        — market-based vs location-based
  scope3_categories.txt     — all 15 categories, focus on Cat 1 and Cat 11
  ghg_protocol_standard.txt
  sbti_framework.txt        — SBTi 1.5°C alignment methodology
  csrd_requirements.txt     — EU CSRD disclosure obligations
  emission_factors.txt      — DEFRA, EPA, IEA factor sources
  carbon_offsets.txt        — offsets vs removals, permanence distinction
  reduction_pathways.txt    — near-term vs long-term, ROI ranking
  lifecycle_assessment.txt  — LCA basics for Scope 3 Cat 1
```

---

### 8.3 — Sample agent output

```python
emissions_agent.invoke({"company_id": "COMPANY-001"})
# Returns EmissionsAlert:
# scope_breakdown: {"scope_1": 1250, "scope_2": 3847, "scope_3": 28400}
# primary_sources: ["Scope 3 Cat 1 (purchased goods)", "Scope 2 (grid electricity)"]
# reduction_pathway: "Supplier engagement on Cat 1 + PPA for Scope 2"
# sbti_aligned: False
# csrd_reportable: True
# recommended_action: "Set science-based target aligned with 1.5°C"
```

---

### 8.4 — Phase 8 success criteria

| Metric | Target |
|---|---|
| Scope analysis specialist produces valid output | ✅ |
| Reduction pathway reasoning references KB chunks | ✅ |
| GHG Protocol compliance validator working | ✅ |
| Demo query produces EmissionsAlert in < 5s | ✅ |

---

## Unified Summary: Fix to Phase Mapping

| Fix | Description | Phase | Priority |
|-----|-------------|-------|----------|
| FIX-1 | Feature order assertion in `train_classifier.py` | Phase 4 | 🔴 |
| FIX-2 | Input logging (z_scores, hrv_values) in `audit.db` | Phase 4 | 🔴 |
| FIX-3 | Pin exact dependency versions + API contract tests | Phase 4 | 🔴 |
| FIX-4 | Mixed-signal hard scenarios in eval suite | Phase 4 | 🟡 |
| FIX-5 | Baseline skew warning in `runner.py` | Phase 4 | 🟡 |
| FIX-6 | Schema version tracking in `audit.db` | Phase 5 | 🔴 |
| FIX-7 | Specialist output logging (signal + brady + agent_version) | Phase 5 | 🟡 |
| FIX-8 | Cross-agent CI comparison with hard-scenario FNR gate | Phase 5 | 🟡 |
| FIX-9 | Qdrant local vs networked parity test | Phase 5 | 🟡 |
| FIX-10 | Training data distribution logging | Phase 6 | 🟡 |
| FIX-11 | LoRA training label validation gate with class balance check | Phase 6 | 🟡 |
| FIX-12 | Prediction distribution monitoring in `/health` | Phase 7 | 🟢 |
| FIX-13 | Chunk count verification in `/health` | Phase 7 | 🟢 |
| FIX-14 | Docker migration parity test pre-flight | Phase 7 | 🟢 |

---

## Full Tech Stack

### Core Agent Stack
- **LangGraph** — multi-agent orchestration (supervisor + 4 specialist subgraphs)
- **Groq (llama-3.3-70b-versatile)** — LLM inference for clinical and reasoning specialists
- **instructor** — schema-enforced LLM outputs, Pydantic validation, auto-retry
- **LangSmith** — per-specialist observability, cost tracking, prompt versioning

### RAG Stack
- **Qdrant** (self-hosted, Docker) — vector DB with metadata filtering
- **all-MiniLM-L6-v2** — dense embedding (384d)
- **TF-IDF sparse vectors** — BM25-style keyword matching
- **RRF fusion** — Reciprocal Rank Fusion merging dense + sparse
- **FlashRank (ms-marco-MiniLM-L-12-v2)** — cross-encoder reranking

### Signal Processing / ML Stack
- **NeuroKit2** — ECG processing, R-peak detection
- **ONNX Runtime** — edge inference on M2 (CoreML provider)
- **scikit-learn** — GBC classifier, AUC-PR, F1 evaluation
- **skl2onnx** — sklearn to ONNX export

### Fine-Tuning Stack
- **HuggingFace Transformers + PEFT** — QLoRA fine-tuning
- **Phi-3-mini-4k-instruct** — base model (3.8B, M2 compatible)
- **BitsAndBytes** — 4-bit quantisation

### Production Stack
- **FastAPI** — REST API + SSE streaming
- **Docker + docker-compose** — 4-service deployment
- **SQLite** — episodic memory + versioned audit log
- **Pydantic v2** — all I/O contracts
- **GitHub Actions** — CI eval gate, FNR=0 enforcement, cross-agent comparison

---

## BENCHMARKS.md (Target state after Phase 6)

```markdown
# NeonatalGuard Benchmarks

## Pipeline
| Metric | Value |
|---|---|
| AUC-ROC | X.XXX |
| AUC-PR  | 0.0176 (595 positives / 144,653 windows) |
| ONNX vs sklearn max diff | < 1e-7 |

## RAG Retrieval (25 ground-truth pairs)
| Metric | Vector-only | Hybrid+Rerank | Delta |
|---|---|---|---|
| MRR@3 | X.XXX | X.XXX | +X.XXX |
| Recall@3 | X.XXX | X.XXX | +X.XXX |
| Numeric query accuracy | X.XXX | X.XXX | +X.XXX |

## Agent Performance — Clean Scenarios (24)
| Approach | F1 | FNR(RED) | Protocol | Latency p50 |
|---|---|---|---|---|
| Generalist (Phase 4) | X.XXX | 0.000 | XX% | ~2s |
| Multi-agent Groq (Phase 5) | X.XXX | 0.000 | XX% | ~4s |
| Multi-agent LoRA+Groq (Phase 6) | X.XXX | 0.000 | XX% | ~1.8s |

## Agent Performance — Hard Scenarios (6, mixed-signal)
| Approach | F1 | FNR(RED) | Notes |
|---|---|---|---|
| Generalist (Phase 4) | X.XXX | X.XXX | Baseline on ambiguous cases |
| Multi-agent Groq (Phase 5) | X.XXX | X.XXX | Specialist routing benefit |
| Multi-agent LoRA+Groq (Phase 6) | X.XXX | X.XXX | LoRA trained on mixed-signal data |
```

---

## Dependency Map

```
Phase 4 (eval + hardening fixes 1–5)
    └── Phase 5 (multi-agent + hardening fixes 6–9)
            ├── Phase 6 (re-eval + LoRA + hardening fixes 10–11)
            └── Phase 7 (production + hardening fixes 12–14)
                        └── Phase 8 (emissions RAG bridge)
```

Phase 6 and Phase 7 are independent of each other after Phase 5.
Phase 8 depends on Phase 5 (specialist pattern) and Phase 7 (API pattern).

---

*Unified gameplan version 4.0 — March 2026*
*Integrates: eval framework, multi-agent supervisor, post-mortem hardening,*
*QLoRA fine-tuning, SSE streaming, 4-service Docker, production monitoring,*
*emissions RAG bridge. 14 hardening fixes woven into 5 phases.*