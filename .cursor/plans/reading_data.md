# Neonatal Sepsis — Feature Engineering Foundation Plan

**Overall Progress:** `0%` — 0/4 steps complete

---

## TLDR

Steal `get_serie_describe()` from acampillos/sepsis-prediction and adapt it into `src/features/hrv.py` as the core feature encoding function for the neonatal pipeline. This function takes a window of RR intervals and returns a flat dictionary of statistical features (mean, std, min, max, quantiles) — the direct input to the XGBoost feature matrix in notebook 03. After this plan executes, `src/features/hrv.py` exists with one working, tested function ready to be called from notebook 03.

---

## Critical Decisions

- **Decision 1:** Place function in `src/features/hrv.py` not `util.py` — HRV feature encoding belongs in the features module, not a generic utility file.
- **Decision 2:** Replace `icustay_id` with `record_name` — PICS uses infant record names, not ICU stay IDs.
- **Decision 3:** Input is a 1D numpy array of RR intervals, not a full DataFrame — simpler interface, matches output of notebook 02.

---

## Agent Failure Protocol

1. A verification command fails → read the full error output.
2. Cause is unambiguous → make ONE targeted fix → re-run the same verification command.
3. If still failing after one fix → **STOP**. Before stopping, output the full current contents of every file modified in this step. Report: (a) command run, (b) full error verbatim, (c) fix attempted, (d) current state of each modified file, (e) why you cannot proceed.
4. Never attempt a second fix without human instruction.
5. Never modify files not named in the current step.

---

## Clarification Gate

| Unknown | Required | Source | Blocking | Resolved |
|---------|----------|--------|----------|----------|
| Does `src/features/hrv.py` already exist? | Confirm file exists or is empty | `ls src/features/` in terminal | Step 1 | ⬜ |
| Does `src/features/__init__.py` exist? | Confirm package is importable | `ls src/features/` | Step 2 | ⬜ |

---

## Pre-Flight — Run Before Any Code Changes

```bash
# 1. Confirm src/features/ exists
ls ~/Neonatal/src/features/

# 2. Check if hrv.py already has content
cat ~/Neonatal/src/features/hrv.py 2>/dev/null || echo "FILE DOES NOT EXIST"

# 3. Confirm processed RR CSVs exist from notebook 02
ls ~/Neonatal/data/processed/ | head -5

# 4. Confirm pandas is importable in venv
python3 -c "import pandas as pd; print('pandas OK')"
```

**Baseline Snapshot (agent fills during pre-flight):**
```
src/features/hrv.py exists:     ____  (yes/no)
src/features/__init__.py exists: ____  (yes/no)
data/processed/ CSV count:       ____  (expected: 10)
pandas importable:               ____  (expected: OK)
```

**Automated checks — all must pass before Step 1:**
- [ ] `ls src/features/` returns directory listing without error
- [ ] `python3 -c "import pandas as pd"` returns no error
- [ ] `ls data/processed/*.csv | wc -l` returns 10

---

## Tasks

### Phase 1 — Create `src/features/hrv.py` with `get_serie_describe`

**Goal:** `src/features/hrv.py` exists, contains `get_serie_describe()`, and is importable from notebooks.

---

- [ ] 🟥 **Step 1: Create `src/features/__init__.py` if missing** — *Non-critical: package marker only*

  **Idempotent:** Yes — creating an empty file twice is safe.

  ```bash
  touch ~/Neonatal/src/__init__.py
  touch ~/Neonatal/src/features/__init__.py
  ```

  **What it does:** Makes `src` and `src/features` importable Python packages.

  **Why this approach:** Without `__init__.py`, `from src.features.hrv import get_serie_describe` fails with ModuleNotFoundError.

  **Git Checkpoint:**
  ```bash
  cd ~/Neonatal
  git add src/__init__.py src/features/__init__.py
  git commit -m "step 1: add __init__.py to make src.features importable"
  ```

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  python3 -c "import sys; sys.path.insert(0, '.'); from src.features import hrv; print('import OK')" 2>&1 || echo "EXPECTED: may fail until step 2 creates hrv.py"
  ls ~/Neonatal/src/features/__init__.py
  ```

  **Expected:** `__init__.py` file exists at `src/features/__init__.py`

  **Observe:** Terminal output of `ls`

  **Pass:** File listed, no error

  **Fail:**
  - If `No such file or directory` → `touch` command failed → check directory exists with `ls src/`

---

- [ ] 🟥 **Step 2: Create `src/features/hrv.py` with `get_serie_describe`** — *Critical: notebook 03 depends on this function*

  **Idempotent:** Yes — file overwrite produces identical output.

  **Context:** This is the core feature encoding function. It takes a 1D numpy array of RR intervals, wraps it in a DataFrame, calls `.describe()`, and returns a flat dictionary of stats. Every window in the feature matrix is produced by this function. If the output keys change, the feature matrix schema breaks.

  **Pre-Read Gate:**
  ```bash
  # Confirm file does not already exist with conflicting content
  cat ~/Neonatal/src/features/hrv.py 2>/dev/null || echo "FILE DOES NOT EXIST — safe to create"
  ```
  If file exists with content → read it fully before proceeding. Do not overwrite without checking.

  **Self-Contained Rule:** Code block below is complete and runnable as written.

  **No-Placeholder Rule:** No `<VALUE>` tokens present.

  ```python
  # src/features/hrv.py
  import pandas as pd
  import numpy as np


  def get_serie_describe(rr_intervals):
      """
      Takes a 1D numpy array of RR intervals (ms) and returns a flat dictionary
      of statistical features: mean, std, min, max, 25th, 50th, 75th percentile.

      Adapted from acampillos/sepsis-prediction preprocessing/util.py.
      Modified to accept numpy array input instead of DataFrame,
      and to use record_name instead of icustay_id.

      Parameters
      ----------
      rr_intervals : np.array
          1D array of RR intervals in milliseconds

      Returns
      -------
      dict
          Flat dictionary of statistical features keyed as 'rr_ms_mean',
          'rr_ms_std', 'rr_ms_min', 'rr_ms_max', 'rr_ms_25%', 'rr_ms_50%', 'rr_ms_75%'
      """
      serie = pd.DataFrame({'rr_ms': rr_intervals})
      serie_describe = serie.describe().transpose().drop(columns=['count'])

      values = dict()
      for index, row in serie_describe.iterrows():
          for col in row.index:
              values[f'{index}_{col}'] = row[col]
      return values


  def get_window_features(rr_intervals, record_name, window_idx):
      """
      Wraps get_serie_describe with record metadata for building feature matrix rows.

      Parameters
      ----------
      rr_intervals : np.array
          1D array of RR intervals in milliseconds for this window
      record_name : str
          Infant record identifier (e.g. 'infant1')
      window_idx : int
          Index of the window within the recording

      Returns
      -------
      dict
          Feature dictionary with record metadata + statistical features
      """
      features = get_serie_describe(rr_intervals)
      features['record_name'] = record_name
      features['window_idx'] = window_idx
      return features
  ```

  **What it does:** Defines two functions — `get_serie_describe` encodes a window of RR intervals as statistical features; `get_window_features` wraps it with record metadata for building the feature matrix DataFrame.

  **Why this approach:** `.describe()` produces 7 statistics in one call (mean, std, min, 25%, 50%, 75%, max). Flat dictionary output maps directly to a DataFrame row — one row per window.

  **Assumptions:**
  - `rr_intervals` is a clean 1D numpy array (ectopic beats already removed in notebook 02)
  - pandas >= 1.0 installed in venv

  **Risks:**
  - Empty array input crashes `.describe()` → mitigation: caller must check `len(rr_intervals) > 0` before calling
  - Key naming changes if pandas version changes `.describe()` output → mitigation: pin pandas version in requirements.txt

  **Git Checkpoint:**
  ```bash
  git add src/features/hrv.py
  git commit -m "step 2: add get_serie_describe and get_window_features to src/features/hrv.py"
  ```

  **Subtasks:**
  - [ ] 🟥 File created at `src/features/hrv.py`
  - [ ] 🟥 Both functions defined with correct signatures
  - [ ] 🟥 File importable from project root

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  cd ~/Neonatal
  python3 -c "
  import sys
  sys.path.insert(0, '.')
  import numpy as np
  from src.features.hrv import get_serie_describe, get_window_features

  # Test with synthetic RR intervals (120-180bpm range = 333-500ms)
  rr = np.array([420, 415, 430, 410, 425, 418, 422, 435, 408, 419], dtype=float)
  result = get_serie_describe(rr)
  print('Keys:', list(result.keys()))
  print('Mean RR:', round(result['rr_ms_mean'], 1))
  print('Std RR:', round(result['rr_ms_std'], 1))

  row = get_window_features(rr, 'infant1', 0)
  print('Record name:', row['record_name'])
  print('Window idx:', row['window_idx'])
  print('Feature count:', len(row))
  "
  ```

  **Expected:**
  ```
  Keys: ['rr_ms_mean', 'rr_ms_std', 'rr_ms_min', 'rr_ms_25%', 'rr_ms_50%', 'rr_ms_75%', 'rr_ms_max']
  Mean RR: 420.2
  Std RR: 8.0  (approximately)
  Record name: infant1
  Window idx: 0
  Feature count: 9
  ```

  **Observe:** Terminal output

  **Pass:** All 5 print lines produce expected values, no traceback

  **Fail:**
  - If `ModuleNotFoundError` → `__init__.py` missing → re-run Step 1
  - If `KeyError` → pandas `.describe()` column names differ → print `serie.describe()` and check column names
  - If `Feature count` != 9 → function returning wrong keys → check `get_window_features` return dict

---

### Phase 2 — Validate Against Real Processed Data

**Goal:** `get_serie_describe` runs on actual notebook 02 output CSVs and produces a valid feature row.

---

- [ ] 🟥 **Step 3: Run feature encoding on one real RR CSV** — *Non-critical: validation only, no new files written*

  **Idempotent:** Yes — read-only.

  **Context:** Confirms the function works end-to-end on real PICS data, not just synthetic arrays. This is the integration test before notebook 03 is built.

  **Pre-Read Gate:**
  ```bash
  # Confirm at least one CSV exists
  ls ~/Neonatal/data/processed/ | head -3
  ```
  If no CSVs exist → PICS download not complete → skip this step and return when data lands.

  ```bash
  cd ~/Neonatal
  python3 -c "
  import sys, os
  sys.path.insert(0, '.')
  import pandas as pd
  import numpy as np
  from src.features.hrv import get_serie_describe, get_window_features

  # Load first available CSV
  csv_files = [f for f in os.listdir('data/processed/') if f.endswith('.csv')]
  first_csv = csv_files[0]
  df = pd.read_csv(f'data/processed/{first_csv}')
  rr = df['rr_ms'].values

  print(f'Loaded {first_csv}: {len(rr)} RR intervals')
  print(f'Mean RR: {rr.mean():.1f}ms ({60000/rr.mean():.0f} bpm)')

  # Encode first 50-beat window
  window = rr[:50]
  features = get_window_features(window, first_csv.replace('_rr_clean.csv',''), 0)
  print('Feature row:', features)
  "
  ```

  **Git Checkpoint:**
  ```bash
  git add src/features/hrv.py
  git commit -m "step 3: validate get_serie_describe on real PICS RR intervals"
  ```

  **✓ Verification Test:**

  **Type:** Integration

  **Action:** Run command above

  **Expected:**
  - `Loaded infant1_rr_clean.csv: N RR intervals` where N > 100
  - `Mean RR: Xms (Y bpm)` where Y is between 120 and 180
  - Feature row printed with 9 keys, no NaN values

  **Observe:** Terminal output

  **Pass:** Feature row printed with all numeric values, mean RR in physiological range

  **Fail:**
  - If `FileNotFoundError` → data/processed/ empty → PICS still downloading, skip step
  - If `NaN` in features → RR array has NaN values → re-run notebook 02 ectopic filter cell
  - If mean RR outside 333–500ms range → wrong units → check notebook 02 `/ fs * 1000` conversion

---

- [ ] 🟥 **Step 4: Update `requirements.txt`** — *Non-critical: dependency pinning*

  **Idempotent:** Yes — file overwrite is safe.

  ```bash
  cd ~/Neonatal
  pip freeze > requirements.txt
  ```

  **What it does:** Pins all installed package versions so the environment is reproducible.

  **Git Checkpoint:**
  ```bash
  git add requirements.txt
  git commit -m "step 4: pin requirements after adding src/features/hrv.py"
  ```

  **✓ Verification Test:**

  **Type:** Unit

  **Action:** `grep pandas ~/Neonatal/requirements.txt`

  **Expected:** `pandas==X.X.X` line present

  **Observe:** Terminal output

  **Pass:** pandas version line present in requirements.txt

  **Fail:**
  - If empty file → `pip freeze` failed → confirm venv is active with `which python`

---

## Rollback Procedure

```bash
cd ~/Neonatal
git revert HEAD    # reverts requirements.txt update (Step 4)
git revert HEAD~1  # reverts Step 3 commit
git revert HEAD~2  # reverts hrv.py creation (Step 2)
git revert HEAD~3  # reverts __init__.py creation (Step 1)

# Confirm rollback
ls src/features/hrv.py  # should say: No such file or directory
```

---

## Pre-Flight Checklist

| Phase | Check | How to Confirm | Status |
|-------|-------|----------------|--------|
| Pre-flight | venv active | `which python` returns neonatal path | ⬜ |
| Pre-flight | pandas importable | `python3 -c "import pandas"` no error | ⬜ |
| Phase 1 | `src/features/` exists | `ls src/features/` no error | ⬜ |
| Phase 1 | `__init__.py` created | `ls src/features/__init__.py` | ⬜ |
| Phase 1 | `hrv.py` importable | Step 2 verification passes | ⬜ |
| Phase 2 | RR CSVs exist | `ls data/processed/*.csv \| wc -l` = 10 | ⬜ |
| Phase 2 | Feature row has no NaNs | Step 3 verification passes | ⬜ |

---

## Success Criteria

| Feature | Target | Verification |
|---------|--------|--------------|
| `get_serie_describe` importable | No ModuleNotFoundError | `from src.features.hrv import get_serie_describe` |
| Returns 7 statistical features | Keys: mean, std, min, 25%, 50%, 75%, max | Step 2 verification test |
| Works on synthetic data | Mean RR ~420ms for test input | Step 2 print output |
| Works on real PICS data | Mean RR 333–500ms, no NaNs | Step 3 verification test |
| requirements.txt updated | pandas version pinned | `grep pandas requirements.txt` |

---

⚠️ **Do not mark a step 🟩 Done until its verification test passes.**
⚠️ **Do not proceed past a Human Gate without explicit human input.**
⚠️ **If blocked, mark 🟨 In Progress and output the State Manifest before stopping.**
⚠️ **Do not batch multiple steps into one git commit.**
⚠️ **If idempotent = No, confirm the step has not already run before executing.**