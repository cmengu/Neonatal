# Plan: Fix NB02 Truncation & Full Pipeline Rebuild

**Overall Progress:** `0%` (0 / 7 steps complete)

---

## TLDR

NB02 loads only the first 500,000 samples (~16 minutes) of each ECG recording using `sampto=500000`. The PICS recordings are 19–70 hours long. Every downstream file — `rr_clean.csv`, `features.csv`, `labels.csv`, `windowed.csv` — is built on truncated data. Annotations span the full recording and almost none align to the truncated RR array, producing only 2 positive labels across 451 windows (should be 50+). This plan fixes the truncation in NB02 and its run script, persists `first_r_peak_absolute` per patient so NB04 can correctly anchor cumulative RR position to recording coordinates, then rebuilds NB03 and NB04 from scratch. Full rebuild is estimated at 2–5 hours of compute — run Step 4 overnight.

---

## Critical Decisions

- **Decision 1: Remove `sampto` entirely from both NB02 and `scripts/run_nb02_real.py`** — any hardcoded cap risks the same problem at a different scale. Load the full recording and let wfdb handle it.
- **Decision 2: Persist `first_r_peak_absolute` to `data/processed/first_r_peaks.csv`** — NB04 needs the absolute sample position of beat 0 to anchor `cumulative_pos` in recording coordinates. Computing on the fly would make NB04 depend on raw ECG files being present. One small CSV keeps NB04 self-contained.
- **Decision 3: `first_r_peak_absolute = start_idx + r_peaks[0]`** — this is the sample position of the first detected R-peak in the original (pre-trim) recording. It anchors `cumulative_pos` so that `cumulative_pos[i]` gives the absolute sample position of beat `i`.
- **Decision 4: Run infant1 alone first, time it, then run all 10** — processing a 22-hour ECG through neurokit2 is unknown territory. Fail fast on one patient before committing to an overnight run.
- **Decision 5: Fix both `notebooks/02_signal_cleaning.ipynb` AND `scripts/run_nb02_real.py`** — both contain the truncation. Fixing only one leaves the other as a landmine.
- **Decision 6: `fs` is already read from the wfdb record header** — NB02 Cell 1 already overrides `FS_ECG=500` with the actual record fs. Infant1 and infant5 at 250Hz are already handled correctly. No change needed there.

---

## Clarification Gate

| Unknown | Required | Source | Blocking | Resolved |
|---------|----------|--------|----------|----------|
| Full recording duration per patient | Confirmed: 19–70 hours from diagnostic | Diagnostic output | All steps | ✅ |
| Whether `fs` is per-patient or hardcoded | Confirmed: read from record header in NB02 Cell 1 | NB02 code review | Step 1 | ✅ |
| Whether `sampto` appears elsewhere | Only in NB02 Cell 1 and `run_nb02_real.py` | Code review | Step 1 | ✅ |
| Compute time estimate | Unknown until infant1 test run | Step 3 timing | Step 4 | ✅ Resolved by Step 3 |
| NB03 PATIENTS list | Confirmed: all 10 in sync | Previous review | Step 5 | ✅ |

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

# (1) Confirm current beat counts — baseline before rebuild
python -c "
import pandas as pd, glob
for f in sorted(glob.glob('data/processed/infant*_rr_clean.csv')):
    df = pd.read_csv(f)
    print(f.split('/')[-1], len(df), 'beats')
"

# (2) Confirm sampto appears in exactly two places
grep -rn 'sampto' notebooks/02_signal_cleaning.ipynb scripts/run_nb02_real.py

# (3) Confirm raw ECG files exist for all 10 patients
ls data/raw/physionet.org/files/picsdb/1.0.0/infant*_ecg.hea | wc -l

# (4) Confirm NB03 PATIENTS is all 10 (grep the script — Step 5 runs scripts/run_nb03.py, not the notebook)
grep -n 'PATIENTS' scripts/run_nb03.py | head -5

# (5) Check disk space — full recordings will be large
df -h .

# (6) Verify NB04 runner exists (canonical: run_nb04.py)
test -f scripts/run_nb04.py && echo "run_nb04.py exists" || echo "WARNING: run_nb04.py missing"

# (7) Capture current rr_clean, features, labels — write baseline for Steps 4 and 5
python -c "
import pandas as pd, glob, json, sys, hashlib
from pathlib import Path
old_rr = {f.split('/')[-1].replace('_rr_clean.csv',''): len(pd.read_csv(f))
          for f in glob.glob('data/processed/infant*_rr_clean.csv')}
old_w  = {f.split('/')[-1].replace('_features.csv',''): len(pd.read_csv(f))
          for f in glob.glob('data/processed/infant*_features.csv')}
old_l  = {}
old_l_checksum = {}
for f in glob.glob('data/processed/infant*_labels.csv'):
    p = f.split('/')[-1].replace('_labels.csv','')
    df = pd.read_csv(f)
    old_l[p] = len(df)
    old_l_checksum[p] = hashlib.sha256(df['sample_idx'].astype(int).astype(str).str.cat(sep=',').encode()).hexdigest()
if not old_w or len(old_w) < 10:
    print('ERROR: old_windows empty or incomplete — run Pre-Flight after NB03 has produced features')
    sys.exit(1)
Path('data/processed/.baseline_pre_rebuild.json').write_text(
    json.dumps({'old_rr_beats': old_rr, 'old_windows': old_w, 'old_labels': old_l, 'old_labels_checksum': old_l_checksum}, indent=2))
print('Saved .baseline_pre_rebuild.json')
print('old_rr_beats:', old_rr)
print('old_windows:', old_w)
print('old_labels:', old_l)
"
```

**Baseline Snapshot (fill in before Step 1):**
```
infant1 beats (expect ~5125 truncated):   ____
infant5 beats (expect ~706 truncated):    ____
sampto appears in (expect 2 locations):   ____
Raw ECG .hea files (expect 10):           ____
NB03 PATIENTS (expect all 10):            ____
Free disk space (need ~10GB):             ____
run_nb04.py exists:                       ____ (Pre-Flight (6))
.baseline_pre_rebuild.json written:       ____ (Steps 4 and 5 require this)
```

---

## Steps Analysis

```
Step 1 (Fix NB02 notebook)           — Critical     — full code review  — Idempotent: Yes
Step 2 (Fix run_nb02_real.py)        — Critical     — full code review  — Idempotent: Yes
Step 3 (Test run infant1 only)       — Critical     — verification only — Idempotent: Yes
Step 4 (Full rebuild all 10)         — Critical     — verification only — Idempotent: Yes
Step 5 (Rebuild NB03)                — Critical     — verification only — Idempotent: Yes
Step 6 (Rebuild NB04)                — Critical     — verification only — Idempotent: Yes
Step 7 (Verify label alignment)      — Critical     — verification only — Idempotent: Yes
```

---

## Tasks

### Phase 1 — Fix NB02

---

- [ ] 🟥 **Step 1: Fix truncation in `notebooks/02_signal_cleaning.ipynb`** — *Critical: root cause of all label alignment failures*

  **Idempotent:** Yes — same fix on re-run.

  **Context:** NB02 Cell 1's `load_rr_from_wfdb` uses `wfdb.rdsamp(..., sampto=500000)` which caps loading at 500,000 samples (~16 minutes). Recordings are 19–70 hours. This is the root cause of 2/451 positive labels. Two changes in Cell 1: remove `sampto`, and return + persist `first_r_peak_absolute`.

  **Pre-Read Gate:**
  ```bash
  grep -n 'sampto' notebooks/02_signal_cleaning.ipynb
  # Must return exactly 1 match. If 0 or 2+ → STOP.
  ```

  **Changes to make in NB02 Cell 1:**

  **Change A — Remove `sampto=500000`:**

  Find this line:
  ```python
  record = wfdb.rdsamp(str(record_path), sampto=500000)
  ```
  Replace with:
  ```python
  record = wfdb.rdsamp(str(record_path))
  ```

  **Change B — Capture and return `first_r_peak_absolute`:**

  **Scope check:** `start_idx` is defined earlier in the same function. In NB02 Cell 1 the structure is:
  ```python
      start_idx = 0
      for i in range(0, len(ecg_signal) - window, window):
          if ecg_signal[i:i+window].std() > 0.001:
              start_idx = i
              break
      ...
      ecg_signal = ecg_signal[start_idx:]
      signals, info = nk.ecg_process(ecg_signal, ...)
  ```
  `start_idx` is in scope at the insertion point. If your Cell 1 uses a different variable name (e.g. `trim_start`), adapt the formula accordingly.

  Find this block:
  ```python
  signals, info = nk.ecg_process(ecg_signal, sampling_rate=fs)
  r_peaks       = info["ECG_R_Peaks"]
  rr_ms         = np.diff(r_peaks) / fs * 1000.0

  rolling_median = np.median(rr_ms)
  mask           = np.abs(rr_ms - rolling_median) / rolling_median < ectopic_threshold
  rr_clean       = rr_ms[mask]

  print(f"  Raw beats: {len(rr_ms)}, after ectopic removal: {len(rr_clean)}")
  return rr_clean
  ```

  Replace with:
  ```python
  signals, info = nk.ecg_process(ecg_signal, sampling_rate=fs)
  r_peaks              = info["ECG_R_Peaks"]
  first_r_peak_abs     = int(start_idx + r_peaks[0])
  rr_ms                = np.diff(r_peaks) / fs * 1000.0

  rolling_median = np.median(rr_ms)
  mask           = np.abs(rr_ms - rolling_median) / rolling_median < ectopic_threshold
  rr_clean       = rr_ms[mask]

  print(f"  Raw beats: {len(rr_ms)}, after ectopic removal: {len(rr_clean)}")
  print(f"  first_r_peak_absolute: {first_r_peak_abs} samples ({first_r_peak_abs/fs:.2f}s)")
  return rr_clean, first_r_peak_abs
  ```

  **Change C — Update the call site to unpack both return values and save `first_r_peaks.csv`:**

  Find this block:
  ```python
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

  Replace with:
  ```python
  if USE_REAL_DATA:
      first_r_peak_rows = []
      for patient_id in PATIENTS:
          record_path = REAL_DATA_DIR / f"{patient_id}_ecg"
          rr_clean, first_r_peak_abs = load_rr_from_wfdb(record_path, FS_ECG, ECTOPIC_THRESHOLD)
          out_path    = PROCESSED_DIR / f"{patient_id}_rr_clean.csv"
          pd.DataFrame({'rr_ms': rr_clean}).to_csv(out_path, index=False)
          print(f"  Saved: {out_path}  ({len(rr_clean)} rows)")
          first_r_peak_rows.append({
              'record_name':          patient_id,
              'first_r_peak_absolute': first_r_peak_abs
          })

      frp_df   = pd.DataFrame(first_r_peak_rows)
      frp_path = PROCESSED_DIR / "first_r_peaks.csv"
      frp_df.to_csv(frp_path, index=False)
      print(f"\nSaved: {frp_path}")
      print(frp_df.to_string(index=False))
  else:
      print("USE_REAL_DATA=False — run simulated cells below instead")
  ```

  **What it does:** Removes the 500k sample cap so the full recording is loaded. Returns `first_r_peak_absolute` (sample position of the first R-peak in original recording coordinates) alongside `rr_clean`. Saves all 10 values to `data/processed/first_r_peaks.csv` for NB04 to consume.

  **Why this approach:** `first_r_peak_absolute = start_idx + r_peaks[0]` correctly accounts for both the flat-prefix trim offset and the initial signal segment before the first beat. NB04 uses this to anchor `cumulative_pos` so beat positions are in the same coordinate space as `.atr` annotations.

  **Assumptions:**
  - `r_peaks[0]` exists — i.e. at least one R-peak is detected. If the signal is entirely flat after trim, `r_peaks` will be empty and this will crash with an IndexError. This is correct behaviour — a flat signal should not produce an rr_clean file.
  - `start_idx` is in scope at the point of computing `first_r_peak_abs` — confirmed by reading Cell 1 structure.

  **Risks:**
  - Full recording load causes OOM for very long recordings → mitigation: Step 3 tests infant1 (longest at 22h) first before committing to all 10.
  - `nk.ecg_process` is slow on long signals → mitigation: Step 3 times infant1 so we know what to expect.

  **Git Checkpoint:**
  ```bash
  git add notebooks/02_signal_cleaning.ipynb
  git commit -m "step 1: remove sampto truncation and return first_r_peak_absolute from NB02"
  ```

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  python -c "
  import json
  nb  = json.load(open('notebooks/02_signal_cleaning.ipynb'))
  src = ' '.join([''.join(c['source']) for c in nb['cells'] if c['cell_type']=='code'])
  assert 'sampto' not in src, 'sampto still present in notebook'
  assert 'first_r_peak_abs' in src, 'first_r_peak_abs missing'
  assert 'first_r_peaks.csv' in src, 'first_r_peaks.csv save missing'
  assert 'first_r_peak_rows' in src, 'first_r_peak_rows accumulator missing'
  print('NB02 fix verified OK')
  "
  ```

  **Pass:** All 4 assertions pass, `sampto` absent.

  **Fail:**
  - `sampto still present` → Change A not saved → re-apply in Jupyter UI.
  - `first_r_peak_abs missing` → Change B not saved → re-apply.
  - `first_r_peaks.csv save missing` → Change C not saved → re-apply.

---

- [ ] 🟥 **Step 2: Fix truncation in `scripts/run_nb02_real.py`** — *Critical: run script must match notebook*

  **Idempotent:** Yes.

  **Context:** `scripts/run_nb02_real.py` has its own copy of `load_rr_from_wfdb` with `sampto=max_samples` where `MAX_SAMPLES=500000`. This is the script used to actually run NB02 processing. It must be updated to match the notebook fix.

  **Pre-Read Gate:**
  ```bash
  grep -n 'sampto\|MAX_SAMPLES\|max_samples' scripts/run_nb02_real.py
  # Must return matches. If 0 → file already fixed or wrong file — STOP.

  grep -n 'load_rr_from_wfdb' scripts/run_nb02_real.py
  # Must show both the definition line and exactly one call site.
  ```

  **Changes to make in `scripts/run_nb02_real.py`:**

  **Change A — Remove `MAX_SAMPLES` constant:**

  Find:
  ```python
  MAX_SAMPLES = 500000  # enough to get past flat prefixes (e.g. infant5 has ~728s flat)
  ```
  Delete this line entirely.

  **Change B — Remove `sampto` from `wfdb.rdsamp` call:**

  Find:
  ```python
  record = wfdb.rdsamp(str(record_path), sampto=max_samples)
  ```
  Replace with:
  ```python
  record = wfdb.rdsamp(str(record_path))
  ```

  **Change C — Remove `max_samples` parameter from function signature:**

  Find:
  ```python
  def load_rr_from_wfdb(record_path, fs, ectopic_threshold, max_samples=MAX_SAMPLES):
      """Load first max_samples, trim flat prefix, then process."""
  ```
  Replace with (docstring must change — the old one would mislead):
  ```python
  def load_rr_from_wfdb(record_path, fs, ectopic_threshold):
      """Load full recording, trim flat prefix, then process."""
  ```

  **Change D — Return `first_r_peak_absolute` from function body:**

  Find this block in `load_rr_from_wfdb`:
  ```python
    signals, info = nk.ecg_process(ecg_signal, sampling_rate=fs)
    r_peaks = info["ECG_R_Peaks"]
    rr_ms = np.diff(r_peaks) / fs * 1000.0

    rolling_median = np.median(rr_ms)
    mask = np.abs(rr_ms - rolling_median) / rolling_median < ectopic_threshold
    rr_clean = rr_ms[mask]

    print(f"  Raw beats: {len(rr_ms)}, after ectopic removal: {len(rr_clean)}")
    return rr_clean
  ```
  Replace with:
  ```python
    signals, info = nk.ecg_process(ecg_signal, sampling_rate=fs)
    r_peaks = info["ECG_R_Peaks"]
    first_r_peak_abs = int(start_idx + r_peaks[0])
    rr_ms = np.diff(r_peaks) / fs * 1000.0

    rolling_median = np.median(rr_ms)
    mask = np.abs(rr_ms - rolling_median) / rolling_median < ectopic_threshold
    rr_clean = rr_ms[mask]

    print(f"  Raw beats: {len(rr_ms)}, after ectopic removal: {len(rr_clean)}")
    print(f"  first_r_peak_absolute: {first_r_peak_abs} samples ({first_r_peak_abs/fs:.2f}s)")
    return rr_clean, first_r_peak_abs
  ```

  **Change E — Update call site to unpack and save `first_r_peaks.csv`:**

  Find this block (full structure shown for indentation):
  ```python
  if USE_REAL_DATA:
      for patient_id in PATIENTS:
          try:
              record_path = REAL_DATA_DIR / f"{patient_id}_ecg"
              rr_clean = load_rr_from_wfdb(record_path, FS_ECG, ECTOPIC_THRESHOLD)
              out_path = PROCESSED_DIR / f"{patient_id}_rr_clean.csv"
              pd.DataFrame({"rr_ms": rr_clean}).to_csv(out_path, index=False)
              print(f"  Saved: {out_path}  ({len(rr_clean)} rows)")
          except FileNotFoundError as e:
              print(f"  ERROR: {patient_id} record not found at {record_path}: {e}")
              raise
          except Exception as e:
              print(f"  WARNING: {patient_id} skipped ({e})")
  else:
      print("USE_REAL_DATA=False")
  ```
  Replace entire block with (frp_df block is inside `if USE_REAL_DATA:`, same indentation as `for`, after the `for` loop):
  ```python
  if USE_REAL_DATA:
      first_r_peak_rows = []
      for patient_id in PATIENTS:
          try:
              record_path = REAL_DATA_DIR / f"{patient_id}_ecg"
              rr_clean, first_r_peak_abs = load_rr_from_wfdb(record_path, FS_ECG, ECTOPIC_THRESHOLD)
              out_path = PROCESSED_DIR / f"{patient_id}_rr_clean.csv"
              pd.DataFrame({"rr_ms": rr_clean}).to_csv(out_path, index=False)
              print(f"  Saved: {out_path}  ({len(rr_clean)} rows)")
              first_r_peak_rows.append({"record_name": patient_id, "first_r_peak_absolute": first_r_peak_abs})
          except FileNotFoundError as e:
              print(f"  ERROR: {patient_id} record not found at {record_path}: {e}")
              raise
          except Exception as e:
              print(f"  WARNING: {patient_id} skipped ({e})")
      frp_df = pd.DataFrame(first_r_peak_rows)
      frp_df.to_csv(PROCESSED_DIR / "first_r_peaks.csv", index=False)
      print(f"\nSaved: {PROCESSED_DIR / 'first_r_peaks.csv'}")
      print(frp_df.to_string(index=False))
  else:
      print("USE_REAL_DATA=False")
  ```

  **Git Checkpoint:**
  ```bash
  git add scripts/run_nb02_real.py
  git commit -m "step 2: remove sampto truncation from run_nb02_real.py"
  ```

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  python -c "
  src = open('scripts/run_nb02_real.py').read()
  assert 'sampto' not in src,     'sampto still present in run script'
  assert 'MAX_SAMPLES' not in src, 'MAX_SAMPLES still present'
  assert 'max_samples' not in src, 'max_samples still present'
  assert 'first_r_peak_abs' in src, 'first_r_peak_abs missing from run script'
  assert 'first_r_peaks.csv' in src, 'first_r_peaks.csv save missing'
  print('run_nb02_real.py fix verified OK')
  "
  ```

  **Pass:** All 5 assertions pass.

  **Fail:** Any assertion fails → re-apply the corresponding change.

---

### Phase 2 — Test Run (infant1 only)

---

- [ ] 🟥 **Step 3: Test run NB02 for infant1 only — time it** — *Critical: confirms full-recording processing works before overnight run*

  **Idempotent:** Yes — overwrites infant1_rr_clean.csv.

  **Context:** infant1 is the longest recording at ~22 hours. If it works and completes in reasonable time, all 10 will work. If it crashes or takes >60 minutes, we need to investigate before committing to the full run.

  **Action:**

  **Substep 3.1 —** Edit `scripts/run_nb02_real.py` directly: replace the PATIENTS line with exactly `PATIENTS = ["infant1"]` (single line, no trailing comma). Then run:
  ```bash
  cd /Users/ngchenmeng/Neonatal
  time python scripts/run_nb02_real.py
  ```
  The `time` prefix will print elapsed time when done.

  **Substep 3.2 — RESTORE PATIENTS (mandatory; Cursor MUST execute before Human Gate):**
  If this substep is skipped, Step 4 will run with only infant1 and produce no error. Use this restore (matches exactly `PATIENTS = ["infant1"]` as set in 3.1):
  ```bash
  python -c "
  from pathlib import Path
  p = Path('scripts/run_nb02_real.py')
  src = p.read_text()
  if 'PATIENTS = [\"infant1\"]' in src:
      src = src.replace('PATIENTS = [\"infant1\"]',
          'PATIENTS = [\"infant1\", \"infant2\", \"infant3\", \"infant4\", \"infant5\", \"infant6\", \"infant7\", \"infant8\", \"infant9\", \"infant10\"]')
  else:
      raise SystemExit('PATIENTS restore failed: expected PATIENTS = [\"infant1\"] in file')
  p.write_text(src)
  "
  grep 'PATIENTS' scripts/run_nb02_real.py | head -3
  ```
  Expected: output shows all 10 patients. If the restore raises → fix manually before proceeding. Do not output `[WAITING]` until this completes.

  **Human Gate:**
  Paste the full printed output including:
  - `first_r_peak_absolute` value for infant1
  - New beat count for infant1
  - Elapsed time

  Output `"[WAITING: infant1 test run output and timing]"` as the final line.
  Do not write any code after this line. Do not call any tools after this line.

  **✓ Verification Test:**

  **Type:** Integration

  **Action:**
  ```bash
  python -c "
  import pandas as pd
  from pathlib import Path

  # Full 22h recording at ~60–80 bpm ≈ 50,000+ beats; truncated had 5125
  rr = pd.read_csv('data/processed/infant1_rr_clean.csv')
  print(f'infant1 beats: {len(rr)} (was 5125 truncated)')
  assert len(rr) > 50000, f'Beat count {len(rr)} too low for full recording (expect 50,000+)'

  # first_r_peaks.csv should now exist
  frp = pd.read_csv('data/processed/first_r_peaks.csv')
  assert 'infant1' in frp['record_name'].values, 'infant1 missing from first_r_peaks.csv'
  infant1_frp = frp.loc[frp.record_name=='infant1','first_r_peak_absolute'].iloc[0]
  print(f'infant1 first_r_peak_absolute: {infant1_frp}')
  assert infant1_frp > 0, 'first_r_peak_absolute must be > 0'
  print('infant1 test run OK')
  "
  ```

  **Pass:** Beat count > 50,000, `first_r_peaks.csv` exists with infant1 entry, `first_r_peak_absolute > 0`.

  **Fail:**
  - Beat count unchanged → `sampto` still present → re-check Step 1 and 2 verification tests.
  - `first_r_peaks.csv` missing → Change C in Step 1 not saved → re-apply.
  - OOM crash → recording too large for available RAM → report elapsed time and memory usage before stopping.

---

### Phase 3 — Full Rebuild

---

- [ ] 🟥 **Step 4: Full NB02 rebuild — all 10 patients** — *Critical: regenerates all rr_clean CSVs and first_r_peaks.csv*

  **Idempotent:** Yes — overwrites all rr_clean CSVs.

  **Context:** Only run after Step 3 confirms infant1 works and timing is acceptable. Restore `PATIENTS` to all 10 in `scripts/run_nb02_real.py` before running.

  **Action:**
  ```bash
  mkdir -p logs

  grep 'PATIENTS' scripts/run_nb02_real.py | head -3
  # Must show all 10 before running

  cd /Users/ngchenmeng/Neonatal
  nohup python scripts/run_nb02_real.py > logs/nb02_full_run.log 2>&1 &
  echo "PID: $!"
  ```

  Monitor progress:
  ```bash
  tail -f logs/nb02_full_run.log
  ```

  **Human Gate:**
  Paste the final lines of `logs/nb02_full_run.log` showing all 10 patients completed.

  Output `"[WAITING: full NB02 run log output]"` as the final line.
  Do not write any code after this line. Do not call any tools after this line.

  **✓ Verification Test:**

  **Type:** Integration

  **Action:**
  ```bash
  grep -i 'error\|traceback\|exception' logs/nb02_full_run.log | head -20
  # Must return nothing — run can exit 0 but still have per-patient errors

  python -c "
  import pandas as pd, glob, json

  base = json.loads(open('data/processed/.baseline_pre_rebuild.json').read())
  old_rr = base['old_rr_beats']

  for f in sorted(glob.glob('data/processed/infant*_rr_clean.csv')):
      p  = f.split('/')[-1].replace('_rr_clean.csv','')
      df = pd.read_csv(f)
      old = old_rr.get(p, 0)
      assert len(df) > old, f'{p}: beat count {len(df)} not greater than baseline {old}'
      print(f'{p}: {len(df)} beats (was {old}) OK')

  # first_r_peaks.csv must have all 10 patients
  frp = pd.read_csv('data/processed/first_r_peaks.csv')
  assert len(frp) == 10, f'Expected 10 rows in first_r_peaks.csv, got {len(frp)}'
  assert (frp.first_r_peak_absolute > 0).all(), 'Zero or negative first_r_peak_absolute found'
  print(frp.to_string(index=False))
  print('Full NB02 rebuild OK')
  "
  ```

  **Pass:** All 10 have more beats than baseline (from `.baseline_pre_rebuild.json`), `first_r_peaks.csv` has 10 rows. If baseline missing → run Pre-Flight (7) first.

  **Fail:**
  - Beat count unchanged for any patient → `sampto` still in run script → re-check Step 2.
  - Missing patient in `first_r_peaks.csv` → run crashed mid-loop → check log for error, fix, re-run for that patient only.

  **Git Checkpoint:**
  ```bash
  git add data/processed/infant*_rr_clean.csv data/processed/first_r_peaks.csv
  git commit -m "step 4: rebuild rr_clean CSVs from full recordings + first_r_peaks.csv"
  ```

---

- [ ] 🟥 **Step 5: Rebuild NB03 — regenerate features and labels CSVs** — *Critical: features built on truncated beats are wrong*

  **Idempotent:** Yes — overwrites all features and labels CSVs.

  **Context:** NB03 built HRV feature windows from the truncated `rr_clean.csv`. Now that `rr_clean.csv` covers the full recording, NB03 must re-run to produce features and labels from the full beat sequence.

  **Pre-Read Gate (grep the script, NOT the notebook — Step 5 runs `scripts/run_nb03.py`):**
  ```bash
  grep 'PATIENTS' scripts/run_nb03.py | head -3
  python -c "
  import pandas as pd
  cols = pd.read_csv('data/processed/infant1_labels.csv').columns.tolist()
  print('labels columns:', cols)
  assert 'sample_idx' in cols, 'labels CSV must have sample_idx column — checksum formula assumes it'
  "
  ```
  Must show all 10 patients and confirm `sample_idx` exists. If not → fix before running. Do not run nohup until this passes.

  **Action:**
  ```bash
  cd /Users/ngchenmeng/Neonatal
  nohup python scripts/run_nb03.py > logs/nb03_full_run.log 2>&1 &
  echo "PID: $!"

  # Monitor:
  tail -f logs/nb03_full_run.log
  ```

  **Human Gate:**
  Paste the final lines of `logs/nb03_full_run.log` showing all 10 patients completed with window counts.

  Output `"[WAITING: NB03 rebuild log output]"` as the final line.
  Do not write any code after this line. Do not call any tools after this line.

  **✓ Verification Test:**

  **Type:** Integration

  **Action:**
  ```bash
  python -c "
  import pandas as pd, glob, json

  base = json.loads(open('data/processed/.baseline_pre_rebuild.json').read())
  old_w = base['old_windows']
  old_l = base['old_labels']

  for f in sorted(glob.glob('data/processed/infant*_features.csv')):
      p  = f.split('/')[-1].replace('_features.csv','')
      df = pd.read_csv(f)
      old = old_w.get(p, 0)
      assert len(df) > old, f'{p}: window count {len(df)} not greater than baseline {old}'
      assert df.isnull().sum().sum() == 0, f'{p}: NaN in features'
      print(f'{p}: {len(df)} windows (was {old}) OK')

  import hashlib
  old_chk = base.get('old_labels_checksum', {})
  assert old_chk, 'old_labels_checksum missing from baseline — re-run Pre-Flight (7)'
  for f in sorted(glob.glob('data/processed/infant*_labels.csv')):
      p  = f.split('/')[-1].replace('_labels.csv','')
      df = pd.read_csv(f)
      exp = old_l.get(p)
      assert exp is not None, f'{p}: missing from baseline'
      assert len(df) == exp, f'{p}: annotation count {len(df)} != expected {exp}'
      chk = hashlib.sha256(df['sample_idx'].astype(int).astype(str).str.cat(sep=',').encode()).hexdigest()
      assert old_chk.get(p) == chk, f'{p}: sample_idx checksum changed — labels may have been altered'
      print(f'{p}: {len(df)} annotations OK')
  "
  ```

  **Pass:** All 10 have more windows than baseline, annotations unchanged (labels from wfdb), no NaN. If `.baseline_pre_rebuild.json` missing → run Pre-Flight (6) first.

  **Fail:**
  - Window count unchanged → NB03 read old rr_clean → confirm Step 4 completed and rr_clean counts increased.
  - NaN in features → ectopic removal produced empty windows → check rr_clean for that patient.

  **Git Checkpoint:**
  ```bash
  git add data/processed/infant*_features.csv data/processed/infant*_labels.csv
  git commit -m "step 5: rebuild features and labels CSVs from full recordings"
  ```

---

- [ ] 🟥 **Step 6: Rebuild NB04 — update label alignment to use `first_r_peak_absolute`** — *Critical: fixes the coordinate mismatch*

  **Idempotent:** Yes — overwrites all windowed CSVs.

  **Context:** NB04 Cell 2 currently builds `cumulative_pos = np.cumsum(rr_samples)` anchored at 0. It must be updated to `cumulative_pos = first_r_peak_absolute + np.cumsum(rr_samples)` to match annotation coordinates. `first_r_peaks.csv` written in Step 4 provides these values.

  **Pre-Read Gate (execute before any edits; abort if failed):**
  ```bash
  grep -c 'TRIM_OFFSETS' scripts/generate_nb04.py
  grep -c 'cumulative_pos = np.cumsum' scripts/generate_nb04.py
  grep -n -A2 -B2 'Trim offsets' scripts/generate_nb04.py
  ```
  Both counts must be exactly 1. The last command shows context — the insertion point is inside the `cell1 = """..."""` string. The closing `"""` ends the Python triple-quoted string literal; do not search for it in the file as a standalone token.

  **Changes to make in `scripts/generate_nb04.py`:**

  **cell1 —** The file contains `cell1 = """..."""`. Insert the block *after* `print(f"Trim offsets:  {TRIM_OFFSETS}")` and *inside* that same cell1 string (not after its closing `"""` — the closing delimiter ends the Python literal; do not insert there). Find this substring inside the cell1 content (lines ~43–46):
  ```python
  print(f"PROCESSED_DIR: {PROCESSED_DIR}")
  print(f"LOOKBACK:      {LOOKBACK} windows")
  print(f"Patients:      {PATIENTS}")
  print(f"Trim offsets:  {TRIM_OFFSETS}")
  ```
  Insert the following block immediately after the Trim offsets line:
  ```python

  # Load first R-peak absolute positions — written by NB02 (Step 4)
  frp_df         = pd.read_csv(PROCESSED_DIR / "first_r_peaks.csv")
  FIRST_R_PEAKS  = dict(zip(frp_df["record_name"], frp_df["first_r_peak_absolute"].astype(int)))
  print(f"First R-peaks: {FIRST_R_PEAKS}")
  ```
  Result: cell1 string ends with `print(f"Trim offsets:  {TRIM_OFFSETS}")\n\n# Load first...\nprint(f"First R-peaks: {FIRST_R_PEAKS}")"""`.

  **cell2 —** Find this block:
  ```python
    rr_samples     = rr_ms / 1000.0 * FS_ECG
    cumulative_pos = np.cumsum(rr_samples)
  ```
  Replace with (use `[patient_id]` not `.get(patient_id, 0)` — missing patient must raise, not silently anchor at 0):
  ```python
    rr_samples          = rr_ms / 1000.0 * FS_ECG
    first_r_peak_abs    = FIRST_R_PEAKS[patient_id]
    cumulative_pos      = first_r_peak_abs + np.cumsum(rr_samples)
  ```

  Also update the trim-offset guard print line to include `first_r_peak_abs`:
  ```python
  print(f"  {patient_id}: {len(labels_df)} annotations -> "
        f"{len(labelled_windows)} labelled windows "
        f"(dropped_prefix={dropped_prefix}, dropped_range={dropped_range}, "
        f"trim_offset={trim_offset}, first_r_peak_abs={first_r_peak_abs})")
  ```

  **cell4 —** Add a pre-run guard so the job fails fast if any patient is missing (instead of producing partial output and aborting mid-loop). Find:
  ```python
  all_patients = []

  for patient_id in PATIENTS:
  ```
  Replace with:
  ```python
  missing = [p for p in PATIENTS if p not in FIRST_R_PEAKS]
  assert not missing, f"first_r_peaks.csv missing: {missing}"

  all_patients = []

  for patient_id in PATIENTS:
  ```

  Then regenerate the notebook and run it. **Canonical runner:** `python scripts/run_nb04.py` (verified in Pre-Flight (6)). Use nbconvert only if run_nb04.py is missing.
  ```bash
  python scripts/generate_nb04.py

  python scripts/run_nb04.py
  ```
  If run_nb04.py fails (exit non-zero): try `jupyter nbconvert --to notebook --execute notebooks/04_baseline_deviation.ipynb --output 04_executed.ipynb 2>&1 | tail -40`.

  **✓ Verification Test (run immediately after execute; do not defer to Step 7):**
  ```bash
  python -c "
  import pandas as pd
  from pathlib import Path
  combined = pd.read_csv(Path('data/processed') / 'all_patients_windowed.csv')
  total_pos = combined['label'].sum()
  per_patient = combined.groupby('record_name')['label'].sum()
  n_patients_with_pos = (per_patient > 0).sum()
  print(f'Total pos labels: {total_pos} (was 2), patients with pos: {n_patients_with_pos}')
  assert total_pos > 10, f'Only {total_pos} positive labels — alignment broken'
  assert n_patients_with_pos >= 3, f'Only {n_patients_with_pos} patients have pos labels — fix Step 6'
  assert combined.isnull().sum().sum() == 0, 'NaN in combined'
  print('Step 6 label alignment OK')
  "
  ```
  Pass: total_pos > 10, n_patients_with_pos >= 3. Fail: re-check FIRST_R_PEAKS[patient_id], cumulative_pos formula.

  **Human Gate:**
  Paste the full per-patient output showing `labelled_windows` counts.

  Output `"[WAITING: NB04 rebuild output showing per-patient label counts]"` as the final line.
  Do not write any code after this line. Do not call any tools after this line.

  **Git Checkpoint:**
  ```bash
  git add scripts/generate_nb04.py notebooks/04_baseline_deviation.ipynb
  git commit -m "step 6: anchor cumulative_pos to first_r_peak_absolute in NB04"
  ```

---

### Phase 4 — Verify Label Alignment

---

- [ ] 🟥 **Step 7: Verify label alignment is fixed** — *Critical: confirms the root cause is resolved*

  **Idempotent:** Yes — read-only.

  **Action:**
  ```bash
  # trim_offsets.csv was built by extract_trim_offsets.py (sampto=500000). infant5's flat prefix
  # ends at ~364,000 samples, well within 500k, so the value is correct and does not need rebuilding.
  python -c "
  import pandas as pd
  df = pd.read_csv('data/processed/trim_offsets.csv')
  print(df.to_string(index=False))
  i5 = df[df.record_name == 'infant5']
  assert len(i5) == 1 and i5['start_idx_samples'].iloc[0] > 0, 'infant5 must have non-zero trim offset (~364k expected)'
  "

  python -c "
  import pandas as pd
  from pathlib import Path

  combined = pd.read_csv(Path('data/processed') / 'all_patients_windowed.csv')
  print('Combined shape:  ', combined.shape)
  print('Total pos labels:', combined['label'].sum(), '(was 2)')
  print()
  print('Positive labels per patient (all should be > 0 except possibly infant5):')
  per_patient = combined.groupby('record_name')['label'].sum().sort_values()
  print(per_patient)
  total_pos = combined['label'].sum()
  assert total_pos > 10, f'Still only {total_pos} positive labels — alignment broken'
  n_patients_with_pos = (per_patient > 0).sum()
  assert n_patients_with_pos >= 3, f'Only {n_patients_with_pos} patients have positive labels — expect 3+ if alignment works'
  assert combined.isnull().sum().sum() == 0, 'NaN in combined'
  print()
  print('Label alignment fix confirmed OK')
  "
  ```

  **Pass:** Total positive labels > 10 across all patients (expect 50+), zero NaN.

  **Fail:**
  - Still 2 positive labels → `first_r_peak_absolute` not applied → re-check Step 6 changes in `generate_nb04.py`.
  - Positive labels exist but count is suspiciously low → run diagnostic:
    ```bash
    python -c "
    import pandas as pd, numpy as np
    from pathlib import Path
    PROC, FS = Path('data/processed'), 500
    trim = dict(zip(pd.read_csv(PROC/'trim_offsets.csv')['record_name'],
                    pd.read_csv(PROC/'trim_offsets.csv')['start_idx_samples'].astype(int)))
    frp = dict(zip(pd.read_csv(PROC/'first_r_peaks.csv')['record_name'],
                   pd.read_csv(PROC/'first_r_peaks.csv')['first_r_peak_absolute'].astype(int)))
    for p in ['infant1','infant7']:
        rr = pd.read_csv(PROC/f'{p}_rr_clean.csv')['rr_ms'].values
        lab = pd.read_csv(PROC/f'{p}_labels.csv')
        cum = frp[p] + np.cumsum(rr/1000*FS)
        print(f'{p}: cum_pos={cum.min():.0f}..{cum.max():.0f}, ann={lab.sample_idx.min()}..{lab.sample_idx.max()}, trim={trim.get(p,0)}')
    "
    ```

  **Git Checkpoint:**
  ```bash
  git add data/processed/infant*_windowed.csv \
          data/processed/all_patients_windowed.csv
  git commit -m "step 7: verified label alignment fixed — full pipeline rebuild complete"
  ```

---

## Regression Guard

| System | Pre-change behaviour | Post-change verification |
|--------|---------------------|--------------------------|
| `rr_clean.csv` row counts | ~700–5125 beats (truncated) | Step 4: all counts must be greater |
| `features.csv` window counts | 27–122 windows (truncated) | Step 5: all counts must be greater |
| `labels.csv` | Unchanged — annotations are from wfdb, not recomputed | Row counts must be identical to pre-fix |
| `windowed.csv` positive labels | 2 total across 451 windows | Step 7: must be > 10 |
| Simulated rr_clean CSVs | 10 simulated files untouched | `ls data/processed/simulated_*` must still show 10 |

---

## Rollback Procedure

```bash
# This plan modifies source code — rollback via git
git revert HEAD~1  # Step 7
git revert HEAD~1  # Step 6
git revert HEAD~1  # Step 5
git revert HEAD~1  # Step 4

# Restore original truncated rr_clean CSVs from git
git checkout HEAD~4 -- data/processed/infant*_rr_clean.csv

# Remove new files
rm -f data/processed/first_r_peaks.csv
rm -f logs/nb02_full_run.log
rm -f logs/nb03_full_run.log

# Confirm beat counts are back to truncated values
python -c "
import pandas as pd, glob
for f in sorted(glob.glob('data/processed/infant*_rr_clean.csv')):
    df = pd.read_csv(f)
    print(f.split('/')[-1], len(df), 'beats')
"
```

---

## Risk Heatmap

| Step | Risk | What Could Go Wrong | Early Detection | Idempotent |
|------|------|---------------------|-----------------|------------|
| Step 1 | 🟡 Medium | NB02 Cell 1 edits not saved correctly | Token verification test | Yes |
| Step 2 | 🟡 Medium | run_nb02_real.py still has sampto | Token verification test | Yes |
| Step 3 | 🔴 High | infant1 OOM or takes >60min | `time` output — stop if >60min | Yes |
| Step 4 | 🔴 High | Overnight run crashes mid-loop | `nohup` log monitoring | Yes |
| Step 5 | 🟡 Medium | NB03 reads stale rr_clean | Window count assertion | Yes |
| Step 6 | 🔴 High | first_r_peak_abs not anchoring correctly | Per-patient labelled_windows count in human gate | Yes |
| Step 7 | 🟢 Low | Label count still low after fix | Assert > 10 positive labels | Yes |

---

## Success Criteria

| Deliverable | Target | Verification |
|-------------|--------|--------------|
| `rr_clean.csv` covers full recording | Beat counts >> truncated values | Step 4 assertion |
| `first_r_peaks.csv` | 10 rows, all values > 0 | Step 4 assertion |
| `features.csv` covers full recording | Window counts >> truncated values | Step 5 assertion |
| Positive labels | > 10 across all patients (expect 50+) | Step 7 assertion |
| Zero NaN | All windowed CSVs NaN-free | Step 7 assertion |
| Compute time known | Documented from Step 3 timing | Step 3 human gate |

---

## Decisions Log

| Decision | Resolution |
|----------|-----------|
| Remove sampto | Both NB02 and run_nb02_real.py — remove entirely, not replace with larger value |
| first_r_peak_absolute | Persisted to `data/processed/first_r_peaks.csv` |
| Formula | `cumulative_pos = first_r_peak_abs + np.cumsum(rr_samples)` |
| fs per-patient | Already handled in NB02 — `fs` read from record header, no change needed |
| Test strategy | Run infant1 alone first, time it, then all 10 overnight |

---

⚠️ **Do not mark a step 🟩 Done until its verification test passes.**
⚠️ **Do not proceed past a Human Gate without explicit human input.**
⚠️ **If blocked, mark 🟨 In Progress and output the State Manifest before stopping.**
⚠️ **Do not batch multiple steps into one git commit.**
⚠️ **Step 4 is a long-running overnight job — do not wait for it interactively.**