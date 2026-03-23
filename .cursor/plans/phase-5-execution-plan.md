# Phase 5 Execution Plan — Multi-Agent Architecture + Audit Hardening

**Overall Progress:** `0% (0/13 steps done)`

---

## TLDR

Replace the single 6-node generalist agent with a supervisor graph routing through four specialist subgraphs: Signal Interpretation, Bradycardia Classification, Clinical Reasoning, and Protocol Compliance. Each specialist has a narrower prompt and targeted KB retrieval. The goal is to improve YELLOW/GREEN discrimination (generalist live F1=0.533) and protocol compliance (0.667) by separating concerns. FIX-6 adds schema versioning to audit.db so specialist outputs can be logged and traced. FIX-7 logs `SignalAssessment` and `BradycardiaAssessment` outputs per alert. FIX-8 adds a cross-agent CI comparison step. The generalist `agent` object is unchanged — `multi_agent` is exported alongside it. Phase 5 is complete when `multi_agent` passes all 30 eval scenarios with FNR(RED)=0.000 and F1 ≥ generalist baseline (0.533).

---

## Critical Decisions

- **Sequential graph, not parallel fan-out:** The four specialists run sequentially (signal → optional brady → clinical → protocol). LangGraph's `send` fan-out pattern adds complexity for no observable benefit at this scale. A conditional edge after `signal_node` handles the brady routing.
- **Each specialist is a node function, not a nested compiled subgraph:** Flat graph = same LangSmith tracing, simpler state management, easier to debug. The "specialist" is a focused function, not a separate `StateGraph`.
- **`EVAL_NO_LLM` propagates to all specialists:** Every LLM-calling node checks `_is_eval_mode()` at call time and returns deterministic rule-based output. Multi-agent CI gate works without a Groq key.
- **`query_by_category()` uses `should` filter (OR):** Takes a `list[str]` of category strings and returns chunks from any of them. Category values are: `hrv_indicators`, `sepsis_early_warning`, `bradycardia_patterns`, `intervention_thresholds`, `baseline_interpretation`.
- **FIX-6+7 are a split operation:** Phase A adds schema_meta + 5 new columns to audit.db (idempotent via try/except). Phase B updates `save()` signature. Human gate between them.
- **`save()` remains backward-compatible:** New specialist kwargs have `None` defaults. All existing callers pass only positional args — they still work unchanged.
- **Generalist `assemble_alert_node` unchanged:** FIX-7 logging only fires from the multi-agent `assemble_multi_node` which passes specialist outputs explicitly.

---

## Clarification Gate

| Unknown | Required | Source | Blocking | Resolved |
|---------|----------|--------|----------|----------|
| Groq model to use for specialists | Model name string | Codebase (`graph.py` line 231: `llama-3.3-70b-versatile`) | Steps 5–7 | ✅ |
| KB category values | Exact strings for `query_by_category()` | Confirmed: `hrv_indicators`, `sepsis_early_warning`, `bradycardia_patterns`, `intervention_thresholds`, `baseline_interpretation` | Step 2 | ✅ |
| Existing `save()` signature | Current positional args | `memory.py` line 100–107 | Step 4 | ✅ |
| Qdrant `should` filter import | Which Qdrant model class handles OR logic | `knowledge_base.py` imports: `Filter`, `FieldCondition`, `MatchValue` already imported; need to confirm `should` keyword works | Step 2 | ✅ |

---

## Agent Failure Protocol

1. A verification command fails → read the full error output.
2. Cause is unambiguous → make ONE targeted fix → re-run the same verification command.
3. If still failing after one fix → **STOP**. Before stopping, output the full current contents of every file modified in this step. Report: (a) command run, (b) full error verbatim, (c) fix attempted, (d) current state of each modified file, (e) why you cannot proceed.
4. Never attempt a second fix without human instruction.
5. Never modify files not named in the current step.

---

## Pre-Flight — Run Before Any Code Changes

```bash
# 1. Confirm multi_agent does NOT exist yet in graph.py
grep -n "multi_agent" src/agent/graph.py

# 2. Confirm SignalAssessment / BradycardiaAssessment NOT in schemas.py
grep -n "SignalAssessment\|BradycardiaAssessment" src/agent/schemas.py

# 3. Confirm query_by_category NOT in knowledge_base.py
grep -n "query_by_category" src/knowledge/knowledge_base.py

# 4. Confirm specialists/ directory does NOT exist
ls src/agent/specialists/ 2>&1 || echo "specialists/ does not exist"

# 5. Confirm schema_meta table does NOT exist in audit.db
python -c "
import sqlite3
conn = sqlite3.connect('data/audit.db')
tbls = [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]
print('Tables in audit.db:', tbls)
"

# 6. Confirm existing generalist eval still passes
python -m pytest tests/test_dependency_apis.py -v --tb=short 2>&1 | tail -5

# 7. Record current audit.db column count
python -c "
import sqlite3
cols = [r[1] for r in sqlite3.connect('data/audit.db').execute('PRAGMA table_info(alert_history)').fetchall()]
print('alert_history columns:', len(cols), cols)
"

# 8. Confirm save() current signature
grep -n "def save" src/agent/memory.py
```

**Baseline Snapshot (agent fills during pre-flight):**
```
multi_agent in graph.py:                  ____  (expect: 0 matches)
SignalAssessment in schemas.py:           ____  (expect: 0 matches)
query_by_category in knowledge_base.py:  ____  (expect: 0 matches)
specialists/ directory:                   ____  (expect: does not exist)
schema_meta table:                        ____  (expect: not in table list)
alert_history column count:               ____  (expect: 9)
save() signature:                         ____  (confirm current 5-arg form)
```

---

## Steps Analysis

```
Step 1  (schemas: SignalAssessment + BradycardiaAssessment) — Critical (all specialists depend on these types)         — full code review — Idempotent: Yes
Step 2  (KB: query_by_category)                            — Critical (specialists need category-filtered retrieval)   — full code review — Idempotent: Yes
Step 3  (FIX-6+7 Phase A: schema migration)                — Critical (split op: schema before data)                   — full code review — Idempotent: Yes
Step 4  (FIX-6+7 Phase B: update save())                   — Critical (writes specialist outputs to audit.db)          — full code review — Idempotent: Yes
Step 5  (signal_agent.py)                                  — Critical (first specialist; blocks supervisor)            — full code review — Idempotent: Yes
Step 6  (brady_agent.py)                                   — Critical (conditional specialist; blocks supervisor)       — full code review — Idempotent: Yes
Step 7  (clinical_agent.py)                                — Critical (produces LLMOutput; blocks final alert)          — full code review — Idempotent: Yes
Step 8  (protocol_agent.py)                                — Critical (pure logic compliance check)                    — full code review — Idempotent: Yes
Step 9  (supervisor.py + MultiAgentState)                  — Critical (wires all nodes together)                       — full code review — Idempotent: Yes
Step 10 (export multi_agent from graph.py)                 — Critical (eval runner imports this)                        — full code review — Idempotent: Yes
Step 11 (FIX-8: cross-agent CI step in eval.yml)           — Important (CI regression gate)                            — full code review — Idempotent: Yes
Step 12 (FIX-9: tests/test_qdrant_parity.py)               — Non-critical (manual test, no CI)                         — verification only — Idempotent: Yes
Step 13 (re-run evals + update BENCHMARKS.md)              — Critical (Phase 5 cannot be called done without this)     — verification only — Idempotent: Yes
```

---

## Environment Matrix

| Step | Dev | CI | Notes |
|------|-----|----|-------|
| Steps 1–10 | ✅ | ✅ | Code changes only |
| Step 11 (FIX-8) | ✅ | ✅ | eval.yml CI step |
| Step 12 (FIX-9) | ✅ | ❌ Skip | Manual; requires Docker Qdrant |
| Step 13 (no-LLM eval) | ✅ | ✅ | CI runs automatically |
| Step 13 (live-LLM eval) | ✅ | ⚠️ Manual | Requires GROQ_API_KEY |

---

## Phase 1 — Schemas + KB Extension

**Goal:** New Pydantic types for specialist outputs exist. KB supports category-filtered retrieval. No agent code written yet.

---

- [ ] 🟥 **Step 1: Add `SignalAssessment` and `BradycardiaAssessment` to `src/agent/schemas.py`** — *Critical: all four specialist nodes depend on these types*

  **Idempotent:** Yes — appending new classes; no existing code touched.

  **Context:** `schemas.py` currently exports `LLMOutput`, `NeonatalAlert`, and `APPROVED_ACTIONS`. Two new schemas are needed for specialist output contracts. `SignalAssessment` captures the autonomic pattern read by the signal specialist. `BradycardiaAssessment` captures the bradycardia classification. Both use `instructor`-enforced Pydantic validation so malformed LLM output is caught at parse time.

  **Pre-Read Gate:**
  - Run `grep -n "SignalAssessment\|BradycardiaAssessment" src/agent/schemas.py`. Must return 0 matches. If any → already done, skip.
  - Run `grep -n "^class\|^APPROVED" src/agent/schemas.py`. Confirm existing classes: `LLMOutput`, `NeonatalAlert` and `APPROVED_ACTIONS` constant. Expected: lines 15, 27, 72.

  **Self-Contained Rule:** All code below is complete and runnable.

  **No-Placeholder Rule:** No `<VALUE>` tokens.

  In `src/agent/schemas.py`, append the following after the `NeonatalAlert` class (end of file):

  ```python
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
  ```

  **What it does:** Defines two Pydantic schemas with field validators. These are the structured output contracts for the signal and bradycardia specialist nodes.

  **Why this approach:** Pydantic validators at parse time (via `instructor`) catch malformed LLM output before it reaches downstream nodes. Same pattern as existing `LLMOutput`.

  **Assumptions:**
  - `src/agent/schemas.py` already imports `Literal` from `typing` and `field_validator`, `BaseModel` from pydantic — confirmed at lines 12–13.

  **Risks:**
  - `Literal` not imported → `NameError` at import time → Pre-Read Gate confirms existing import.

  **Git Checkpoint:**
  ```bash
  git add src/agent/schemas.py
  git commit -m "step 5.1: add SignalAssessment and BradycardiaAssessment schemas to schemas.py"
  ```

  **Subtasks:**
  - [ ] 🟥 Pre-Read Gate: 0 matches for both new class names
  - [ ] 🟥 `SignalAssessment` appended with validators
  - [ ] 🟥 `BradycardiaAssessment` appended
  - [ ] 🟥 Verification passes

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  python -c "
  import sys; sys.path.insert(0, '.')
  from src.agent.schemas import SignalAssessment, BradycardiaAssessment

  # Valid SignalAssessment
  sa = SignalAssessment(
      autonomic_pattern='pre_sepsis',
      primary_features=['rmssd', 'lf_hf_ratio'],
      confidence=0.85,
      physiological_reasoning='RMSSD and LF/HF suppression consistent with autonomic withdrawal.'
  )
  assert sa.autonomic_pattern == 'pre_sepsis'

  # Valid BradycardiaAssessment
  ba = BradycardiaAssessment(
      classification='recurrent_with_suppression',
      clinical_weight='high',
      reasoning='Three episodes with concurrent HRV suppression.'
  )
  assert ba.clinical_weight == 'high'

  print('PASS Step 1: SignalAssessment and BradycardiaAssessment import and validate correctly')
  "
  ```

  **Expected:** `PASS Step 1:` printed. Exit code 0.

  **Pass:** Both schemas instantiate without error; fields are correct types.

  **Fail:**
  - `ImportError` → class not appended or syntax error — re-read end of schemas.py.
  - `ValidationError` → validator rejecting valid test data — check field constraints.

---

- [ ] 🟥 **Step 2: Add `query_by_category()` to `ClinicalKnowledgeBase`** — *Critical: specialists need category-filtered retrieval*

  **Idempotent:** Yes — adding a new method; `query()` is unchanged.

  **Context:** `knowledge_base.py` has `query()` (hybrid, filters by `risk_tier`) and `query_vector_only()` (dense-only). Specialists need retrieval filtered by KB `category` (payload field). Confirmed category values from `build_knowledge_base.py`: `hrv_indicators`, `sepsis_early_warning`, `bradycardia_patterns`, `intervention_thresholds`, `baseline_interpretation`. The method uses a Qdrant `should` filter (OR across categories) so a specialist can request chunks from multiple source files.

  **Pre-Read Gate:**
  - Run `grep -n "query_by_category" src/knowledge/knowledge_base.py`. Must return 0 matches. If any → already done, skip.
  - Run `grep -n "def query\|def query_vector_only" src/knowledge/knowledge_base.py`. Must return exactly 2 matches (anchor for insertion point: after `query_vector_only`).
  - Run `grep -n "^from qdrant_client.models import" src/knowledge/knowledge_base.py`. Confirm `Filter`, `FieldCondition`, `MatchValue` are already imported (line 24–32). If any are missing → add to the import line in this step.

  **Self-Contained Rule:** All code below is complete and runnable.

  In `src/knowledge/knowledge_base.py`, append the following method after `query_vector_only()` (end of the class):

  ```python
      def query_by_category(
          self,
          text: str,
          categories: list[str],
          n: int = 3,
      ) -> list[str]:
          """Hybrid retrieval filtered to specific KB categories (source files).

          Used by specialist agents to retrieve only the chunks relevant to their
          domain (e.g., signal specialist requests 'hrv_indicators' and
          'sepsis_early_warning' only, not bradycardia or intervention chunks).

          Parameters
          ----------
          text       : Free-text query from the specialist.
          categories : One or more category strings. Qdrant OR-filters across them.
                       Valid values: 'hrv_indicators', 'sepsis_early_warning',
                       'bradycardia_patterns', 'intervention_thresholds',
                       'baseline_interpretation'.
          n          : Chunks to return after reranking.
          """
          dense_vec = self.dense_model.encode(text).tolist()
          sp = self.tfidf.transform([text])
          sparse_vec = SparseVector(
              indices=sp.indices.tolist(),
              values=sp.data.tolist(),
          )

          # OR filter: chunk category must match any of the requested categories.
          category_filter = Filter(
              should=[
                  FieldCondition(key="category", match=MatchValue(value=cat))
                  for cat in categories
              ]
          )

          results = self.client.query_points(
              collection_name="clinical_knowledge",
              prefetch=[
                  Prefetch(query=dense_vec, using="dense", filter=category_filter, limit=10),
                  Prefetch(query=sparse_vec, using="sparse", filter=category_filter, limit=10),
              ],
              query=FusionQuery(fusion=Fusion.RRF),
              limit=20,
              with_payload=True,
          )

          candidates = [
              {"id": str(r.id), "text": r.payload["text"]}
              for r in results.points
          ]
          reranked = self.reranker.rerank(
              RerankRequest(query=text, passages=candidates)
          )
          return [r["text"] for r in reranked[:n]]
  ```

  **What it does:** Same hybrid dense+sparse+RRF+rerank pipeline as `query()`, but filtered to specific KB categories via Qdrant's `should` (OR) condition.

  **Why this approach:** Reuses the existing hybrid pipeline — no new models or clients needed. The OR filter maps directly to Qdrant's `should` clause.

  **Assumptions:**
  - `Prefetch`, `FusionQuery`, `Fusion` are already imported (confirmed: lines 27–32 of knowledge_base.py).
  - `SparseVector`, `Filter`, `FieldCondition`, `MatchValue` already imported.
  - KB collection payload field is named `"category"` (confirmed from `build_knowledge_base.py` line 108).

  **Risks:**
  - `should` clause not supported in `Prefetch.filter` → falls back to unfiltered retrieval silently → verification checks chunk count against known category sizes.

  **Git Checkpoint:**
  ```bash
  git add src/knowledge/knowledge_base.py
  git commit -m "step 5.2: add query_by_category() to ClinicalKnowledgeBase for specialist retrieval"
  ```

  **Subtasks:**
  - [ ] 🟥 Pre-Read Gate: 0 matches for `query_by_category`, confirm existing imports
  - [ ] 🟥 Method appended to class (after `query_vector_only`)
  - [ ] 🟥 Verification passes

  **✓ Verification Test:**

  **Type:** Integration

  **Action:**
  ```bash
  python -c "
  import sys, os; sys.path.insert(0, '.')
  from src.knowledge.knowledge_base import ClinicalKnowledgeBase
  kb = ClinicalKnowledgeBase(path=os.getenv('QDRANT_PATH', 'qdrant_local'))

  # Signal specialist query — should return hrv/sepsis chunks only
  signal_chunks = kb.query_by_category(
      'RMSSD declining z=-2.8 LF/HF elevated sepsis premature neonate',
      categories=['hrv_indicators', 'sepsis_early_warning'],
      n=3,
  )
  assert len(signal_chunks) == 3, f'Expected 3 chunks, got {len(signal_chunks)}'
  assert all(isinstance(c, str) and len(c) > 20 for c in signal_chunks), 'Chunks too short'

  # Brady specialist query — should return bradycardia_patterns chunks only
  brady_chunks = kb.query_by_category(
      'bradycardia events recurrent cluster pattern',
      categories=['bradycardia_patterns'],
      n=2,
  )
  assert len(brady_chunks) == 2, f'Expected 2 brady chunks, got {len(brady_chunks)}'

  print('PASS Step 2: query_by_category returns', len(signal_chunks), 'signal chunks,', len(brady_chunks), 'brady chunks')
  " 2>&1 | grep -E "PASS|Error|assert|ImportError"
  ```

  **Expected:** `PASS Step 2:` printed. Exit code 0.

  **Pass:** Correct chunk counts returned; no exceptions.

  **Fail:**
  - `AttributeError: query_by_category` → method not appended — check indentation inside class.
  - `len == 0` → `should` filter rejected all chunks — confirm category string matches payload exactly.

---

## Phase 2 — Audit Schema Hardening (FIX-6 + FIX-7)

**Goal:** `audit.db` has `schema_meta` version tracking and 5 new specialist columns. `save()` accepts and persists specialist outputs. Migration is idempotent.

---

- [ ] 🟥 **Step 3: FIX-6+7 Phase A — schema migration in `memory.py`** — *Critical: must succeed before Phase B writes data to new columns*

  > ⚠️ **Split Operation** — Phase A modifies the db schema (safe, idempotent). Phase B updates the Python code that writes to new columns. A Human Gate separates them.

  **Idempotent:** Yes — `CREATE TABLE IF NOT EXISTS` + `ALTER TABLE` in try/except; safe to re-run.

  **Context:** `audit.db` currently has 9 columns (confirmed in Pre-Flight). FIX-7 adds 5 specialist columns: `signal_pattern`, `signal_confidence`, `brady_classification`, `brady_weight`, `agent_version`. FIX-6 adds `schema_meta` table with `version='2.0'`. The `_init_schema()` migration pattern already uses try/except for `ALTER TABLE` — extending it is safe.

  **Pre-Read Gate:**
  - Run `grep -n "schema_meta\|signal_pattern\|agent_version" src/agent/memory.py`. Must return 0 matches. If any → step already done, skip.
  - Run `grep -n "def _init_schema" src/agent/memory.py`. Must return exactly 1 match.
  - Run `grep -n "hrv_values_json TEXT" src/agent/memory.py`. Must return exactly 1 match (last column in existing CREATE TABLE — insertion anchor).
  - Run `grep -n "self._init_schema()" src/agent/memory.py`. Must return exactly 1 match inside `__init__` — this is the line that will be extended to also call `_check_schema_version()`.

  **Self-Contained Rule:** All code below is complete and runnable.

  In `src/agent/memory.py`, replace the entire `_init_schema` method:

  ```python
      def _init_schema(self) -> None:
          with sqlite3.connect(self.db_path) as conn:
              conn.execute(
                  """
                  CREATE TABLE IF NOT EXISTS alert_history (
                      id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                      patient_id           TEXT,
                      timestamp            TEXT,
                      concern_level        TEXT,
                      risk_score           REAL,
                      top_feature          TEXT,
                      top_z_score          REAL,
                      z_scores_json        TEXT,
                      hrv_values_json      TEXT,
                      signal_pattern       TEXT,
                      signal_confidence    REAL,
                      brady_classification TEXT,
                      brady_weight         TEXT,
                      agent_version        TEXT
                  )
                  """
              )
              # Migrate existing tables (Phase 4 added z_scores_json/hrv_values_json;
              # Phase 5 adds specialist columns + schema_meta).
              # ALTER TABLE ADD COLUMN raises OperationalError on re-run — try/except is safe.
              for col_def in (
                  "z_scores_json        TEXT",
                  "hrv_values_json      TEXT",
                  "signal_pattern       TEXT",
                  "signal_confidence    REAL",
                  "brady_classification TEXT",
                  "brady_weight         TEXT",
                  "agent_version        TEXT",
              ):
                  try:
                      conn.execute(f"ALTER TABLE alert_history ADD COLUMN {col_def}")
                  except Exception:
                      pass  # column already present — safe to ignore

              # FIX-6: Schema version table — tracks which migration level this db is at.
              # Allows Phase 6 to detect and reject un-migrated Phase 3/4 databases.
              conn.execute(
                  """
                  CREATE TABLE IF NOT EXISTS schema_meta (
                      key   TEXT PRIMARY KEY,
                      value TEXT
                  )
                  """
              )
              conn.execute(
                  "INSERT OR REPLACE INTO schema_meta (key, value) VALUES ('version', '2.0')"
              )
  ```

  Also add `_check_schema_version()` as a new method immediately after `_init_schema`, and call it from `__init__`:

  In `__init__`, replace:
  ```python
          self._init_schema()
  ```
  With:
  ```python
          self._init_schema()
          self._check_schema_version()
  ```

  New method to insert immediately after `_init_schema`:
  ```python
      def _check_schema_version(self) -> None:
          """Raise RuntimeError if audit.db schema version is not 2.0.

          Protects against accidentally using a Phase 3/4 database that lacks
          the specialist output columns added in Phase 5.
          """
          with sqlite3.connect(self.db_path) as conn:
              row = conn.execute(
                  "SELECT value FROM schema_meta WHERE key='version'"
              ).fetchone()
          if not row or row[0] != "2.0":
              raise RuntimeError(
                  f"audit.db schema version mismatch: expected '2.0', got {row[0] if row else 'None'}. "
                  "Run: python -c \"from src.agent.memory import EpisodicMemory; EpisodicMemory()\" "
                  "to apply the Phase 5 migration."
              )
  ```

  **What it does:** Extends `_init_schema()` with 5 new columns and a `schema_meta` table. Adds `_check_schema_version()` to fail fast on un-migrated databases.

  **Why this approach:** Idempotent `ALTER TABLE` in try/except is the existing Phase 4 migration pattern — consistent extension. `INSERT OR REPLACE` ensures version is always set correctly on re-run.

  **Assumptions:**
  - `self._init_schema()` call exists in `__init__` on a single line (confirmed: line 43).

  **Risks:**
  - `ALTER TABLE` silently fails for a non-duplicate reason → `PRAGMA table_info` check in verification catches this.

  **Git Checkpoint (Phase A):**
  ```bash
  git add src/agent/memory.py
  git commit -m "step 5.3a: FIX-6+7 Phase A — add schema_meta + 5 specialist columns to alert_history"
  ```

  **Phase A Verification:**
  ```bash
  python -c "
  import sqlite3, sys; sys.path.insert(0, '.')
  from src.agent.memory import EpisodicMemory
  EpisodicMemory()
  conn = sqlite3.connect('data/audit.db')
  cols = [r[1] for r in conn.execute('PRAGMA table_info(alert_history)').fetchall()]
  for col in ['signal_pattern', 'signal_confidence', 'brady_classification', 'brady_weight', 'agent_version']:
      assert col in cols, f'MISSING column: {col} — got {cols}'
  tbls = [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]
  assert 'schema_meta' in tbls, f'schema_meta table missing — got {tbls}'
  ver = conn.execute(\"SELECT value FROM schema_meta WHERE key='version'\").fetchone()
  assert ver[0] == '2.0', f'Expected version 2.0, got {ver}'
  print('PASS Phase 3A: 5 specialist columns present, schema_meta version=2.0')
  print('Columns:', cols)
  "
  ```

  **State Manifest — Phase A:**
  ```
  Files modified: src/agent/memory.py (_init_schema extended, _check_schema_version added, __init__ updated)
  Values produced: audit.db now has 14 columns + schema_meta table at version 2.0
  Verifications passed: Steps 1 ✅, Step 2 ✅, Step 3A ✅
  Next: Step 4 (Phase B) — update save() to accept and write specialist outputs
  ```

  **Human Gate — Phase A complete:**
  Output `"[PHASE 3A COMPLETE — WAITING FOR HUMAN TO CONFIRM PHASE A VERIFICATION PASSED]"` as the final line of your response.
  Do not write any code or call any tools after this line.

  **Subtasks:**
  - [ ] 🟥 `_init_schema()` replaced with extended version
  - [ ] 🟥 `_check_schema_version()` added as new method
  - [ ] 🟥 `__init__` updated to call `_check_schema_version()`
  - [ ] 🟥 Phase A verification passes
  - [ ] 🟥 Human gate cleared

---

- [ ] 🟥 **Step 4: FIX-6+7 Phase B — update `save()` to accept specialist outputs** — *Critical: multi-agent assemble node needs to log SignalAssessment + BradycardiaAssessment*

  **Idempotent:** Yes — pure code replacement; re-running writes same column names.

  **Context:** Phase A added the 5 new db columns. Phase B updates the Python `save()` method to accept and write them. New kwargs have `None` defaults — all existing callers (`assemble_alert_node` in generalist graph) remain unchanged.

  **Pre-Read Gate:**
  - **Enforce Phase A gate:** Run:
    ```bash
    python -c "
    import sqlite3, sys; sys.path.insert(0, '.')
    from src.agent.memory import EpisodicMemory; EpisodicMemory()
    cols = [r[1] for r in sqlite3.connect('data/audit.db').execute('PRAGMA table_info(alert_history)').fetchall()]
    for c in ['signal_pattern', 'signal_confidence', 'brady_classification', 'brady_weight', 'agent_version']:
        assert c in cols, f'STOP: Phase A incomplete — {c} missing'
    print('Phase A confirmed: all 5 specialist columns present')
    "
    ```
    If assertion fails → Phase A (Step 3) was not applied — return to Step 3 before proceeding.
  - Run `grep -n "def save" src/agent/memory.py`. Must return 1 match with current 5-arg signature `(self, alert, top_feature, top_z, z_scores=None, hrv_values=None)`.
  - Run `grep -n "signal_pattern\|agent_version" src/agent/memory.py`. Must return 0 matches (Phase B not yet applied). If any → already done, skip.

  **Self-Contained Rule:** All code below is complete and runnable.

  In `src/agent/memory.py`, replace the entire `save` method:

  ```python
      def save(
          self,
          alert: NeonatalAlert,
          top_feature: str,
          top_z: float,
          z_scores: dict | None = None,
          hrv_values: dict | None = None,
          signal_pattern: str | None = None,
          signal_confidence: float | None = None,
          brady_classification: str | None = None,
          brady_weight: str | None = None,
          agent_version: str = "generalist",
      ) -> None:
          """Persist a finalised alert to the audit log.

          Phase 4 (FIX-2): z_scores and hrv_values trace model inputs.
          Phase 5 (FIX-7): specialist outputs (signal_pattern, signal_confidence,
          brady_classification, brady_weight, agent_version) trace multi-agent decisions.
          All specialist kwargs default to None so existing generalist callers are unaffected.
          """
          with sqlite3.connect(self.db_path) as conn:
              conn.execute(
                  """
                  INSERT INTO alert_history
                  (patient_id, timestamp, concern_level, risk_score,
                   top_feature, top_z_score, z_scores_json, hrv_values_json,
                   signal_pattern, signal_confidence,
                   brady_classification, brady_weight, agent_version)
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                  """,
                  (
                      alert.patient_id,
                      alert.timestamp.isoformat(),
                      alert.concern_level,
                      alert.risk_score,
                      top_feature,
                      top_z,
                      json.dumps(z_scores)   if z_scores   is not None else None,
                      json.dumps(hrv_values) if hrv_values is not None else None,
                      signal_pattern,
                      signal_confidence,
                      brady_classification,
                      brady_weight,
                      agent_version,
                  ),
              )
  ```

  **What it does:** Adds 5 optional kwargs to `save()`. INSERT now writes to all 13 non-id columns. Generalist callers that omit the new kwargs get `None` / `"generalist"` written automatically.

  **Risks:**
  - Phase A not done → `table has no column named signal_pattern` → Phase A gate in Pre-Read prevents this.

  **Git Checkpoint (Phase B):**
  ```bash
  git add src/agent/memory.py
  git commit -m "step 5.4: FIX-7 Phase B — update save() to accept and write specialist outputs"
  ```

  **Subtasks:**
  - [ ] 🟥 Phase A gate confirmed
  - [ ] 🟥 `save()` replaced with 10-arg version
  - [ ] 🟥 Verification passes

  **✓ Verification Test:**

  **Type:** Integration

  **Action:**
  ```bash
  python -c "
  import sys, json, sqlite3, os; sys.path.insert(0, '.')
  os.environ['EVAL_NO_LLM'] = '1'
  from eval.scenarios import SCENARIOS, inject_scenario, clear_injection
  inject_scenario(SCENARIOS[0])
  from src.agent.graph import agent
  agent.invoke({'patient_id': SCENARIOS[0].patient_id})
  clear_injection()
  conn = sqlite3.connect('data/audit.db')
  row = conn.execute(
      'SELECT agent_version, signal_pattern FROM alert_history WHERE patient_id=? ORDER BY id DESC LIMIT 1',
      (SCENARIOS[0].patient_id,)
  ).fetchone()
  assert row is not None, 'No row inserted'
  assert row[0] == 'generalist', f'Expected agent_version=generalist, got {row[0]}'
  # signal_pattern is NULL for generalist runs — correct behaviour
  print(f'PASS Phase 3B: agent_version={row[0]}, signal_pattern={row[1]} (NULL expected for generalist)')
  " 2>&1 | grep -E "PASS|Error|assert"
  ```

  **Expected:** `PASS Phase 3B:` with `agent_version=generalist` and `signal_pattern=None`. Exit code 0.

  **Fail:**
  - `table has no column named signal_pattern` → Phase A not applied — STOP.
  - `agent_version=None` → default not set in `save()` — check method signature.

---

## Phase 3 — Specialist Agent Nodes

**Goal:** Four specialist node functions exist in `src/agent/specialists/`. Each has a targeted prompt, category-filtered RAG, and an `EVAL_NO_LLM`-safe rule-based path. Each can be imported and called independently.

---

- [ ] 🟥 **Step 5: Create `src/agent/specialists/signal_agent.py`** — *Critical: first specialist; supervisor depends on it*

  **Idempotent:** Yes — creating new file.

  **Context:** Signal specialist always runs. It reads the top HRV z-scores from `PipelineResult`, retrieves from `hrv_indicators` and `sepsis_early_warning` KB categories, and returns a `SignalAssessment`. In `EVAL_NO_LLM` mode, it returns a deterministic assessment from risk_score and top z-score.

  **Pre-Read Gate:**
  - Run `ls src/agent/specialists/ 2>&1`. Must return error or show only `__init__.py`. If `signal_agent.py` exists → skip.
  - Run `grep -n "def signal_agent_node" src/agent/specialists/signal_agent.py 2>/dev/null`. Must return 0 matches (file absent). If file exists → check if step already done.

  **Self-Contained Rule:** All code below is complete and runnable.

  First, create the package init (empty):

  **File 1 — `src/agent/specialists/__init__.py`:** Empty file.

  **File 2 — `src/agent/specialists/signal_agent.py`:**

  ```python
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
  ```

  **What it does:** Returns a `SignalAssessment` via Groq (live) or deterministic rule-based (eval). Retrieves only `hrv_indicators` and `sepsis_early_warning` chunks.

  **Why this approach:** TYPE_CHECKING import avoids circular dependency (supervisor imports signal_agent; signal_agent imports MultiAgentState from supervisor). `_get_groq()` and `_get_kb()` are already singletons in `graph.py` — reusing them avoids reinitialising the 90MB SentenceTransformer.

  **Git Checkpoint:**
  ```bash
  git add src/agent/specialists/__init__.py src/agent/specialists/signal_agent.py
  git commit -m "step 5.5: create signal_agent.py — HRV autonomic pattern specialist"
  ```

  **Subtasks:**
  - [ ] 🟥 `src/agent/specialists/__init__.py` created (empty)
  - [ ] 🟥 `signal_agent.py` created with `_rule_based_signal()` and `signal_agent_node()`
  - [ ] 🟥 Verification passes

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  python -c "
  import sys, os; sys.path.insert(0, '.')
  os.environ['EVAL_NO_LLM'] = '1'
  from src.pipeline.result import PipelineResult
  from src.agent.specialists.signal_agent import signal_agent_node

  # Build a minimal PipelineResult stub with required fields
  r = PipelineResult(
      patient_id='test',
      risk_score=0.80,
      risk_level='RED',
      z_scores={'rmssd': -2.8, 'lf_hf_ratio': 2.5, 'pnn50': -2.1, 'sdnn': -1.8,
                'rr_ms_min': -1.0, 'rr_ms_max': 0.5, 'rr_ms_25%': -0.8,
                'rr_ms_50%': -1.2, 'rr_ms_75%': -0.6, 'mean_rr': -1.5},
      hrv_values={'rmssd': 8.0, 'lf_hf_ratio': 4.2, 'pnn50': 2.1, 'sdnn': 12.0,
                  'rr_ms_min': 380.0, 'rr_ms_max': 540.0, 'rr_ms_25%': 410.0,
                  'rr_ms_50%': 450.0, 'rr_ms_75%': 490.0, 'mean_rr': 450.0},
      personal_baseline={k: {'mean': 0.0, 'std': 1.0} for k in ['rmssd', 'lf_hf_ratio', 'pnn50', 'sdnn',
                          'rr_ms_min', 'rr_ms_max', 'rr_ms_25%', 'rr_ms_50%', 'rr_ms_75%', 'mean_rr']},
      detected_events=[],
  )
  state = {'pipeline_result': r}
  result = signal_agent_node(state)
  sa = result['signal_assessment']
  assert sa.autonomic_pattern == 'pre_sepsis', f'Expected pre_sepsis, got {sa.autonomic_pattern}'
  assert len(sa.primary_features) >= 1
  assert 0.0 <= sa.confidence <= 1.0
  print(f'PASS Step 5: signal_agent_node returns autonomic_pattern={sa.autonomic_pattern}, confidence={sa.confidence:.2f}')
  "
  ```

  **Expected:** `PASS Step 5: signal_agent_node returns autonomic_pattern=pre_sepsis`. Exit code 0.

  **Fail:**
  - `ModuleNotFoundError` → `__init__.py` missing or wrong path — check `src/agent/specialists/`.
  - `autonomic_pattern != pre_sepsis` → rule-based thresholds wrong — risk_score=0.80 > 0.70, should be `pre_sepsis`.

---

- [ ] 🟥 **Step 6: Create `src/agent/specialists/brady_agent.py`** — *Critical: conditional specialist; supervisor routes to it when events > 0 OR max_z > 2.0*

  **Idempotent:** Yes — creating new file.

  **Context:** Brady specialist runs conditionally. It reads `n_brady = len(r.detected_events)` and retrieves from `bradycardia_patterns` only. In `EVAL_NO_LLM` mode, it returns a deterministic classification based on event count.

  **Pre-Read Gate:**
  - Run `grep -n "brady_agent_node" src/agent/specialists/brady_agent.py 2>/dev/null`. Must return 0 (file absent). If exists → skip.

  **Self-Contained Rule:** All code below is complete and runnable.

  **File — `src/agent/specialists/brady_agent.py`:**

  ```python
  """Bradycardia Classification specialist node.

  Classifies the clinical significance of detected bradycardia events.
  Runs conditionally: only when len(detected_events) > 0 OR max_z > 2.0.

  Retrieves from 'bradycardia_patterns' KB category only — isolating bradycardia
  clinical knowledge from HRV spectral analysis. The generalist mixes both in one
  prompt, causing confusion on cases where brady pattern and HRV signals disagree.

  In EVAL_NO_LLM mode: deterministic classification from event count.
  """
  from __future__ import annotations

  import os
  from typing import TYPE_CHECKING

  from langsmith import traceable

  from src.agent.schemas import BradycardiaAssessment

  if TYPE_CHECKING:
      from src.agent.supervisor import MultiAgentState


  _BRADY_CATEGORIES = ["bradycardia_patterns"]


  def _rule_based_brady(n_events: int) -> BradycardiaAssessment:
      """Deterministic bradycardia classification for EVAL_NO_LLM mode."""
      if n_events == 0:
          return BradycardiaAssessment(
              classification="none",
              clinical_weight="low",
              reasoning="No bradycardia events detected in last 6h.",
          )
      if n_events >= 4:
          return BradycardiaAssessment(
              classification="cluster",
              clinical_weight="high",
              reasoning=f"Rule-based: {n_events} events — cluster pattern, high clinical weight.",
          )
      if n_events >= 2:
          return BradycardiaAssessment(
              classification="recurrent_without_suppression",
              clinical_weight="medium",
              reasoning=f"Rule-based: {n_events} events — recurrent pattern without clear HRV suppression.",
          )
      return BradycardiaAssessment(
          classification="isolated_reflex",
          clinical_weight="low",
          reasoning=f"Rule-based: {n_events} event — isolated, likely reflex bradycardia.",
      )


  @traceable(name="brady_agent_node")
  def brady_agent_node(state: dict) -> dict:
      """Classify bradycardia event pattern. Runs only when events present or max_z > 2.0."""
      r = state["pipeline_result"]
      n_events = len(r.detected_events)

      if os.getenv("EVAL_NO_LLM", "").lower() in {"1", "true", "yes"}:
          return {"bradycardia_assessment": _rule_based_brady(n_events)}

      from src.agent.graph import _get_groq, _get_kb

      signal_ctx = ""
      sa = state.get("signal_assessment")
      if sa:
          signal_ctx = (
              f"\nSignal assessment from HRV specialist: "
              f"pattern={sa.autonomic_pattern}, confidence={sa.confidence:.2f}\n"
          )

      query = (
          f"Bradycardia events: {n_events} in last 6h. "
          f"Risk score {r.risk_score:.2f}. "
          + ", ".join(
              f"{d.name} z={d.z_score:+.1f}"
              for d in r.get_top_deviated(3)
          )
      )
      chunks = _get_kb().query_by_category(query, categories=_BRADY_CATEGORIES, n=2)
      context = "\n\n".join(chunks)

      prompt = f"""You are a neonatal bradycardia classification specialist.
  Your ONLY task is to classify the clinical significance of these bradycardia events.
  Do NOT recommend clinical actions.

  Bradycardia events last 6h: {n_events}
  {signal_ctx}
  Retrieved bradycardia reference:
  {context}

  Classify the bradycardia pattern and assign clinical weight. Output a BradycardiaAssessment."""

      assessment: BradycardiaAssessment = _get_groq().chat.completions.create(
          model="llama-3.3-70b-versatile",
          response_model=BradycardiaAssessment,
          messages=[{"role": "user", "content": prompt}],
          temperature=0.1,
          max_retries=3,
      )
      return {"bradycardia_assessment": assessment}
  ```

  **Git Checkpoint:**
  ```bash
  git add src/agent/specialists/brady_agent.py
  git commit -m "step 5.6: create brady_agent.py — bradycardia classification specialist"
  ```

  **Subtasks:**
  - [ ] 🟥 `brady_agent.py` created
  - [ ] 🟥 Verification passes

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  python -c "
  import sys, os; sys.path.insert(0, '.')
  os.environ['EVAL_NO_LLM'] = '1'
  from src.pipeline.result import PipelineResult, BradycardiaEvent
  from src.agent.specialists.brady_agent import brady_agent_node

  r = PipelineResult(
      patient_id='test', risk_score=0.75, risk_level='RED',
      z_scores={k: 0.0 for k in ['rmssd','lf_hf_ratio','pnn50','sdnn','rr_ms_min','rr_ms_max','rr_ms_25%','rr_ms_50%','rr_ms_75%','mean_rr']},
      hrv_values={k: 0.0 for k in ['rmssd','lf_hf_ratio','pnn50','sdnn','rr_ms_min','rr_ms_max','rr_ms_25%','rr_ms_50%','rr_ms_75%','mean_rr']},
      personal_baseline={k: {'mean': 0.0, 'std': 1.0} for k in ['rmssd','lf_hf_ratio','pnn50','sdnn','rr_ms_min','rr_ms_max','rr_ms_25%','rr_ms_50%','rr_ms_75%','mean_rr']},
      detected_events=[BradycardiaEvent(i, 650.0, 3) for i in range(4)],  # 4 events = cluster
  )
  result = brady_agent_node({'pipeline_result': r, 'signal_assessment': None})
  ba = result['bradycardia_assessment']
  assert ba.classification == 'cluster', f'Expected cluster, got {ba.classification}'
  assert ba.clinical_weight == 'high'
  print(f'PASS Step 6: brady_agent_node returns classification={ba.classification}, weight={ba.clinical_weight}')
  "
  ```

  **Expected:** `PASS Step 6: brady_agent_node returns classification=cluster, weight=high`. Exit code 0.

---

- [ ] 🟥 **Step 7: Create `src/agent/specialists/clinical_agent.py`** — *Critical: produces the final `LLMOutput` that becomes the alert; receives pre-interpreted findings*

  **Idempotent:** Yes — creating new file.

  **Context:** Clinical reasoning specialist always runs after signal (and optionally brady). It receives `SignalAssessment` and optionally `BradycardiaAssessment` as pre-interpreted findings — not raw z-scores. This separation is the key fix for YELLOW/GREEN confusion: the generalist receives raw numbers; this specialist receives clinical interpretations. Retrieves from `intervention_thresholds` and `baseline_interpretation`. Returns `LLMOutput` (same schema as generalist).

  **Pre-Read Gate:**
  - Run `grep -n "clinical_agent_node" src/agent/specialists/clinical_agent.py 2>/dev/null`. Must return 0 (file absent).

  **Self-Contained Rule:** All code below is complete and runnable.

  **File — `src/agent/specialists/clinical_agent.py`:**

  ```python
  """Clinical Reasoning specialist node.

  Synthesises pre-interpreted specialist findings into a final clinical decision.
  Receives SignalAssessment and optionally BradycardiaAssessment — not raw numbers.
  Reasoning like a consultant receiving a handover, not a technician reading sensors.

  This is the key improvement over the generalist: the specialist only decides
  WHAT TO DO given already-interpreted evidence. It does not also have to interpret
  what the z-scores mean — that is signal_agent's job.

  Retrieves from 'intervention_thresholds' and 'baseline_interpretation' only.
  In EVAL_NO_LLM mode: deterministic LLMOutput from risk_score (same as generalist).
  """
  from __future__ import annotations

  import os
  from typing import TYPE_CHECKING

  from langsmith import traceable

  from src.agent.schemas import LLMOutput

  if TYPE_CHECKING:
      from src.agent.supervisor import MultiAgentState


  _CLINICAL_CATEGORIES = ["intervention_thresholds", "baseline_interpretation"]


  @traceable(name="clinical_agent_node")
  def clinical_agent_node(state: dict) -> dict:
      """Synthesise specialist findings into a structured clinical alert."""
      r = state["pipeline_result"]

      if os.getenv("EVAL_NO_LLM", "").lower() in {"1", "true", "yes"}:
          # Rule-based path — delegates to generalist llm_reasoning_node.
          # Delegation is intentional: llm_reasoning_node only reads pipeline_result,
          # rag_context, and past_alerts — all fields present in MultiAgentState.
          # TypedDict is not enforced at runtime so this is safe.
          from src.agent.graph import llm_reasoning_node
          return llm_reasoning_node(state)

      from src.agent.graph import _get_groq, _get_kb

      sa = state.get("signal_assessment")
      ba = state.get("bradycardia_assessment")
      past = state.get("past_alerts") or []

      signal_summary = (
          f"Signal assessment: pattern={sa.autonomic_pattern}, "
          f"confidence={sa.confidence:.2f}, features={sa.primary_features}\n"
          f"Reasoning: {sa.physiological_reasoning}"
      ) if sa else "Signal assessment: not available."

      brady_summary = (
          f"Bradycardia assessment: classification={ba.classification}, "
          f"clinical_weight={ba.clinical_weight}\nReasoning: {ba.reasoning}"
      ) if ba else "Bradycardia assessment: no events detected."

      episodic = ""
      if past:
          episodic = f"Patient history (last {len(past)} alerts):\n"
          episodic += "\n".join(
              f"  [{a.timestamp[:10]}] {a.concern_level} - {a.top_feature} z={a.top_z_score:.1f}"
              for a in past
          )

      query = (
          f"Intervention decision for neonatal {r.risk_level} risk patient. "
          f"Autonomic pattern: {sa.autonomic_pattern if sa else 'unknown'}. "
          f"Brady events: {len(r.detected_events)}. Risk score: {r.risk_score:.2f}."
      )
      chunks = _get_kb().query_by_category(query, categories=_CLINICAL_CATEGORIES, n=3)
      context = "\n\n".join(chunks)

      prompt = f"""You are a neonatal intensive care clinical decision support consultant.
  You receive pre-interpreted specialist findings — not raw numbers.
  Your task: determine the concern level and recommend an appropriate clinical action.

  ONNX risk score: {r.risk_score:.3f}
  {signal_summary}
  {brady_summary}
  {episodic}

  Clinical intervention guidelines:
  {context}

  Generate a structured neonatal clinical alert. Recommended actions must follow standard NICU protocols."""

      output: LLMOutput = _get_groq().chat.completions.create(
          model="llama-3.3-70b-versatile",
          response_model=LLMOutput,
          messages=[{"role": "user", "content": prompt}],
          temperature=0.1,
          max_retries=3,
      )
      return {"llm_output": output}
  ```

  **Git Checkpoint:**
  ```bash
  git add src/agent/specialists/clinical_agent.py
  git commit -m "step 5.7: create clinical_agent.py — clinical reasoning from pre-interpreted findings"
  ```

  **Subtasks:**
  - [ ] 🟥 `clinical_agent.py` created
  - [ ] 🟥 Verification passes

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  python -c "
  import sys, os; sys.path.insert(0, '.')
  os.environ['EVAL_NO_LLM'] = '1'
  from src.pipeline.result import PipelineResult
  from src.agent.schemas import SignalAssessment
  from src.agent.specialists.clinical_agent import clinical_agent_node

  r = PipelineResult(
      patient_id='test', risk_score=0.80, risk_level='RED',
      z_scores={k: -2.0 for k in ['rmssd','lf_hf_ratio','pnn50','sdnn','rr_ms_min','rr_ms_max','rr_ms_25%','rr_ms_50%','rr_ms_75%','mean_rr']},
      hrv_values={k: 0.0 for k in ['rmssd','lf_hf_ratio','pnn50','sdnn','rr_ms_min','rr_ms_max','rr_ms_25%','rr_ms_50%','rr_ms_75%','mean_rr']},
      personal_baseline={k: {'mean': 0.0, 'std': 1.0} for k in ['rmssd','lf_hf_ratio','pnn50','sdnn','rr_ms_min','rr_ms_max','rr_ms_25%','rr_ms_50%','rr_ms_75%','mean_rr']},
      detected_events=[],
  )
  sa = SignalAssessment(autonomic_pattern='pre_sepsis', primary_features=['rmssd'],
                        confidence=0.9, physiological_reasoning='RMSSD suppressed, autonomic withdrawal.')
  state = {'pipeline_result': r, 'signal_assessment': sa, 'bradycardia_assessment': None, 'past_alerts': [], 'rag_context': []}
  result = clinical_agent_node(state)
  out = result['llm_output']
  assert out.concern_level in ['RED', 'YELLOW', 'GREEN']
  assert len(out.primary_indicators) >= 1
  print(f'PASS Step 7: clinical_agent_node returns concern_level={out.concern_level}')
  "
  ```

  **Expected:** `PASS Step 7:` printed. Exit code 0.

---

- [ ] 🟥 **Step 8: Create `src/agent/specialists/protocol_agent.py`** — *Critical: pure logic compliance check; no LLM*

  **Idempotent:** Yes — creating new file.

  **Context:** Protocol agent is pure Python — no LLM, no retrieval. It validates `LLMOutput.recommended_action` against `concern_level` semantically. The generalist uses a substring match in `LLMOutput.enforce_protocol_compliance()`. The specialist adds concern-level awareness: e.g., "Blood culture" is appropriate for RED/YELLOW but not GREEN. Also sets `self_check_passed = True` (replacing the generalist's self_check_node for the multi-agent path).

  **Pre-Read Gate:**
  - Run `grep -n "protocol_agent_node" src/agent/specialists/protocol_agent.py 2>/dev/null`. Must return 0 (file absent).
  - Run `grep -n "APPROVED_ACTIONS" src/agent/schemas.py`. Must return 1 match — confirm the list is importable.

  **Self-Contained Rule:** All code below is complete and runnable.

  **File — `src/agent/specialists/protocol_agent.py`:**

  ```python
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
  def protocol_agent_node(state: dict) -> dict:
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
  ```

  **Git Checkpoint:**
  ```bash
  git add src/agent/specialists/protocol_agent.py
  git commit -m "step 5.8: create protocol_agent.py — concern-level-aware protocol compliance check"
  ```

  **Subtasks:**
  - [ ] 🟥 `protocol_agent.py` created
  - [ ] 🟥 Verification passes

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  python -c "
  import sys; sys.path.insert(0, '.')
  from src.agent.schemas import LLMOutput
  from src.agent.specialists.protocol_agent import protocol_agent_node

  # GREEN patient with high-acuity action — should be flagged
  out = LLMOutput(concern_level='GREEN', primary_indicators=['rmssd'],
                  clinical_reasoning='HRV within normal range for this patient at baseline.',
                  recommended_action='Blood culture and CBC with differential', confidence=0.85)
  result = protocol_agent_node({'llm_output': out})
  assert 'PROTOCOL FLAG' in result['llm_output'].recommended_action, 'GREEN+blood culture not flagged'
  assert result['self_check_passed'] is True

  # RED patient with appropriate action — should pass unchanged
  out2 = LLMOutput(concern_level='RED', primary_indicators=['rmssd'],
                   clinical_reasoning='Autonomic withdrawal pattern with suppressed HRV consistent with sepsis.',
                   recommended_action='Immediate clinical review', confidence=0.90)
  result2 = protocol_agent_node({'llm_output': out2})
  assert 'PROTOCOL FLAG' not in result2['llm_output'].recommended_action

  print('PASS Step 8: protocol_agent_node flags GREEN+blood_culture, passes RED+immediate_review')
  "
  ```

  **Expected:** `PASS Step 8:` printed. Exit code 0.

---

## Phase 4 — Supervisor Graph

**Goal:** `multi_agent` compiled graph exists. All 4 specialists are wired into a flat StateGraph. `eval_agent.py --agent multi_agent` loads and runs it. All 30 eval scenarios pass in no-LLM mode with FNR(RED)=0.000.

---

- [ ] 🟥 **Step 9: Create `src/agent/supervisor.py` with `MultiAgentState` and `build_multi_agent_graph()`** — *Critical: the outer graph that wires all specialist nodes*

  **Idempotent:** Yes — creating new file.

  **Context:** The supervisor graph is a flat `StateGraph(MultiAgentState)` with 7 nodes: `supervisor` (pipeline + routing), `signal`, `brady` (conditional), `clinical`, `protocol`, `assemble_multi`. A conditional edge after `signal` routes to `brady` if `state["run_brady"]` is True, else directly to `clinical`. The `assemble_multi_node` calls `EpisodicMemory().save()` with specialist outputs, setting `agent_version="multi_agent"`.

  **Pre-Read Gate:**
  - Run `ls src/agent/supervisor.py 2>&1`. Must return error. If file exists → check if step done.
  - Run `grep -n "from src.agent.specialists" src/agent/supervisor.py 2>/dev/null`. Must return 0.
  - Confirm all four specialist modules are importable (Steps 5–8 prerequisite):
    ```bash
    EVAL_NO_LLM=1 python -c "
    from src.agent.specialists.signal_agent import signal_agent_node
    from src.agent.specialists.brady_agent import brady_agent_node
    from src.agent.specialists.clinical_agent import clinical_agent_node
    from src.agent.specialists.protocol_agent import protocol_agent_node
    print('All 4 specialist imports OK')
    "
    ```
    Must print `All 4 specialist imports OK`. If any ImportError → return to the failing step (5/6/7/8) before proceeding.

  **Self-Contained Rule:** All code below is complete and runnable.

  **File — `src/agent/supervisor.py`:**

  ```python
  """Multi-agent supervisor graph for NeonatalGuard Phase 5.

  Replaces the single 6-node generalist graph with a 7-node supervisor
  routing through four specialist subgraphs:

    supervisor → signal → [brady (conditional)] → clinical → protocol → assemble_multi

  Bradycardia specialist runs when: len(detected_events) > 0 OR max_z > 2.0.
  All other nodes always run.

  The generalist `agent` object in graph.py is unchanged — this graph is exported
  as `multi_agent` alongside it for side-by-side eval comparison.
  """
  from __future__ import annotations

  import os
  from datetime import datetime
  from typing import Optional, TypedDict

  from langgraph.graph import END, StateGraph
  from langsmith import traceable

  from src.agent.memory import EpisodicMemory, PastAlert
  from src.agent.schemas import LLMOutput, NeonatalAlert
  from src.agent.schemas import SignalAssessment, BradycardiaAssessment
  from src.agent.specialists.signal_agent import signal_agent_node
  from src.agent.specialists.brady_agent import brady_agent_node
  from src.agent.specialists.clinical_agent import clinical_agent_node
  from src.agent.specialists.protocol_agent import protocol_agent_node
  from src.pipeline.result import PipelineResult


  class MultiAgentState(TypedDict):
      """State schema for the multi-agent graph."""

      patient_id:             str
      pipeline_result:        Optional[PipelineResult]
      run_brady:              Optional[bool]           # routing flag set by supervisor_node
      rag_context:            Optional[list[str]]      # kept for compat with assemble_alert_node
      signal_assessment:      Optional[SignalAssessment]
      bradycardia_assessment: Optional[BradycardiaAssessment]
      past_alerts:            Optional[list[PastAlert]]
      llm_output:             Optional[LLMOutput]
      self_check_passed:      Optional[bool]
      final_alert:            Optional[NeonatalAlert]
      error:                  Optional[str]


  @traceable(name="supervisor_node")
  def supervisor_node(state: MultiAgentState) -> dict:
      """Run the ONNX pipeline and determine specialist routing.

      Sets run_brady=True if bradycardia events present OR any z-score abs > 2.0.
      This mirrors the project plan routing logic exactly.
      """
      synthetic = os.environ.get("_SYNTHETIC_RESULT")
      if synthetic:
          import pickle
          try:
              result = pickle.loads(bytes.fromhex(synthetic))
          except Exception as exc:
              raise RuntimeError(f"_SYNTHETIC_RESULT could not be deserialised: {exc}") from exc
      else:
          from src.pipeline.runner import NeonatalPipeline
          result = NeonatalPipeline().run(state["patient_id"])

      max_z = max(abs(z) for z in result.z_scores.values()) if result.z_scores else 0.0
      run_brady = len(result.detected_events) > 0 or max_z > 2.0
      past = EpisodicMemory().get_recent(state["patient_id"], n=7)

      return {
          "pipeline_result": result,
          "run_brady": run_brady,
          "past_alerts": past,
          "rag_context": [],  # filled by specialists; kept for NeonatalAlert compat
      }


  def _route_brady(state: MultiAgentState) -> str:
      """Conditional edge: route to brady specialist or skip directly to clinical."""
      return "brady" if state.get("run_brady") else "clinical"


  @traceable(name="assemble_multi_node")
  def assemble_multi_node(state: MultiAgentState) -> dict:
      """Assemble the final NeonatalAlert and persist with specialist outputs to audit.db."""
      result = state["pipeline_result"]
      llm_out = state["llm_output"]
      sa = state.get("signal_assessment")
      ba = state.get("bradycardia_assessment")

      top_one = result.get_top_deviated(1)
      top_feature_name = top_one[0].name if top_one else "none"
      top_feature_z = top_one[0].z_score if top_one else 0.0

      alert = NeonatalAlert(
          patient_id=result.patient_id,
          timestamp=datetime.now(),
          concern_level=llm_out.concern_level,
          risk_score=result.risk_score,
          primary_indicators=llm_out.primary_indicators,
          clinical_reasoning=llm_out.clinical_reasoning,
          recommended_action=llm_out.recommended_action,
          confidence=llm_out.confidence,
          retrieved_context=state.get("rag_context") or [],
          self_check_passed=state.get("self_check_passed", True),
          protocol_compliant="PROTOCOL FLAG" not in llm_out.recommended_action,
          past_similar_events=len(state.get("past_alerts") or []),
      )

      EpisodicMemory().save(
          alert,
          top_feature_name,
          top_feature_z,
          z_scores=result.z_scores,
          hrv_values=result.hrv_values,
          signal_pattern=sa.autonomic_pattern if sa else None,
          signal_confidence=sa.confidence if sa else None,
          brady_classification=ba.classification if ba else None,
          brady_weight=ba.clinical_weight if ba else None,
          agent_version="multi_agent",
      )
      return {"final_alert": alert}


  def build_multi_agent_graph():
      """Compile the 7-node multi-agent supervisor graph."""
      g = StateGraph(MultiAgentState)

      g.add_node("supervisor",   supervisor_node)
      g.add_node("signal",       signal_agent_node)
      g.add_node("brady",        brady_agent_node)
      g.add_node("clinical",     clinical_agent_node)
      g.add_node("protocol",     protocol_agent_node)
      g.add_node("assemble_multi", assemble_multi_node)

      g.set_entry_point("supervisor")
      g.add_edge("supervisor", "signal")
      g.add_conditional_edges("signal", _route_brady, {"brady": "brady", "clinical": "clinical"})
      g.add_edge("brady", "clinical")
      g.add_edge("clinical", "protocol")
      g.add_edge("protocol", "assemble_multi")
      g.add_edge("assemble_multi", END)

      return g.compile()
  ```

  **What it does:** Defines `MultiAgentState`, all routing logic, and `build_multi_agent_graph()`. `assemble_multi_node` passes specialist outputs to `EpisodicMemory().save()`.

  **Why this approach:** Flat graph (not nested compiled subgraphs) matches existing codebase pattern. Conditional edge on `run_brady` is the simplest correct implementation of project plan routing logic.

  **Assumptions:**
  - `EpisodicMemory().save()` now accepts `signal_pattern`, `brady_classification`, etc. (Step 4 done).
  - `_get_kb()` singleton in `graph.py` is importable from `supervisor.py`.

  **Git Checkpoint:**
  ```bash
  git add src/agent/supervisor.py
  git commit -m "step 5.9: create supervisor.py — 7-node multi-agent graph with specialist routing"
  ```

  **Subtasks:**
  - [ ] 🟥 `MultiAgentState` TypedDict defined with all fields
  - [ ] 🟥 `supervisor_node`, `_route_brady`, `assemble_multi_node` implemented
  - [ ] 🟥 `build_multi_agent_graph()` compiles without error
  - [ ] 🟥 Verification passes

  **✓ Verification Test:**

  **Type:** Integration

  **Action:**
  ```bash
  python -c "
  import sys, os; sys.path.insert(0, '.')
  os.environ['EVAL_NO_LLM'] = '1'
  from src.agent.supervisor import build_multi_agent_graph
  g = build_multi_agent_graph()
  print('Graph nodes:', list(g.nodes))

  # Smoke-test: run one no-LLM scenario end-to-end
  from eval.scenarios import SCENARIOS, inject_scenario, clear_injection
  s = SCENARIOS[0]  # first RED scenario
  inject_scenario(s)
  state = g.invoke({'patient_id': s.patient_id})
  clear_injection()
  alert = state.get('final_alert')
  assert alert is not None, 'final_alert is None — graph failed'
  assert alert.concern_level in ['RED', 'YELLOW', 'GREEN']
  assert state.get('signal_assessment') is not None, 'signal_assessment missing'
  print(f'PASS Step 9: multi_agent produced concern_level={alert.concern_level} for {s.patient_id}')
  " 2>&1 | grep -E "PASS|Error|assert|Graph"
  ```

  **Expected:** `Graph nodes:` list printed, then `PASS Step 9:`. Exit code 0.

  **Fail:**
  - `ImportError` from supervisor → check specialist module paths.
  - `final_alert is None` → one of the nodes returned no `llm_output` — check clinical_agent_node in no-LLM mode.
  - `signal_assessment missing` → signal_agent_node returned wrong key — check return dict key name.

---

- [ ] 🟥 **Step 10: Export `multi_agent` from `src/agent/graph.py`** — *Critical: `eval_agent.py` imports `multi_agent` from this module*

  **Idempotent:** Yes — appending two lines to module bottom.

  **Context:** `eval_agent.py` already contains `load_agent("multi_agent")` which does `from src.agent.graph import multi_agent`. This step makes that import available by building the graph at module load time, exactly as `agent = build_graph()` does for the generalist.

  **Pre-Read Gate:**
  - Run `grep -n "multi_agent" src/agent/graph.py`. Must return 0 matches. If any → step already done, skip.
  - Run `grep -n "^agent = build_graph" src/agent/graph.py`. Must return exactly 1 match (anchor: append after this line).

  **Self-Contained Rule:** All code below is complete and runnable.

  In `src/agent/graph.py`, append after `agent = build_graph()` (current last line, line 340):

  ```python

  # Phase 5: multi-agent graph — supervisor routing through four specialist nodes.
  # Imported by eval_agent.py via: from src.agent.graph import multi_agent
  # The generalist `agent` above is kept unchanged for Phase 4/6 baseline comparison.
  from src.agent.supervisor import build_multi_agent_graph
  multi_agent = build_multi_agent_graph()
  ```

  **What it does:** Exports `multi_agent` alongside `agent`. `eval_agent.py --agent multi_agent` now resolves.

  **Risks:**
  - Circular import: `supervisor.py` imports from `graph.py` (`_get_groq`, `_get_kb`, `llm_reasoning_node`); `graph.py` now imports from `supervisor.py`. → Resolved by lazy imports inside node functions (the `from src.agent.graph import ...` calls happen at node invocation time, not at module load time). Verify by confirming `python -c "from src.agent.graph import agent, multi_agent"` succeeds.

  **Git Checkpoint:**
  ```bash
  git add src/agent/graph.py
  git commit -m "step 5.10: export multi_agent from graph.py alongside generalist agent"
  ```

  **Subtasks:**
  - [ ] 🟥 `multi_agent = build_multi_agent_graph()` appended to `graph.py`
  - [ ] 🟥 No circular import on module load
  - [ ] 🟥 Verification passes

  **✓ Verification Test:**

  **Type:** Integration

  **Action:**
  ```bash
  python -c "
  import sys, os; sys.path.insert(0, '.')
  os.environ['EVAL_NO_LLM'] = '1'
  from src.agent.graph import agent, multi_agent
  print('agent nodes:', list(agent.nodes))
  print('multi_agent nodes:', list(multi_agent.nodes))
  assert 'signal' in multi_agent.nodes, 'signal node missing from multi_agent'
  assert 'reason' in agent.nodes, 'reason node missing from generalist agent'
  print('PASS Step 10: both agent and multi_agent import from graph.py without circular import')
  "
  ```

  **Expected:** Both node lists printed. `PASS Step 10:`. Exit code 0.

  **Fail:**
  - `ImportError: cannot import name multi_agent` → append not applied or wrong indentation.
  - `RecursionError` or `ImportError: circular` → lazy import inside node function broke — check `from src.agent.graph import ...` is inside the function body, not at module level in supervisor.py.

---

## Phase 5 — CI + Eval

**Goal:** CI compares generalist vs multi-agent on every push. No-LLM eval for multi-agent passes with FNR(RED)=0.000 and F1 ≥ 0.80. BENCHMARKS.md updated with Phase 5 results.

---

- [ ] 🟥 **Step 11: FIX-8 — Add cross-agent comparison step to `eval.yml`** — *Important: CI regression gate ensures multi-agent never regresses below generalist FNR*

  **Idempotent:** Yes — adding new YAML steps after existing eval step.

  **Pre-Read Gate:**
  - Run `grep -n "multi_agent\|multi-agent" .github/workflows/eval.yml`. Must return 0 matches.
  - Run `grep -n "Upload eval results" .github/workflows/eval.yml`. Must return exactly 1 match (insertion anchor).
  - Run `python -c "import yaml; yaml.safe_load(open('.github/workflows/eval.yml')); print('YAML OK')"`. Must print `YAML OK` before any edits.

  **Self-Contained Rule:** All code below is complete and runnable.

  In `.github/workflows/eval.yml`, insert the following two steps immediately **before** the `- name: Upload eval results` step:

  ```yaml
        - name: Run multi-agent eval (no-LLM, CI gate)
          env:
            QDRANT_PATH: qdrant_local
          run: >
            python eval/eval_agent.py
            --agent multi_agent
            --no-llm
            --fail-below-f1 0.80
            --fail-above-fnr 0.0
            --output results/eval_multiagent.json

        - name: Compare generalist vs multi-agent (FNR regression gate)
          run: |
            python -c "
            import json
            g = json.load(open('results/eval_agent.json'))
            m = json.load(open('results/eval_multiagent.json'))
            delta_f1       = m['f1']      - g['f1']
            delta_fnr      = m['fnr_red'] - g['fnr_red']
            delta_fnr_hard = m['fnr_hard'] - g['fnr_hard']
            print(f'F1 delta:       {delta_f1:+.3f}')
            print(f'FNR delta:      {delta_fnr:+.3f}')
            print(f'Hard-FNR delta: {delta_fnr_hard:+.3f}')
            assert delta_fnr <= 0, f'Multi-agent FNR WORSE than generalist: {delta_fnr:+.3f}'
            assert delta_fnr_hard <= 0, f'Multi-agent hard-FNR WORSE: {delta_fnr_hard:+.3f}'
            print('CI PASS: multi-agent FNR not worse than generalist on clean or hard scenarios')
            "
  ```

  **What it does:** Adds two CI steps: the multi-agent no-LLM eval (same gates as generalist) and a comparison that asserts multi-agent FNR cannot regress. F1 improvement is not a hard gate — only FNR is.

  **Git Checkpoint:**
  ```bash
  git add .github/workflows/eval.yml
  git commit -m "step 5.11: FIX-8 — add multi-agent eval + FNR comparison gate to eval.yml"
  ```

  **Subtasks:**
  - [ ] 🟥 Multi-agent eval step inserted before Upload step
  - [ ] 🟥 Comparison step inserted after multi-agent eval
  - [ ] 🟥 YAML valid after edit
  - [ ] 🟥 Verification passes

  **✓ Verification Test:**

  **Type:** Unit + Integration

  **Action:**
  ```bash
  # VG-1: YAML still valid
  python -c "import yaml; yaml.safe_load(open('.github/workflows/eval.yml')); print('PASS VG-1: eval.yml valid YAML')"

  # VG-2: multi_agent step present
  grep -c "multi_agent" .github/workflows/eval.yml
  ```

  **Expected:** `PASS VG-1:` printed. `grep -c` returns ≥ 2 (once in run step, once in output path). Exit code 0.

  **Fail:**
  - `yaml.safe_load raises` → YAML indentation error — re-read the block and confirm 8-space indent matches surrounding steps.

---

- [ ] 🟥 **Step 12: Create `tests/test_qdrant_parity.py` (FIX-9)** — *Non-critical: manual test; not in CI*

  **Idempotent:** Yes — creating new file.

  **Context:** Verifies that local on-disk Qdrant and Docker networked Qdrant return identical results. Run manually after `docker compose up qdrant -d`. Skipped in CI (Docker not available).

  **Pre-Read Gate:**
  - Run `ls tests/test_qdrant_parity.py 2>&1`. Must return error. If file exists → skip.

  **File — `tests/test_qdrant_parity.py`:**

  ```python
  """FIX-9: Qdrant mode parity test — local-path vs Docker networked.

  Run manually only — requires Docker:
      docker compose up qdrant -d
      python tests/test_qdrant_parity.py

  NOT in CI (Docker not available in GitHub Actions eval workflow).
  Verifies that local-path and networked Qdrant return identical query results
  so development and production behaviour are provably the same.
  """
  import os
  import sys
  from pathlib import Path

  REPO_ROOT = Path(__file__).resolve().parent.parent
  sys.path.insert(0, str(REPO_ROOT))

  from src.knowledge.knowledge_base import ClinicalKnowledgeBase

  TEST_QUERIES = [
      "RMSSD declining sepsis premature neonate",
      "bradycardia cluster three episodes 60 minutes",
      "personalised baseline LOOKBACK rolling window",
  ]


  def test_parity():
      qdrant_path = os.getenv("QDRANT_PATH", str(REPO_ROOT / "qdrant_local"))
      kb_local  = ClinicalKnowledgeBase(path=qdrant_path)
      kb_remote = ClinicalKnowledgeBase(host="localhost", port=6333)

      for query in TEST_QUERIES:
          local_results  = kb_local.query(query, n=3)
          remote_results = kb_remote.query(query, n=3)
          assert local_results == remote_results, (
              f"Parity failure for query: '{query}'\n"
              f"  Local:  {[r[:80] for r in local_results]}\n"
              f"  Remote: {[r[:80] for r in remote_results]}"
          )
          print(f"  OK: '{query[:50]}...' — 3 identical results")

      print("PASS FIX-9: local-path and networked Qdrant return identical results for all queries")


  if __name__ == "__main__":
      test_parity()
  ```

  **Git Checkpoint:**
  ```bash
  git add tests/test_qdrant_parity.py
  git commit -m "step 5.12: FIX-9 — add tests/test_qdrant_parity.py (manual, not CI)"
  ```

  **✓ Verification Test:**

  **Type:** Unit (import check only — Docker not required)

  **Action:**
  ```bash
  python -c "
  import sys; sys.path.insert(0, '.')
  import ast
  src = open('tests/test_qdrant_parity.py').read()
  ast.parse(src)
  print('PASS Step 12: test_qdrant_parity.py parses cleanly')
  "
  ```

  **Expected:** `PASS Step 12:`. Exit code 0.

---

- [ ] 🟥 **Step 13: Re-run evals with `multi_agent` + update `BENCHMARKS.md`** — *Critical: Phase 5 is not done until numbers are documented*

  **Idempotent:** Yes — overwrites result files.

  **Pre-Read Gate:**
  - Run `EVAL_NO_LLM=1 python -c "from src.agent.graph import multi_agent; print('multi_agent loaded')"`. Must succeed. If ImportError → Step 10 incomplete. (`EVAL_NO_LLM=1` required: without it, graph.py calls `_build_groq_client()` at import time and raises `RuntimeError` if no key.)
  - Run `python -c "from eval.scenarios import SCENARIOS; print(len(SCENARIOS))"`. Must print `30`.
  - Run `grep -c "## Phase 5 Multi-Agent Results" BENCHMARKS.md`. Must return 0. (Do NOT use `grep -c "Phase 5"` — the existing file already contains "Phase 5" multiple times in the header and improvement-claim sections. Only the exact heading `## Phase 5 Multi-Agent Results` is unique to the new section.)

  **Run no-LLM eval for multi_agent (CI gate):**
  ```bash
  QDRANT_PATH=qdrant_local python eval/eval_agent.py \
      --agent multi_agent \
      --no-llm \
      --fail-below-f1 0.80 \
      --fail-above-fnr 0.0 \
      --output results/eval_multiagent.json
  ```

  **Run live-LLM eval for multi_agent (requires `GROQ_API_KEY` in `.env`):**
  ```bash
  QDRANT_PATH=qdrant_local python eval/eval_agent.py \
      --agent multi_agent \
      --output results/eval_multiagent_live.json
  ```

  **Extract values from no-LLM results and update BENCHMARKS.md:**

  > NOTE: Live-LLM results (`eval_agent_live.json`, `eval_multiagent_live.json`) are run manually by the user after the no-LLM gates pass. The extraction script below uses only no-LLM result files that exist on disk. Live-LLM F1 values are filled into BENCHMARKS.md manually by the user after running `python eval/eval_agent.py` and `python eval/eval_agent.py --agent multi_agent` without `--no-llm`.

  ```bash
  python -c "
  import json
  from pathlib import Path

  g = json.load(open('results/eval_agent.json'))
  m = json.load(open('results/eval_multiagent.json'))

  print('Generalist no-LLM:  F1={:.3f} FNR={:.3f} FNR_hard={:.3f} protocol={:.3f}'.format(
      g['f1'], g['fnr_red'], g['fnr_hard'], g['protocol_compliance']))
  print('Multi-agent no-LLM: F1={:.3f} FNR={:.3f} FNR_hard={:.3f} protocol={:.3f}'.format(
      m['f1'], m['fnr_red'], m['fnr_hard'], m['protocol_compliance']))
  print('F1 delta (no-LLM): {:+.3f}'.format(m['f1'] - g['f1']))
  print('FNR delta (no-LLM): {:+.3f}'.format(m['fnr_red'] - g['fnr_red']))
  "
  ```

  Then append to `BENCHMARKS.md` using actual values from the command above. Live-LLM columns marked `[run manually]` until the user provides them:

  ```markdown

  ---

  ## Phase 5 Multi-Agent Results (30 Scenarios)

  *No-LLM gate recorded 2026-03-22. Live-LLM results to be filled after manual run.*

  | Metric | Generalist (Phase 4) | Multi-Agent (Phase 5) | Delta |
  |--------|---------------------|----------------------|-------|
  | F1 (macro, no-LLM) | [g_nollm_f1] | [m_nollm_f1] | [delta] |
  | F1 (macro, live LLM) | 0.533 | [run manually] | — |
  | FNR (RED) | 0.000 | 0.000 | 0.000 |
  | FNR (RED, hard scenarios, no-LLM) | [g_hard_fnr] | [m_hard_fnr] | [delta] |
  | Protocol compliance (no-LLM) | [g_protocol] | [m_protocol] | [delta] |

  *Phase 6 LoRA fine-tuning results will follow.*
  ```

  **No-Placeholder Rule for BENCHMARKS.md:** Replace every `[g_nollm_f1]`, `[m_nollm_f1]`, `[delta]`, `[g_hard_fnr]`, `[m_hard_fnr]`, `[g_protocol]`, `[m_protocol]` with actual values from the extraction command before committing. Do NOT commit with `[...]` tokens still present.

  **Regression check (generalist must still pass after all Phase 5 changes):**
  ```bash
  QDRANT_PATH=qdrant_local python eval/eval_agent.py \
      --agent agent \
      --no-llm \
      --fail-below-f1 0.80 \
      --fail-above-fnr 0.0
  ```

  **Git Checkpoint:**
  ```bash
  git add BENCHMARKS.md
  git commit -m "step 5.13: update BENCHMARKS.md with Phase 5 multi-agent results"
  ```

  **Subtasks:**
  - [ ] 🟥 Multi-agent no-LLM eval passes (F1 ≥ 0.80, FNR = 0.000, n=30)
  - [ ] 🟥 Generalist regression check passes (F1 ≥ 0.80, FNR = 0.000)
  - [ ] 🟥 BENCHMARKS.md updated with actual no-LLM values (no `[VALUE]` placeholders)
  - [ ] 🟥 Live-LLM column marked `[run manually]` (not invented)

  **✓ Verification Test:**

  **Type:** Integration

  **Action:**
  ```bash
  python -c "
  import json
  from pathlib import Path
  m = json.load(open('results/eval_multiagent.json'))
  assert m['n_scenarios'] == 30, f'Expected 30, got {m[\"n_scenarios\"]}'
  assert m['fnr_red'] == 0.0, f'FNR(RED) must be 0.000, got {m[\"fnr_red\"]}'
  assert m['f1'] >= 0.80, f'F1 must be >= 0.80, got {m[\"f1\"]}'
  bm = Path('BENCHMARKS.md').read_text()
  # Section-presence check: this exact heading does not exist before Step 13.
  assert '## Phase 5 Multi-Agent Results' in bm, \
      'Phase 5 section not appended — agent stopped before writing BENCHMARKS.md'
  # Placeholder completeness check: all 7 no-LLM tokens must be filled.
  # [run manually] in the live-LLM column is intentional — do NOT flag it.
  for token in ['g_nollm_f1', 'm_nollm_f1', 'g_hard_fnr', 'm_hard_fnr', 'g_protocol', 'm_protocol']:
      assert f'[{token}]' not in bm, f'Unfilled placeholder [{token}] still in BENCHMARKS.md'
  assert '[delta]' not in bm, 'Unfilled [delta] placeholder still in BENCHMARKS.md'
  print(f'PASS Step 13: multi-agent n={m[\"n_scenarios\"]} F1={m[\"f1\"]:.3f} FNR={m[\"fnr_red\"]:.3f}; BENCHMARKS.md updated')
  "
  ```

  **Expected:** `PASS Step 13:` printed. Exit code 0.

  **Fail:**
  - `F1 < 0.80` in no-LLM mode → clinical_agent_node rule-based path broken — check it delegates to `llm_reasoning_node`.
  - `FNR > 0.000` → a RED scenario classified as non-RED in no-LLM mode — check signal/clinical rule-based paths preserve `risk_level`.

---

## Regression Guard

**Systems at risk:**
- `EpisodicMemory.save()` — new kwargs added; existing generalist callers must still work.
- `src/agent/graph.py` — `multi_agent` appended; generalist `agent` must be unchanged.
- `eval/eval_agent.py` — `--agent agent` path must still pass (no-LLM F1=1.000, FNR=0.000).

**Regression verification:**

| System | Pre-change behaviour | Post-change verification |
|--------|---------------------|--------------------------|
| Generalist `agent` | no-LLM F1=1.000, FNR=0.000, n=30 | `eval_agent.py --agent agent --no-llm` — same results |
| `EpisodicMemory.save()` | 3-positional + 2-optional-kwargs | `grep -rn "EpisodicMemory().save(" src/` — existing call in graph.py unchanged |
| Dep contract tests | `2 passed` | `python -m pytest tests/test_dependency_apis.py -v` |

---

## Rollback Procedure

```bash
# Rollback in reverse step order
git revert HEAD    # Step 13: remove Phase 5 BENCHMARKS section
git revert HEAD    # Step 12: remove test_qdrant_parity.py
git revert HEAD    # Step 11: revert eval.yml FIX-8
git revert HEAD    # Step 10: remove multi_agent from graph.py
git revert HEAD    # Step 9:  remove supervisor.py
git revert HEAD    # Step 8:  remove protocol_agent.py
git revert HEAD    # Step 7:  remove clinical_agent.py
git revert HEAD    # Step 6:  remove brady_agent.py
git revert HEAD    # Step 5:  remove signal_agent.py + specialists/__init__.py
git revert HEAD    # Step 4:  revert save() signature
git revert HEAD    # Step 3b: revert save() Phase B
git revert HEAD    # Step 3a: revert _init_schema + schema_meta migration
git revert HEAD    # Step 2:  revert query_by_category
git revert HEAD    # Step 1:  revert schemas.py additions

# Confirm rollback:
python -c "from src.agent.graph import agent; print('generalist OK')"
python -c "from src.agent.graph import multi_agent" 2>&1 | grep -c "cannot import"  # expect 1
```

---

## Pre-Flight Checklist

| Phase | Check | How to Confirm | Status |
|-------|-------|----------------|--------|
| **Pre-flight** | multi_agent absent from graph.py | `grep -c "multi_agent" src/agent/graph.py` = 0 | ⬜ |
| | schemas absent | `grep -c "SignalAssessment" src/agent/schemas.py` = 0 | ⬜ |
| | specialists/ absent | `ls src/agent/specialists/` returns error | ⬜ |
| | audit.db has 9 columns | PRAGMA table_info count = 9 | ⬜ |
| **Phase 1** | `Literal` imported in schemas.py | `grep "from typing import.*Literal" src/agent/schemas.py` returns 1 | ⬜ |
| | `Filter`, `FieldCondition`, `MatchValue` imported in knowledge_base.py | grep returns ≥ 1 each | ⬜ |
| **Phase 2** | Phase A verified before Phase B | PRAGMA confirms 14 columns + schema_meta | ⬜ |
| **Phase 3** | specialists/__init__.py exists | `ls src/agent/specialists/__init__.py` | ⬜ |
| | Each specialist verified standalone | Per-step unit tests pass | ⬜ |
| **Phase 4** | No circular import | `python -c "from src.agent.graph import agent, multi_agent"` exits 0 | ⬜ |
| **Phase 5** | eval.yml valid YAML after Step 11 | `yaml.safe_load` succeeds | ⬜ |
| | Step 13 pre-req | `multi_agent` importable + 30 scenarios loaded | ⬜ |

---

## Risk Heatmap

| Step | Risk | What Could Go Wrong | Early Detection | Idempotent |
|------|------|---------------------|-----------------|------------|
| Step 1 | 🟢 Low | Missing import (`Literal`) | Verification import fails | Yes |
| Step 2 | 🟡 Medium | `should` filter returns 0 results | Verification asserts len==3 | Yes |
| Step 3 Phase A | 🟡 Medium | ALTER TABLE swallows non-duplicate error | PRAGMA table_info check catches it | Yes |
| Step 4 Phase B | 🟡 Medium | Phase A skipped → INSERT fails | Phase A gate in Pre-Read Gate | Yes |
| Step 5–8 | 🟢 Low | Rule-based path returns wrong keys | Per-step unit tests catch key names | Yes |
| Step 9 | 🟡 Medium | Circular import supervisor↔graph | Lazy imports inside node functions prevent it | Yes |
| Step 10 | 🟡 Medium | Circular import at module load | Verification import test catches it immediately | Yes |
| Step 11 | 🟢 Low | YAML indentation breaks CI | VG-1 yaml.safe_load check | Yes |
| Step 13 | 🟡 Medium | F1 < 0.80 in no-LLM mode for multi_agent | clinical_agent delegates to llm_reasoning_node | Yes |

---

## Success Criteria

| Metric | Target | Verification |
|--------|--------|--------------|
| `SignalAssessment` / `BradycardiaAssessment` importable | ✅ | `from src.agent.schemas import SignalAssessment, BradycardiaAssessment` |
| `query_by_category()` returns correct category-filtered chunks | ✅ | Returns ≥ 1 chunk; category confirmed by specialist test |
| audit.db schema version | 2.0 | `SELECT value FROM schema_meta WHERE key='version'` = '2.0' |
| `save()` logs specialist outputs | ✅ | `agent_version='multi_agent'` row in audit.db after multi_agent run |
| All 4 specialist nodes importable standalone | ✅ | Per-step unit tests pass |
| `multi_agent` importable from `graph.py` | ✅ | `from src.agent.graph import agent, multi_agent` — no ImportError |
| Multi-agent no-LLM FNR(RED) | 0.000 | `results/eval_multiagent.json` → `fnr_red: 0.0` |
| Multi-agent no-LLM F1 | ≥ 0.80 | `results/eval_multiagent.json` → `f1 ≥ 0.80` |
| Generalist no-LLM not regressed | F1=1.000, FNR=0.000 | `eval_agent.py --agent agent --no-llm` — same as Phase 4 |
| BENCHMARKS.md Phase 5 section | Written with actual values | No `[VALUE]` in BENCHMARKS.md; Phase 5 row present |

---

⚠️ **Do not mark a step 🟩 Done until its verification test passes.**
⚠️ **Do not proceed past a Human Gate without explicit human input.**
⚠️ **If blocked, mark 🟨 In Progress and output the State Manifest before stopping.**
⚠️ **Do not batch multiple steps into one git commit.**
⚠️ **Steps 3 and 4 are a split operation — do not combine their commits.**
