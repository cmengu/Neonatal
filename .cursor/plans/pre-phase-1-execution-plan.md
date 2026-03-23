# Pre-Phase 1 Execution Plan — Extend HRV Feature Extraction

**Overall Progress:** `0% (0/7 steps complete)`

---

## TLDR

Extends the HRV feature extractor (`src/features/hrv.py`) to output clinically named metrics — RMSSD, SDNN, pNN50, LF/HF ratio — in addition to the existing statistical features. Propagates the new column names through `run_nb03.py` and `run_nb04.py`, regenerates all processed feature CSVs, and builds a labelled training dataset (`combined_features_labelled.csv`) for Phase 1 classifier training. After this plan executes, `infant{N}_features.csv` contains 10 clinical HRV columns and `combined_features_labelled.csv` is ready to be consumed by `src/models/train_classifier.py`.

---

## Critical Decisions

- **Rename `rr_ms_mean` → `mean_rr` and `rr_ms_std` → `sdnn`:** SDNN is by definition `std(RR intervals)`, so `rr_ms_std` was already SDNN — renaming for clinical alignment throughout.
- **Keep existing percentile/min/max columns:** `rr_ms_min`, `rr_ms_max`, `rr_ms_25%`, `rr_ms_50%`, `rr_ms_75%` are retained unchanged. These names appear in `run_nb04.py` `HRV_COLS` and must stay consistent across both scripts.
- **LF/HF via Welch PSD:** Computed by resampling the RR series to 4 Hz uniform grid, then integrating LF (0.04–0.15 Hz) and HF (0.15–0.40 Hz) bands. Falls back to `1.0` for windows shorter than 20 beats.
- **`get_serie_describe` removed:** Only `run_nb03.py` consumes `src/features/hrv.py` (via `get_window_features`). The old helper is not used externally. Removing it keeps the module clean.

---

## Clarification Gate

| Unknown | Required | Source | Blocking | Resolved |
|---------|----------|--------|----------|----------|
| All files importing `src/features/hrv.py` | Confirm no other consumer of `get_serie_describe` | codebase grep | Step 1 | ✅ — only `run_nb03.py` imports `get_window_features`; nothing imports `get_serie_describe` externally |
| Exact `HRV_COLS` in `run_nb04.py` | Anchor string for replacement | codebase read | Step 3 | ✅ — lines 28–31: `"rr_ms_mean", "rr_ms_std", "rr_ms_min", "rr_ms_max", "rr_ms_25%", "rr_ms_50%", "rr_ms_75%"` |
| Exact `expected_cols` in `run_nb03.py` | Anchor string for replacement | codebase read | Step 2 | ✅ — lines 54–61: same 7 columns plus `record_name`, `window_idx` |
| Patient IDs with existing `_rr_clean.csv` | Confirm all 10 exist before re-running scripts | filesystem | Steps 5–6 | ✅ — PATIENTS = `infant1`–`infant10`, confirmed from `run_nb03.py` line 27 |

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
# 1. Confirm the two functions currently defined in src/features/hrv.py
grep -n "^def " src/features/hrv.py

# 2. Confirm get_window_features signature
grep -n "def get_window_features" src/features/hrv.py

# 3. Confirm every file that imports from src/features/hrv
grep -rn "from src.features.hrv import" .
grep -rn "import src.features.hrv" .

# 4. Confirm expected_cols anchor in run_nb03.py (must return exactly 1 match)
grep -n "rr_ms_mean.*rr_ms_std" scripts/run_nb03.py

# 5. Confirm HRV_COLS anchor in run_nb04.py (must return exactly 1 match)
grep -n "HRV_COLS" scripts/run_nb04.py

# 6. Confirm HRV_COLS definition anchor in generate_nb04.py cell1 (must return exactly 1 match)
# Note: grep for "HRV_COLS" returns 2 matches (definition + usage in cell3) — use specific anchor instead
grep -n '"rr_ms_mean", "rr_ms_std", "rr_ms_min"' scripts/generate_nb04.py

# 7. Confirm all 10 rr_clean files exist
ls data/processed/infant*_rr_clean.csv | wc -l

# 8. Confirm all 10 _labels.csv files exist (required by run_nb04.py — these come from raw WFDB data)
ls data/processed/*_labels.csv | wc -l

# 9. Confirm raw WFDB annotations exist for at least infant1 (proxy for all raw data)
ls data/raw/physionet.org/files/picsdb/1.0.0/infant1_ecg.atr

# 10. Confirm first_r_peaks.csv exists (required by run_nb04.py)
ls data/processed/first_r_peaks.csv

# 11. Check NumPy version — np.trapz removed in 2.0; plan uses scipy.integrate.trapezoid instead
python -c "import numpy; print('NumPy:', numpy.__version__)"

# 12. Confirm scipy.integrate.trapezoid is available (scipy >= 1.7.0)
python -c "from scipy.integrate import trapezoid; print('scipy.integrate.trapezoid: ok')"

# 13. Record current line counts
wc -l src/features/hrv.py scripts/run_nb03.py scripts/run_nb04.py scripts/generate_nb04.py
```

**Baseline Snapshot (agent fills during pre-flight):**
```
Functions in src/features/hrv.py:   ____
Imports of src/features/hrv:        ____  (files)
rr_clean files present:             ____ / 10
Line count src/features/hrv.py:     ____
Line count scripts/run_nb03.py:     ____
Line count scripts/run_nb04.py:     ____
Line count scripts/generate_nb04.py: ____
```

**Required checks (all must pass before Step 1):**
- [ ] `grep -n "^def " src/features/hrv.py` returns exactly 2 functions: `get_serie_describe`, `get_window_features`
- [ ] `grep -rn "from src.features.hrv import" .` returns exactly 1 file: `scripts/run_nb03.py`
- [ ] `grep -n "rr_ms_mean.*rr_ms_std" scripts/run_nb03.py` returns exactly 1 match (line ~55)
- [ ] `grep -n "HRV_COLS" scripts/run_nb04.py` returns exactly 1 match (line ~28)
- [ ] `ls data/processed/infant*_rr_clean.csv | wc -l` returns `10`
- [ ] `ls data/processed/*_labels.csv | wc -l` returns `10`
- [ ] `ls data/raw/physionet.org/files/picsdb/1.0.0/infant1_ecg.atr` exits 0 (raw data present)
- [ ] `python -c "from scipy.integrate import trapezoid"` exits 0
- [ ] `ls data/processed/first_r_peaks.csv` exists
- [ ] `python -c "from scipy.integrate import trapezoid"` exits 0 (covers NumPy 2.0 risk — `np.trapz` was removed; plan uses `scipy.integrate.trapezoid` exclusively)

---

## Steps Analysis

```
Step 1 (rewrite src/features/hrv.py)         — Critical   (shared module; changes keys returned by get_window_features)  — Full code review — Idempotent: Yes
Step 2 (update run_nb03.py expected_cols)    — Critical   (assertion + column filter; wrong names crash the run)         — Full code review — Idempotent: Yes
Step 3 (update run_nb04.py HRV_COLS)         — Critical   (determines deviation columns written to _windowed.csv)        — Full code review — Idempotent: Yes
Step 4 (update generate_nb04.py HRV_COLS)   — Non-critical (generates Jupyter notebook, secondary to script runner)     — Verification only — Idempotent: Yes
Step 5 (run scripts/run_nb03.py)             — Critical   (regenerates all _features.csv; steps 6–7 depend on it)       — Verification only — Idempotent: Yes
Step 6 (run scripts/run_nb04.py)             — Critical   (regenerates all _windowed.csv; step 7 depends on it)         — Verification only — Idempotent: Yes
Step 7 (create + run build_training_data.py) — Non-critical (new file; produces combined_features_labelled.csv)         — Verification only — Idempotent: Yes
```

---

## Tasks

### Phase 1 — Code changes (Steps 1–4)

**Goal:** All three scripts have consistent, clinically named column definitions. No scripts have been run yet.

---

- [ ] 🟥 **Step 1: Rewrite `src/features/hrv.py`** — *Critical: sole source of HRV feature keys consumed by run_nb03.py*

  **Idempotent:** Yes — overwrites the file; re-running produces identical output.

  **Context:** `get_window_features` currently delegates to `get_serie_describe`, which wraps `pd.DataFrame.describe()` to produce 7 keys prefixed `rr_ms_`. The new implementation replaces both functions with `compute_hrv_features` (time-domain + frequency-domain) and `_compute_lf_hf` (Welch PSD). `get_window_features` signature is unchanged — same 3 arguments, same dict-with-metadata return — so `run_nb03.py`'s import requires no update.

  **Pre-Read Gate:**
  - Run `grep -rn "from src.features.hrv import" .` — must return exactly `scripts/run_nb03.py`. If any other file appears → STOP and report.
  - Run `grep -rn "get_serie_describe" .` — must return only matches inside `src/features/hrv.py` itself (no external callers). If any external caller found → STOP and report.

  ```python
  # src/features/hrv.py
  """
  HRV feature extraction for neonatal sepsis pipeline.

  Computes time-domain and frequency-domain HRV metrics from windowed RR intervals.
  Time-domain:       mean_rr, sdnn, rmssd, pnn50
  Frequency-domain:  lf_hf_ratio  (Welch PSD, LF 0.04–0.15 Hz / HF 0.15–0.40 Hz)
  Statistical:       rr_ms_min, rr_ms_max, rr_ms_25%, rr_ms_50%, rr_ms_75%
  """
  import numpy as np
  from scipy import signal, interpolate
  from scipy.integrate import trapezoid as _trapz


  def _compute_lf_hf(rr_ms: np.ndarray, fs_resample: float = 4.0) -> float:
      """
      Compute LF/HF power ratio from RR intervals (ms).

      Resamples the RR series onto a uniform 4 Hz grid using linear interpolation,
      then estimates PSD via Welch's method and integrates over LF and HF bands.
      Returns 1.0 (neutral) for windows too short for reliable estimation (< 20 beats).
      """
      rr = np.asarray(rr_ms, dtype=np.float64)
      if len(rr) < 20:
          return 1.0

      t_rr = np.cumsum(rr / 1000.0)
      t_rr = np.insert(t_rr, 0, 0.0)[:-1]

      t_uniform = np.arange(t_rr[0], t_rr[-1], 1.0 / fs_resample)
      if len(t_uniform) < 16:
          return 1.0

      f_interp = interpolate.interp1d(
          t_rr, rr, kind="linear", bounds_error=False, fill_value="extrapolate"
      )
      rr_uniform = f_interp(t_uniform)
      rr_uniform = rr_uniform - rr_uniform.mean()

      nperseg = min(len(rr_uniform), 256)
      freqs, psd = signal.welch(rr_uniform, fs=fs_resample, nperseg=nperseg)

      lf_mask = (freqs >= 0.04) & (freqs < 0.15)
      hf_mask = (freqs >= 0.15) & (freqs < 0.40)

      lf_power = float(_trapz(psd[lf_mask], freqs[lf_mask])) if lf_mask.any() else 0.0
      hf_power = float(_trapz(psd[hf_mask], freqs[hf_mask])) if hf_mask.any() else 0.0

      return float(lf_power / max(hf_power, 1e-9))


  def compute_hrv_features(rr_ms: np.ndarray) -> dict:
      """
      Compute all HRV features from a 1D array of RR intervals (ms).

      Returns a flat dict with keys:
        mean_rr, sdnn, rmssd, pnn50, lf_hf_ratio,
        rr_ms_min, rr_ms_max, rr_ms_25%, rr_ms_50%, rr_ms_75%

      Raises
      ------
      ValueError
          If rr_ms is empty.
      """
      rr = np.asarray(rr_ms, dtype=np.float64)
      n = len(rr)
      if n == 0:
          raise ValueError("rr_ms cannot be empty")

      mean_rr = float(np.mean(rr))
      sdnn    = float(np.std(rr, ddof=1)) if n > 1 else 0.0
      rmssd   = float(np.sqrt(np.mean(np.diff(rr) ** 2))) if n > 1 else 0.0
      pnn50   = float(np.sum(np.abs(np.diff(rr)) > 50) / max(n - 1, 1) * 100) if n > 1 else 0.0
      lf_hf   = _compute_lf_hf(rr)

      return {
          "mean_rr":     mean_rr,
          "sdnn":        sdnn,
          "rmssd":       rmssd,
          "pnn50":       pnn50,
          "lf_hf_ratio": lf_hf,
          "rr_ms_min":   float(np.min(rr)),
          "rr_ms_max":   float(np.max(rr)),
          "rr_ms_25%":   float(np.percentile(rr, 25)),
          "rr_ms_50%":   float(np.percentile(rr, 50)),
          "rr_ms_75%":   float(np.percentile(rr, 75)),
      }


  def get_window_features(rr_intervals: np.ndarray, record_name: str, window_idx: int) -> dict:
      """
      Encode a window of RR intervals with record metadata for feature matrix rows.

      Parameters
      ----------
      rr_intervals : np.ndarray
          1D array of RR intervals in milliseconds for this window.
      record_name : str
          Infant record identifier (e.g. 'infant1').
      window_idx : int
          Index of this window within the recording.

      Returns
      -------
      dict
          Feature dict with record_name, window_idx, plus all keys from compute_hrv_features().
      """
      features = compute_hrv_features(rr_intervals)
      features["record_name"] = record_name
      features["window_idx"]  = window_idx
      return features
  ```

  **What it does:** Replaces `get_serie_describe` + `get_window_features` with `_compute_lf_hf`, `compute_hrv_features`, and an updated `get_window_features` that now outputs 10 clinical HRV features instead of 7 statistical ones.

  **Why this approach:** Keeps the public function signature of `get_window_features` identical so the single consumer (`run_nb03.py` line 21) requires no import change. `scipy` is already installed as a transitive dependency of `neurokit2`.

  **Assumptions:**
  - `scipy` is installed in the active Python environment.
  - No external code calls `get_serie_describe` directly (confirmed in pre-read gate).

  **Risks:**
  - `scipy` not installed → `ImportError` at module load → mitigation: `pip install scipy` before running.
  - `np.trapz` was removed in NumPy 2.0 → resolved by using `scipy.integrate.trapezoid` (aliased as `_trapz`), which is stable across all scipy >= 1.7.0 versions. Pre-flight confirms availability.
  - LF/HF = 0.0 on constant-RR windows (all-zeros signal after detrend → zero PSD everywhere). This is mathematically correct but semantically "unknown". The deviation guard in `run_nb04.py` (`roll_std == 0 → 0.0`) handles this correctly at the downstream level.

  **Git Checkpoint:**
  ```bash
  git add src/features/hrv.py
  git commit -m "step 1: replace hrv.py with clinical HRV features (rmssd, sdnn, pnn50, lf_hf_ratio)"
  ```

  **Subtasks:**
  - [ ] 🟥 Pre-read gate passed (no external callers of `get_serie_describe`)
  - [ ] 🟥 File written
  - [ ] 🟥 Verification test passes

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  python -c "
  import numpy as np
  from src.features.hrv import get_window_features, compute_hrv_features
  rr = np.array([400.0] * 50)
  feats = compute_hrv_features(rr)
  expected_keys = {'mean_rr','sdnn','rmssd','pnn50','lf_hf_ratio','rr_ms_min','rr_ms_max','rr_ms_25%','rr_ms_50%','rr_ms_75%'}
  missing = expected_keys - set(feats.keys())
  assert not missing, f'Missing keys: {missing}'
  row = get_window_features(rr, 'infant1', 0)
  assert 'record_name' in row and 'window_idx' in row
  assert 'rr_ms_mean' not in row, 'OLD key rr_ms_mean still present'
  assert 'rr_ms_std' not in row, 'OLD key rr_ms_std still present'
  rr_var = np.array([380.0, 410.0, 395.0, 420.0, 385.0] * 10)
  feats_var = compute_hrv_features(rr_var)
  assert feats_var['lf_hf_ratio'] > 0, f'LF/HF is zero on variable RR — Welch computation failed (got {feats_var[\"lf_hf_ratio\"]})'
  print('PASS: all 10 keys present, old keys absent, LF/HF > 0 on variable RR')
  print('Keys:', sorted(feats.keys()))
  "
  ```

  **Expected:**
  - Prints `PASS: all 10 keys present, old keys absent`
  - Prints `Keys:` list containing `lf_hf_ratio`, `mean_rr`, `pnn50`, `rmssd`, `rr_ms_25%`, `rr_ms_50%`, `rr_ms_75%`, `rr_ms_max`, `rr_ms_min`, `sdnn`
  - `rr_ms_mean` and `rr_ms_std` are confirmed absent

  **Observe:** stdout

  **Pass:** Line `PASS: all 10 keys present, old keys absent, LF/HF > 0 on variable RR` printed without exception.

  **Fail:**
  - `ImportError: cannot import name 'compute_hrv_features'` → file not saved correctly → re-read `src/features/hrv.py`
  - `ImportError: No module named 'scipy'` → `pip install scipy`, then re-run
  - `AssertionError: OLD key rr_ms_mean still present` → file still contains old `get_serie_describe` logic → check file was fully overwritten
  - `AssertionError: LF/HF is zero on variable RR` → Welch frequency axis, band bounds, or interpolation grid has a bug → re-read `_compute_lf_hf` and verify `lf_mask` and `hf_mask` cover non-empty ranges

---

- [ ] 🟥 **Step 2: Update `expected_cols` in `scripts/run_nb03.py`** — *Critical: assertion blocks execution if column names don't match*

  **Idempotent:** Yes — replacing a literal list; re-running is safe.

  **Context:** `extract_features()` in `run_nb03.py` (lines 54–61) hardcodes `expected_cols` for both an assertion check and column ordering. After Step 1, `get_window_features` returns different keys. This update makes the assertion match the new keys and preserves `record_name, window_idx` as the first two columns.

  **Pre-Read Gate:**
  - Run `grep -n "rr_ms_mean" scripts/run_nb03.py` — must return exactly 1 match (inside `expected_cols`, line ~55). If 0 or 2+ → STOP.
  - Run `grep -n "expected_cols" scripts/run_nb03.py` — must return exactly 3 matches (assignment, assert, return). If not 3 → STOP.

  **Anchor Uniqueness Check:**
  - Target block starts with `    expected_cols = [`
  - Must appear exactly 1 time in `scripts/run_nb03.py`, inside `extract_features()`
  - If outside `extract_features` → STOP regardless of match count

  Replace this block (lines 54–61):
  ```python
      expected_cols = [
          "record_name", "window_idx",
          "rr_ms_mean", "rr_ms_std", "rr_ms_min",
          "rr_ms_max", "rr_ms_25%", "rr_ms_50%", "rr_ms_75%"
      ]
      missing = [c for c in expected_cols if c not in df.columns]
      assert not missing, f"Missing columns: {missing}"
      return df[expected_cols]
  ```

  With:
  ```python
      expected_cols = [
          "record_name", "window_idx",
          "mean_rr", "sdnn", "rmssd", "pnn50", "lf_hf_ratio",
          "rr_ms_min", "rr_ms_max", "rr_ms_25%", "rr_ms_50%", "rr_ms_75%"
      ]
      missing = [c for c in expected_cols if c not in df.columns]
      assert not missing, f"Missing columns: {missing}"
      return df[expected_cols]
  ```

  **What it does:** Updates the column name list so the assertion and column-ordering `return` statement match the keys now produced by `get_window_features`.

  **Why this approach:** The assertion is a deliberate schema contract — keeping it means any future regression in `hrv.py` will be caught immediately at the per-patient loop, not silently at training time.

  **Assumptions:**
  - `expected_cols` block appears exactly once in `run_nb03.py`.

  **Risks:**
  - Edit applied to wrong location → mitigation: pre-read gate confirms single match inside `extract_features`.

  **Git Checkpoint:**
  ```bash
  git add scripts/run_nb03.py
  git commit -m "step 2: update run_nb03.py expected_cols to clinical HRV column names"
  ```

  **Subtasks:**
  - [ ] 🟥 Pre-read gate passed
  - [ ] 🟥 Edit applied
  - [ ] 🟥 Verification test passes

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  grep -n "rr_ms_mean\|rr_ms_std\|mean_rr\|rmssd" scripts/run_nb03.py
  ```

  **Expected:**
  - Lines containing `mean_rr`, `rmssd` present
  - No lines containing `rr_ms_mean` or `rr_ms_std`

  **Observe:** grep stdout

  **Pass:** Zero matches for `rr_ms_mean` and `rr_ms_std`; at least one match each for `mean_rr` and `rmssd`.

  **Fail:**
  - `rr_ms_mean` still appears → edit not applied → check the StrReplace matched the correct block

---

- [ ] 🟥 **Step 3: Update `HRV_COLS` in `scripts/run_nb04.py`** — *Critical: determines which columns are z-scored and written to `_windowed.csv`*

  **Idempotent:** Yes — replacing a literal list.

  **Context:** `compute_deviations()` iterates over `HRV_COLS` to read from `{patient_id}_features.csv`. After Step 5 runs `run_nb03.py`, `_features.csv` will contain the new column names. If `HRV_COLS` is not updated, `run_nb04.py` will raise `KeyError` on the first missing column.

  **Pre-Read Gate:**
  - Run `grep -n "^HRV_COLS = \[" scripts/run_nb04.py` — must return exactly 1 match (the list assignment, not the `for col in HRV_COLS` usage at line ~87). If 0 or 2+ → STOP.
  - Run `grep -n "rr_ms_mean" scripts/run_nb04.py` — must return exactly 1 match (inside the HRV_COLS list). If 0 or 2+ → STOP.

  Replace this block (lines 28–31):
  ```python
  HRV_COLS = [
      "rr_ms_mean", "rr_ms_std", "rr_ms_min",
      "rr_ms_max", "rr_ms_25%", "rr_ms_50%", "rr_ms_75%"
  ]
  ```

  With:
  ```python
  HRV_COLS = [
      "mean_rr", "sdnn", "rmssd", "pnn50", "lf_hf_ratio",
      "rr_ms_min", "rr_ms_max", "rr_ms_25%", "rr_ms_50%", "rr_ms_75%"
  ]
  ```

  **What it does:** Extends the deviation-column list from 7 to 10 columns, adding `rmssd_dev`, `sdnn_dev`, `pnn50_dev`, `lf_hf_ratio_dev` to the windowed output. The `_windowed.csv` deviation column names are derived automatically as `f"{col}_dev"` so no other code in `run_nb04.py` needs changing.

  **Risks:**
  - `rr_ms_mean_dev` column removed from `_windowed.csv` → any downstream code reading that column would break → mitigation: no current downstream consumers read `_windowed.csv` except `build_training_data.py` (created in Step 7).

  **Git Checkpoint:**
  ```bash
  git add scripts/run_nb04.py
  git commit -m "step 3: update run_nb04.py HRV_COLS to clinical HRV column names"
  ```

  **Subtasks:**
  - [ ] 🟥 Pre-read gate passed
  - [ ] 🟥 Edit applied
  - [ ] 🟥 Verification test passes

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  grep -n "rr_ms_mean\|rr_ms_std\|mean_rr\|rmssd" scripts/run_nb04.py
  ```

  **Expected:**
  - Lines containing `mean_rr`, `rmssd` present inside `HRV_COLS`
  - No lines containing `rr_ms_mean` or `rr_ms_std`

  **Pass:** Zero matches for `rr_ms_mean`, `rr_ms_std`; matches for `mean_rr`, `rmssd`.

  **Fail:**
  - `rr_ms_mean` still appears → edit not applied or wrong target

---

- [ ] 🟥 **Step 4: Update `scripts/generate_nb04.py` — `HRV_COLS` in `cell1` and `rr_ms_mean_dev` references in `cell5`** — *Non-critical: regenerates the Jupyter notebook; scripts are authoritative runners*

  **Idempotent:** Yes — replacing literal strings.

  **Context:** `generate_nb04.py` generates `notebooks/04_baseline_deviation.ipynb` via 5 cell strings (`cell1`–`cell5`). Two things need updating:
  1. `cell1` defines `HRV_COLS` with old column names — must be updated to new names.
  2. `cell5` hardcodes three references to `rr_ms_mean_dev` (lines 205, 207, 211 of the file) — must be updated to `mean_rr_dev`. After Step 6, `_windowed.csv` no longer contains `rr_ms_mean_dev`. If `cell5` is not updated, running `python scripts/generate_nb04.py` produces a notebook that crashes in cell5 with `KeyError: 'rr_ms_mean_dev'`.

  This step makes **4 distinct replacements** in the same file. Execute them in the order listed below.

  ---

  **Replacement 4a — `cell1` HRV_COLS:**

  **Pre-Read Gate:**
  - Run `grep -n '"rr_ms_mean", "rr_ms_std", "rr_ms_min"' scripts/generate_nb04.py` — must return exactly 1 match (inside `cell1`). If 0 or 2+ → STOP.

  Replace:
  ```python
  HRV_COLS = [
      "rr_ms_mean", "rr_ms_std", "rr_ms_min",
      "rr_ms_max", "rr_ms_25%", "rr_ms_50%", "rr_ms_75%"
  ]
  ```

  With:
  ```python
  HRV_COLS = [
      "mean_rr", "sdnn", "rmssd", "pnn50", "lf_hf_ratio",
      "rr_ms_min", "rr_ms_max", "rr_ms_25%", "rr_ms_50%", "rr_ms_75%"
  ]
  ```

  ---

  **Replacement 4b — `cell5` plot line:**

  **Pre-Read Gate:**
  - Run `grep -n 'rr_ms_mean_dev' scripts/generate_nb04.py` — must return exactly 3 matches (lines ~205, 207, 211). If any other count → STOP.

  Replace:
  ```python
      ax.plot(df["window_idx"], df["rr_ms_mean_dev"], linewidth=0.8, color="steelblue")
  ```

  With:
  ```python
      ax.plot(df["window_idx"], df["mean_rr_dev"], linewidth=0.8, color="steelblue")
  ```

  **Intermediate check after 4b:**
  ```bash
  grep -c "rr_ms_mean_dev" scripts/generate_nb04.py
  ```
  Must return `2`. If it returns 3, Replacement 4b was not applied. If it returns 1 or 0, something else already changed — STOP and report.

  ---

  **Replacement 4c — `cell5` scatter line:**

  Replace:
  ```python
      ax.scatter(pos["window_idx"], pos["rr_ms_mean_dev"],
  ```

  With:
  ```python
      ax.scatter(pos["window_idx"], pos["mean_rr_dev"],
  ```

  ---

  **Intermediate check after 4c:**
  ```bash
  grep -c "rr_ms_mean_dev" scripts/generate_nb04.py
  ```
  Must return `1`. If it returns 2, Replacement 4c was not applied. If it returns 0, something else already changed — STOP and report.

  ---

  **Replacement 4d — `cell5` ylabel string:**

  Replace:
  ```python
      ax.set_ylabel("rr_ms_mean_dev", fontsize=7)
  ```

  With:
  ```python
      ax.set_ylabel("mean_rr_dev", fontsize=7)
  ```

  ---

  **Git Checkpoint:**
  ```bash
  git add scripts/generate_nb04.py
  git commit -m "step 4: update generate_nb04.py HRV_COLS and cell5 column references to new names"
  ```

  **Subtasks:**
  - [ ] 🟥 Replacement 4a applied (HRV_COLS in cell1)
  - [ ] 🟥 Replacements 4b–4d applied (rr_ms_mean_dev → mean_rr_dev in cell5)
  - [ ] 🟥 Verification test passes

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  grep -n "rr_ms_mean\|rr_ms_std\|rr_ms_mean_dev" scripts/generate_nb04.py
  ```

  **Expected:** Zero output (no matches for any old name).

  **Pass:** Command returns nothing.

  **Fail:**
  - `rr_ms_mean` still appears → Replacement 4a not applied → confirm anchor `'"rr_ms_mean", "rr_ms_std", "rr_ms_min"'` exists exactly once
  - `rr_ms_mean_dev` still appears → one or more of Replacements 4b–4d not applied → grep the file to find which line remains

---

### Phase 2 — Data regeneration (Steps 5–7)

**Goal:** All 10 `infant{N}_features.csv` files contain the 10 clinical HRV columns. All 10 `infant{N}_windowed.csv` files contain deviation columns for those features plus `label`. `combined_features_labelled.csv` exists and is ready for the Phase 1 classifier.

---

- [ ] 🟥 **Step 5: Run `scripts/run_nb03.py`** — *Critical: regenerates all `_features.csv`; Step 6 depends on these files*

  **Idempotent:** Yes — overwrites existing CSVs; re-running produces identical output.

  **Context:** Step 1 changed what `get_window_features` returns. Running `run_nb03.py` now regenerates `data/processed/infant{N}_features.csv` for all 10 patients with the 10 new column names. Note: `run_nb03.py` also regenerates `{patient_id}_labels.csv` for each patient — Step 6 depends on these files being current.

  **Pre-Read Gate:**
  - Confirm Steps 1–4 are all committed: `git log --oneline -4` shows all 4 commits for steps 1–4.
  - Confirm `scipy` is importable: `python -c "from scipy import signal; print('ok')"`.
  - Confirm `logs/` directory exists: `ls -d logs/ || mkdir -p logs`.

  **Action:**
  ```bash
  python scripts/run_nb03.py 2>&1 | tee logs/run_nb03_rerun.log
  ```

  **Expected runtime:** 2–10 minutes (reads RR intervals from existing `_rr_clean.csv` files, no ECG re-processing).

  **Git Checkpoint:**
  ```bash
  git add data/processed/infant*_features.csv
  git commit -m "step 5: regenerate _features.csv with clinical HRV columns (rmssd, sdnn, pnn50, lf_hf_ratio)"
  ```

  **✓ Verification Test:**

  **Type:** Integration

  **Action:**
  ```bash
  python -c "
  import pandas as pd
  from pathlib import Path

  PROCESSED = Path('data/processed')
  EXPECTED = {'mean_rr','sdnn','rmssd','pnn50','lf_hf_ratio',
               'rr_ms_min','rr_ms_max','rr_ms_25%','rr_ms_50%','rr_ms_75%'}
  failures = []
  for i in range(1, 11):
      path = PROCESSED / f'infant{i}_features.csv'
      if not path.exists():
          failures.append(f'infant{i}: file missing')
          continue
      df = pd.read_csv(path)
      missing = EXPECTED - set(df.columns)
      old = {'rr_ms_mean','rr_ms_std'} & set(df.columns)
      if missing:
          failures.append(f'infant{i}: missing {missing}')
      if old:
          failures.append(f'infant{i}: OLD columns still present {old}')

  if failures:
      print('FAIL:')
      for f in failures: print(' ', f)
  else:
      print(f'PASS: all 10 patients have correct columns')
      sample = pd.read_csv(PROCESSED / 'infant1_features.csv')
      print(f'  infant1 shape: {sample.shape}')
      print(f'  columns: {list(sample.columns)}')
  "
  ```

  **Expected:** Prints `PASS: all 10 patients have correct columns` with shape and column list.

  **Pass:** `PASS` line printed, no `FAIL` lines.

  **Fail:**
  - `infant{N}: file missing` → `run_nb03.py` skipped that patient (FileNotFoundError on `_rr_clean.csv`) → check logs for warning
  - `infant{N}: missing {cols}` → Step 1 edit not correctly written — re-read `src/features/hrv.py` and verify `compute_hrv_features` returns the correct keys
  - `infant{N}: OLD columns still present` → Step 1 was not applied or old features file was not overwritten

---

- [ ] 🟥 **Step 6: Run `scripts/run_nb04.py`** — *Critical: regenerates all `_windowed.csv` with new deviation columns + labels*

  **Idempotent:** Yes — overwrites existing CSVs.

  **Context:** `compute_deviations()` now iterates the 10-column `HRV_COLS` (from Step 3), reading from the freshly regenerated `_features.csv` files (from Step 5). Output files gain `rmssd_dev`, `sdnn_dev`, `pnn50_dev`, `lf_hf_ratio_dev` and lose `rr_ms_mean_dev`, `rr_ms_std_dev`.

  **Pre-Read Gate:**
  - Confirm Step 5 verification passed (all 10 `_features.csv` have `rmssd` column).
  - Confirm Steps 1–4 are all committed: `git log --oneline | head -4` should show all four step commits.
  - Confirm `logs/` directory exists: `ls -d logs/ || mkdir -p logs`.

  **Action:**
  ```bash
  python scripts/run_nb04.py 2>&1 | tee logs/run_nb04_rerun.log
  ```

  **Expected runtime:** Under 1 minute (pure pandas operations on already-processed RR data).

  **Git Checkpoint:**
  ```bash
  git add data/processed/infant*_windowed.csv data/processed/all_patients_windowed.csv
  git commit -m "step 6: regenerate _windowed.csv with clinical HRV deviation columns"
  ```

  **✓ Verification Test:**

  **Type:** Integration

  **Action:**
  ```bash
  python -c "
  import pandas as pd
  from pathlib import Path

  PROCESSED = Path('data/processed')
  EXPECTED_DEV = {'mean_rr_dev','sdnn_dev','rmssd_dev','pnn50_dev','lf_hf_ratio_dev',
                  'rr_ms_min_dev','rr_ms_max_dev','rr_ms_25%_dev','rr_ms_50%_dev','rr_ms_75%_dev'}
  failures = []
  for i in range(1, 11):
      path = PROCESSED / f'infant{i}_windowed.csv'
      if not path.exists():
          failures.append(f'infant{i}: file missing')
          continue
      df = pd.read_csv(path)
      missing = EXPECTED_DEV - set(df.columns)
      old = {'rr_ms_mean_dev','rr_ms_std_dev'} & set(df.columns)
      if missing:
          failures.append(f'infant{i}: missing dev cols {missing}')
      if old:
          failures.append(f'infant{i}: OLD dev cols still present {old}')
      if 'label' not in df.columns:
          failures.append(f'infant{i}: label column missing')
      if df.isnull().sum().sum() > 0:
          failures.append(f'infant{i}: NaN values present')

  combined = pd.read_csv(PROCESSED / 'all_patients_windowed.csv')
  if failures:
      print('FAIL:')
      for f in failures: print(' ', f)
  else:
      pos = combined['label'].sum()
      print(f'PASS: all 10 windowed CSVs correct')
      print(f'  combined shape: {combined.shape}')
      print(f'  positive labels: {pos} / {len(combined)} ({100*pos/len(combined):.1f}%)')
  "
  ```

  **Expected:** Prints `PASS: all 10 windowed CSVs correct` with combined shape and label distribution.

  **Pass:** `PASS` line printed; `positive labels` shows a non-zero count.

  **Fail:**
  - `infant{N}: missing dev cols` → Step 3 (`HRV_COLS` in `run_nb04.py`) not applied → re-read `scripts/run_nb04.py` line 28
  - `infant{N}: label column missing` → annotation file for that patient missing → check `data/processed/infant{N}_labels.csv` exists
  - `infant{N}: NaN values present` → assertion in `run_nb04.py` line 111 would have already caught this; check logs

---

- [ ] 🟥 **Step 7: Create and run `scripts/build_training_data.py`** — *Non-critical: produces `combined_features_labelled.csv` for Phase 1 classifier*

  **Idempotent:** Yes — overwrites output file on re-run.

  **Context:** The Phase 1 classifier (`src/models/train_classifier.py`) needs raw HRV features + labels in a single file. `_features.csv` has raw features; `_windowed.csv` has labels. This script joins them on `window_idx` per patient and concatenates all 10 patients.

  **Action — create the file:**

  ```python
  # scripts/build_training_data.py
  """Build combined_features_labelled.csv for Phase 1 classifier training.

  Joins each patient's _features.csv (raw HRV) with _windowed.csv (labels) on window_idx.
  Saves to data/processed/combined_features_labelled.csv.
  Run from repo root: python scripts/build_training_data.py
  """
  import pandas as pd
  from pathlib import Path

  PROCESSED = Path("data/processed")
  PATIENTS = [f"infant{i}" for i in range(1, 11)]

  FEATURE_COLS = [
      "mean_rr", "sdnn", "rmssd", "pnn50", "lf_hf_ratio",
      "rr_ms_min", "rr_ms_max", "rr_ms_25%", "rr_ms_50%", "rr_ms_75%"
  ]

  rows = []
  for pid in PATIENTS:
      feat_path  = PROCESSED / f"{pid}_features.csv"
      label_path = PROCESSED / f"{pid}_windowed.csv"

      if not feat_path.exists():
          print(f"  SKIP {pid}: {feat_path} not found")
          continue
      if not label_path.exists():
          print(f"  SKIP {pid}: {label_path} not found")
          continue

      feat_df  = pd.read_csv(feat_path)
      label_df = pd.read_csv(label_path)[["window_idx", "label"]]
      # inner join drops warmup windows (idx 0–9) which have no label row in _windowed.csv
      # because run_nb04.py drops the first LOOKBACK=10 rows before writing labels
      merged   = feat_df.merge(label_df, on="window_idx", how="inner")

      missing_feat = [c for c in FEATURE_COLS if c not in merged.columns]
      assert not missing_feat, f"{pid}: feature columns missing after merge: {missing_feat}"

      rows.append(merged)
      print(f"  {pid}: {len(merged)} rows  (pos={merged['label'].sum()}, neg={(merged['label']==0).sum()})")

  assert len(rows) == 10, f"Expected 10 patients, got {len(rows)} — check that data/processed/ is accessible from {Path.cwd()}"

  combined = pd.concat(rows, ignore_index=True)
  out_path = PROCESSED / "combined_features_labelled.csv"
  combined.to_csv(out_path, index=False)

  print(f"\nSaved: {out_path}")
  print(f"Shape:            {combined.shape}")
  print(f"Positive labels:  {combined['label'].sum()} / {len(combined)} ({100*combined['label'].mean():.1f}%)")
  print(f"NaN count:        {combined.isnull().sum().sum()}")
  print(f"Columns:          {list(combined.columns)}")
  ```

  **Then run it:**
  ```bash
  python scripts/build_training_data.py
  ```

  **Git Checkpoint:**
  ```bash
  git add scripts/build_training_data.py data/processed/combined_features_labelled.csv
  git commit -m "step 7: add build_training_data.py and generate combined_features_labelled.csv"
  ```

  **✓ Verification Test:**

  **Type:** Integration

  **Action:**
  ```bash
  python -c "
  import pandas as pd
  df = pd.read_csv('data/processed/combined_features_labelled.csv')
  required = ['mean_rr','sdnn','rmssd','pnn50','lf_hf_ratio',
               'rr_ms_min','rr_ms_max','rr_ms_25%','rr_ms_50%','rr_ms_75%','label']
  missing = [c for c in required if c not in df.columns]
  assert not missing, f'Missing columns: {missing}'
  assert df['label'].sum() > 0, 'No positive labels — label join failed'
  assert df.isnull().sum().sum() == 0, f'NaN present: {df.isnull().sum()}'
  assert len(df) > 100, f'Too few rows: {len(df)}'
  assert df['record_name'].nunique() == 10, f"Expected 10 patients, got {df['record_name'].nunique()} — check data/processed/ is accessible from {__import__('pathlib').Path.cwd()}"
  print(f'PASS: combined_features_labelled.csv ready for Phase 1')
  print(f'  Shape:   {df.shape}')
  print(f'  Pos rate: {df[\"label\"].mean():.1%}')
  print(f'  Patients: {df[\"record_name\"].nunique()} (expect 10)')
  "
  ```

  **Expected:**
  - Prints `PASS: combined_features_labelled.csv ready for Phase 1`
  - Shape shows ~1000+ rows and 13 columns
  - `Patients: 10`
  - Pos rate > 0%

  **Pass:** `PASS` line printed, 10 patients, non-zero positive rate.

  **Fail:**
  - `Missing columns` → Steps 1/2/5 not applied correctly → re-run Step 5 verification
  - `No positive labels` → `_windowed.csv` label join failed → check `window_idx` range overlaps between features and windowed files
  - `Too few rows: N` where N < 100 → most patients were skipped → check `_features.csv` existence

---

## Regression Guard

**Systems at risk:**
- `notebooks/03_hrv_extraction.ipynb` — hardcodes the old 7 column names in cell output. Not used by scripts but may show stale column references if opened. Not blocking; notebook is secondary.
- `notebooks/04_baseline_deviation.ipynb` — generated by `generate_nb04.py`; outdated until regenerated. After Step 4 completes all four replacements, the notebook can be regenerated safely with `python scripts/generate_nb04.py`. Do NOT regenerate before Step 4 is verified — a partial Step 4 leaves `cell5` referencing the deleted `rr_ms_mean_dev` column.

| System | Pre-change behavior | Post-change verification |
|--------|---------------------|--------------------------|
| `run_nb03.py` produces `_features.csv` | 9 columns (7 HRV + record_name + window_idx) | Now 12 columns (10 HRV + record_name + window_idx) — Step 5 verification confirms |
| `run_nb04.py` produces `_windowed.csv` | 9 deviation columns + label | Now 12 deviation columns + label — Step 6 verification confirms |
| `get_window_features` public signature | `(rr_intervals, record_name, window_idx) → dict` | Signature unchanged — Step 1 verification confirms `record_name` and `window_idx` still present |

---

## Rollback Procedure

```bash
# Full rollback — reverse commit order
git revert HEAD      # step 7: removes build_training_data.py commit
git revert HEAD      # step 6: reverts _windowed.csv regeneration  (or git checkout HEAD~1 -- data/processed/)
git revert HEAD      # step 5: reverts _features.csv regeneration
git revert HEAD      # step 4: reverts generate_nb04.py
git revert HEAD      # step 3: reverts run_nb04.py HRV_COLS
git revert HEAD      # step 2: reverts run_nb03.py expected_cols
git revert HEAD      # step 1: reverts hrv.py

# Confirm restored to pre-plan state:
python -c "from src.features.hrv import get_serie_describe; print('RESTORED')"
```

---

## Pre-Flight Checklist

| Phase | Check | How to Confirm | Status |
|-------|-------|----------------|--------|
| **Pre-flight** | `scipy` installed | `python -c "from scipy import signal"` exits 0 | ⬜ |
| | `scipy.integrate.trapezoid` available | `python -c "from scipy.integrate import trapezoid"` exits 0 | ⬜ |
| | `get_serie_describe` is only internal | `grep -rn "get_serie_describe" . \| grep -v hrv.py` returns 0 lines | ⬜ |
| | `expected_cols` appears once in run_nb03.py | `grep -c "expected_cols" scripts/run_nb03.py` returns `3` | ⬜ |
| | `HRV_COLS` appears once in run_nb04.py | `grep -c "HRV_COLS" scripts/run_nb04.py` returns `1` | ⬜ |
| | HRV_COLS anchor unique in generate_nb04.py | `grep -c '"rr_ms_mean", "rr_ms_std", "rr_ms_min"' scripts/generate_nb04.py` returns `1` | ⬜ |
| | `rr_ms_mean_dev` appears exactly 3× in generate_nb04.py | `grep -c "rr_ms_mean_dev" scripts/generate_nb04.py` returns `3` | ⬜ |
| | All 10 `_rr_clean.csv` exist | `ls data/processed/*_rr_clean.csv \| wc -l` returns `10` | ⬜ |
| | All 10 `_labels.csv` exist | `ls data/processed/*_labels.csv \| wc -l` returns `10` | ⬜ |
| | Raw WFDB annotations present | `ls data/raw/physionet.org/files/picsdb/1.0.0/infant1_ecg.atr` exits 0 | ⬜ |
| | `first_r_peaks.csv` exists | `ls data/processed/first_r_peaks.csv` exits 0 | ⬜ |
| | `logs/` directory present | `ls -d logs/ \|\| mkdir -p logs` | ⬜ |
| **Phase 1** | Step 1 committed before Step 2 | `git log --oneline -1` shows step 1 commit | ⬜ |
| | Step 2 committed before Step 5 | All code changes committed before running scripts | ⬜ |
| **Phase 2** | Steps 1–4 all committed | `git log --oneline -4` shows all 4 commits | ⬜ |
| | Step 5 passed before Step 6 | Step 5 verification printed `PASS` | ⬜ |
| | Step 6 passed before Step 7 | Step 6 verification printed `PASS` | ⬜ |

---

## Risk Heatmap

| Step | Risk Level | What Could Go Wrong | Early Detection | Idempotent |
|------|-----------|---------------------|-----------------|------------|
| Step 1 | 🟡 **Medium** | `scipy` not installed; LF/HF fallback returns 1.0 for short windows | Verification test catches import errors | Yes |
| Step 2 | 🟢 **Low** | Wrong anchor matched (only 1 exists, so low risk) | Pre-read gate grep | Yes |
| Step 3 | 🟢 **Low** | Wrong anchor matched | Pre-read gate grep | Yes |
| Step 4 | 🟡 **Medium** | One of 4 replacements (4a–4d) skipped — cell5 crashes with `KeyError: 'rr_ms_mean_dev'` | Final grep for `rr_ms_mean` and `rr_ms_mean_dev` must return zero lines | Yes |
| Step 5 | 🟡 **Medium** | 1–2 patients skipped due to missing `_rr_clean.csv` | Step 5 verification lists missing patients | Yes |
| Step 6 | 🟡 **Medium** | Labels missing for a patient (missing `_labels.csv`) | Step 6 verification checks label column | Yes |
| Step 7 | 🟢 **Low** | window_idx mismatch between features and windowed (join produces 0 rows) | Script asserts `len(merged) > 0` per patient | Yes |

---

## Success Criteria

| Feature | Target | Verification |
|---------|--------|--------------|
| `src/features/hrv.py` produces clinical keys | `rmssd`, `sdnn`, `pnn50`, `lf_hf_ratio` present; `rr_ms_mean`, `rr_ms_std` absent | Step 1 unit test |
| All 10 `_features.csv` updated | 12 columns, no `rr_ms_mean` | Step 5 integration test |
| All 10 `_windowed.csv` updated | 12 deviation columns + `label` | Step 6 integration test |
| `combined_features_labelled.csv` ready | ≥100 rows, 10 patients, non-zero positive rate, zero NaN | Step 7 integration test |
| `get_window_features` signature unchanged | Same 3-arg call still works in `run_nb03.py` | Implicit — Step 5 runs without import errors |

---

⚠️ **Do not mark a step 🟩 Done until its verification test passes.**
⚠️ **Do not proceed past a Human Gate without explicit human input.**
⚠️ **If blocked, mark 🟨 In Progress and output the State Manifest before stopping.**
⚠️ **Do not batch multiple steps into one git commit.**
⚠️ **If idempotent = No, confirm the step has not already run before executing.**
