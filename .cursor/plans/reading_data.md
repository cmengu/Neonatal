# Plan: Build Notebook 04 — Baseline Deviation & Label Alignment (Revised)

**Overall Progress:** `100%` (5 / 5 steps complete)

---

## TLDR

Notebook 03 produced per-patient feature CSVs (9 HRV columns, no NaN) and label CSVs (`sample_idx`, `symbol` only). Notebook 04 has three jobs: (1) persist the infant5 flat-prefix trim offset from NB02 into a metadata CSV so label alignment can correct for the sample-clock shift; (2) align `sample_idx` annotations to `window_idx` using cumulative RR sum with trim-offset correction; (3) compute a rolling 10-window baseline mean and std per feature per patient, dropping warmup rows, and z-score each feature window against its baseline. Output is one `{patient_id}_windowed.csv` per patient plus a combined `all_patients_windowed.csv`, consumed by NB05 and NB06.

---

## Critical Decisions

- **Decision 1: Trim offset persisted as `data/processed/trim_offsets.csv`** — NB02's `start_idx` is a local variable that is printed but never saved. It must be extracted and written to disk before NB04 can correctly align annotations. A one-time extraction script (Step 1) re-runs the trim-detection logic read-only and writes `record_name, start_idx_samples` for all 10 patients. Patients with no trim get `start_idx_samples = 0`.
- **Decision 2: Label alignment formula is `min(beat_idx // STEP_SIZE, n_windows - 1)`** — The original formula `(beat_idx - WINDOW_SIZE) // STEP_SIZE` consistently assigns labels to windows that have already passed the event. The correct formula maps beat_idx to the last window that contains it. Proven correct for WINDOW_SIZE=50, STEP_SIZE=25 with actual infant5 window indices 0–26.
- **Decision 3: Trim offset subtracted before cumulative comparison** — `.atr` sample indices are in original-signal coordinates. `cumulative_pos` is in trimmed-signal coordinates. Without subtraction, all infant5 annotations where `sample_idx > cumulative_pos.max()` are silently dropped as out-of-range. Annotations in the trimmed prefix (`adjusted_sample_idx < 0`) are legitimately dropped.
- **Decision 4: Warmup drop = first LOOKBACK=10 windows via `iloc[LOOKBACK:]`** — valid because `window_idx` is confirmed contiguous from 0 for all patients.
- **Decision 5: std=0 guard sets deviation to 0.0** — flat signal segment means no deviation from baseline. NaN would propagate into model.
- **Decision 6: `assert nan_count == 0` hard-crashes per patient** — NaN must never reach NB05/06 silently.

---

## Clarification Gate

| Unknown | Required | Source | Blocking | Resolved |
|---------|----------|--------|----------|----------|
| Which patients have non-zero trim offsets | `start_idx` per patient | Step 1 extraction script | Steps 2–4 | ✅ Resolved by Step 1 |
| NB05 column expectations | Confirm `*_dev` + `label` schema | NB05 not yet written | None — NB05 is blank | ✅ No conflict |
| window_idx formula correctness | Proven: `min(beat_idx // STEP_SIZE, n_windows - 1)` | Logic check against infant5 feature CSV | Step 3 | ✅ Resolved in review |

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
# From /Users/ngchenmeng/Neonatal — run all, paste full output

# (1) Confirm all 10 feature + label + rr_clean CSVs exist
ls data/processed/*_features.csv | wc -l
ls data/processed/*_labels.csv   | wc -l
ls data/processed/*_rr_clean.csv | grep -v simulated | wc -l

# (2) Confirm feature schema and window_idx range
python -c "
import pandas as pd, glob
for f in sorted(glob.glob('data/processed/*_features.csv')):
    df = pd.read_csv(f)
    p  = f.split('/')[-1].replace('_features.csv','')
    print(p, df.shape, 'window_idx:', df.window_idx.min(), '-', df.window_idx.max(),
          'contiguous:', (df.window_idx.diff().dropna() == 1).all())
"

# (3) Confirm label schema
python -c "
import pandas as pd, glob
for f in sorted(glob.glob('data/processed/*_labels.csv')):
    df = pd.read_csv(f)
    print(f.split('/')[-1], df.shape, list(df.columns), sorted(df.symbol.unique()))
"

# (4) Confirm NB02 trim logic is readable (needed for Step 1 extraction)
grep -n 'start_idx\|flat prefix\|Trimmed' notebooks/02_signal_cleaning.ipynb | head -20

# (5) Confirm trim_offsets.csv does NOT yet exist (Step 1 creates it)
ls data/processed/trim_offsets.csv 2>/dev/null || echo "NOT FOUND — safe to create"

# (6) Confirm NB04 does NOT yet exist
ls notebooks/04_baseline_deviation.ipynb 2>/dev/null || echo "NOT FOUND — safe to create"
```

**Baseline Snapshot (fill in before Step 1):**
```
Feature CSVs present (expect 10):      ____
Label CSVs present (expect 10):        ____
rr_clean CSVs (real, expect 10):       ____
window_idx contiguous for all:         ____
trim_offsets.csv already exists:       ____
NB04 already exists:                   ____
```

---

## Steps Analysis

```
Step 1 (Extract trim offsets)     — Critical      — full code review  — Idempotent: Yes
Step 2 (Build NB04)               — Critical      — full code review  — Idempotent: Yes
Step 3 (Run NB04)                 — Critical      — verification only — Idempotent: Yes
Step 4 (Smoke-check outputs)      — Non-critical  — verification only — Idempotent: Yes
Step 5 (Regression guard)         — Non-critical  — verification only — Idempotent: Yes
```

---

## Tasks

### Phase 1 — Persist Trim Offsets

---

- [ ] 🟥 **Step 1: Extract and persist trim offsets to `data/processed/trim_offsets.csv`** — *Critical: NB04 label alignment is wrong without this*

  **Idempotent:** Yes — script overwrites `trim_offsets.csv` with identical content on re-run.

  **Context:** NB02 detects and trims a flat prefix from each patient's ECG signal before R-peak detection. The trim offset (`start_idx`) is printed but never saved. `.atr` annotation `sample_idx` values are in original-signal coordinates; `cumulative_pos` built from `rr_clean.csv` is in trimmed-signal coordinates. Without subtracting `start_idx` from each annotation's `sample_idx`, all annotations where `sample_idx > cumulative_pos.max()` are silently dropped — confirmed to affect infant5 where ~364,000 samples were trimmed. This step re-runs the trim-detection logic read-only across all 10 patients and writes `{record_name, start_idx_samples}` to `data/processed/trim_offsets.csv`.

  **Pre-Read Gate — run once; output decides action:**
  ```bash
  grep -n 'start_idx\|flat prefix' notebooks/02_signal_cleaning.ipynb | head -5
  python -c "
  import pandas as pd, os
  p = 'data/processed/trim_offsets.csv'
  if os.path.exists(p):
      df = pd.read_csv(p)
      assert len(df) == 10 and list(df.columns) == ['record_name','start_idx_samples'], 'BAD SCHEMA'
      print('EXISTS AND VALID — skip script')
  else:
      print('NOT FOUND — run script')
  "
  ```
  If `EXISTS AND VALID` → skip Step 1 script. If `NOT FOUND` or assertion fails → run script.

  ```python
  # scripts/extract_trim_offsets.py
  # Run from repo root: python scripts/extract_trim_offsets.py

  import os
  from pathlib import Path
  import numpy as np
  import wfdb
  import pandas as pd

  REPO_ROOT  = Path(os.getcwd())
  RAW_DIR    = REPO_ROOT / "data" / "raw" / "physionet.org" / "files" / "picsdb" / "1.0.0"
  OUT_PATH   = REPO_ROOT / "data" / "processed" / "trim_offsets.csv"
  PATIENTS   = [f"infant{i}" for i in range(1, 11)]
  FS_ECG     = 500
  WINDOW     = 100     # must match NB02 trim-detection window size
  STD_THRESH = 0.001   # must match NB02 threshold

  rows = []
  for patient_id in PATIENTS:
      record_path = str(RAW_DIR / f"{patient_id}_ecg")
      record      = wfdb.rdsamp(record_path, sampto=500000)
      ecg_signal  = record[0][:, 0].astype(float)

      start_idx = 0
      for i in range(0, len(ecg_signal) - WINDOW, WINDOW):
          if ecg_signal[i : i + WINDOW].std() > STD_THRESH:
              start_idx = i
              break

      rows.append({"record_name": patient_id, "start_idx_samples": start_idx})
      print(f"  {patient_id}: start_idx_samples = {start_idx} "
            f"({start_idx / FS_ECG:.1f}s trimmed)")

  df = pd.DataFrame(rows)
  df.to_csv(OUT_PATH, index=False)
  print(f"\nSaved: {OUT_PATH}")
  print(df.to_string(index=False))
  ```

  **What it does:** Reads each patient's raw ECG record, detects the flat-prefix boundary using the same logic as NB02 (window=100 samples, std threshold=0.001), records `start_idx_samples`, and writes `data/processed/trim_offsets.csv`.

  **Why this approach:** Re-running the detection logic is safer than parsing printed NB02 output. The logic is a direct copy from NB02 Cell 1 — if NB02 is ever re-run with different parameters, this script must be updated to match.

  **Assumptions:**
  - NB02 trim-detection uses `window=100` and `std > 0.001` — confirmed by reading NB02 Cell 1.
  - Raw ECG files live directly under `RAW_DIR` (no per-patient subdir): `RAW_DIR / f"{patient_id}_ecg"` — e.g. `.../1.0.0/infant5_ecg.hea`.
  - Patients with no flat prefix will produce `start_idx = 0` (correct — no offset needed).

  **Risks:**
  - NB02 trim parameters changed → offsets wrong → mitigation: `grep` NB02 for `window` and `0.001` before running.
  - `start_idx` loop exits at first non-flat window → if signal starts non-flat, `start_idx = 0` (correct for those patients).

  **Git Checkpoint:**
  ```bash
  git add scripts/extract_trim_offsets.py data/processed/trim_offsets.csv
  git commit -m "step 1: persist trim offsets for all 10 patients"
  ```

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  python -c "
  import pandas as pd
  df = pd.read_csv('data/processed/trim_offsets.csv')
  assert list(df.columns) == ['record_name', 'start_idx_samples'], f'Wrong columns: {list(df.columns)}'
  assert len(df) == 10, f'Expected 10 rows, got {len(df)}'
  assert df['start_idx_samples'].dtype in ['int64','float64'], 'start_idx not numeric'
  assert (df['start_idx_samples'] >= 0).all(), 'Negative offset found'
  infant5_offset = df.loc[df.record_name == 'infant5', 'start_idx_samples'].iloc[0]
  print(df.to_string(index=False))
  print(f'infant5 offset: {infant5_offset} samples ({infant5_offset/500:.1f}s)')
  assert infant5_offset > 0, 'infant5 should have non-zero trim offset'
  print('trim_offsets.csv OK')
  "
  ```

  **Pass:** 10 rows, correct columns, infant5 `start_idx_samples > 0`.

  **Fail:**
  - `infant5 should have non-zero trim offset` → trim detection returned 0 → check raw ECG path and NB02 window/threshold parameters match script.
  - `Expected 10 rows` → one patient's raw file missing → check `RAW_DIR` path.

---

### Phase 2 — Build and Run Notebook 04

---

- [ ] 🟥 **Step 2: Create `notebooks/04_baseline_deviation.ipynb`** — *Critical: produces final feature matrix for NB05 + NB06*

  **Idempotent:** Yes — `nbformat` script overwrites notebook with identical cells on re-run.

  **Pre-Read Gate:**
  ```bash
  ls data/processed/trim_offsets.csv
  python -c "import pandas as pd; pd.read_csv('data/processed/trim_offsets.csv'); print('trim_offsets OK')"
  ls scripts/generate_nb04.py 2>/dev/null && echo "EXISTS — verify content matches below before overwriting" || echo "NOT FOUND — proceed to create"
  ```
  If `NOT FOUND` → proceed. If `EXISTS` → verify script content matches the block below before overwriting; if mismatched, update script then run.

  **Action:** Create `scripts/generate_nb04.py` with the content below, then run from repo root:
  ```bash
  python scripts/generate_nb04.py
  ```

  **scripts/generate_nb04.py** (create this file; run from repo root):

  ```python
  #!/usr/bin/env python3
  """Generate notebooks/04_baseline_deviation.ipynb. Run from repo root: python scripts/generate_nb04.py"""
  import os
  from pathlib import Path
  import nbformat

  REPO_ROOT = Path(os.getcwd())
  if REPO_ROOT.name == "notebooks":
      REPO_ROOT = REPO_ROOT.parent

  nb = nbformat.v4.new_notebook()

  cell1 = '''import sys
  import os
  from pathlib import Path
  import numpy as np
  import pandas as pd

  REPO_ROOT = Path(os.getcwd())
  if REPO_ROOT.name == "notebooks":
      REPO_ROOT = REPO_ROOT.parent

  sys.path.insert(0, str(REPO_ROOT))

  # NOTE: PATIENTS must stay in sync with notebooks 02 and 03.
  PATIENTS      = [f"infant{i}" for i in range(1, 11)]
  PROCESSED_DIR = REPO_ROOT / "data" / "processed"

  WINDOW_SIZE = 50    # beats — must match NB03
  STEP_SIZE   = 25    # beats — must match NB03
  LOOKBACK    = 10    # windows for rolling baseline
  FS_ECG      = 500   # Hz

  HRV_COLS = [
      "rr_ms_mean", "rr_ms_std", "rr_ms_min",
      "rr_ms_max", "rr_ms_25%", "rr_ms_50%", "rr_ms_75%"
  ]

  # Load trim offsets — written by scripts/extract_trim_offsets.py (Step 1)
  trim_df      = pd.read_csv(PROCESSED_DIR / "trim_offsets.csv")
  TRIM_OFFSETS = dict(zip(trim_df["record_name"], trim_df["start_idx_samples"].astype(int)))

  print(f"REPO_ROOT:     {REPO_ROOT}")
  print(f"PROCESSED_DIR: {PROCESSED_DIR}")
  print(f"LOOKBACK:      {LOOKBACK} windows")
  print(f"Patients:      {PATIENTS}")
  print(f"Trim offsets:  {TRIM_OFFSETS}")'''

  cell2 = '''def align_labels_to_windows(patient_id):
      """
      Map annotation sample_idx -> window_idx using cumulative RR sum
      with trim-offset correction.

      Method:
        1. Load rr_clean -> cumulative sum in samples (trimmed-signal coordinates)
        2. Load trim offset for this patient from TRIM_OFFSETS
        3. For each annotation: adjusted_sample_idx = sample_idx - trim_offset
           - If adjusted_sample_idx < 0: annotation is in trimmed prefix -> drop
        4. Find beat_idx: first beat where cumulative_pos >= adjusted_sample_idx
        5. Map beat_idx -> window_idx: min(beat_idx // STEP_SIZE, n_windows - 1)
        6. Drop annotations outside valid window range

      Returns: set of window_idx values containing a bradycardia episode start.
      """
      rr_ms     = pd.read_csv(PROCESSED_DIR / f"{patient_id}_rr_clean.csv")["rr_ms"].values
      labels_df = pd.read_csv(PROCESSED_DIR / f"{patient_id}_labels.csv")

      rr_samples     = rr_ms / 1000.0 * FS_ECG
      cumulative_pos = np.cumsum(rr_samples)
      n_windows      = (len(rr_ms) - WINDOW_SIZE) // STEP_SIZE + 1
      trim_offset    = TRIM_OFFSETS.get(patient_id, 0)

      labelled_windows = set()
      dropped_prefix   = 0
      dropped_range    = 0

      for _, row in labels_df.iterrows():
          sample_idx          = row["sample_idx"]
          adjusted_sample_idx = sample_idx - trim_offset

          # Drop annotations that fall inside the trimmed prefix
          if adjusted_sample_idx < 0:
              dropped_prefix += 1
              continue

          # Find beat_idx: first beat whose cumulative position >= adjusted_sample_idx
          matches = np.where(cumulative_pos >= adjusted_sample_idx)[0]
          if len(matches) == 0:
              dropped_range += 1
              continue

          beat_idx   = int(matches[0])
          window_idx = min(beat_idx // STEP_SIZE, n_windows - 1)

          if 0 <= window_idx < n_windows:
              labelled_windows.add(window_idx)
          else:
              dropped_range += 1

      # Alignment bug check: if any annotation is within rr range and trim_offset=0, at least one must map
      if trim_offset == 0 and len(labels_df) > 0:
          in_range = (labels_df["sample_idx"] <= cumulative_pos[-1]).any()
          if in_range:
              assert len(labelled_windows) > 0, (
                  f"{patient_id}: annotations in range but all dropped — alignment bug"
              )
      print(f"  {patient_id}: {len(labels_df)} annotations -> "
            f"{len(labelled_windows)} labelled windows "
            f"(dropped_prefix={dropped_prefix}, dropped_range={dropped_range}, "
            f"trim_offset={trim_offset})")
      return labelled_windows'''

  cell3 = '''def compute_deviations(patient_id, labelled_windows):
      """
      Compute rolling z-score deviation from personal baseline.

      Steps:
        1. Load features CSV
        2. For each HRV column compute rolling mean and std over
           previous LOOKBACK windows (exclusive of current window)
        3. Z-score: (current - rolling_mean) / rolling_std
        4. Guard: if rolling_std == 0, deviation = 0.0
        5. Drop first LOOKBACK rows (warmup)
        6. Add binary label from labelled_windows
      """
      features = pd.read_csv(PROCESSED_DIR / f"{patient_id}_features.csv")

      # Assert window_idx is contiguous from 0 — required for iloc[LOOKBACK:] to be correct
      assert features["window_idx"].iloc[0] == 0, \
          f"{patient_id}: window_idx does not start at 0"
      assert (features["window_idx"].diff().dropna() == 1).all(), \
          f"{patient_id}: window_idx is not contiguous"

      dev_cols = {}
      for col in HRV_COLS:
          values    = features[col].values
          roll_mean = np.full(len(values), np.nan)
          roll_std  = np.full(len(values), np.nan)

          for i in range(LOOKBACK, len(values)):
              window_vals  = values[i - LOOKBACK : i]
              roll_mean[i] = window_vals.mean()
              roll_std[i]  = window_vals.std(ddof=1)

          with np.errstate(invalid="ignore", divide="ignore"):
              deviation = np.where(
                  roll_std == 0,
                  0.0,
                  (values - roll_mean) / roll_std
              )
          dev_cols[f"{col}_dev"] = deviation

      result = pd.DataFrame(dev_cols)
      result.insert(0, "window_idx",  features["window_idx"])
      result.insert(0, "record_name", features["record_name"])

      # Drop warmup rows — valid because window_idx is contiguous from 0
      result = result.iloc[LOOKBACK:].reset_index(drop=True)

      result["label"] = result["window_idx"].apply(
          lambda w: 1 if w in labelled_windows else 0
      )

      n_pos = result["label"].sum()
      n_neg = len(result) - n_pos
      print(f"  {patient_id}: {len(result)} windows after warmup drop "
            f"(pos={n_pos}, neg={n_neg}, ratio={n_pos/max(len(result),1):.2%})")

      nan_count = result.isnull().sum().sum()
      assert nan_count == 0, f"NaN in output for {patient_id}: {result.isnull().sum()}"

      return result'''

  cell4 = '''all_patients = []

  for patient_id in PATIENTS:
      print(f"\\n-- {patient_id} --")
      labelled_windows = align_labels_to_windows(patient_id)
      windowed_df      = compute_deviations(patient_id, labelled_windows)

      out_path = PROCESSED_DIR / f"{patient_id}_windowed.csv"
      windowed_df.to_csv(out_path, index=False)
      print(f"  Saved: {out_path}")
      all_patients.append(windowed_df)

  combined      = pd.concat(all_patients, ignore_index=True)
  combined_path = PROCESSED_DIR / "all_patients_windowed.csv"
  combined.to_csv(combined_path, index=False)

  print(f"\\nNotebook 04 complete.")
  print(f"Combined shape:   {combined.shape}")
  print(f"Total pos labels: {combined['label'].sum()} / {len(combined)}")
  print(f"Overall pos rate: {combined['label'].mean():.2%}")
  print(f"NaN in combined:  {combined.isnull().sum().sum()}")'''

  cell5 = '''import matplotlib.pyplot as plt

  fig, axes = plt.subplots(2, 5, figsize=(18, 6))
  axes = axes.flatten()

  for idx, patient_id in enumerate(PATIENTS):
      df  = pd.read_csv(PROCESSED_DIR / f"{patient_id}_windowed.csv")
      ax  = axes[idx]
      ax.plot(df["window_idx"], df["rr_ms_mean_dev"], linewidth=0.8, color="steelblue")
      pos = df[df["label"] == 1]
      ax.scatter(pos["window_idx"], pos["rr_ms_mean_dev"],
                 color="red", s=30, zorder=5, label="bradycardia")
      ax.set_title(f"{patient_id} (n={len(df)}, pos={len(pos)})", fontsize=9)
      ax.set_xlabel("window_idx", fontsize=7)
      ax.set_ylabel("rr_ms_mean_dev", fontsize=7)
      ax.axhline(0, color="grey", linestyle="--", linewidth=0.5)

  plt.suptitle("RR Mean Deviation with Bradycardia Events (red) — post trim-offset fix", fontsize=11)
  plt.tight_layout()
  plt.show()'''

  nb.cells = [
      nbformat.v4.new_code_cell(cell1),
      nbformat.v4.new_code_cell(cell2),
      nbformat.v4.new_code_cell(cell3),
      nbformat.v4.new_code_cell(cell4),
      nbformat.v4.new_code_cell(cell5),
  ]

  out_path = REPO_ROOT / "notebooks" / "04_baseline_deviation.ipynb"
  with open(out_path, "w") as f:
      nbformat.write(nb, f)
  print(f"Notebook written: {out_path}")
  ```

  **What it does:** Generates NB04 programmatically via `nbformat`. Cell 1 loads trim offsets. Cell 2 aligns labels with trim-offset correction and the fixed window formula. Cell 3 computes rolling z-score deviations with contiguous-window assertion and std=0 guard. Cell 4 runs all patients and saves CSVs. Cell 5 is a sanity plot.

  **Why this approach:** `nbformat` prevents raw JSON corruption. All critical fixes from the logic review are baked in — trim offset subtraction and corrected `min(beat_idx // STEP_SIZE, n_windows - 1)` formula.

  **Assumptions:**
  - `trim_offsets.csv` exists with columns `record_name, start_idx_samples` (Step 1 guarantee).
  - `window_idx` is contiguous from 0 for all patients (confirmed in pre-flight).
  - HRV column names match `src/features/hrv.py` exactly — confirmed: `rr_ms_25%` etc.

  **Risks:**
  - `trim_offsets.csv` has wrong offset for infant5 → wrong label alignment → mitigation: Step 1 verification asserts `infant5 > 0` and printed offset is visually checkable.
  - NB03 `PATIENTS` list still set to `["infant5"]` → Cell 4 fails for other patients → mitigation: pre-flight grep confirms NB03 PATIENTS.

  **Git Checkpoint:**
  ```bash
  git add scripts/generate_nb04.py notebooks/04_baseline_deviation.ipynb
  git commit -m "step 2: build notebook 04 with trim-offset fix and corrected window formula"
  ```

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  python -m json.tool notebooks/04_baseline_deviation.ipynb > /dev/null && echo "valid JSON"

  python -c "
  import json
  nb  = json.load(open('notebooks/04_baseline_deviation.ipynb'))
  src = ' '.join([''.join(c['source']) for c in nb['cells'] if c['cell_type']=='code'])
  checks = [
      'cumulative_pos',
      'align_labels_to_windows',
      'compute_deviations',
      'LOOKBACK',
      'roll_mean',
      'roll_std',
      'all_patients_windowed',
      'nan_count',
      'label',
      'trim_offset',
      'adjusted_sample_idx',
      'TRIM_OFFSETS',
      'min(beat_idx // STEP_SIZE',
      'iloc[0] == 0',
      'trim_offset == 0',
      'in_range',
      'alignment bug',
  ]
  for token in checks:
      assert token in src, f'MISSING: {token}'
      print(f'{token} OK')
  print('Cell count:', sum(1 for c in nb['cells'] if c['cell_type']=='code'))
  "
  ```

  **Pass:** All 17 tokens print OK, cell count = 5, valid JSON.

  **Fail:**
  - Token `trim_offset` or `in_range` missing → Cell 2 did not save → re-run generate script.
  - Token `min(beat_idx // STEP_SIZE` missing → old formula still present → re-run nbformat script.
  - JSON invalid → file corrupted → `rm notebooks/04_baseline_deviation.ipynb` and re-run script.

---

- [ ] 🟥 **Step 3: Run Notebook 04** — *Critical: produces all_patients_windowed.csv consumed by NB05 + NB06*

  **Idempotent:** Yes — overwrites CSVs with identical content on re-run.

  **Action:**
  ```bash
  cd /Users/ngchenmeng/Neonatal
  python scripts/run_nb04.py
  # Fallback if run script fails: jupyter nbconvert --to notebook --execute \
  #   notebooks/04_baseline_deviation.ipynb --output notebooks/04_baseline_deviation_executed.ipynb 2>&1 | tail -40
  ```

  **Human Gate:**
  Paste the full per-patient printed output (window counts, pos/neg labels, trim offsets, dropped counts) before proceeding to Step 4.

  ⚠️ **Specifically check infant5:** confirm `trim_offset` matches Step 1 value, `dropped_prefix` accounts for annotations before trimmed region, and `n_pos >= 0` (may be 0 — valid if all events fall in trimmed prefix, but now unlikely given offset fix).

  **Termination (mandatory):** After pasting the output, output this exactly as the final line:
  ```
  [WAITING: per-patient NB04 execution output]
  ```
  Do not write any code after this line. Do not call any tools after this line. Stop and wait for human confirmation before proceeding to Step 4.

  **✓ Verification Test:**

  **Type:** Integration

  **Action:**
  ```bash
  python -c "
  import pandas as pd
  from pathlib import Path

  expected_cols = [
      'record_name', 'window_idx',
      'rr_ms_mean_dev', 'rr_ms_std_dev', 'rr_ms_min_dev',
      'rr_ms_max_dev', 'rr_ms_25%_dev', 'rr_ms_50%_dev', 'rr_ms_75%_dev',
      'label'
  ]

  for i in range(1, 11):
      p    = f'infant{i}'
      path = Path('data/processed') / f'{p}_windowed.csv'
      assert path.exists(), f'MISSING: {path}'
      df   = pd.read_csv(path)

      assert list(df.columns) == expected_cols, f'{p} wrong cols: {list(df.columns)}'
      assert len(df) > 0,                       f'{p}: zero rows'
      assert df.isnull().sum().sum() == 0,       f'{p}: NaN present'
      assert df['label'].isin([0,1]).all(),       f'{p}: label not binary'
      assert df['record_name'].iloc[0] == p,     f'{p}: record_name mismatch'
      assert df['window_idx'].min() == 10,       f'{p}: warmup drop wrong (min must be LOOKBACK=10, got {df["window_idx"].min()})'

      print(f'{p}: {len(df)} windows, pos={df.label.sum()}, '
            f'neg={len(df)-df.label.sum()}, NaN={df.isnull().sum().sum()} OK')

  combined = pd.read_csv(Path('data/processed') / 'all_patients_windowed.csv')
  assert combined.isnull().sum().sum() == 0, 'NaN in combined'
  print(f'Combined: {combined.shape}, total pos={combined.label.sum()} OK')
  "
  ```

  **Pass:** All 10 patients print OK, combined prints OK, `window_idx.min() == 10` for all, zero NaN.

  **Fail:**
  - `min must be LOOKBACK=10` → warmup drop failed or wrong LOOKBACK → check `iloc[LOOKBACK:]` in Cell 3.
  - `zero rows` for infant5 → LOOKBACK drop consumed all 17 usable rows → check window count vs LOOKBACK.
  - `label not binary` → `labelled_windows` set contains non-int → print `labelled_windows` for failing patient.
  - `NaN present` → std=0 guard not firing → print `roll_std` for the affected patient and column.

---

### Phase 3 — Smoke-Check and Confirm

---

- [ ] 🟥 **Step 4: Smoke-check outputs** — *Non-critical: statistical sanity*

  **Idempotent:** Yes — read-only.

  **Action:**
  ```bash
  python -c "
  import pandas as pd
  from pathlib import Path

  combined = pd.read_csv(Path('data/processed') / 'all_patients_windowed.csv')
  print('Combined shape:   ', combined.shape)
  print('Overall pos rate: ', f\"{combined['label'].mean():.2%}\")
  print()
  print('Per-patient summary:')
  for p, grp in combined.groupby('record_name'):
      print(f'  {p}: {len(grp)} windows, pos={grp.label.sum()}, '
            f'pos_rate={grp.label.mean():.1%}')
  print()
  print('Feature deviation stats (all patients):')
  dev_cols = [c for c in combined.columns if c.endswith('_dev')]
  print(combined[dev_cols].describe().round(3))
  "
  ```

  **What to look for:**
  - Deviation scores centred near 0 with std ≈ 1 for most features. If std > 5 for any feature → rolling baseline is computing on too few windows.
  - Positive rate 5–20% across the combined set — expected for rare bradycardia.
  - infant5 may show `pos=0` if all its annotations fall in the trimmed prefix even after offset correction — document but do not treat as error.
  - Last-window label density: `min(beat_idx // STEP_SIZE, n_windows - 1)` clamps all late-recording annotations to the final window. Patients with many annotations at recording end (e.g. infant9 with 97) may show artificially high pos rate at window `n_windows - 1` — document for NB05 interpretation.

  **Git Checkpoint:**
  ```bash
  git add data/processed/infant*_windowed.csv \
          data/processed/all_patients_windowed.csv
  git commit -m "step 4: add notebook 04 windowed CSV outputs"
  ```

---

- [ ] 🟥 **Step 5: Regression guard — confirm upstream CSVs untouched** — *Non-critical*

  **Idempotent:** Yes — read-only.

  **Action:**
  ```bash
  python -c "
  import pandas as pd, glob

  # Feature CSVs unchanged
  for f in sorted(glob.glob('data/processed/*_features.csv')):
      df = pd.read_csv(f)
      assert df.isnull().sum().sum() == 0, f'{f}: NaN introduced'
      print(f.split('/')[-1], df.shape, 'OK')

  # Label CSVs unchanged
  for f in sorted(glob.glob('data/processed/*_labels.csv')):
      df = pd.read_csv(f)
      assert list(df.columns) == ['sample_idx','symbol'], f'{f}: columns changed'
      print(f.split('/')[-1], df.shape, 'OK')

  # rr_clean CSVs unchanged
  for f in sorted(glob.glob('data/processed/infant*_rr_clean.csv')):
      df = pd.read_csv(f)
      assert list(df.columns) == ['rr_ms'], f'{f}: columns changed'
      print(f.split('/')[-1], df.shape, 'OK')
  "
  ```

  **Pass:** All print OK. No shape or column changes from pre-flight baseline.

  **Fail:** Any shape mismatch → a step wrote to the wrong file → check git diff for unintended changes.

---

## Regression Guard

| System | Pre-change behaviour | Post-change verification |
|--------|---------------------|--------------------------|
| `*_features.csv` | 9 columns, no NaN, shape unchanged | Step 5 shape + NaN check |
| `*_labels.csv` | 2 columns `sample_idx, symbol`, row counts unchanged | Step 5 column + shape check |
| `*_rr_clean.csv` | 1 column `rr_ms`, row counts unchanged | Step 5 column + shape check |
| NB03 PATIENTS | All 10 infants | `grep PATIENTS notebooks/03_hrv_extraction.ipynb` |

---

## Rollback Procedure

```bash
# Rollback NB04 outputs:
rm -f data/processed/*_windowed.csv
rm -f data/processed/all_patients_windowed.csv
rm -f data/processed/trim_offsets.csv
rm -f notebooks/04_baseline_deviation.ipynb
rm -f scripts/extract_trim_offsets.py
rm -f scripts/generate_nb04.py
rm -f scripts/run_nb04.py

# Confirm upstream outputs untouched:
ls data/processed/*_features.csv   # must show 10 files
ls data/processed/*_labels.csv     # must show 10 files
ls data/processed/*_rr_clean.csv   # must show 10 real + 10 simulated
```

---

## Risk Heatmap

| Step | Risk | What Could Go Wrong | Early Detection | Idempotent |
|------|------|---------------------|-----------------|------------|
| Step 1 | 🟡 Medium | Trim window/threshold mismatches NB02 → wrong offset | Verify infant5 offset > 0 and plausible (~364000) | Yes |
| Step 2 | 🟡 Medium | nbformat script fails silently | JSON validity check + 17-token assertion | Yes |
| Step 3 | 🟡 Medium | infant5 still shows 0 pos labels despite fix | Human gate output — check dropped_prefix vs dropped_range | Yes |
| Step 3 | 🔴 High | Warmup drop leaves infant5 with 0 rows | Zero-row assert in verification | Yes |
| Step 3 | 🟢 Low | std=0 produces NaN | `assert nan_count == 0` per patient | Yes |
| Step 4 | 🟢 Low | Deviation std wildly off | `describe()` output — check std ≈ 1 | Yes |

---

## Success Criteria

| Deliverable | Target | Verification |
|-------------|--------|--------------|
| `trim_offsets.csv` | 10 rows, infant5 offset > 0 | Step 1 verification |
| Per-patient windowed CSVs | `infant1..10_windowed.csv` in `data/processed/` | Step 3 verification |
| Combined CSV | `all_patients_windowed.csv` in `data/processed/` | Step 3 verification |
| Output schema | `record_name`, `window_idx`, 7 `*_dev` cols, `label` | Step 3 column assert |
| Zero NaN | All CSVs NaN-free | Step 3 `assert nan_count == 0` |
| Binary labels | `label` ∈ {0,1} only | Step 3 label assert |
| Warmup dropped | `window_idx.min() == LOOKBACK` (10) in all outputs | Step 3 min assert |
| Trim offset applied | infant5 has `n_pos >= 0`, dropped_prefix reported | Step 3 human gate |
| Window formula correct | Labels fall in windows containing the event beat | Sanity plot — red dots at deviation spikes |

---

## Decisions Log (carried from logic review)

| Decision | Resolution |
|----------|-----------|
| Window formula | `min(beat_idx // STEP_SIZE, n_windows - 1)` — replaces `(beat_idx - WINDOW_SIZE) // STEP_SIZE` |
| Trim offset persistence | Written by `scripts/extract_trim_offsets.py` to `data/processed/trim_offsets.csv` |
| Trim offset application | `adjusted_sample_idx = sample_idx - trim_offset` before cumulative comparison |
| Annotations in trimmed prefix | `adjusted_sample_idx < 0` → `dropped_prefix` counter, silently dropped |
| Warmup drop method | `iloc[LOOKBACK:]` — valid because `window_idx` confirmed contiguous from 0 |
| std=0 guard | Deviation set to `0.0`, not NaN |
| NaN guard | `assert nan_count == 0` hard-crashes per patient in Cell 3 |

---

⚠️ **Do not mark a step 🟩 Done until its verification test passes.**
⚠️ **Do not proceed past a Human Gate without explicit human input.**
⚠️ **If blocked, mark 🟨 In Progress and output the State Manifest before stopping.**
⚠️ **Do not batch multiple steps into one git commit.**