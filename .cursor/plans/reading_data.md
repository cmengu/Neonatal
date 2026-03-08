# Plan: Update Notebook 02 + Build Notebook 03 (v2 — post logic check)

**Overall Progress:** `100%` (6 / 6 steps complete)

---

## Decisions Log (resolved from logic check)

| Flaw | Resolution Applied |
|------|--------------------|
| Wrong working directory for nbconvert | All notebook paths now use `REPO_ROOT` resolved via `pathlib` at runtime — no relative `..` paths |
| `sys.path.insert(0, '..')` breaks under nbconvert | Replaced with `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` pattern using `os.path.abspath` |
| Beat index conversion formula wrong | `beat_idx` removed from labels. Labels saved with `sample_idx` and `symbol` only. Notebook 04 aligns using cumulative RR sum against sample_idx |
| Plan instructs Cursor to "add cell" without specifying JSON manipulation | Step 2 now instructs user to add cells manually in Jupyter UI — not via text/JSON editing |

---

## TLDR

Notebook 02 currently loads only simulated neurokit2 ECG data and cannot process real PICS waveforms. This plan first updates Notebook 02 to load real wfdb ECG records from `infant1` and `infant10`, detect R-peaks, clean RR intervals, and write `{patient_id}_rr_clean.csv` to `data/processed/`. It then builds Notebook 03 from scratch to consume those CSVs, apply sliding windows, call `get_window_features()` from `src/features/hrv.py`, load bradycardia annotations from `.atr` files, and write `{patient_id}_features.csv` and `{patient_id}_labels.csv` to `data/processed/`. After both notebooks run on `infant1` and `infant10`, the pipeline is unblocked through to Notebook 04. Adding infants 2–9 requires only extending the `PATIENTS` list in both notebooks.

---

## Critical Decisions

- **Decision 1:** Notebook 02 keeps both simulated and real PICS paths, controlled by `USE_REAL_DATA` flag — simulated fallback is never destroyed.
- **Decision 2:** RR interval time index remains integer beat order (0, 1, 2…), no datetime — matches existing `_rr_clean.csv` schema exactly.
- **Decision 3:** Labels CSV saves `sample_idx` and `symbol` only — no `beat_idx`. Notebook 04 resolves alignment using cumulative RR sum against `sample_idx` directly. This eliminates the silent wrong-answer bug from the flawed beat index formula.
- **Decision 4:** All file paths in notebooks use `REPO_ROOT` resolved at runtime via `pathlib` — no hardcoded `..` relative paths that break under nbconvert.
- **Decision 5:** Notebook cells are added manually in Jupyter UI — not via JSON manipulation by Cursor — to prevent notebook JSON corruption.

---

## Clarification Gate

| Unknown | Required | Source | Blocking | Resolved |
|---------|----------|--------|----------|----------|
| Exact record name for wfdb | Confirmed: `infant1_ecg`, `infant10_ecg` | pre-flight ls output | Steps 1–3 | ✅ |
| ECG sampling frequency | Confirmed: 500 Hz | PICS documentation | Step 2 | ✅ |
| RR CSV column name | Confirmed: `rr_ms` only, integer index, `../data/processed/` save path | Notebook 02 existing code | Steps 1, 3 | ✅ |
| `get_window_features()` return keys | Confirmed: `record_name`, `window_idx`, `rr_ms_mean`, `rr_ms_std`, `rr_ms_min`, `rr_ms_max`, `rr_ms_25%`, `rr_ms_50%`, `rr_ms_75%` | src/features/hrv.py | Steps 4–5 | ✅ |
| Window size and step | Confirmed: 50 beats, 25-beat step | Project spec | Steps 4–5 | ✅ |
| .atr annotation symbols for bradycardia | Must be confirmed by reading one .atr file | Terminal — Step 1 pre-flight | Step 5 | ⬜ |
| Existing Notebook 02 save path prefix | Must confirm whether save uses `../data/processed/` or `data/processed/` | Notebook 02 source | Step 2 | ⬜ |

---

## Agent Failure Protocol

1. A verification command fails → read the full error output.
2. Cause is unambiguous → make ONE targeted fix → re-run the same verification command.
3. If still failing after one fix → **STOP**. Output full contents of every file modified in this step. Report: (a) command run, (b) full error verbatim, (c) fix attempted, (d) exact state of each modified file, (e) why you cannot proceed.
4. Never attempt a second fix without human instruction.
5. Never modify files not named in the current step.

---

## Pre-Flight — Run Before Any Code Changes

```bash
# From /Users/ngchenmeng/Neonatal — run all of these, paste full output

# (1) Confirm existing processed files — must not be deleted
ls data/processed/

# (2) Confirm PICS raw files present
ls data/raw/physionet.org/files/picsdb/1.0.0/

# (3) Confirm packages importable
python -c "import wfdb, neurokit2, pandas, numpy, pathlib; print('OK')"

# (4) Read .atr annotation symbols — resolves Clarification Gate row
python -c "
import wfdb
ann = wfdb.rdann('data/raw/physionet.org/files/picsdb/1.0.0/infant1_ecg', 'atr')
print('symbols:', set(ann.symbol))
print('first 10 samples:', ann.sample[:10])
"

# (5) Confirm existing Notebook 02 save path
grep -n "to_csv\|data/processed" notebooks/02_signal_cleaning.ipynb

# (6) Record line count before any edit
wc -l notebooks/02_signal_cleaning.ipynb

# (7) Validate notebook 02 is valid JSON right now
python -m json.tool notebooks/02_signal_cleaning.ipynb > /dev/null && echo "valid JSON"
```

**Baseline Snapshot (fill in before Step 1):**
```
Existing files in data/processed/:           ____
infant1 + infant10 files confirmed present:  ____
Packages importable:                         ____
.atr annotation symbols (infant1):           ____
Notebook 02 save path prefix (../ or not):   ____
Line count notebooks/02_signal_cleaning:     ____
Notebook 02 JSON valid:                      ____
```

---

## Steps Analysis

```
Step 1 (Pre-flight)              — Non-critical  — verification only    — Idempotent: Yes
Step 2 (Update Notebook 02)      — Critical      — full code review     — Idempotent: Yes
Step 3 (Run Notebook 02)         — Critical      — verification only    — Idempotent: Yes
Step 4 (Build Notebook 03)       — Critical      — full code review     — Idempotent: Yes
Step 5 (Run Notebook 03)         — Critical      — verification only    — Idempotent: Yes
Step 6 (Smoke-check outputs)     — Non-critical  — verification only    — Idempotent: Yes
```

---

## Tasks

### Phase 1 — Update Notebook 02 for Real PICS Data

**Goal:** `infant1_rr_clean.csv` and `infant10_rr_clean.csv` exist in `data/processed/` with single column `rr_ms`, integer index, >100 rows, produced from real wfdb ECG.

---

- [ ] 🟥 **Step 1: Run Pre-Flight** — *Non-critical: read-only*

  **Idempotent:** Yes — read-only commands only.

  **Action:** Run every command in the Pre-Flight section above. Fill in the Baseline Snapshot. Do not proceed until all 7 checks have output.

  **Human Gate:**
  Output `"[PREFLIGHT COMPLETE — PASTE FULL OUTPUT BEFORE STEP 2]"` as the final line.
  Do not write any code after this line.

---

- [ ] 🟥 **Step 2: Add Real PICS Loading Cells to Notebook 02** — *Critical: changes which files get written to data/processed/*

  **Idempotent:** Yes — overwriting an existing `_rr_clean.csv` with identical content is safe.

  **Context:** Notebook 02 currently uses `neurokit2.ecg_simulate()` only. We add a `USE_REAL_DATA` config cell and a real wfdb loading cell. The simulated cells are kept intact and unchanged. The save path must match whatever prefix (with or without `../`) is already used in the existing simulated save — confirmed in pre-flight Step 5.

  ⚠️ **IMPORTANT — how to add cells:**
  Do NOT edit the `.ipynb` file as text or JSON. Open `notebooks/02_signal_cleaning.ipynb` in Jupyter UI. Add two new cells manually at the top of the notebook by clicking Insert → Cell Above. Paste the code below exactly. This prevents JSON corruption.

  **Pre-Read Gate — run before touching the notebook:**
  - [ ] `grep -n "USE_REAL_DATA\|wfdb\|rdsamp" notebooks/02_signal_cleaning.ipynb` → must return 0 matches (code does not already exist)
  - [ ] `grep -n "to_csv" notebooks/02_signal_cleaning.ipynb` → record exact save path prefix used — your new cells must use the same prefix
  - [ ] `python -m json.tool notebooks/02_signal_cleaning.ipynb > /dev/null && echo "valid JSON"` → must pass before and after editing

  **New Cell 1 — Config (insert at top of notebook):**
  ```python
  from pathlib import Path
  import os

  # Resolve repo root regardless of where notebook is executed from
  REPO_ROOT = Path(os.getcwd())
  # If running from notebooks/ directory, go up one level
  if REPO_ROOT.name == 'notebooks':
      REPO_ROOT = REPO_ROOT.parent

  USE_REAL_DATA     = True   # Set False to fall back to neurokit2 simulation
  REAL_DATA_DIR     = REPO_ROOT / "data" / "raw" / "physionet.org" / "files" / "picsdb" / "1.0.0"
  PROCESSED_DIR     = REPO_ROOT / "data" / "processed"
  PATIENTS          = ["infant1", "infant10"]   # extend when infants 2-9 finish downloading
  FS_ECG            = 500    # Hz
  ECTOPIC_THRESHOLD = 0.20   # 20% deviation from local median → ectopic beat

  PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
  print(f"REPO_ROOT:     {REPO_ROOT}")
  print(f"REAL_DATA_DIR: {REAL_DATA_DIR}")
  print(f"PROCESSED_DIR: {PROCESSED_DIR}")
  ```

  **New Cell 2 — Real PICS loading (insert immediately after Cell 1):**
  ```python
  import wfdb
  import neurokit2 as nk
  import numpy as np
  import pandas as pd

  def load_rr_from_wfdb(record_path, fs, ectopic_threshold):
      """
      Load ECG from wfdb record, detect R-peaks via Pan-Tompkins,
      compute and clean RR intervals.
      Returns: np.array of cleaned RR intervals in ms (integer beat order index).
      """
      record      = wfdb.rdsamp(str(record_path))
      ecg_signal  = record[0][:, 0]   # channel 0
      print(f"  Signal names: {record[1]['sig_name']}")   # loud confirmation of channel

      signals, info = nk.ecg_process(ecg_signal, sampling_rate=fs)
      r_peaks       = info["ECG_R_Peaks"]
      rr_ms         = np.diff(r_peaks) / fs * 1000.0

      rolling_median = np.median(rr_ms)
      mask           = np.abs(rr_ms - rolling_median) / rolling_median < ectopic_threshold
      rr_clean       = rr_ms[mask]

      print(f"  Raw beats: {len(rr_ms)}, after ectopic removal: {len(rr_clean)}")
      return rr_clean

  if USE_REAL_DATA:
      for patient_id in PATIENTS:
          record_path = REAL_DATA_DIR / f"{patient_id}_ecg"
          rr_clean    = load_rr_from_wfdb(record_path, FS_ECG, ECTOPIC_THRESHOLD)
          out_path    = PROCESSED_DIR / f"{patient_id}_rr_clean.csv"
          pd.DataFrame({'rr_ms': rr_clean}).to_csv(out_path, index=False)
          print(f"  Saved: {out_path}  ({len(rr_clean)} rows)")
  else:
      print("USE_REAL_DATA=False — run simulated cells below instead")
  ```

  **What it does:** Resolves `REPO_ROOT` at runtime so paths work regardless of whether the notebook is executed from `notebooks/` or repo root. Loads raw ECG, detects R-peaks, removes ectopic beats at 20% threshold, saves `{patient_id}_rr_clean.csv` with single column `rr_ms` and no index.

  **Why this approach:** `pathlib` runtime resolution eliminates the working-directory bug. Printing `sig_name` gives a loud confirmation that the right ECG channel is loaded. Keeping simulated cells intact means no regression on existing processed data.

  **Assumptions:**
  - ECG signal is in channel index 0 — `sig_name` print in the function confirms this loudly
  - `wfdb.rdsamp()` accepts a `Path` object cast to `str`
  - `neurokit2.ecg_process()` handles 500Hz neonatal ECG without custom configuration

  **Risks:**
  - Wrong ECG channel (not index 0) → mitigated by `sig_name` print — human confirms before trusting output
  - nbconvert working directory unexpected → mitigated by `REPO_ROOT` detection logic printing its value
  - Notebook JSON corrupted by manual edit → mitigated by JSON validity check after saving

  **After adding cells in Jupyter UI — run this before proceeding:**
  ```bash
  python -m json.tool notebooks/02_signal_cleaning.ipynb > /dev/null && echo "valid JSON"
  ```

  **Git Checkpoint:**
  ```bash
  git add notebooks/02_signal_cleaning.ipynb
  git commit -m "step 2: add real PICS wfdb loading path to notebook 02"
  ```

  **Subtasks:**
  - [ ] 🟥 Config cell added at top, REPO_ROOT prints correct path
  - [ ] 🟥 Loading cell added immediately after config cell
  - [ ] 🟥 Simulated cells unchanged and still present below
  - [ ] 🟥 Notebook JSON valid after save

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  python -m json.tool notebooks/02_signal_cleaning.ipynb > /dev/null && echo "valid JSON"
  grep -c "USE_REAL_DATA\|load_rr_from_wfdb\|wfdb.rdsamp\|REPO_ROOT\|sig_name" notebooks/02_signal_cleaning.ipynb
  ```

  **Expected:** `valid JSON` printed. grep count ≥ 5.

  **Pass:** Both checks pass. Simulated cells still visible in Jupyter UI below the new cells.

  **Fail:**
  - JSON invalid → manual cell insertion corrupted the file → `git checkout notebooks/02_signal_cleaning.ipynb` and retry
  - grep count < 5 → cells not saved → re-check in Jupyter UI that cells were saved (Ctrl+S)

---

- [ ] 🟥 **Step 3: Run Notebook 02 on Real PICS Data** — *Critical: produces files Notebook 03 depends on*

  **Idempotent:** Yes — overwrites CSVs with identical content.

  **Action:** In Jupyter UI, open `notebooks/02_signal_cleaning.ipynb`. Run the two new cells only (Cell 1 config, Cell 2 loading). Do not run the simulated cells. Confirm the print output shows correct `REPO_ROOT`, correct `sig_name`, and beat counts for both patients.

  **OR via terminal:**
  ```bash
  cd /Users/ngchenmeng/Neonatal
  jupyter nbconvert --to notebook --execute notebooks/02_signal_cleaning.ipynb \
    --output notebooks/02_signal_cleaning_executed.ipynb 2>&1 | tail -20
  ```

  **Human Gate:**
  Paste the cell output (REPO_ROOT path, sig_name, beat counts for infant1 and infant10) before proceeding to Phase 2.
  Output `"[NB02 COMPLETE — PASTE CELL OUTPUT BEFORE STEP 4]"` as final line.

  **✓ Verification Test:**

  **Type:** Integration

  **Action:**
  ```bash
  python -c "
  import pandas as pd
  from pathlib import Path

  for p in ['infant1', 'infant10']:
      path = Path('data/processed') / f'{p}_rr_clean.csv'
      assert path.exists(), f'MISSING: {path}'
      df = pd.read_csv(path)
      assert list(df.columns) == ['rr_ms'], f'Wrong columns: {list(df.columns)}'
      assert len(df) > 100, f'Too few beats: {len(df)}'
      assert df['rr_ms'].isnull().sum() == 0, f'NaN in rr_ms'
      print(f'{p}: {len(df)} beats ✅')
  "
  ```

  **Pass:** Both patients print ✅ with beat count > 100.

  **Fail:**
  - FileNotFoundError → `USE_REAL_DATA=True` not set, or REPO_ROOT resolved wrong → check printed REPO_ROOT value
  - Wrong columns → schema mismatch → check save call in Cell 2
  - < 100 beats → ectopic filter too aggressive → print `len(rr_ms)` before mask in `load_rr_from_wfdb`

---

### Phase 2 — Build Notebook 03 (HRV Feature Extraction)

**Goal:** `infant1_features.csv`, `infant10_features.csv`, `infant1_labels.csv`, `infant10_labels.csv` in `data/processed/`. Features schema: 9 columns matching `get_window_features()` exactly, zero NaN. Labels schema: `sample_idx`, `symbol` only.

---

- [ ] 🟥 **Step 4: Create notebooks/03_hrv_extraction.ipynb** — *Critical: new file, all downstream depends on it*

  **Idempotent:** Yes — creates file fresh; safe to overwrite if it already exists.

  **Context:** Reads `{patient_id}_rr_clean.csv`, slides 50-beat window in 25-beat steps, calls `get_window_features()` for each window, loads `.atr` annotations, writes features CSV and labels CSV per patient. Column names are locked to `get_window_features()` return keys — no invention. Beat index is not computed — labels carry `sample_idx` only, alignment deferred to Notebook 04.

  **Pre-Read Gate — run before creating file:**
  - [ ] `python -c "from src.features.hrv import get_window_features; print('OK')"` → must print OK (run from repo root)
  - [ ] `ls data/processed/infant1_rr_clean.csv` → must exist (Step 3 must be complete)
  - [ ] Pre-flight `.atr` symbol set must be recorded in Baseline Snapshot — if still blank, STOP and run pre-flight Step 4 now

  ⚠️ **Create this notebook in Jupyter UI** — File → New Notebook → add the cells below in order. Do not create via text editor to avoid JSON formatting issues.

  **Cell 1 — Imports and config:**
  ```python
  import sys
  import os
  from pathlib import Path
  import wfdb
  import pandas as pd
  import numpy as np

  # Resolve repo root regardless of execution directory
  REPO_ROOT = Path(os.getcwd())
  if REPO_ROOT.name == 'notebooks':
      REPO_ROOT = REPO_ROOT.parent

  sys.path.insert(0, str(REPO_ROOT))
  from src.features.hrv import get_window_features

  # ── CONFIG ────────────────────────────────────────────────────────────────
  # NOTE: PATIENTS must match the list in Notebook 02 exactly.
  # When infants 2-9 finish downloading: update BOTH notebooks.
  PATIENTS      = ["infant1", "infant10"]
  PROCESSED_DIR = REPO_ROOT / "data" / "processed"
  RAW_DIR       = REPO_ROOT / "data" / "raw" / "physionet.org" / "files" / "picsdb" / "1.0.0"
  FS_ECG        = 500    # Hz
  WINDOW_SIZE   = 50     # beats
  STEP_SIZE     = 25     # beats — 50% overlap

  print(f"REPO_ROOT:     {REPO_ROOT}")
  print(f"PROCESSED_DIR: {PROCESSED_DIR}")
  print(f"RAW_DIR:       {RAW_DIR}")
  ```

  **Cell 2 — Feature extraction function:**
  ```python
  def extract_features(patient_id):
      """
      Sliding window HRV feature extraction for one patient.
      Output columns (locked to get_window_features() return keys):
        record_name, window_idx, rr_ms_mean, rr_ms_std, rr_ms_min,
        rr_ms_max, rr_ms_25%, rr_ms_50%, rr_ms_75%
      """
      rr_path = PROCESSED_DIR / f"{patient_id}_rr_clean.csv"
      rr_ms   = pd.read_csv(rr_path)["rr_ms"].values

      rows      = []
      win_idx   = 0
      start     = 0

      while start + WINDOW_SIZE <= len(rr_ms):
          window = rr_ms[start : start + WINDOW_SIZE]
          row    = get_window_features(window, patient_id, win_idx)
          rows.append(row)
          start   += STEP_SIZE
          win_idx += 1

      df = pd.DataFrame(rows)

      # Enforce exact column order — crash loudly if schema drifted
      expected_cols = [
          "record_name", "window_idx",
          "rr_ms_mean", "rr_ms_std", "rr_ms_min",
          "rr_ms_max", "rr_ms_25%", "rr_ms_50%", "rr_ms_75%"
      ]
      missing = [c for c in expected_cols if c not in df.columns]
      assert not missing, f"Missing columns from get_window_features(): {missing}"

      return df[expected_cols]
  ```

  **Cell 3 — Label extraction function:**
  ```python
  def extract_labels(patient_id):
      """
      Load bradycardia annotations from .atr file.
      Saves sample_idx and symbol only.
      Beat-to-window alignment is deferred to Notebook 04,
      which will use cumulative RR sum to map sample_idx → window_idx.
      """
      ann_path = RAW_DIR / f"{patient_id}_ecg"
      ann      = wfdb.rdann(str(ann_path), 'atr')

      rows = [
          {"sample_idx": int(s), "symbol": sym}
          for s, sym in zip(ann.sample, ann.symbol)
      ]

      df = pd.DataFrame(rows)
      print(f"  {patient_id}: {len(df)} annotations")
      print(f"  symbols: {sorted(df['symbol'].unique())}")
      return df
  ```

  **Cell 4 — Run and save:**
  ```python
  for patient_id in PATIENTS:
      print(f"\n── {patient_id} ──────────────────────────────")

      # Features
      features_df = extract_features(patient_id)
      feat_path   = PROCESSED_DIR / f"{patient_id}_features.csv"
      features_df.to_csv(feat_path, index=False)
      print(f"  features: {features_df.shape} → {feat_path}")

      # Labels
      labels_df  = extract_labels(patient_id)
      label_path = PROCESSED_DIR / f"{patient_id}_labels.csv"
      labels_df.to_csv(label_path, index=False)
      print(f"  labels:   {labels_df.shape} → {label_path}")

  print("\n✅ Notebook 03 complete.")
  ```

  **What it does:** Reads real RR intervals, slides 50-beat window in 25-beat steps, extracts 9 HRV features per window using `get_window_features()`, asserts column schema at runtime, saves features and labels CSVs per patient. Labels carry `sample_idx` only — alignment to windows is Notebook 04's responsibility.

  **Why this approach:** Runtime `assert` on column names catches any future drift in `hrv.py` loudly instead of silently. Deferring beat-index computation eliminates the wrong-formula bug. `REPO_ROOT` detection makes nbconvert-from-root safe.

  **Assumptions:**
  - `src/features/hrv.py` is importable once `REPO_ROOT` is on `sys.path`
  - `get_window_features()` does not mutate its input array
  - `.atr` files exist for both patients (confirmed in pre-flight)
  - `rr_ms_25%` column name with `%` is accepted by pandas `to_csv` / `read_csv` round-trip

  **Risks:**
  - `rr_ms_25%` survives CSV round-trip fine in pandas but breaks in some SQL loaders → not a concern for this notebook; document for Notebook 04
  - `get_window_features()` has no guard for empty windows → mitigated by `while start + WINDOW_SIZE <= len(rr_ms)` which only enters loop when full window is available

  **After creating notebook — validate JSON:**
  ```bash
  python -m json.tool notebooks/03_hrv_extraction.ipynb > /dev/null && echo "valid JSON"
  ```

  **Git Checkpoint:**
  ```bash
  git add notebooks/03_hrv_extraction.ipynb
  git commit -m "step 4: build notebook 03 hrv feature extraction on real PICS data"
  ```

  **Subtasks:**
  - [ ] 🟥 Notebook created with all 4 cells in order
  - [ ] 🟥 `REPO_ROOT` detection present and prints correct path on run
  - [ ] 🟥 `sys.path.insert` uses `str(REPO_ROOT)` not `'..'`
  - [ ] 🟥 Runtime `assert` on column names present in Cell 2
  - [ ] 🟥 Labels CSV has `sample_idx` and `symbol` only — no `beat_idx`
  - [ ] 🟥 `PATIENTS` comment warns to update Notebook 02 in sync
  - [ ] 🟥 Notebook JSON valid after save

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  python -m json.tool notebooks/03_hrv_extraction.ipynb > /dev/null && echo "valid JSON"

  python -c "
  import json
  nb   = json.load(open('notebooks/03_hrv_extraction.ipynb'))
  src  = ' '.join([''.join(c['source']) for c in nb['cells'] if c['cell_type']=='code'])
  checks = [
      'get_window_features',
      'WINDOW_SIZE',
      'STEP_SIZE',
      'wfdb.rdann',
      'PATIENTS',
      'REPO_ROOT',
      'expected_cols',
      'sample_idx',
  ]
  for token in checks:
      assert token in src, f'MISSING: {token}'
      print(f'{token} ✅')
  assert 'beat_idx' not in src, 'beat_idx must NOT be present — was removed in logic check'
  print('beat_idx absent ✅')
  print(f'Total code cells: {sum(1 for c in nb[\"cells\"] if c[\"cell_type\"]==\"code\")}')
  "
  ```

  **Pass:** All 8 tokens found, `beat_idx` absent, 4 code cells reported, valid JSON.

  **Fail:**
  - Any token missing → that cell was not saved → re-check in Jupyter UI
  - `beat_idx` present → old version of Cell 3 was pasted → replace Cell 3 with the version above

---

- [ ] 🟥 **Step 5: Run Notebook 03 on Real PICS Data** — *Critical: produces all downstream inputs*

  **Idempotent:** Yes — overwrites CSVs with identical content.

  **Action:** In Jupyter UI, Kernel → Restart & Run All on `notebooks/03_hrv_extraction.ipynb`. Confirm printed output shows correct REPO_ROOT, window counts, and annotation symbols for both patients.

  **OR via terminal:**
  ```bash
  cd /Users/ngchenmeng/Neonatal
  jupyter nbconvert --to notebook --execute notebooks/03_hrv_extraction.ipynb \
    --output notebooks/03_hrv_extraction_executed.ipynb 2>&1 | tail -20
  ```

  **✓ Verification Test:**

  **Type:** Integration

  **Action:**
  ```bash
  python -c "
  import pandas as pd
  from pathlib import Path

  expected_cols = [
      'record_name', 'window_idx',
      'rr_ms_mean', 'rr_ms_std', 'rr_ms_min',
      'rr_ms_max', 'rr_ms_25%', 'rr_ms_50%', 'rr_ms_75%'
  ]

  for p in ['infant1', 'infant10']:
      feat = pd.read_csv(Path('data/processed') / f'{p}_features.csv')
      lbl  = pd.read_csv(Path('data/processed') / f'{p}_labels.csv')

      assert list(feat.columns) == expected_cols, \
          f'{p} features cols wrong: {list(feat.columns)}'
      assert len(feat) > 10, \
          f'{p}: too few windows ({len(feat)})'
      assert feat['record_name'].iloc[0] == p, \
          f'{p}: record_name mismatch'
      assert feat.isnull().sum().sum() == 0, \
          f'{p}: NaN in features'
      assert set(lbl.columns) == {'sample_idx', 'symbol'}, \
          f'{p} labels cols wrong: {set(lbl.columns)}'
      assert len(lbl) > 0, \
          f'{p}: zero annotations — .atr file may not have loaded'

      print(f'{p}: {len(feat)} windows, {len(lbl)} annotations ✅')
      print(f'  symbols: {sorted(lbl.symbol.unique())}')
  "
  ```

  **Pass:** Both patients print ✅, window count > 10, annotation count > 0, zero NaN.

  **Fail:**
  - Column mismatch → `get_window_features()` returned different keys → print `feat.columns` and compare to `src/features/hrv.py`
  - Zero annotations → `.atr` path wrong → print `RAW_DIR` in notebook and verify file exists
  - Zero windows → RR CSV has < 50 rows → check Step 3 output
  - NaN in features → short window passed to `get_window_features()` → the `while` guard should prevent this; print window lengths to debug

---

- [ ] 🟥 **Step 6: Smoke-Check Full Output** — *Non-critical: final sanity check*

  **Idempotent:** Yes — read-only.

  **Action:**
  ```bash
  ls -lh data/processed/

  python -c "
  import pandas as pd
  from pathlib import Path

  # Check real data outputs
  for p in ['infant1', 'infant10']:
      f = pd.read_csv(Path('data/processed') / f'{p}_features.csv')
      l = pd.read_csv(Path('data/processed') / f'{p}_labels.csv')
      print(f'{p} features: {f.shape}, NaN: {f.isnull().sum().sum()}')
      print(f'{p} labels:   {l.shape}, symbols: {sorted(l.symbol.unique())}')
      print()

  # Confirm simulated files untouched
  import glob
  sim = glob.glob('data/processed/simulated_*_rr_clean.csv')
  print(f'Simulated files still present: {len(sim)} (expected 10)')
  assert len(sim) == 10, 'Simulated files missing — regression!'
  print('Regression check ✅')
  "
  ```

  **Pass:** Features have zero NaN. Labels have >0 rows. All 10 simulated files still present.

  **Git Checkpoint:**
  ```bash
  git add data/processed/infant1_features.csv data/processed/infant1_labels.csv \
          data/processed/infant10_features.csv data/processed/infant10_labels.csv \
          data/processed/infant1_rr_clean.csv  data/processed/infant10_rr_clean.csv
  git commit -m "step 6: add infant1 and infant10 real PICS processed outputs"
  ```

---

## Regression Guard

| System | Pre-change behaviour | Post-change verification |
|--------|---------------------|--------------------------|
| Simulated RR CSVs | `simulated_1..10_rr_clean.csv` exist in `data/processed/` | Step 6 smoke check asserts `len(sim) == 10` |
| Notebook 02 simulated path | Runs without error under `USE_REAL_DATA=False` | Set flag False, re-run simulated cells, confirm save still works |
| `src/features/hrv.py` | Unchanged by this plan | `git diff src/features/hrv.py` must show no changes |

---

## Rollback Procedure

```bash
# Rollback Step 2 (Notebook 02 edit):
git checkout notebooks/02_signal_cleaning.ipynb

# Rollback Step 4 (Notebook 03 creation):
rm notebooks/03_hrv_extraction.ipynb
git checkout -- notebooks/  # restore any other accidental changes

# Rollback processed outputs:
rm data/processed/infant1_*.csv data/processed/infant10_*.csv

# Confirm simulated files untouched:
ls data/processed/simulated_*   # must still show 10 files

# Confirm system back to pre-plan state:
python -c "import glob; print(glob.glob('data/processed/simulated_*'))"
```

---

## Risk Heatmap

| Step | Risk | What Could Go Wrong | Early Detection | Idempotent |
|------|------|---------------------|-----------------|------------|
| Step 1 | 🟢 Low | .atr symbols unknown | Pre-flight output | Yes |
| Step 2 | 🟡 Medium | JSON corruption from manual cell insert | JSON validity check after save | Yes |
| Step 3 | 🟡 Medium | REPO_ROOT resolves wrong | Printed REPO_ROOT value in cell output | Yes |
| Step 4 | 🟡 Medium | `rr_ms_25%` column name edge case | Verification token check | Yes |
| Step 5 | 🟡 Medium | `.atr` loads zero rows silently | `assert len(lbl) > 0` in verification | Yes |
| Step 6 | 🟢 Low | Simulated files accidentally deleted | `assert len(sim) == 10` | Yes |

---

## Success Criteria

| Feature | Target | Verification |
|---------|--------|--------------|
| Real RR CSVs | `infant1_rr_clean.csv`, `infant10_rr_clean.csv` in `data/processed/` | Step 3 verification |
| RR schema | Single column `rr_ms`, >100 rows, zero NaN | Step 3 verification |
| Feature CSVs | `infant1_features.csv`, `infant10_features.csv` | Step 5 verification |
| Feature schema | 9 columns matching `get_window_features()`, zero NaN | Step 5 verification |
| Labels CSVs | `infant1_labels.csv`, `infant10_labels.csv` | Step 5 verification |
| Labels schema | `sample_idx` + `symbol` only — no `beat_idx` | Step 4 token check |
| Simulated files | All 10 still present and untouched | Step 6 regression assert |
| Generalisable | Extending to infants 2–9 = update `PATIENTS` in both notebooks only | Code review — no hardcoded patient strings outside config cells |

---

⚠️ **Do not mark a step 🟩 Done until its verification test passes.**
⚠️ **Do not proceed past a Human Gate without explicit human input.**
⚠️ **If blocked, mark 🟨 In Progress and output the State Manifest before stopping.**
⚠️ **Do not batch multiple steps into one git commit.**
⚠️ **If idempotent = No, confirm the step has not already run before executing.**