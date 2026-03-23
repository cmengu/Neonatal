# Phase 4 Execution Plan — Eval Framework + CI + Pre-Flight Hardening

**Overall Progress:** `0% (0/11 steps done)`

---

## TLDR

Five post-mortem hardening fixes (FIX-1 through FIX-5) need to be applied before the Phase 4 baseline is trustworthy. The eval infra (scenarios.py, eval_agent.py, eval_retrieval.py, run_all_evals.py, eval.yml) already exists and has produced 24-scenario no-LLM results (F1=1.000) and live-LLM results (F1=0.533, FNR(RED)=0.000). What remains: FIX-1 feature order assertion, FIX-2 input logging in audit.db, FIX-3 dependency version pinning + API contract tests, FIX-4 six hard mixed-signal scenarios, FIX-5 baseline skew runtime warning. After those five fixes, re-run evals on 30 scenarios and commit the generalist baseline to BENCHMARKS.md. Phase 5 cannot start without BENCHMARKS.md.

---

## Critical Decisions

- **FIX-2 schema migration:** Use `ALTER TABLE ADD COLUMN` with silent exception swallow in `_init_schema()` rather than deleting `audit.db`. This is idempotent and preserves existing rows.
- **FIX-3 version pins:** Human gate before pinning — agent runs `pip show` and human confirms exact installed versions before writing to `requirements.txt`. Project plan provides reference values but installed versions are authoritative.
- **FIX-4 fnr_hard:** Computed inside `eval_agent.py::run_eval()` using `'HARD' in scenario.patient_id` filter, same pattern as the project plan's `[s for s in SCENARIOS if 'HARD' in s.patient_id]`.
- **eval.yml dep test step:** CI workflow gains a `pytest tests/test_dependency_apis.py -v` step before the agent eval step. This detects API contract drift on every push.

---

## Clarification Gate

| Unknown | Required | Source | Blocking | Resolved |
|---------|----------|--------|----------|----------|
| Exact installed versions of flashrank, qdrant-client, sentence-transformers, skl2onnx, onnxruntime, scikit-learn, pytest | Exact `==` pins for requirements.txt | `pip show` output (Step 4 Phase A) | Step 4 Phase B | ⬜ (resolved at Human Gate) |

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
# 1. Confirm feature assertion absent (expect: no output)
grep -n "assert actual_cols" src/models/train_classifier.py

# 2. Confirm input logging absent in memory.py (expect: no output)
grep -n "z_scores_json\|hrv_values_json" src/agent/memory.py

# 3. Confirm skew warning absent in runner.py (expect: no output)
grep -n "skew_warnings" src/pipeline/runner.py

# 4. Confirm scenarios count is 24
grep -n "assert len(SCENARIOS)" eval/scenarios.py

# 5. Confirm tests/ directory does not exist
ls tests/ 2>&1 || echo "tests/ does not exist"

# 6. Confirm requirements.txt uses ranges (not pins) for critical packages
grep -E "flashrank|qdrant-client|sentence-transformers|skl2onnx" requirements.txt

# 7. Confirm BENCHMARKS.md does not exist
ls BENCHMARKS.md 2>&1 || echo "BENCHMARKS.md does not exist"

# 8. Record existing eval baselines
cat results/eval_agent.json | python -c "import json,sys; r=json.load(sys.stdin); print('no-LLM F1:', r['f1'], 'FNR:', r['fnr_red'], 'n:', r['n_scenarios'])"
cat results/eval_agent_live.json | python -c "import json,sys; r=json.load(sys.stdin); print('live-LLM F1:', r['f1'], 'FNR:', r['fnr_red'], 'n:', r['n_scenarios'])"
```

**Baseline Snapshot (agent fills during pre-flight):**
```
grep "assert actual_cols" train_classifier.py:   ____  (expect: 0 matches)
grep "z_scores_json" memory.py:                  ____  (expect: 0 matches)
grep "skew_warnings" runner.py:                  ____  (expect: 0 matches)
Scenario count assertion:                        ____  (expect: == 24)
tests/ directory:                                ____  (expect: does not exist)
requirements.txt flashrank pin:                  ____  (expect: no ==)
BENCHMARKS.md:                                   ____  (expect: does not exist)
no-LLM baseline F1 / FNR / n:                   ____
live-LLM baseline F1 / FNR / n:                 ____
```

**Automated checks (all must pass before Step 1):**
- [ ] Pre-flight commands run and output captured above
- [ ] None of the five hardening assertions already present
- [ ] No in-progress migrations or uncommitted schema changes to audit.db

---

## Steps Analysis

```
Step 1  (FIX-1: feature order assertion)        — Critical  (silent wrong predictions if absent)   — full code review — Idempotent: Yes
Step 2  (FIX-2 Phase A: schema migration)        — Critical  (db schema change, split op)           — full code review — Idempotent: Yes
Step 3  (FIX-2 Phase B: save() + graph.py)       — Critical  (writes model inputs to audit log)     — full code review — Idempotent: Yes
Step 4  (FIX-3 Phase A+B: dep version pins + pytest) — Critical  (human gate for version values; pytest pin unblocks Step 5) — full code review — Idempotent: Yes
Step 5  (FIX-3: dep API tests + CI step)             — Critical  (API contract regression on every push; depends on Step 4B pytest pin) — full code review — Idempotent: Yes
Step 6  (FIX-5: baseline skew assertion)             — Critical  (z-score correctness for Phase 5)      — full code review — Idempotent: Yes
Step 7  (FIX-4: add 6 hard scenarios)            — Important (expand eval coverage)                 — full code review — Idempotent: Yes
Step 8  (FIX-4: fnr_hard in eval_agent.py)       — Important (track hard-scenario FNR)              — full code review — Idempotent: Yes
Step 9  (FIX-4: update eval.yml PR comment)      — Non-critical (CI comment cosmetic)               — verification only — Idempotent: Yes
Step 10 (Re-run evals with 30 scenarios)         — Critical  (30-scenario baseline for Phase 5)     — full code review — Idempotent: Yes
Step 11 (Write BENCHMARKS.md)                    — Critical  (Phase 5 cannot start without it)      — verification only — Idempotent: Yes
```

---

## Environment Matrix

| Step | Dev | CI | Notes |
|------|-----|----|-------|
| Steps 1–9 | ✅ | ✅ | Code changes, no env-specific behaviour |
| Step 10 (no-LLM) | ✅ | ✅ | CI runs this automatically |
| Step 10 (live-LLM) | ✅ | ⚠️ Manual | Requires GROQ_API_KEY in .env; run locally |
| Step 11 | ✅ | ❌ Skip | Manually committed after step 10 |

---

## Phase 1 — Correctness Hardening

**Goal:** Two silent-failure vectors (feature order drift, missing input audit trail) are eliminated. Any future retrain produces an assertion error if column order drifts; every alert is traceable to its exact model inputs.

---

- [ ] 🟥 **Step 1: FIX-1 — Feature order assertion in `train_classifier.py`** — *Critical: ONNX model uses positional features; column order drift produces wrong predictions with no error*

  **Idempotent:** Yes — `assert` statement is a no-op if condition holds; insertion is a single new block.

  **Context:** `train_classifier.py::train()` builds `X_train` by calling `train_df[HRV_FEATURE_COLS].values`. If pandas reorders columns (e.g., after a CSV regeneration), features silently shift positions and all predictions are wrong. The assertion fires at train time before `clf.fit()` and before the feature values are extracted to numpy.

  **Pre-Read Gate:**
  - Run `grep -n "X_train = train_df\[HRV_FEATURE_COLS\]" src/models/train_classifier.py`. Must return exactly 1 match. If 0 or 2+ → STOP.
  - Run `grep -n "assert actual_cols" src/models/train_classifier.py`. Must return 0 matches (assertion not yet present). If 1 → step already done, skip.

  **Self-Contained Rule:** All code below is complete and runnable.

  **No-Placeholder Rule:** No `<VALUE>` tokens.

  In `src/models/train_classifier.py`, insert the following block immediately **before** the line `X_train = train_df[HRV_FEATURE_COLS].values.astype(np.float32)`:

  ```python
      # FIX-1: Assert feature column order matches HRV_FEATURE_COLS before fitting.
      # ONNX inference uses positional columns — silent order drift produces wrong predictions.
      actual_cols = train_df[HRV_FEATURE_COLS].columns.tolist()
      assert actual_cols == list(HRV_FEATURE_COLS), (
          f"Column order mismatch between HRV_FEATURE_COLS and CSV.\n"
          f"  Expected: {list(HRV_FEATURE_COLS)}\n"
          f"  Got:      {actual_cols}\n"
          f"  The ONNX model uses positional features — order must be identical."
      )
      logging.info("FIX-1: Feature order verified: %s", actual_cols)
  ```

  **What it does:** Asserts that `train_df[HRV_FEATURE_COLS]` preserves the declared column order before values are passed to the classifier. If order drifts, training aborts with a clear diagnostic message.

  **Why this approach:** Positional assertion at train time rather than inference time — catching it earlier prevents a bad model from being exported.

  **Assumptions:**
  - `HRV_FEATURE_COLS` is a sequence (list or tuple) already imported at file top.
  - `train_df` has already had `dropna` applied — all declared columns are present.

  **Risks:**
  - Assertion fires on first run if CSV was generated with different order → this is the intended behaviour; re-run notebook 03 to regenerate CSV.

  **Git Checkpoint:**
  ```bash
  git add src/models/train_classifier.py
  git commit -m "step 1: FIX-1 — add feature order assertion before clf.fit() in train_classifier.py"
  ```

  **Subtasks:**
  - [ ] 🟥 Pre-Read Gate: anchor exists exactly once, assertion not yet present
  - [ ] 🟥 Block inserted immediately before `X_train = train_df[HRV_FEATURE_COLS].values.astype(np.float32)`
  - [ ] 🟥 Verification passes

  **✓ Verification Test:**

  **Type:** Integration

  **Action:**
  ```bash
  python -c "
  import pandas as pd, sys
  from pathlib import Path
  sys.path.insert(0, str(Path('.').resolve()))
  from src.features.constants import HRV_FEATURE_COLS
  df = pd.read_csv('data/processed/combined_features_labelled.csv')
  actual = df[HRV_FEATURE_COLS].columns.tolist()
  assert actual == list(HRV_FEATURE_COLS), f'ORDER MISMATCH: {actual}'
  print('PASS FIX-1: feature order matches HRV_FEATURE_COLS')
  print('Order:', actual)
  "
  ```

  **Expected:** `PASS FIX-1: feature order matches HRV_FEATURE_COLS` followed by the feature list. Exit code 0.

  **Pass:** Exit code 0, PASS line printed.

  **Fail:**
  - `ORDER MISMATCH` → CSV column order differs — re-run notebook 03.
  - `ModuleNotFoundError` → run from repo root.

---

- [ ] 🟥 **Step 2: FIX-2 Phase A — Schema migration in `memory.py`** — *Critical: audit.db already exists; CREATE TABLE IF NOT EXISTS will not add new columns to existing table*

  > ⚠️ **Split Operation** — Phase A migrates the db schema. Phase B (Step 3) updates the Python `save()` call. Phase A must verify the new columns exist before Phase B writes to them.

  **Idempotent:** Yes — `ALTER TABLE ADD COLUMN` is wrapped in try/except so re-running does not fail if columns already exist.

  **Context:** `audit.db` stores one row per alert with 6 columns. FIX-2 adds `z_scores_json` and `hrv_values_json` so every alert can be traced back to its model inputs. Without these columns, debugging a wrong specialist output in Phase 5 is impossible.

  **Pre-Read Gate:**
  - Run `grep -n "z_scores_json\|hrv_values_json" src/agent/memory.py`. Must return 0 matches. If any → step already done, skip.
  - Run `grep -n "def _init_schema" src/agent/memory.py`. Must return exactly 1 match.
  - Run `grep -n "CREATE TABLE IF NOT EXISTS alert_history" src/agent/memory.py`. Must return exactly 1 match.

  **Self-Contained Rule:** All code below is complete and runnable.

  In `src/agent/memory.py`, replace the entire `_init_schema` method:

  ```python
      def _init_schema(self) -> None:
          with sqlite3.connect(self.db_path) as conn:
              conn.execute(
                  """
                  CREATE TABLE IF NOT EXISTS alert_history (
                      id              INTEGER PRIMARY KEY AUTOINCREMENT,
                      patient_id      TEXT,
                      timestamp       TEXT,
                      concern_level   TEXT,
                      risk_score      REAL,
                      top_feature     TEXT,
                      top_z_score     REAL,
                      z_scores_json   TEXT,
                      hrv_values_json TEXT
                  )
                  """
              )
              # Migrate existing tables that predate FIX-2.
              # ALTER TABLE ADD COLUMN raises OperationalError on re-run ("duplicate column name").
              # The try/except makes this migration idempotent.
              for col_def in ("z_scores_json TEXT", "hrv_values_json TEXT"):
                  try:
                      conn.execute(f"ALTER TABLE alert_history ADD COLUMN {col_def}")
                  except Exception:
                      pass  # column already present — safe to ignore
  ```

  **What it does:** Creates the table with both new columns on fresh dbs. For existing dbs, silently adds the two columns via `ALTER TABLE`.

  **Why this approach:** Idempotent migration without deleting existing audit data. SQLite `ALTER TABLE ADD COLUMN` raises `OperationalError: duplicate column name` on re-run — the try/except makes the migration safe to run multiple times.

  **Risks:**
  - `ALTER TABLE` fails for a reason other than duplicate column → the exception is silently swallowed. Mitigation: run the Phase A verification (`PRAGMA table_info`) immediately after to confirm columns are present.

  **Git Checkpoint (Phase A):**
  ```bash
  git add src/agent/memory.py
  git commit -m "step 2a: FIX-2 Phase A — add z_scores_json/hrv_values_json columns to alert_history schema"
  ```

  **Phase A Verification:**
  ```bash
  python -c "
  import sqlite3, sys
  sys.path.insert(0, '.')
  from src.agent.memory import EpisodicMemory
  EpisodicMemory()  # triggers _init_schema() with ALTER TABLE migration
  conn = sqlite3.connect('data/audit.db')
  cols = [row[1] for row in conn.execute('PRAGMA table_info(alert_history)').fetchall()]
  assert 'z_scores_json'   in cols, f'z_scores_json missing — got {cols}'
  assert 'hrv_values_json' in cols, f'hrv_values_json missing — got {cols}'
  print('PASS Phase 2A: columns present:', cols)
  "
  ```

  **State Manifest — Phase A:**
  ```
  Files modified: src/agent/memory.py (_init_schema replaced)
  Values produced: audit.db now has z_scores_json and hrv_values_json columns (NULL for existing rows)
  Verifications passed: Step 1 ✅, Step 2A ✅
  Next: Step 3 (Phase B) — update save() signature and graph.py assemble_alert_node
  ```

  **Human Gate — Phase A complete:**
  Output `"[PHASE 2A COMPLETE — WAITING FOR HUMAN TO CONFIRM PHASE A VERIFICATION PASSED]"` as the final line of your response.
  Do not write any code or call any tools after this line.

---

- [ ] 🟥 **Step 3: FIX-2 Phase B — Update `save()` and `assemble_alert_node`** — *Critical: writes z-scores and HRV values into audit.db on every alert*

  **Idempotent:** Yes — pure code replacement; re-running writes the same columns.

  **Context:** Phase A added the columns. Phase B updates the Python code to populate them. Two files change: `memory.py` (`save()` signature and INSERT) and `graph.py` (`EpisodicMemory().save()` call in `assemble_alert_node`).

  **Pre-Read Gate:**
  - Run `grep -n "def save" src/agent/memory.py`. Must return exactly 1 match with signature `def save(self, alert: NeonatalAlert, top_feature: str, top_z: float)`.
  - Run `grep -n "EpisodicMemory().save(" src/agent/graph.py`. Must return exactly 1 match.
  - Run `grep -n "^import json\|^from __future__" src/agent/memory.py`. Must return 0 matches (neither import present yet).
  - **Confirm `result` attributes exist on PipelineResult:** Run `grep -n "z_scores\b" src/pipeline/runner.py`. Must return ≥ 1 match confirming `z_scores` is a field on the result object. Run `grep -n "hrv_values\b" src/pipeline/runner.py`. Must return ≥ 1 match. If either returns 0 → `PipelineResult` does not expose these attributes; STOP and add them to the data model before proceeding.
  - **Enforce Phase A gate:** Run the Phase A verification command below. Both columns must be confirmed present. If either is missing → Phase A (Step 2) was not applied or failed — STOP and return to Step 2 before proceeding.
    ```bash
    python -c "
    import sqlite3, sys; sys.path.insert(0, '.')
    from src.agent.memory import EpisodicMemory
    EpisodicMemory()
    cols = [r[1] for r in sqlite3.connect('data/audit.db').execute('PRAGMA table_info(alert_history)').fetchall()]
    assert 'z_scores_json'   in cols, f'STOP: z_scores_json missing — Phase A incomplete. cols={cols}'
    assert 'hrv_values_json' in cols, f'STOP: hrv_values_json missing — Phase A incomplete. cols={cols}'
    print('Phase A confirmed: both columns present')
    "
    ```

  **Self-Contained Rule:** All code below is complete and runnable.

  **Change 1 — add `from __future__ import annotations` and `import json` to `src/agent/memory.py`:**

  `memory.py` does not currently have `from __future__ import annotations`. The new `save()` signature uses `dict | None` union syntax which requires Python 3.10+ without this import. Adding it ensures compatibility with Python 3.9 and makes the annotation evaluation lazy.

  The existing file starts with the module docstring followed by:
  ```python
  import sqlite3
  from dataclasses import dataclass
  ```
  Replace with:
  ```python
  from __future__ import annotations

  import json
  import sqlite3
  from dataclasses import dataclass
  ```

  **Change 2 — replace the entire `save` method in `src/agent/memory.py`:**

  Replace:
  ```python
      def save(self, alert: NeonatalAlert, top_feature: str, top_z: float) -> None:
          """Persist a finalised alert to the audit log."""
          with sqlite3.connect(self.db_path) as conn:
              conn.execute(
                  """
                  INSERT INTO alert_history
                  (patient_id, timestamp, concern_level, risk_score, top_feature, top_z_score)
                  VALUES (?, ?, ?, ?, ?, ?)
                  """,
                  (
                      alert.patient_id,
                      alert.timestamp.isoformat(),
                      alert.concern_level,
                      alert.risk_score,
                      top_feature,
                      top_z,
                  ),
              )
  ```
  With:
  ```python
      def save(
          self,
          alert: NeonatalAlert,
          top_feature: str,
          top_z: float,
          z_scores: dict | None = None,
          hrv_values: dict | None = None,
      ) -> None:
          """Persist a finalised alert to the audit log including full model inputs."""
          with sqlite3.connect(self.db_path) as conn:
              conn.execute(
                  """
                  INSERT INTO alert_history
                  (patient_id, timestamp, concern_level, risk_score,
                   top_feature, top_z_score, z_scores_json, hrv_values_json)
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
                  ),
              )
  ```

  **Change 3 — update `EpisodicMemory().save(...)` call in `src/agent/graph.py`:**

  Replace:
  ```python
      EpisodicMemory().save(alert, top_feature_name, top_feature_z)
  ```
  With:
  ```python
      EpisodicMemory().save(
          alert,
          top_feature_name,
          top_feature_z,
          z_scores=result.z_scores,
          hrv_values=result.hrv_values,
      )
  ```

  **What it does:** `save()` now accepts optional `z_scores` and `hrv_values` dicts and serialises them to JSON in the two new columns. New kwargs have `None` defaults so existing test callers that pass only 3 positional args do not break.

  **Risks:**
  - Phase A not done → INSERT fails with `table has no column named z_scores_json` → confirm Phase A verification passed first.
  - `result.z_scores` is an empty dict for a synthetic scenario → `json.dumps({})` = `"{}"`, which is valid; not a failure.

  **Git Checkpoint:**
  ```bash
  git add src/agent/memory.py src/agent/graph.py
  git commit -m "step 3: FIX-2 Phase B — update save() to log z_scores/hrv_values; update assemble_alert_node call"
  ```

  **Subtasks:**
  - [ ] 🟥 `import json` added to `memory.py` imports
  - [ ] 🟥 `save()` method replaced in `memory.py`
  - [ ] 🟥 `EpisodicMemory().save(...)` call updated in `graph.py`
  - [ ] 🟥 Verification passes

  **✓ Verification Test:**

  **Type:** Integration

  **Action:**
  ```bash
  python -c "
  import sys, json, sqlite3, os
  sys.path.insert(0, '.')
  os.environ['EVAL_NO_LLM'] = '1'
  from eval.scenarios import SCENARIOS, inject_scenario, clear_injection
  inject_scenario(SCENARIOS[0])
  from src.agent.graph import agent
  agent.invoke({'patient_id': SCENARIOS[0].patient_id})
  clear_injection()
  conn = sqlite3.connect('data/audit.db')
  row = conn.execute(
      'SELECT z_scores_json, hrv_values_json FROM alert_history WHERE patient_id = ? ORDER BY id DESC LIMIT 1',
      (SCENARIOS[0].patient_id,)
  ).fetchone()
  assert row is not None, 'No row found'
  assert row[0] is not None, 'z_scores_json is NULL'
  assert row[1] is not None, 'hrv_values_json is NULL'
  z = json.loads(row[0])
  h = json.loads(row[1])
  assert len(z) == 10, f'Expected 10 z-scores, got {len(z)}'
  assert len(h) == 10, f'Expected 10 hrv values, got {len(h)}'
  print('PASS FIX-2:', len(z), 'z-scores and', len(h), 'hrv values stored per alert')
  "
  ```

  **Expected:** `PASS FIX-2: 10 z-scores and 10 hrv values stored per alert`. Exit code 0.

  **Fail:**
  - `table has no column named z_scores_json` → Phase A not applied — run Step 2 first.
  - `z_scores_json is NULL` → `save()` not updated — check Change 2.
  - `len(z) != 10` → `result.z_scores` has wrong key count — check `HRV_FEATURE_COLS` length.

---

## Phase 2 — Dependency Hardening + Baseline Skew Guard

**Goal:** All critical dependencies are pinned to exact verified versions. API contracts are tested on every CI push. The baseline skew runtime guard (FIX-5) is added so Phase 5 specialist agents always receive correctly computed z-scores.

---

- [ ] 🟥 **Step 4: FIX-3 — Pin exact versions in `requirements.txt`** — *Critical: range versions allow silent API-breaking updates between environments*

  > ⚠️ **Split Operation** — Phase A captures installed versions (read-only). Human confirms. Phase B writes pins.

  **Idempotent:** Phase A: Yes (read-only). Phase B: Yes (replacing same lines).

  **Context:** `requirements.txt` uses `>=` ranges for `qdrant-client`, `scikit-learn`, and no pin at all for `flashrank`, `sentence-transformers`, `skl2onnx`, `onnxruntime`. The FlashRank API change in the post-mortem would have been a silent runtime crash in production. Pinning locks every environment to the versions verified in development.

  ---

  **Phase A — Capture installed versions (read-only)**

  **Pre-Read Gate:**
  - Run `grep -n "flashrank\|qdrant-client\|sentence-transformers\|skl2onnx\|onnxruntime\|scikit-learn" requirements.txt`. Confirm these packages are present with range or no-pin forms. If any already use `==` → that package is already pinned, skip it in Phase B.

  ```bash
  pip show flashrank qdrant-client sentence-transformers skl2onnx onnxruntime scikit-learn pytest \
      | grep -E "^Name:|^Version:"
  ```

  Show the full output. Do not change anything.

  **Phase A Verification:** The `pip show` command ran and returned `Name`/`Version` pairs for all six packages.

  **State Manifest — Phase A:**
  ```
  Files modified: none (read-only step)
  Values produced:
    flashrank version:             ____
    qdrant-client version:         ____
    sentence-transformers version: ____
    skl2onnx version:              ____
    onnxruntime version:           ____
    scikit-learn version:          ____
    pytest version:                ____
  Next: Phase B requires human confirmation of version strings above
  ```

  **Human Gate — Phase A complete:**
  Output `"[PHASE 4A COMPLETE — WAITING FOR HUMAN TO CONFIRM VERSION STRINGS FROM pip show OUTPUT]"` as the final line of your response.
  Do not write any code or call any tools after this line.

  ---

  **Phase B — Pin versions in `requirements.txt`**

  > Only execute after human provides confirmed version strings from Phase A.

  **Agent instruction:** Use ONLY the versions confirmed by the human. Do not use the reference values in the project plan document unless the human confirms they match. If human has not confirmed, output `"WAITING FOR HUMAN CONFIRMATION"` and stop.

  In `requirements.txt`, replace each of the seven unpinned lines with the confirmed exact version. The lines to replace are:
  - `qdrant-client>=1.7` → `qdrant-client==<CONFIRMED>`
  - `sentence-transformers` → `sentence-transformers==<CONFIRMED>`
  - `flashrank` → `flashrank==<CONFIRMED>`
  - `skl2onnx` → `skl2onnx==<CONFIRMED>`
  - `onnxruntime` → `onnxruntime==<CONFIRMED>`
  - `scikit-learn>=1.3` → `scikit-learn==<CONFIRMED>`
  - Add `pytest==<CONFIRMED>` as a new line (pytest is not currently in requirements.txt — append it under a `# Dev / CI` comment at the end of the file).

  **Phase B Verification:**
  ```bash
  python -c "
  reqs = open('requirements.txt').read()
  for pkg in ['flashrank', 'qdrant-client', 'sentence-transformers', 'skl2onnx', 'onnxruntime', 'scikit-learn', 'pytest']:
      lines = [l for l in reqs.splitlines() if l.startswith(pkg)]
      assert lines, f'{pkg} not found in requirements.txt'
      assert '==' in lines[0], f'{pkg} not pinned with ==: got {lines[0]}'
      assert '>=' not in lines[0], f'{pkg} still uses >=: {lines[0]}'
      print(f'OK: {lines[0]}')
  print('PASS FIX-3: all 7 packages pinned with ==')
  "
  ```

  **Git Checkpoint (Phase B):**
  ```bash
  git add requirements.txt
  git commit -m "step 4b: FIX-3 — pin exact versions for 7 packages (including pytest) in requirements.txt"
  ```

  **Subtasks:**
  - [ ] 🟥 Phase A: `pip show` run, versions captured in State Manifest (including pytest)
  - [ ] 🟥 Human gate: version strings confirmed
  - [ ] 🟥 Phase B: all 7 packages pinned with `==`; pytest added as new line
  - [ ] 🟥 Phase B verification passes

  **✓ Verification Test (Phase B):**

  **Type:** Unit

  **Action:** Phase B Verification command above.

  **Expected:** Seven `OK:` lines each showing `package==version`, followed by `PASS FIX-3`. Exit code 0.

  **Pass:** No `>=` remaining for the seven packages; `pytest` entry present.

  **Fail:**
  - `pytest not found in requirements.txt` → pytest line was not appended — add it at end of file under `# Dev / CI`.
  - `not pinned with ==` → replacement missed that line — re-read requirements.txt and check exact line content.

---

- [ ] 🟥 **Step 5: FIX-3 — Create `tests/test_dependency_apis.py` and add CI dep test step** — *Critical: API contract regression tests fire on every push*

  **Idempotent:** Yes — creating new files and adding a new YAML step.

  **Context:** Two API contracts are at risk: FlashRank's result format (dict with `"text"` key) and ONNX output format (`ndarray` with shape `(n, 2)` when `zipmap=False`). A new `tests/` directory is created. The `eval.yml` CI workflow gains a pytest step before the agent eval step.

  **Pre-Read Gate:**
  - Run `ls tests/ 2>&1`. Must return `No such file or directory`. If directory exists → check if test file already present.
  - Run `grep -n "test_dependency_apis\|pytest" .github/workflows/eval.yml`. Must return 0 matches.
  - Run `grep -n "Install dependencies" .github/workflows/eval.yml`. Must return exactly 1 match (anchor for new YAML step).
  - Run `grep -n "^pytest==" requirements.txt`. Must return exactly 1 match — confirms Step 4B added the pytest pin. If 0 matches → Step 4B is incomplete; STOP and complete Step 4 before proceeding.

  **Self-Contained Rule:** All code below is complete and runnable.

  **File 1 — Create `tests/__init__.py`** (empty, makes `tests/` importable as a package):

  Write an empty file at `tests/__init__.py`.

  **File 2 — Create `tests/test_dependency_apis.py`:**

  ```python
  """FIX-3: API contract tests for flashrank and ONNX runtime.

  These tests verify that the external API shapes we depend on have not drifted.
  Run in CI (pytest tests/test_dependency_apis.py -v) before the agent eval suite.

  flashrank contract: results[0] is a dict with a 'text' key (not an object attribute).
  ONNX contract:      output[1] is ndarray with shape (n, 2) when zipmap=False.
  """
  import numpy as np
  import pytest


  def test_flashrank_returns_dict_with_text_key():
      """Verify flashrank API contract — results[0]['text'] not results[0].text."""
      from flashrank import Ranker, RerankRequest

      ranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2", cache_dir="/tmp/flashrank_cache")
      results = ranker.rerank(
          RerankRequest(
              query="RMSSD neonatal sepsis",
              passages=[{"id": "1", "text": "RMSSD measures short-term HRV in premature neonates."}],
          )
      )
      assert len(results) > 0, "flashrank returned no results"
      assert isinstance(results[0], dict), (
          f"flashrank API changed — results[0] is {type(results[0])}, expected dict. "
          "Check flashrank release notes for breaking API changes."
      )
      assert "text" in results[0], (
          f"flashrank API changed — 'text' key missing from result dict. "
          f"Got keys: {list(results[0].keys())}"
      )


  def test_onnx_output_format():
      """Verify ONNX output[1] is ndarray with shape (n, 2) when zipmap=False."""
      import onnxruntime as ort
      from pathlib import Path

      onnx_path = Path(__file__).resolve().parent.parent / "models" / "exports" / "neonatalguard_v1.onnx"
      if not onnx_path.exists():
          pytest.skip(f"ONNX model not found: {onnx_path} — run export_onnx.py first")

      sess = ort.InferenceSession(str(onnx_path))
      dummy = np.random.randn(3, 10).astype("float32")
      out = sess.run(None, {"hrv_features": dummy})

      assert isinstance(out[1], np.ndarray), (
          f"ONNX output[1] type changed: {type(out[1])}. "
          "Expected ndarray. Was the model re-exported with zipmap=True?"
      )
      assert out[1].shape == (3, 2), (
          f"ONNX output[1] shape changed: {out[1].shape}. "
          "Expected (3, 2). Was the model re-exported with a different number of classes?"
      )
  ```

  **Change to `.github/workflows/eval.yml`** — insert a new step between `- name: Install dependencies` and `- name: Run agent eval (no-LLM, CI gate)`:

  ```yaml
        - name: Run dependency API contract tests
          run: pytest tests/test_dependency_apis.py -v
  ```

  The surrounding context for the insertion (to confirm the anchor):
  ```yaml
        - name: Install dependencies
          run: pip install -r requirements.txt

        - name: Run dependency API contract tests   # <-- INSERT THIS STEP
          run: pytest tests/test_dependency_apis.py -v

        - name: Run agent eval (no-LLM, CI gate)
  ```

  **What it does:** Creates `tests/` package with API contract tests. Adds a pytest step to CI so these tests run on every push before the agent eval.

  **Risks:**
  - FlashRank downloads model on first run in CI → mitigation: `cache_dir="/tmp/flashrank_cache"` plus HuggingFace cache in eval.yml already handles this.
  - YAML indentation error when inserting CI step → mitigation: VG-1 yaml.safe_load() check in verification catches this immediately.

  **Git Checkpoint:**
  ```bash
  git add tests/__init__.py tests/test_dependency_apis.py .github/workflows/eval.yml
  git commit -m "step 5: FIX-3 — create tests/test_dependency_apis.py; add pytest step to eval.yml CI"
  ```

  **Subtasks:**
  - [ ] 🟥 `tests/__init__.py` created (empty)
  - [ ] 🟥 `tests/test_dependency_apis.py` created with both test functions
  - [ ] 🟥 `eval.yml` updated with pytest step between "Install dependencies" and "Run agent eval"
  - [ ] 🟥 Verification passes

  **✓ Verification Test:**

  **Type:** Integration

  **Action:**
  ```bash
  # VG-1: Confirm eval.yml is valid YAML after edit
  python -c "
  import yaml
  yaml.safe_load(open('.github/workflows/eval.yml'))
  print('PASS VG-1: eval.yml is valid YAML')
  "

  # Run API contract tests
  python -m pytest tests/test_dependency_apis.py -v 2>&1
  ```

  **Expected:** `PASS VG-1: eval.yml is valid YAML` printed, then `test_flashrank_returns_dict_with_text_key PASSED` and `test_onnx_output_format PASSED`. `2 passed` in summary. Exit code 0.

  **Pass:** YAML check passes; `2 passed`, exit code 0.

  **Fail:**
  - `yaml.safe_load() raises` → indentation error in the new YAML step — re-read eval.yml and check the 6-space indentation of the new step matches surrounding steps.
  - `flashrank test FAILED — results[0] is not dict` → installed flashrank uses object API — check pinned version matches installed.
  - `onnx test SKIPPED` → ONNX file not found — run `src/models/export_onnx.py` first.
  - `onnx test FAILED — shape` → model re-exported with `zipmap=True` — re-export with `zipmap=False`.

---

- [ ] 🟥 **Step 6: FIX-5 — Baseline skew assertion in `runner.py`** — *Critical: catches lookback-window mismatch before Phase 5 specialist agents receive bad z-scores*

  **Idempotent:** Yes — the warning block is inserted once; re-running a second time would duplicate it, so the Pre-Read Gate must confirm absence before inserting.

  **Context:** `runner.py` re-derives `personal_baseline` from the last `_LOOKBACK=10` rows of `_features.csv`. The z-scores in `_windowed.csv` were computed by `run_nb04.py` with its own `LOOKBACK` constant. If these ever differ, z-scores in `PipelineResult` will be wrong but no error fires. FIX-5 recomputes each z-score at runtime and warns if stored vs recomputed values diverge by more than 0.5. Raises `RuntimeError` only when ALL features are skewed (structural bug).

  **Pre-Read Gate:**
  - Run `grep -n "skew_warnings\|FIX-5" src/pipeline/runner.py`. Must return 0 matches.
  - Run `grep -n "# ONNX inference" src/pipeline/runner.py`. Must return exactly 1 match.
  - Run `grep -n "personal_baseline = {" src/pipeline/runner.py`. Must return exactly 1 match.
  - **Confirm all four variable names are in scope at the insertion point** — the skew block references them by these exact names; a NameError will not be caught by the syntax-only verification:
    - Run `grep -n "\bz_scores\b" src/pipeline/runner.py`. Must return ≥ 1 match.
    - Run `grep -n "\bhrv_values\b" src/pipeline/runner.py`. Must return ≥ 1 match.
    - Run `grep -n "\bpersonal_baseline\b" src/pipeline/runner.py`. Must return ≥ 1 match.
    - Run `grep -n "self\._feature_cols\b" src/pipeline/runner.py`. Must return ≥ 1 match.
  - If any of the four greps above return 0 → the inserted block will raise NameError at runtime. STOP and resolve the name mismatch before inserting.

  **Self-Contained Rule:** All code below is complete and runnable.

  In `src/pipeline/runner.py`, insert the following block immediately **before** the line `# ONNX inference`. The block must be indented with 8 spaces (matching the surrounding method body — 4 spaces for class + 4 for method).

  ```python
          # FIX-5: Runtime skew check — warns if stored z-scores diverge from recomputed values.
          # Catches lookback-window mismatch between runner.py (_LOOKBACK) and run_nb04.py.
          import math as _math
          import logging as _log
          _skew_warnings: list[str] = []
          for _feat in self._feature_cols:
              if _feat not in z_scores or _feat not in personal_baseline:
                  continue
              _stored_z   = z_scores[_feat]
              _x          = hrv_values[_feat]
              _mean       = personal_baseline[_feat]["mean"]
              _std        = personal_baseline[_feat]["std"]
              _recomputed = (_x - _mean) / _std
              if not (_math.isfinite(_stored_z) and _math.isfinite(_recomputed)):
                  continue
              if abs(_recomputed - _stored_z) > 0.5:
                  _skew_warnings.append(
                      f"{_feat}: stored_z={_stored_z:.3f} recomputed={_recomputed:.3f} "
                      f"diff={abs(_recomputed - _stored_z):.3f}"
                  )
          if _skew_warnings:
              _log.warning(
                  "FIX-5 baseline skew detected for %s — runner.py and run_nb04.py "
                  "may be using different lookback windows:\n%s",
                  patient_id,
                  "\n".join(_skew_warnings),
              )
              if len(_skew_warnings) == len(self._feature_cols):
                  raise RuntimeError(
                      f"All features show baseline skew for {patient_id}. "
                      "Check _LOOKBACK in runner.py matches LOOKBACK in run_nb04.py."
                  )
  ```

  **What it does:** After z-scores and personal_baseline are fully populated, re-derives each z-score from raw HRV values and logs a warning for any stored vs recomputed difference > 0.5. Raises `RuntimeError` only when ALL features are skewed (structural constant mismatch).

  **Why this approach:** Warning (not error) on partial skew — a few features may legitimately differ due to floating-point precision in std computation. All-features skew always indicates a lookback constant mismatch.

  **Risks:**
  - False positive `RuntimeError` if all features skew on first window of a new patient with tiny baseline → investigate before dismissing; this threshold is intentionally strict.

  **Git Checkpoint:**
  ```bash
  git add src/pipeline/runner.py
  git commit -m "step 6: FIX-5 — add baseline skew runtime warning to runner.py"
  ```

  **Subtasks:**
  - [ ] 🟥 Pre-Read Gate: `# ONNX inference` anchor exists once, no `skew_warnings` present
  - [ ] 🟥 Skew block inserted immediately before `# ONNX inference` at 8-space indentation
  - [ ] 🟥 Both verification tests pass

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  python -c "
  src = open('src/pipeline/runner.py').read()
  assert 'FIX-5 baseline skew' in src, 'skew warning block not found'
  assert '_skew_warnings' in src, '_skew_warnings variable not found'
  print('PASS FIX-5 text: skew warning block present in runner.py')
  "
  python -c "
  import sys; sys.path.insert(0, '.')
  import src.pipeline.runner
  print('PASS FIX-5 syntax: runner.py imports cleanly — no IndentationError or SyntaxError')
  "
  ```

  **Expected:** Both PASS lines printed. Exit code 0.

  **Pass:** Text check and import check both succeed.

  **Fail:**
  - `skew warning block not found` → block not inserted — check anchor and indentation.
  - `IndentationError` or `SyntaxError` on import → inserted block has wrong indentation — confirm 8 spaces match surrounding `run()` method body.

---

## Phase 3 — Eval Suite Expansion

**Goal:** 6 hard mixed-signal scenarios are added (total 30). `eval_agent.py` tracks `fnr_hard` separately. CI PR comment displays `fnr_hard`. All three metrics are part of the generalist baseline.

---

- [ ] 🟥 **Step 7: FIX-4 — Add 6 hard scenarios to `eval/scenarios.py`** — *Important: without hard scenarios the Phase 5 improvement delta is unmeasurable on mixed-signal cases*

  **Idempotent:** Yes — appending to the `SCENARIOS` list and updating assert lines.

  **Context:** Current `scenarios.py` has 24 clean scenarios. The project plan adds 6 hard scenarios (2 per class) with mixed/contradictory signals. The count assertions must change from `== 24 / == 8` to `== 30 / == 10`.

  **Pre-Read Gate:**
  - Run `grep -n "assert len(SCENARIOS)" eval/scenarios.py`. Must return exactly 1 match with `== 24`.
  - Run `grep -n "assert sum" eval/scenarios.py`. Must return exactly 3 matches, all `== 8`.
  - Run `grep -n "EVAL-HARD" eval/scenarios.py`. Must return 0 matches.

  **Self-Contained Rule:** All code below is complete and runnable.

  In `eval/scenarios.py`, replace the assertion block at the end of the file:

  ```python
  assert len(SCENARIOS) == 24, f"Expected 24 scenarios, got {len(SCENARIOS)}"
  assert sum(1 for s in SCENARIOS if s.expected == "RED")    == 8
  assert sum(1 for s in SCENARIOS if s.expected == "YELLOW") == 8
  assert sum(1 for s in SCENARIOS if s.expected == "GREEN")  == 8
  ```

  With:

  ```python
  # fmt: off
  SCENARIOS += [
      # HARD scenarios (6) — mixed/contradictory signals, 2 per class.
      # RED hard: risk_score > 0.70 so rule-based path returns RED in --no-llm mode.
      Scenario("EVAL-HARD-RED-001", 0.75,
               {"rmssd": -2.8, "lf_hf_ratio": +0.3, "pnn50": -2.5, "sdnn": -2.2},
               0, "RED",
               "RED — RMSSD+SDNN+pNN50 suppressed but LF/HF normal. No brady events."),
      Scenario("EVAL-HARD-RED-002", 0.71,
               {"rmssd": -1.2, "lf_hf_ratio": +3.1, "pnn50": -0.8, "sdnn": -0.6},
               4, "RED",
               "RED — dominant LF/HF shift with brady events, mild RMSSD change"),
      # YELLOW hard: risk_score 0.41–0.69
      Scenario("EVAL-HARD-YEL-001", 0.55,
               {"rmssd": -2.1, "lf_hf_ratio": -0.4, "pnn50": -1.9, "sdnn": +0.3},
               0, "YELLOW",
               "YELLOW — RMSSD+pNN50 declining but LF/HF improving. Contradictory."),
      Scenario("EVAL-HARD-YEL-002", 0.48,
               {"rmssd": +0.2, "lf_hf_ratio": +2.4, "pnn50": +0.1, "sdnn": -0.3},
               3, "YELLOW",
               "YELLOW — isolated LF/HF elevation with brady, other HRV features normal"),
      # GREEN hard: risk_score < 0.40
      Scenario("EVAL-HARD-GRN-001", 0.35,
               {"rmssd": -1.8, "lf_hf_ratio": +1.5, "pnn50": -1.6, "sdnn": -1.4},
               0, "GREEN",
               "GREEN — looks like YELLOW but risk_score low. Tests against false positives."),
      Scenario("EVAL-HARD-GRN-002", 0.28,
               {"rmssd": -0.9, "lf_hf_ratio": +0.8, "pnn50": +1.2, "sdnn": -0.7},
               1, "GREEN",
               "GREEN — mixed directions, single brady, low overall risk"),
  ]
  # fmt: on

  assert len(SCENARIOS) == 30, f"Expected 30 scenarios, got {len(SCENARIOS)}"
  assert sum(1 for s in SCENARIOS if s.expected == "RED")    == 10
  assert sum(1 for s in SCENARIOS if s.expected == "YELLOW") == 10
  assert sum(1 for s in SCENARIOS if s.expected == "GREEN")  == 10
  ```

  **What it does:** Appends 6 HARD scenarios to the existing 24-item list. Updates the module-level count assertions from 24/8 to 30/10.

  **Why this approach:** Appending (not replacing) preserves existing scenario IDs and their order — any prior result files referencing scenario indices remain interpretable.

  **Risks:**
  - Assertion `== 30` fires if a previous partial edit left stale content → Pre-Read Gate confirms 0 `EVAL-HARD` matches before this step.

  **Git Checkpoint:**
  ```bash
  git add eval/scenarios.py
  git commit -m "step 7: FIX-4 — add 6 hard mixed-signal scenarios to eval suite (24→30)"
  ```

  **Subtasks:**
  - [ ] 🟥 Pre-Read Gate: 0 `EVAL-HARD` matches, assertions at `== 24 / == 8`
  - [ ] 🟥 6 HARD scenarios appended
  - [ ] 🟥 Assertions updated to `== 30 / == 10`
  - [ ] 🟥 Verification passes

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  python -c "
  import sys; sys.path.insert(0, '.')
  from eval.scenarios import SCENARIOS
  hard = [s for s in SCENARIOS if 'HARD' in s.patient_id]
  print('Total scenarios:', len(SCENARIOS))
  print('Hard scenarios:', len(hard))
  assert len(SCENARIOS) == 30, f'Expected 30, got {len(SCENARIOS)}'
  assert len(hard) == 6, f'Expected 6 hard, got {len(hard)}'
  print('PASS FIX-4: 30 scenarios (6 hard)')
  "
  ```

  **Expected:** `Total scenarios: 30`, `Hard scenarios: 6`, `PASS FIX-4`. Exit code 0.

  **Fail:**
  - `AssertionError: Expected 30` → hard scenarios not appended or assertion not updated.
  - `ImportError` → syntax error in added Scenario block — check for missing comma in constructor call.

---

- [ ] 🟥 **Step 8: FIX-4 — Add `fnr_hard` tracking to `eval/eval_agent.py`** — *Important: hard-scenario FNR must be tracked separately to measure Phase 5 improvement*

  **Idempotent:** Yes — adding new computation and new key to return dict.

  **Context:** `run_eval()` currently computes overall `fnr_red` but not hard-scenario FNR. Adding `fnr_hard` (FNR on RED hard scenarios only) provides the specific metric Phase 5 specialist agents are expected to improve.

  **Pre-Read Gate:**
  - Run `grep -n "fnr_hard" eval/eval_agent.py`. Must return 0 matches.
  - Run `grep -n "fnr.*missed.*n_red\|n_red.*missed.*fnr" eval/eval_agent.py`. Look for the FNR computation block.
  - Run `grep -n '"fnr_red"' eval/eval_agent.py`. Must return exactly 1 match in the return dict.

  **Self-Contained Rule:** All code below is complete and runnable.

  **Change 1 — docstring update in `run_eval()`:**

  Replace:
  ```python
  def run_eval(run_agent) -> dict:
      """Run all 24 scenarios and collect predictions + latencies."""
  ```
  With:
  ```python
  def run_eval(run_agent) -> dict:
      """Run all 30 scenarios and collect predictions + latencies."""
  ```

  **Change 2 — add `fnr_hard` computation after the existing `fnr` block:**

  Replace:
  ```python
      # FNR (RED): missed RED / total RED
      n_red  = sum(1 for t in y_true if t == "RED")
      missed = sum(1 for t, p in zip(y_true, y_pred) if t == "RED" and p != "RED")
      fnr    = missed / n_red if n_red > 0 else 0.0
  ```
  With:
  ```python
      # FNR (RED): missed RED / total RED
      n_red  = sum(1 for t in y_true if t == "RED")
      missed = sum(1 for t, p in zip(y_true, y_pred) if t == "RED" and p != "RED")
      fnr    = missed / n_red if n_red > 0 else 0.0

      # FNR (RED, hard scenarios only) — Phase 5 improvement target
      hard_pairs      = [(t, p) for s, t, p in zip(SCENARIOS, y_true, y_pred) if "HARD" in s.patient_id]
      n_hard_red      = sum(1 for t, _ in hard_pairs if t == "RED")
      missed_hard_red = sum(1 for t, p in hard_pairs if t == "RED" and p != "RED")
      fnr_hard        = missed_hard_red / n_hard_red if n_hard_red > 0 else 0.0
  ```

  **Change 3 — add `fnr_hard` to the return dict:**

  Replace:
  ```python
      return {
          "n_scenarios":         len(SCENARIOS),
          "n_correct":           n_correct,
          "f1":                  f1,
          "fnr_red":             fnr,
          "protocol_compliance": protocol,
          "latency_p50_ms":      p50,
          "latency_p95_ms":      p95,
          "no_llm_mode":         os.getenv("EVAL_NO_LLM", "") in {"1", "true", "yes"},
          "y_true":              y_true,
          "y_pred":              y_pred,
      }
  ```
  With:
  ```python
      return {
          "n_scenarios":         len(SCENARIOS),
          "n_correct":           n_correct,
          "f1":                  f1,
          "fnr_red":             fnr,
          "fnr_hard":            fnr_hard,
          "protocol_compliance": protocol,
          "latency_p50_ms":      p50,
          "latency_p95_ms":      p95,
          "no_llm_mode":         os.getenv("EVAL_NO_LLM", "") in {"1", "true", "yes"},
          "y_true":              y_true,
          "y_pred":              y_pred,
      }
  ```

  **What it does:** Adds `fnr_hard` — the false negative rate on RED scenarios with `"HARD"` in their `patient_id`. In `--no-llm` mode this will be 0.000 (hard-RED scenarios have `risk_score > 0.70`, so rule-based path returns RED). In live-LLM mode this is the generalist baseline for Phase 5.

  **Risks:**
  - `SCENARIOS` not available inside `run_eval()` → `SCENARIOS` is a module-level import on line 37; it is always in scope.

  **Git Checkpoint:**
  ```bash
  git add eval/eval_agent.py
  git commit -m "step 8: FIX-4 — add fnr_hard tracking for hard RED scenarios in eval_agent.py"
  ```

  **Subtasks:**
  - [ ] 🟥 Docstring updated from 24 to 30
  - [ ] 🟥 `fnr_hard` computation block added after `fnr` computation
  - [ ] 🟥 `fnr_hard` key added to return dict
  - [ ] 🟥 Verification passes

  **✓ Verification Test:**

  **Type:** Integration

  **Action:**
  ```bash
  python -c "
  import sys, os
  sys.path.insert(0, '.')
  os.environ['EVAL_NO_LLM'] = '1'
  from eval.eval_agent import run_eval
  from src.agent.graph import agent
  results = run_eval(agent)
  assert 'fnr_hard' in results, 'fnr_hard key missing from results dict'
  assert results['n_scenarios'] == 30, f'Expected 30 scenarios, got {results[\"n_scenarios\"]}'
  print(f'PASS FIX-4 eval_agent: fnr_hard={results[\"fnr_hard\"]:.3f}, n={results[\"n_scenarios\"]}')
  "
  ```

  **Expected:** `PASS FIX-4 eval_agent: fnr_hard=0.000, n=30`. Exit code 0.

  **Pass:** `fnr_hard` key present, `n_scenarios == 30`, `fnr_hard == 0.000` in no-LLM mode.

  **Fail:**
  - `fnr_hard key missing` → Change 3 not applied — check return dict.
  - `n_scenarios == 24` → Step 7 not complete.

---

- [ ] 🟥 **Step 9: Update `eval.yml` PR comment to include `fnr_hard`** — *Non-critical: makes hard-scenario regression visible on every PR*

  **Idempotent:** Yes — replacing a string literal in YAML.

  **Pre-Read Gate:**
  - Run `grep -n "fnr_hard" .github/workflows/eval.yml`. Must return 0 matches.
  - Run `grep -n "fnr_red" .github/workflows/eval.yml`. Must return exactly 1 match inside the `body:` block.

  In `.github/workflows/eval.yml`, replace:
  ```yaml
              body: [
                '## NeonatalGuard Eval (no-LLM)',
                `F1: ${r.f1.toFixed(3)} | FNR(RED): ${r.fnr_red.toFixed(3)} | Protocol: ${(r.protocol_compliance*100).toFixed(1)}%`,
                `Correct: ${r.n_correct}/${r.n_scenarios} | Latency p50: ${Math.round(r.latency_p50_ms)}ms`
              ].join('\n')
  ```
  With:
  ```yaml
              body: [
                '## NeonatalGuard Eval (no-LLM)',
                `F1: ${r.f1.toFixed(3)} | FNR(RED): ${r.fnr_red.toFixed(3)} | Protocol: ${(r.protocol_compliance*100).toFixed(1)}%`,
                `Hard-scenario FNR: ${(r.fnr_hard ?? 0).toFixed(3)} | Correct: ${r.n_correct}/${r.n_scenarios} | Latency p50: ${Math.round(r.latency_p50_ms)}ms`
              ].join('\n')
  ```

  **Git Checkpoint:**
  ```bash
  git add .github/workflows/eval.yml
  git commit -m "step 9: FIX-4 — add fnr_hard to eval.yml CI PR comment"
  ```

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  grep -n "fnr_hard" .github/workflows/eval.yml
  ```

  **Expected:** Exactly 1 match showing `fnr_hard` in the PR comment body.

  **Pass:** 1 match returned. Exit code 0.

  **Fail:**
  - 0 matches → replacement not applied — re-read the YAML block and check quote style.

---

## Phase 4 — Baseline Documentation

**Goal:** Both eval results (no-LLM + live-LLM, 30 scenarios each) are recorded in `BENCHMARKS.md`. Phase 5 has concrete targets to beat.

---

- [ ] 🟥 **Step 10: Re-run all evals with 30 scenarios** — *Critical: existing results/ reflect 24-scenario runs; Phase 5 comparison requires 30-scenario baseline*

  **Idempotent:** Yes — overwrites result JSON files with new values.

  **Pre-Read Gate:**
  - Run `python -c "from eval.scenarios import SCENARIOS; print(len(SCENARIOS))"`. Must print `30`. If `24` → Step 7 not complete.
  - Run `python -c "import json; r=json.load(open('results/eval_agent.json')); print(r['n_scenarios'])"`. Must print `24` (old run) — confirms re-run is needed.
  - **Confirm CLI flags exist in eval_agent.py:** Run `grep -n "fail-below-f1\|fail-above-fnr" eval/eval_agent.py`. Must return ≥ 1 match for each flag. If either returns 0 → the `--fail-below-f1` / `--fail-above-fnr` arguments are not registered in the argparse setup; the run command will exit immediately with an argparse error. STOP and add the flags before running.

  **Run no-LLM eval (blocks until < threshold → CI gate):**
  ```bash
  QDRANT_PATH=qdrant_local python eval/eval_agent.py \
      --no-llm \
      --fail-below-f1 0.80 \
      --fail-above-fnr 0.0 \
      --output results/eval_agent.json
  ```

  **Run live-LLM eval (requires `GROQ_API_KEY` in `.env`):**
  ```bash
  QDRANT_PATH=qdrant_local python eval/eval_agent.py \
      --output results/eval_agent_live.json
  ```

  **Run retrieval eval:**
  ```bash
  QDRANT_PATH=qdrant_local python eval/eval_retrieval.py
  ```

  **What it does:** Regenerates all three result JSON files using the 30-scenario suite.

  **Risks:**
  - Live-LLM run rate-limited → re-run; each scenario is independent.
  - `GROQ_API_KEY` missing → run no-LLM only for CI gate; live-LLM is required for BENCHMARKS.md generalist baseline.

  **Git Checkpoint:**
  ```bash
  git add results/eval_agent.json results/eval_agent_live.json results/eval_retrieval.json
  git commit -m "step 10: re-run all evals on 30-scenario suite; update results/"
  ```

  **Subtasks:**
  - [ ] 🟥 Confirm `len(SCENARIOS) == 30` before running
  - [ ] 🟥 No-LLM eval completes with F1 ≥ 0.80 and FNR(RED) = 0.000
  - [ ] 🟥 Live-LLM eval completes and produces updated `eval_agent_live.json`
  - [ ] 🟥 Retrieval eval completes and produces updated `eval_retrieval.json`

  **✓ Verification Test:**

  **Type:** Integration

  **Action:**
  ```bash
  python -c "
  import json
  r = json.load(open('results/eval_agent.json'))
  assert r['n_scenarios'] == 30, f'Expected 30, got {r[\"n_scenarios\"]}'
  assert r['fnr_red'] == 0.0,    f'FNR(RED) must be 0.000, got {r[\"fnr_red\"]}'
  assert r['f1'] >= 0.80,        f'F1 must be >= 0.80, got {r[\"f1\"]}'
  assert 'fnr_hard' in r,        'fnr_hard key missing — check Step 8'
  print(f'PASS no-LLM: n={r[\"n_scenarios\"]} F1={r[\"f1\"]:.3f} FNR(RED)={r[\"fnr_red\"]:.3f} FNR(hard)={r[\"fnr_hard\"]:.3f}')
  r2 = json.load(open('results/eval_agent_live.json'))
  assert r2['n_scenarios'] == 30, f'Live n_scenarios expected 30, got {r2[\"n_scenarios\"]}'
  print(f'PASS live-LLM: n={r2[\"n_scenarios\"]} F1={r2[\"f1\"]:.3f} FNR(RED)={r2[\"fnr_red\"]:.3f}')
  "
  ```

  **Expected:** Both PASS lines printed; no-LLM FNR(RED)=0.000 and F1≥0.80.

  **Fail:**
  - `n_scenarios == 24` in results → Step 7 incomplete or evals not re-run.
  - `fnr_hard key missing` → Step 8 incomplete.
  - `F1 < 0.80` in no-LLM mode → rule-based path broken — check `llm_reasoning_node` in graph.py.

---

- [ ] 🟥 **Step 11: Write `BENCHMARKS.md`** — *Critical: Phase 5 cannot be evaluated without documented generalist baseline numbers*

  **Idempotent:** Yes — creating a new file; safe to overwrite.

  **Pre-Read Gate:**
  - Run `ls BENCHMARKS.md 2>&1`. Must return `ls: BENCHMARKS.md: No such file or directory`.
  - Run `python -c "import json; r=json.load(open('results/eval_agent_live.json')); print(r['n_scenarios'])"`. Must print `30` (confirming Step 10 is done).

  **Agent instruction:** Extract actual values from result files first, then write BENCHMARKS.md. Do NOT write placeholder text or `____` into the file.

  Run to extract values:
  ```bash
  python -c "
  import json
  nollm = json.load(open('results/eval_agent.json'))
  live  = json.load(open('results/eval_agent_live.json'))
  ret   = json.load(open('results/eval_retrieval.json'))
  print('no_llm  n:', nollm['n_scenarios'], 'F1:', round(nollm['f1'],3), 'FNR:', round(nollm['fnr_red'],3), 'FNR_hard:', round(nollm.get('fnr_hard',0),3), 'protocol:', round(nollm['protocol_compliance'],3))
  print('live    n:', live['n_scenarios'],  'F1:', round(live['f1'],3),  'FNR:', round(live['fnr_red'],3),  'FNR_hard:', round(live.get('fnr_hard',0),3),  'protocol:', round(live['protocol_compliance'],3))
  print('mrr_vector:', round(ret['mrr_vector'],3))
  print('mrr_hybrid:', round(ret['mrr_hybrid'],3))
  print('mrr_delta:', round(ret['mrr_delta'],3), '(must be >= 0.05 to claim hybrid advantage)')
  print('recall_at3_vector:', round(ret['recall_at3_vector'],3))
  print('recall_at3_hybrid:', round(ret['recall_at3_hybrid'],3))
  "
  ```

  Then create `BENCHMARKS.md` substituting ALL values from the command output above:

  ```markdown
  # NeonatalGuard — Generalist Baseline Benchmarks

  *Phase 4 baseline — recorded 2026-03-21.*
  *Phase 5 multi-agent results will be added as a new section below.*
  *Hard-scenario FNR is the primary Phase 5 improvement target.*

  ---

  ## Eval Suite: 30 Scenarios (24 clean + 6 hard mixed-signal)

  | Metric | No-LLM (rule-based) | Live LLM (Groq generalist) |
  |--------|---------------------|---------------------------|
  | F1 (macro) | [VALUE] | [VALUE] |
  | FNR (RED) | [VALUE] | [VALUE] |
  | FNR (RED, hard scenarios only) | [VALUE] | [VALUE] |
  | Protocol compliance | [VALUE] | [VALUE] |
  | Scenarios run | [VALUE] | [VALUE] |

  ## RAG Retrieval

  | Metric | Vector-only | Hybrid + Rerank | Delta |
  |--------|-------------|-----------------|-------|
  | MRR@3 | [VALUE] | [VALUE] | [VALUE] |
  | Recall@3 | [VALUE] | [VALUE] | — |

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
  2. Hard-scenario FNR(RED) ≤ Phase 4 live-LLM value
  3. Overall F1 (live LLM) > Phase 4 live-LLM value
  ```

  **Git Checkpoint:**
  ```bash
  git add BENCHMARKS.md
  git commit -m "step 11: write BENCHMARKS.md with Phase 4 generalist baseline (30 scenarios)"
  ```

  **Subtasks:**
  - [ ] 🟥 Values extracted from result JSON files (no invented numbers)
  - [ ] 🟥 BENCHMARKS.md written with actual values (no `____` or `[VALUE]` remaining)
  - [ ] 🟥 Verification passes

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  python -c "
  import json
  from pathlib import Path
  bm = Path('BENCHMARKS.md').read_text()
  assert '[VALUE]' not in bm, 'BENCHMARKS.md contains unfilled [VALUE] placeholders'
  assert '____'   not in bm, 'BENCHMARKS.md contains ____ placeholders'
  live = json.load(open('results/eval_agent_live.json'))
  f1_str = f'{live[\"f1\"]:.3f}'
  assert f1_str in bm, f'Live F1 value {f1_str} not found in BENCHMARKS.md — was the file written before Step 10?'
  print('PASS: BENCHMARKS.md written with actual values. Live F1', f1_str, 'present.')
  "
  ```

  **Expected:** `PASS: BENCHMARKS.md written with actual values.` Exit code 0.

  **Pass:** No placeholders; actual live-LLM F1 value found in file.

  **Fail:**
  - `[VALUE] placeholder found` → agent wrote template instead of actual values — re-extract values and rewrite.
  - `Live F1 value not found` → BENCHMARKS.md written before Step 10 completed — rerun Step 10 first then rewrite.

---

## Regression Guard

**Systems at risk from this plan:**
- `EpisodicMemory.save()` — new optional kwargs; existing callers with 3 positional args must still work.
- `eval_agent.py` return dict — gains `fnr_hard`; CI PR comment uses `?? 0` fallback to tolerate old results.

**Regression verification:**

| System | Pre-change behaviour | Post-change verification |
|--------|---------------------|--------------------------|
| `EpisodicMemory.save()` existing callers | Called with 3 positional args | `grep -rn "EpisodicMemory().save(" src/` — all existing call sites pass; new kwargs are optional |
| `eval_agent.py` result schema | Original 9 keys | `results/eval_agent.json` must contain all original keys plus new `fnr_hard` |
| CI no-LLM gate | F1 ≥ 0.80, FNR ≤ 0.000 | Same gate passes on 30 scenarios — hard-RED has risk_score > 0.70 so rule-based path always returns RED |

---

## Rollback Procedure

```bash
# Rollback in reverse step order (each revert is one commit)
git revert HEAD  # Step 11: remove BENCHMARKS.md
git revert HEAD  # Step 10: restore 24-scenario results/
git revert HEAD  # Step 9: revert eval.yml fnr_hard PR comment
git revert HEAD  # Step 8: revert eval_agent.py fnr_hard
git revert HEAD  # Step 7: revert scenarios.py 24→30
git revert HEAD  # Step 6: revert FIX-5 runner.py skew block
git revert HEAD  # Step 5: revert tests/ and eval.yml dep test step
git revert HEAD  # Step 4b: revert requirements.txt pins
git revert HEAD  # Step 3: revert FIX-2 Phase B memory.py + graph.py
git revert HEAD  # Step 2a: revert FIX-2 Phase A memory.py schema
git revert HEAD  # Step 1: revert FIX-1 train_classifier.py

# Confirm pre-plan state:
python -c "from eval.scenarios import SCENARIOS; print(len(SCENARIOS))"  # must be 24
grep "assert actual_cols" src/models/train_classifier.py                  # must be empty
grep "z_scores_json" src/agent/memory.py                                  # must be empty
grep "skew_warnings" src/pipeline/runner.py                               # must be empty
```

---

## Pre-Flight Checklist

| Phase | Check | How to Confirm | Status |
|-------|-------|----------------|--------|
| **Pre-flight** | All pre-flight commands run | Baseline snapshot captured | ⬜ |
| | No hardening assertions already present | All 5 grep commands return 0 matches | ⬜ |
| **Phase 1** | train_classifier.py anchor exists once | `grep -c "X_train = train_df" src/models/train_classifier.py` = 1 | ⬜ |
| | memory.py `_init_schema` exists once | grep returns 1 match | ⬜ |
| | Phase A db migration verified before Step 3 | PRAGMA table_info confirms both columns | ⬜ |
| **Phase 2** | pip show run (7 packages incl. pytest) | Human confirmed version strings | ⬜ |
| | tests/ does not exist | ls returns error | ⬜ |
| | pytest pinned in requirements.txt | Step 4B complete before Step 5 | ⬜ |
| | runner.py `# ONNX inference` anchor exists once | grep returns 1 match | ⬜ |
| **Phase 3** | 0 `EVAL-HARD` matches in scenarios.py | grep returns 0 | ⬜ |
| | 0 `fnr_hard` matches in eval_agent.py | grep returns 0 | ⬜ |
| **Phase 4** | BENCHMARKS.md does not exist | ls returns error | ⬜ |
| | Step 10 done before Step 11 | results/eval_agent.json has n_scenarios=30 | ⬜ |

---

## Risk Heatmap

| Step | Risk Level | What Could Go Wrong | Early Detection | Idempotent |
|------|-----------|---------------------|-----------------|------------|
| Step 1 (FIX-1) | 🟢 Low | Assertion fires if CSV order already wrong | Verification command fails with ORDER MISMATCH | Yes |
| Step 2 (FIX-2A) | 🟡 Medium | ALTER TABLE swallows non-duplicate errors silently | Run PRAGMA table_info immediately after to confirm columns | Yes |
| Step 3 (FIX-2B) | 🟡 Medium | Phase A skipped — INSERT fails with missing column | Run Phase A verification before Phase B | Yes |
| Step 4 Phase B | 🟡 Medium | Wrong version pinned (human error) | pip install -r requirements.txt will fail if version unavailable | Yes |
| Step 5 (dep API tests) | 🟡 Medium | YAML indentation error breaks CI workflow; flashrank model download slow in CI | VG-1 yaml.safe_load check catches YAML errors; HF cache covers downloads | Yes |
| Step 6 (FIX-5) | 🟢 Low | Skew warning fires for legitimate float noise | RuntimeError only on all-features skew | Yes |
| Step 7 (hard scenarios) | 🟢 Low | Scenario constructor typo | Import-time assert fires on syntax error | Yes |
| Step 8 (fnr_hard) | 🟢 Low | SCENARIOS not in scope inside run_eval | SCENARIOS is module-level import | Yes |
| Step 9 (eval.yml) | 🟢 Low | fnr_hard undefined if old results loaded | `?? 0` fallback in JS handles missing key | Yes |
| Step 10 (re-run evals) | 🟡 Medium | Live LLM rate-limited or API key missing | Run no-LLM first; live-LLM is best-effort | Yes |
| Step 11 (BENCHMARKS.md) | 🟢 Low | Placeholder values written | Verification checks for actual F1 value from JSON | Yes |

---

## Success Criteria

| Metric | Target | Verification |
|--------|--------|--------------|
| FIX-1 present | Assertion in `train_classifier.py` before `clf.fit()` | `grep "assert actual_cols" src/models/train_classifier.py` → 1 match |
| FIX-2 active | `z_scores_json` + `hrv_values_json` in alert_history | Run one agent invocation → PRAGMA table_info shows both columns populated |
| FIX-3 deps pinned | 7 packages use `==` in requirements.txt (incl. pytest) | `grep ">=" requirements.txt` → 0 matches for the 7 target packages; `grep "^pytest==" requirements.txt` → 1 match |
| FIX-3 API tests pass | `pytest tests/test_dependency_apis.py` | `2 passed` in output, exit code 0 |
| FIX-5 present | Skew block in `runner.py` | `grep "FIX-5 baseline skew" src/pipeline/runner.py` → 1 match |
| Scenario count | 30 (24 clean + 6 hard) | `from eval.scenarios import SCENARIOS; print(len(SCENARIOS))` → `30` |
| No-LLM FNR(RED) | 0.000 | `results/eval_agent.json` → `fnr_red: 0.0` |
| No-LLM F1 | ≥ 0.80 | `results/eval_agent.json` → `f1 ≥ 0.80` |
| `fnr_hard` key | Present in both result JSONs | `json.load(open('results/eval_agent.json'))['fnr_hard']` → no KeyError |
| BENCHMARKS.md | Written with actual live-LLM values | Live F1 from `eval_agent_live.json` found verbatim in BENCHMARKS.md |

---

⚠️ **Do not mark a step 🟩 Done until its verification test passes.**
⚠️ **Do not proceed past a Human Gate without explicit human input.**
⚠️ **If blocked, mark 🟨 In Progress and output the State Manifest before stopping.**
⚠️ **Do not batch multiple steps into one git commit.**
⚠️ **If idempotent = No, confirm the step has not already run before executing.**
