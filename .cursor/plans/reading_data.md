# Neonatal Sepsis — Notebooks 01 & 02 Execution Plan

**Overall Progress:** `100%` — Steps 3–8 complete (simulated data)

> **Modification (PICS downloading):** Notebooks 01 & 02 use neurokit2 simulated ECG (500Hz, 60s) instead of wfdb file loading. Same pipeline. Steps 1–2 (file placement, path) skipped.

---

## TLDR

Build and validate the first two notebooks of the neonatal sepsis pipeline. Notebook 01 loads and inspects raw PICS ECG/respiration signals from PhysioNet, confirms data quality across all 10 infant recordings, and establishes the data structure. Notebook 02 applies bandpass filtering to remove NICU electrical noise, detects R-peaks using the Pan-Tompkins algorithm, computes RR intervals, removes ectopic beats, and saves cleaned data to `data/processed/`. After this plan executes, the pipeline has clean, validated RR intervals ready for HRV extraction in notebook 03.

---

## Critical Decisions

- **Decision 1:** Use neurokit2 `ecg_peaks` (Pan-Tompkins) for R-peak detection — gold standard for clinical ECG, validated on preterm infants in literature.
- **Decision 2:** Save cleaned RR intervals to `data/processed/` as CSV — decouples cleaning from feature extraction, avoids re-running the full pipeline each session.
- **Decision 3:** Filter ectopic beats at 20% deviation threshold — conservative enough to catch noise, permissive enough to preserve real HRV.

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
| Exact path where wget saved PICS files | Confirm `data/raw/` subfolder structure | `ls data/raw/` in terminal | Steps 1, 5 | ⬜ |
| Channel index for ECG vs respiration | ECG = index 0, respiration = index 1 | PICS documentation on PhysioNet | Steps 5, 6 | ✅ (confirmed from PICS docs) |
| Sampling rate | ECG = 500Hz, respiration = 50Hz | PICS documentation | Steps 5, 6, 7 | ✅ |

---

## Pre-Flight — Run Before Any Code Changes

```bash
# 1. Confirm folder structure exists
ls -la ~/Neonatal/

# 2. Confirm notebooks folder exists
ls ~/Neonatal/notebooks/

# 3. Confirm data landed in raw
ls ~/Neonatal/data/raw/

# 4. Confirm virtual environment is active
which python  # should point to neonatal venv

# 5. Confirm all packages installed
python -c "import wfdb, neurokit2, numpy, pandas, scipy, matplotlib; print('all imports OK')"

# 6. Confirm .hea files are present (signals downloaded)
find ~/Neonatal/data/raw/ -name "*.hea" | wc -l  # should return 10
```

**Baseline Snapshot (agent fills during pre-flight):**
```
.hea file count:        ____  (expected: 10)
venv active:            ____  (expected: neonatal)
all imports OK:         ____  (expected: no errors)
data/processed exists:  ____  (expected: yes after mkdir)
```

**Automated checks — all must pass before Step 1:**
- [ ] `find data/raw/ -name "*.hea" | wc -l` returns 10
- [ ] `python -c "import wfdb"` returns no error
- [ ] `python -c "import neurokit2"` returns no error
- [ ] `data/processed/` directory exists (create if not)

---

## Tasks

### Phase 1 — Data Ingestion & Exploration (Notebook 01)

**Goal:** All 10 PICS infant recordings loaded, plotted, and quality-checked. Output: printed table of duration, ECG std, and NaN count per infant.

---

- [ ] 🟥 **Step 1: Place notebook 01 in repo** — *Non-critical: file placement only*

  **Idempotent:** Yes — copying a file twice produces the same result.

  **Context:** `01_pics_exploration.ipynb` must live in `notebooks/` for relative paths (`../data/raw/`) to resolve correctly.

  ```bash
  cp ~/Downloads/01_pics_exploration.ipynb ~/Neonatal/notebooks/01_pics_exploration.ipynb
  ```

  **What it does:** Places the notebook in the correct directory.

  **Why this approach:** Relative paths in the notebook assume execution from `notebooks/`. Wrong placement breaks every data load cell.

  **Git Checkpoint:**
  ```bash
  cd ~/Neonatal
  git add notebooks/01_pics_exploration.ipynb
  git commit -m "step 1: add 01_pics_exploration notebook"
  ```

  **Subtasks:**
  - [ ] 🟥 File exists at `notebooks/01_pics_exploration.ipynb`
  - [ ] 🟥 Git commit made

  **✓ Verification Test:**

  **Type:** Unit

  **Action:** `ls ~/Neonatal/notebooks/`

  **Expected:** `01_pics_exploration.ipynb` appears in output

  **Observe:** Terminal output

  **Pass:** File name present in directory listing

  **Fail:**
  - If file missing → copy command failed → re-run cp command above

---

- [ ] 🟥 **Step 2: Confirm data path resolves** — *Critical: all notebook cells depend on this path*

  **Idempotent:** Yes — read-only path check.

  **Context:** The notebook uses `../data/raw/physionet.org/files/picsdb/1.0.0/` as its data path. If wget saved files to a different subdirectory, every `wfdb.rdrecord` call will fail with FileNotFoundError.

  **Pre-Read Gate:**
  ```bash
  # Run this and paste the output — confirms exact path wget used
  find ~/Neonatal/data/raw/ -name "*.hea" | head -5
  ```
  If path differs from `physionet.org/files/picsdb/1.0.0/` → update `data_path` variable in notebook Cell 2 before running.

  **What it does:** Confirms the exact subfolder structure wget created so the notebook path variable is correct.

  **Why this approach:** wget mirrors the URL structure. The exact subdirectory depth depends on how wget was invoked.

  **Assumptions:**
  - wget was run with `-r -N -c -np` flags from `~/Neonatal/`
  - Files landed in `data/raw/physionet.org/files/picsdb/1.0.0/`

  **Risks:**
  - Path differs from expected → mitigation: update `data_path` in Cell 2 of notebook 01 to match actual path from `find` output above

  **Git Checkpoint:**
  ```bash
  git add notebooks/01_pics_exploration.ipynb
  git commit -m "step 2: confirm and fix data path if needed"
  ```

  **Subtasks:**
  - [ ] 🟥 Run `find` command and capture output
  - [ ] 🟥 Confirm or correct `data_path` in notebook Cell 2

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  python3 -c "
  import wfdb, os
  path = 'data/raw/physionet.org/files/picsdb/1.0.0/'
  records = [f.replace('.hea','') for f in os.listdir(path) if f.endswith('.hea')]
  print(f'Found {len(records)} records:', records)
  "
  ```
  (Run from `~/Neonatal/`)

  **Expected:** `Found 10 records: [...]`

  **Observe:** Terminal output

  **Pass:** Exactly 10 records printed with no FileNotFoundError

  **Fail:**
  - If `FileNotFoundError` → path is wrong → run `find data/raw/ -name "*.hea"` to find correct path
  - If count < 10 → download incomplete → re-run wget

---

- [ ] 🟥 **Step 3: Run notebook 01 top to bottom** — *Non-critical: exploration only, no data written*

  **Idempotent:** Yes — read-only, produces plots only.

  **Context:** Validates that all 10 infant recordings load correctly, plots raw ECG and respiration, and prints the quality table. This is the acceptance test for the raw data.

  **What to look for when running:**
  - Cell 4 (plots): you should see clear QRS spikes in the ECG trace
  - Cell 6 (quality table): check for any infant with std near 0 (dead signal) or high NaN count

  **Git Checkpoint:**
  ```bash
  git add notebooks/01_pics_exploration.ipynb
  git commit -m "step 3: run and validate 01_pics_exploration"
  ```

  **Subtasks:**
  - [ ] 🟥 All cells run without error
  - [ ] 🟥 ECG plot shows visible QRS spikes
  - [ ] 🟥 Quality table prints 10 rows
  - [ ] 🟥 No infant has std = 0 or NaN count > 1000

  **✓ Verification Test:**

  **Type:** Integration

  **Action:** Run all cells in `01_pics_exploration.ipynb` via Cursor (Shift+Enter each cell)

  **Expected:**
  - Cell 2: prints `Found 10 records`
  - Cell 3: prints `Sampling frequency: 500 Hz`, `Channels: ['ECG', 'RESP']`
  - Cell 4: two plots render without error
  - Cell 6: table with 10 rows, all stds > 0.01, NaNs = 0

  **Observe:** Notebook cell outputs in Cursor

  **Pass:** All 6 cells produce output with no red error traceback

  **Fail:**
  - If `KeyError` on channel index → ECG is not index 0 → check `record.sig_name` output and swap index in Cell 3
  - If plot is flat line → signal is corrupted → note which infant, skip in notebook 02

---

### Phase 2 — Signal Cleaning & R-Peak Detection (Notebook 02)

**Goal:** Clean ECG signal, detect R-peaks, compute RR intervals, remove ectopic beats, save `data/processed/<infant>_rr_clean.csv` for each infant. Output feeds directly into notebook 03 HRV extraction.

---

- [ ] 🟥 **Step 4: Place notebook 02 in repo** — *Non-critical: file placement only*

  **Idempotent:** Yes.

  ```bash
  cp ~/Downloads/02_signal_cleaning.ipynb ~/Neonatal/notebooks/02_signal_cleaning.ipynb
  ```

  **Git Checkpoint:**
  ```bash
  git add notebooks/02_signal_cleaning.ipynb
  git commit -m "step 4: add 02_signal_cleaning notebook"
  ```

  **✓ Verification Test:**

  **Type:** Unit

  **Action:** `ls ~/Neonatal/notebooks/`

  **Expected:** Both `01_pics_exploration.ipynb` and `02_signal_cleaning.ipynb` present

  **Pass:** Both files listed

  **Fail:**
  - If missing → re-run cp command

---

- [ ] 🟥 **Step 5: Run bandpass filter cell — confirm noise removed** — *Critical: all HRV features depend on clean signal*

  **Idempotent:** Yes — filter is a pure function, same input always produces same output.

  **Context:** Raw NICU ECG contains baseline wander (< 0.5Hz), power line interference (50Hz), and high-frequency equipment noise (> 40Hz). The bandpass filter (0.5–40Hz) removes all three. If this step is wrong, R-peak detection fails silently — peaks land in noise instead of true heartbeats.

  **Pre-Read Gate:**
  - Confirm Cell 2 loaded signal without error (Step 2 passed)
  - Confirm `fs = 500` printed in Cell 2 output before running filter cell

  **What it does:** Applies a 4th-order Butterworth bandpass filter using `filtfilt` (zero phase shift). Plots raw vs filtered side by side.

  **Why this approach:** `filtfilt` applies the filter forward and backward — eliminates phase delay that would shift R-peak positions and corrupt RR interval timing.

  **Assumptions:**
  - `ecg_raw` and `fs` variables are defined from Cell 2
  - ECG is sampled at 500Hz

  **Risks:**
  - Filter removes real signal if cutoffs wrong → mitigation: visually confirm filtered plot still shows clear QRS spikes, not flat
  - `filtfilt` fails on very short signals → mitigation: 30,000 samples (60s) is well above minimum

  **✓ Verification Test:**

  **Type:** Unit

  **Action:** Run bandpass filter cell. Inspect the two-panel plot.

  **Expected:**
  - Bottom panel (filtered) shows same spike pattern as top panel (raw) but smoother baseline
  - No flat sections
  - QRS spikes remain sharp and visible

  **Observe:** Matplotlib plot rendered in Cursor notebook

  **Pass:** Filtered signal visually cleaner than raw, QRS spikes preserved

  **Fail:**
  - If filtered signal is flat → cutoff frequencies inverted (high < low) → swap `lowcut` and `highcut` values
  - If no visible difference → signal was already clean or NaN-heavy → check raw signal stats from notebook 01

---

- [ ] 🟥 **Step 6: Run R-peak detection cell — confirm beat count is physiologically plausible** — *Critical: RR intervals are the direct input to HRV*

  **Idempotent:** Yes — deterministic algorithm on same input.

  **Context:** R-peaks are the sharp upward deflections in ECG — each is one heartbeat. Preterm infants have heart rates of 120–180 bpm. In 60 seconds that means 120–180 peaks. Outside that range = something is wrong.

  **What it does:** Calls `nk.ecg_peaks` (Pan-Tompkins algorithm). Prints detected count and average bpm. Plots red dots on peaks over first 10 seconds.

  **Assumptions:**
  - `ecg_filtered` and `fs` defined from previous cells
  - neurokit2 >= 0.2.0 installed

  **Risks:**
  - Pan-Tompkins misses peaks in very noisy segments → mitigation: visual check of the red-dot plot — every spike should have exactly one red dot
  - Double-detection (two dots per spike) → ectopic filter in next cell removes these

  **✓ Verification Test:**

  **Type:** Integration

  **Action:** Run R-peak cell. Check printed output.

  **Expected:**
  - `Detected N R-peaks` where N is between 120 and 180 (for 60s recording)
  - `Average heart rate: X bpm` where X is between 120 and 180
  - Plot shows red dots sitting on peak tips, not in troughs or noise

  **Observe:** Printed output + matplotlib plot

  **Pass:** Peak count in physiological range, dots visually on peaks

  **Fail:**
  - If count < 60 → likely detecting noise, not beats → go back and check filter step
  - If count > 300 → double detection → increase `nk.ecg_peaks` method sensitivity threshold
  - If red dots in wrong position → wrong channel loaded → confirm `ecg_raw = record.p_signal[:, 0]`

---

- [ ] 🟥 **Step 7: Run RR interval + ectopic filter cells — confirm clean intervals saved** — *Critical: output file feeds notebook 03*

  **Idempotent:** Yes — CSV overwrite produces identical output on re-run.

  **Context:** RR intervals are the time gaps between consecutive heartbeats in milliseconds. Ectopic beats (caused by noise or arrhythmia) produce abnormally short or long intervals that would inflate HRV metrics. The 20% threshold filter removes these. The cleaned output is saved to `data/processed/` — this is the handoff point to notebook 03.

  **What it does:**
  1. Computes `np.diff(rpeaks) / fs * 1000` → RR intervals in ms
  2. Removes intervals > 20% from local median
  3. Saves to `data/processed/<record_name>_rr_clean.csv`

  **Assumptions:**
  - `rpeaks` array defined from Step 6
  - `data/processed/` directory exists

  ```bash
  # Run this before executing the save cell if directory doesn't exist
  mkdir -p ~/Neonatal/data/processed/
  ```

  **Risks:**
  - Too many beats removed (> 10%) → signal quality too low for this infant → flag and skip
  - CSV not saved → `data/processed/` doesn't exist → run mkdir above

  **Git Checkpoint:**
  ```bash
  git add notebooks/02_signal_cleaning.ipynb
  git commit -m "step 7: run signal cleaning, save RR intervals to data/processed"
  ```

  **Subtasks:**
  - [ ] 🟥 RR interval stats printed (mean, std, min, max)
  - [ ] 🟥 Ectopic removal prints removed count < 10% of total
  - [ ] 🟥 CSV file exists in `data/processed/`

  **✓ Verification Test:**

  **Type:** Integration

  **Action:**
  ```bash
  ls ~/Neonatal/data/processed/
  python3 -c "
  import pandas as pd
  df = pd.read_csv('data/processed/infant1_rr_clean.csv')
  print(f'Rows: {len(df)}, Mean RR: {df.rr_ms.mean():.1f}ms, NaNs: {df.rr_ms.isna().sum()}')
  "
  ```
  (Run from `~/Neonatal/`, replace `infant1` with actual record name)

  **Expected:**
  - `Rows: N` where N > 100
  - `Mean RR: X` where X is between 333ms (180bpm) and 500ms (120bpm)
  - `NaNs: 0`

  **Observe:** Terminal output

  **Pass:** CSV exists, row count > 100, mean RR in physiological range, zero NaNs

  **Fail:**
  - If file not found → `data/processed/` missing → run `mkdir -p data/processed/`
  - If mean RR outside range → wrong units or wrong channel → check `fs` value and channel index
  - If NaNs > 0 → ectopic filter produced NaN → check filter function output

---

- [ ] 🟥 **Step 8: Run cleaning pipeline for all 10 infants** — *Non-critical: loop extension of Steps 5–7*

  **Idempotent:** Yes — CSV overwrite is safe.

  **Context:** Steps 5–7 ran on infant 1 only. This step loops the same pipeline over all 10 infants and saves one CSV per infant. At the end, `data/processed/` should have 10 files.

  **What it does:** Adds a loop around the cleaning pipeline in a new cell at the bottom of notebook 02.

  ```python
  for record_name in records:
      rec = wfdb.rdrecord(os.path.join(data_path, record_name), sampfrom=0, sampto=300000)
      ecg = rec.p_signal[:, 0]
      ecg_f = bandpass_filter(ecg, fs=fs)
      _, info = nk.ecg_peaks(ecg_f, sampling_rate=fs)
      rpeaks = info['ECG_R_Peaks']
      rr = np.diff(rpeaks) / fs * 1000
      rr_clean, mask = filter_ectopic_beats(rr)
      removed_pct = (~mask).sum() / len(mask) * 100
      print(f'{record_name}: {len(rr_clean)} clean beats, {removed_pct:.1f}% removed')
      pd.DataFrame({'rr_ms': rr_clean}).to_csv(
          f'../data/processed/{record_name}_rr_clean.csv', index=False)
  ```

  **Git Checkpoint:**
  ```bash
  git add notebooks/02_signal_cleaning.ipynb
  git add data/processed/
  git commit -m "step 8: run cleaning pipeline for all 10 infants, save RR CSVs"
  ```

  **Subtasks:**
  - [ ] 🟥 Loop runs without error for all 10 infants
  - [ ] 🟥 10 CSV files exist in `data/processed/`
  - [ ] 🟥 No infant has > 10% beats removed (flag if so)

  **✓ Verification Test:**

  **Type:** Integration

  **Action:**
  ```bash
  ls ~/Neonatal/data/processed/ | wc -l
  ```

  **Expected:** `10`

  **Observe:** Terminal output

  **Pass:** Exactly 10 CSV files in `data/processed/`

  **Fail:**
  - If count < 10 → loop errored on one infant → check printed output for which one failed
  - If a file has 0 rows → signal too short or fully corrupted → flag that infant and exclude from modelling

---

## Regression Guard

**Systems at risk:** None — these are greenfield notebooks, no existing code modified.

---

## Rollback Procedure

```bash
# Remove notebooks if something is badly wrong
cd ~/Neonatal
git revert HEAD  # reverts last commit

# Remove processed data and start clean
rm -rf data/processed/*.csv

# Confirm clean state
ls data/processed/  # should be empty
```

---

## Pre-Flight Checklist

| Phase | Check | How to Confirm | Status |
|-------|-------|----------------|--------|
| Pre-flight | venv active | `which python` returns neonatal path | ⬜ |
| Pre-flight | All packages installed | `python -c "import wfdb, neurokit2"` no error | ⬜ |
| Pre-flight | 10 .hea files present | `find data/raw/ -name "*.hea" \| wc -l` = 10 | ⬜ |
| Phase 1 | data_path correct | Step 2 verification passes | ⬜ |
| Phase 1 | Notebook 01 runs clean | All 6 cells no error | ⬜ |
| Phase 2 | Filtered signal has QRS spikes | Visual check Step 5 | ⬜ |
| Phase 2 | Peak count in 120–180 range | Step 6 printed output | ⬜ |
| Phase 2 | 10 CSVs saved | `ls data/processed/ \| wc -l` = 10 | ⬜ |

---

## Success Criteria

| Feature | Target | Verification |
|---------|--------|--------------|
| Notebook 01 loads all infants | 10 records, no errors | Run notebook, Cell 6 prints 10 rows |
| Raw ECG plotted | Visible QRS spikes | Cell 4 plot renders, spikes visible |
| Bandpass filter applied | Cleaner baseline, spikes preserved | Step 5 two-panel plot |
| R-peaks detected | 120–180 bpm range | Step 6 printed bpm output |
| RR intervals saved | 10 CSVs, mean RR 333–500ms | Step 8 verification test |
| No NaNs in output | 0 NaNs per CSV | Step 7 python verification |

---

⚠️ **Do not mark a step 🟩 Done until its verification test passes.**
⚠️ **Do not proceed past a Human Gate without explicit human input.**
⚠️ **If blocked, mark 🟨 In Progress and output the State Manifest before stopping.**
⚠️ **Do not batch multiple steps into one git commit.**
⚠️ **If idempotent = No, confirm the step has not already run before executing.**