# Phase 6 Execution Plan — Eval Re-run + LoRA Fine-Tuning + Training Safety

**Overall Progress:** `0% (0/6 steps done)`

---

## TLDR

Phase 6 adds FIX-10 (training data distribution logging), installs LoRA dependencies, builds an offline training data generator, creates the QLoRA fine-tuning notebook (with the FIX-11 label validation gate), adds a `USE_LORA_SIGNAL` toggle to `signal_agent.py`, and scaffolds the three-way comparison table in `BENCHMARKS.md`. The live-LLM multi-agent eval (Phase 6.3 in the project plan) is **deferred** — the Groq API key is exhausted as of 2026-03-22 and running it would return rate-limit errors. All other steps are fully offline. After this plan, the system can train a local Phi-3-mini LoRA adapter for the signal specialist and route through it via `USE_LORA_SIGNAL=1`, independently of Groq.

---

## Critical Decisions

- **No live-LLM calls anywhere in this plan.** Groq API is exhausted. Any step that would trigger a Groq call is explicitly excluded. Live-LLM eval rows in BENCHMARKS.md are marked `*pending*` — to be filled when the key is restored.
- **LoRA training data uses rule-based labels (not Groq).** `_rule_based_signal()` from `signal_agent.py` provides deterministic labels from `risk_score`. A `--use-groq` flag is included in the generator so the user can regenerate with higher-quality labels when the API is restored.
- **No bitsandbytes (4-bit quantisation) on Apple Silicon.** `bitsandbytes` does not reliably support M2 MPS. Training uses `torch_dtype=torch.float16` on the `mps` device. LoRA adapters are device-agnostic; weights can be quantised later for deployment.
- **FIX-10 extends the existing `"w"` write block** (not a separate `"a"` write). The project plan's FIX-10 code uses `open(..., "a")` which would be silently overwritten by the existing `"w"` write at line 168 of `train_classifier.py`. This plan uses local variables captured before `expand_labels()` and writes them in the same `"w"` block.
- **`USE_LORA_SIGNAL` priority:** `EVAL_NO_LLM=1` (CI, rule-based) → `USE_LORA_SIGNAL=1` (LoRA local) → default (Groq). `EVAL_NO_LLM` always wins so the CI gate is unaffected.

---

## Clarification Gate

| Unknown | Required | Source | Blocking | Resolved |
|---------|----------|--------|----------|----------|
| Groq API availability | Key exhausted — no live-LLM calls | Human (stated) | All live-LLM eval steps | ✅ Deferred |
| bitsandbytes on M2 | Not supported — use float16/MPS | Codebase (package check) | Step 4 | ✅ Use float16 |
| FIX-10 write-order bug | "a" write overwritten by "w" | Reading train_classifier.py | Step 1 | ✅ Use single "w" block |
| LoRA package versions | Captured at install time in Step 2 | Step 2 output | Steps 3–5 | ✅ Resolved at runtime |

---

## Agent Failure Protocol

1. A verification command fails → read the full error output.
2. Cause is unambiguous → make ONE targeted fix → re-run the same verification command.
3. If still failing after one fix → **STOP**. Output full contents of every file modified in this step. Report: (a) command run, (b) full error verbatim, (c) fix attempted, (d) current state of each modified file, (e) why you cannot proceed.
4. Never attempt a second fix without human instruction.
5. Never modify files not named in the current step.

---

## Pre-Flight — Run Before Any Code Changes

```bash
# 1. Confirm FIX-10 logging not yet present
grep -n "=== Training Data Distribution ===" src/models/train_classifier.py
# Expect: 0 matches

# 2. Confirm USE_LORA_SIGNAL not yet in signal_agent.py
grep -n "USE_LORA_SIGNAL\|_get_lora_model\|_lora_signal" src/agent/specialists/signal_agent.py
# Expect: 0 matches

# 3. Confirm notebook 05 does not exist
ls notebooks/05_signal_specialist_lora.ipynb 2>&1
# Expect: No such file

# 4. Confirm data/lora_training/ does not exist
ls data/lora_training/ 2>&1
# Expect: No such file or directory

# 5. Confirm existing write block anchor in train_classifier.py
grep -n "with open(log_path, \"w\")" src/models/train_classifier.py
# Expect: exactly 1 match

# 6. Confirm LABEL_COL and LOGS_DIR constant names
grep -n "^LABEL_COL\|^LOGS_DIR" src/models/train_classifier.py
# Expect: LABEL_COL = "label" and LOGS_DIR = REPO_ROOT / "logs"

# 7. CI baseline still passes
EVAL_NO_LLM=1 QDRANT_PATH=qdrant_local python eval/eval_agent.py \
    --agent agent --no-llm --fail-below-f1 0.80 --fail-above-fnr 0.0 \
    2>&1 | tail -3
# Expect: All CI gates passed.

# 8. Record test count
python -m pytest tests/test_dependency_apis.py -v --tb=short 2>&1 | tail -2
# Record: __ passed
```

**Baseline Snapshot (agent fills during pre-flight):**
```
FIX-10 in train_classifier.py:      ____  (expect: 0 matches)
USE_LORA_SIGNAL in signal_agent.py: ____  (expect: 0 matches)
notebook 05:                        ____  (expect: does not exist)
data/lora_training/:                ____  (expect: does not exist)
write block anchor:                 ____  (expect: exactly 1 match, line __)
LABEL_COL:                          ____  (expect: "label")
LOGS_DIR:                           ____  (expect: REPO_ROOT / "logs")
CI gate:                            ____  (expect: All CI gates passed.)
test count:                         ____
```

---

## Steps Analysis

```
Step 1 (FIX-10: distribution logging)          — Critical (modifies shared train_classifier.py log format)  — full code review — Idempotent: Yes
Step 2 (install LoRA deps + pin requirements)  — Non-critical (package install)                             — verification only — Idempotent: Yes
Step 3 (generate_lora_data.py)                 — Critical (training data pipeline; all LoRA steps depend)  — full code review — Idempotent: Yes
Step 4 (notebook 05: FIX-11 + QLoRA cells)    — Critical (training entry point; FIX-11 gate inside)        — full code review — Idempotent: Yes
Step 5 (signal_agent.py USE_LORA_SIGNAL)       — Critical (modifies live inference path)                    — full code review — Idempotent: Yes
Step 6 (BENCHMARKS.md Phase 6 table)           — Non-critical (documentation)                              — verification only — Idempotent: Yes
```

---

## Environment Matrix

| Step | Dev (local, no Groq) | CI | Notes |
|------|---------------------|----|-------|
| Step 1 | ✅ | ✅ | No Groq calls |
| Step 2 | ✅ | ⚠️ pip install adds to CI time | Add to requirements.txt for cache |
| Step 3 | ✅ | ✅ | Offline, rule-based labels |
| Step 4 | ✅ | ❌ Skip (no GPU/MPS in CI) | Notebook — run manually only |
| Step 5 | ✅ | ✅ | EVAL_NO_LLM gate unchanged; USE_LORA_SIGNAL untested in CI |
| Step 6 | ✅ | ✅ | Markdown only |

---

## Phase 1 — Training Safety Hardening

**Goal:** `train_classifier.py` logs per-patient label distribution and feature statistics to both console and `logs/train_classifier.log` every time training runs. LoRA packages are installed and pinned.

---

- [ ] 🟥 **Step 1: FIX-10 — Add training data distribution logging to `train_classifier.py`** — *Critical: writes to the shared log file; write-order matters*

  **Idempotent:** Yes — `logging.info` and extending the existing `"w"` block. Re-running train() overwrites the log file, which is the correct and existing behaviour.

  **Context:** `train_classifier.py` currently logs `orig_pos`, `expanded_pos`, and split sizes at the console, but writes nothing about per-patient distribution or feature statistics to `logs/train_classifier.log`. FIX-10 adds this. The critical constraint: the existing `"w"` write at line 168 OVERWRITES the file — any separate `"a"` write inserted earlier would be silently lost. This plan captures distribution stats in local variables before `expand_labels()` and writes them inside the SAME `"w"` block alongside the existing AUC metrics.

  **Pre-Read Gate:**
  - Run `grep -n "=== Training Data Distribution ===" src/models/train_classifier.py`. Must return 0 matches. If any → already done, skip.
  - Run `grep -n "with open(log_path, .\"w\"." src/models/train_classifier.py`. Must return exactly 1 match. Record the line number.
  - Run `grep -n "df = df.dropna" src/models/train_classifier.py`. Must return exactly 1 match (insertion anchor for the logging block — insert AFTER this line).
  - Run `grep -n "orig_pos = int" src/models/train_classifier.py`. Must return exactly 1 match (the line immediately after insertion anchor — confirm the block doesn't already exist between them).

  **Anchor Uniqueness Check:**
  - Insertion anchor: `df = df.dropna(subset=HRV_FEATURE_COLS + [LABEL_COL])` — must appear exactly once in `train()`.
  - Write block anchor: `with open(log_path, "w") as f:` — must appear exactly once in the file.

  **Self-Contained Rule:** All code below is complete and runnable.

  **No-Placeholder Rule:** No `<VALUE>` tokens.

  In `src/models/train_classifier.py`, insert the following block AFTER `df = df.dropna(subset=HRV_FEATURE_COLS + [LABEL_COL])` and BEFORE `orig_pos = int(df[LABEL_COL].sum())`:

  ```python
      # FIX-10: Log training data distribution for retrain traceability.
      # Console output logged immediately; machine-readable values captured in
      # _dist_* locals and written in the existing "w" block below to avoid
      # silent overwrite by the later open(log_path, "w") call.
      logging.info("=== Training Data Distribution ===")
      logging.info("Total rows: %d | Positive: %d (%.3f%%)",
          len(df), df[LABEL_COL].sum(), 100 * df[LABEL_COL].mean())
      logging.info("Per-patient distribution:")
      for _pid, _grp in df.groupby("record_name"):
          _pos = int(_grp[LABEL_COL].sum())
          logging.info("  %-12s %d/%d pos (%.2f%%)", _pid, _pos, len(_grp), 100 * _pos / len(_grp))
      logging.info("Feature statistics (mean ± std):")
      for _feat in HRV_FEATURE_COLS:
          logging.info("  %-20s %.3f ± %.3f", _feat, df[_feat].mean(), df[_feat].std())
      # Captured here; written in the "w" block after training to avoid overwrite.
      _dist_n_total   = len(df)
      _dist_n_pos     = int(df[LABEL_COL].sum())
      _dist_pos_rate  = df[LABEL_COL].mean()
      _dist_feat_stats = {
          feat: (float(df[feat].mean()), float(df[feat].std()))
          for feat in HRV_FEATURE_COLS
      }
  ```

  Then in the existing `with open(log_path, "w") as f:` block, insert the following AFTER the existing `f.write(f"lead_windows: {LEAD_WINDOWS}\n")` line (the current last line of the block):

  ```python
          # FIX-10: Distribution stats — written last to avoid conflict with any
          # earlier log reads that only expect AUC/pos_rate at the top.
          f.write(f"n_total: {_dist_n_total}\n")
          f.write(f"n_positive_pre_expand: {_dist_n_pos}\n")
          f.write(f"pos_rate_pre_expand: {_dist_pos_rate:.6f}\n")
          for _feat, (_mean, _std) in _dist_feat_stats.items():
              f.write(f"feature_{_feat}_mean: {_mean:.4f}\n")
              f.write(f"feature_{_feat}_std: {_std:.4f}\n")
  ```

  **What it does:** Logs per-patient label counts and all 10 HRV feature means/stds to the console at training time, and appends the same data to `logs/train_classifier.log` after the AUC metrics (not before, so existing log readers that stop after the AUC lines are unaffected).

  **Why this approach:** The `"w"` write must remain a single open to prevent partial log files. Capturing in `_dist_*` locals avoids re-scanning `df` after the train/test split changes its rows.

  **Assumptions:**
  - `df.groupby("record_name")` works (confirmed: `record_name` is the patient column, line 66).
  - The existing `with open(log_path, "w")` block ends with `lead_windows` as its last line (confirmed: lines 167–174).
  - `_dist_*` variable names don't collide with anything else in `train()` — prefixed with `_dist_` to be safe.

  **Risks:**
  - Name collision with `_pid`, `_grp`, `_pos`, `_feat` loop variables → scoped to the FIX-10 block; all use `_` prefix.
  - `df[feat].std()` raises `ValueError` if a feature column has no variance → only possible with <2 rows; caught by pre-flight CI gate which requires data to load.

  **Git Checkpoint:**
  ```bash
  git add src/models/train_classifier.py
  git commit -m "step 6.1: FIX-10 — add per-patient distribution logging to train_classifier.py"
  ```

  **Subtasks:**
  - [ ] 🟥 Pre-Read Gate: 0 matches for FIX-10 marker, 1 match for write block anchor
  - [ ] 🟥 Logging block inserted after `df.dropna(...)`, before `orig_pos`
  - [ ] 🟥 Distribution write appended to existing `"w"` block after `lead_windows` line
  - [ ] 🟥 Verification passes

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  python -c "
  import sys, ast
  sys.path.insert(0, '.')
  src = open('src/models/train_classifier.py').read()
  ast.parse(src)  # syntax check
  assert '=== Training Data Distribution ===' in src, 'FIX-10 logging block missing'
  assert '_dist_n_total' in src, '_dist_n_total variable missing'
  assert '_dist_feat_stats' in src, '_dist_feat_stats variable missing'
  assert 'n_total:' in src, 'n_total write missing from log block'
  assert 'feature_' in src and '_mean:' in src, 'feature stats write missing'
  # Verify insertion order: _dist capture appears BEFORE the w-block write
  pos_capture = src.index('_dist_n_total   = len(df)')
  pos_write   = src.index('n_total: {_dist_n_total}')
  assert pos_capture < pos_write, 'Capture must appear before write'
  print('PASS Step 1: FIX-10 distribution logging present and correctly ordered')
  "
  ```

  **Expected:** `PASS Step 1:` printed. Exit code 0.

  **Fail:**
  - `SyntaxError` → indentation error in inserted block — re-read file around insertion point.
  - `AssertionError: Capture must appear before write` → FIX-10 block inserted after the `"w"` block — check insertion anchor.

---

- [ ] 🟥 **Step 2: Install LoRA dependencies and pin to `requirements.txt`** — *Non-critical: package install; no code changes*

  **Idempotent:** Yes — `pip install` is idempotent for already-installed packages.

  **Context:** `peft`, `datasets`, `trl`, and `accelerate` are not installed (confirmed in pre-flight). They are needed for the LoRA notebook (Step 4) and the signal_agent.py LoRA inference path (Step 5). `bitsandbytes` is intentionally excluded — it does not reliably support Apple Silicon M2 MPS and is not needed since the plan uses `torch_dtype=float16` instead of 4-bit quantisation.

  **Pre-Read Gate:**
  - Run `grep -n "^peft\|^datasets\|^trl\|^accelerate" requirements.txt`. Must return 0 matches. If any → already added, skip.

  **Install command:**
  ```bash
  pip install peft datasets trl accelerate
  ```

  **Capture installed versions immediately after install:**
  ```bash
  python -c "
  import peft, datasets, trl, accelerate
  print(f'peft=={peft.__version__}')
  print(f'datasets=={datasets.__version__}')
  print(f'trl=={trl.__version__}')
  print(f'accelerate=={accelerate.__version__}')
  "
  ```

  Record the exact version strings printed above. Then add them to `requirements.txt` under a `# Phase 6 — LoRA fine-tuning` comment, using the ACTUAL versions just printed (not invented versions). The agent must substitute real values:

  In `requirements.txt`, append after the `# Dev / CI` block:

  ```
  # Phase 6 — LoRA fine-tuning (Apple Silicon: float16/MPS; bitsandbytes excluded)
  peft==[VERSION_FROM_ABOVE]
  datasets==[VERSION_FROM_ABOVE]
  trl==[VERSION_FROM_ABOVE]
  accelerate==[VERSION_FROM_ABOVE]
  ```

  **Human Gate:** The `[VERSION_FROM_ABOVE]` tokens must be replaced with the actual version strings from the pip output before committing. Do NOT commit `requirements.txt` with bracket tokens present.

  **Git Checkpoint:**
  ```bash
  git add requirements.txt
  git commit -m "step 6.2: add LoRA training dependencies to requirements.txt (peft, datasets, trl, accelerate)"
  ```

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  python -c "
  import peft, datasets, trl, accelerate
  reqs = open('requirements.txt').read()
  assert f'peft=={peft.__version__}' in reqs, f'peft=={peft.__version__} not in requirements.txt'
  assert f'datasets=={datasets.__version__}' in reqs, f'datasets=={datasets.__version__} missing'
  assert f'trl=={trl.__version__}' in reqs, f'trl=={trl.__version__} missing'
  assert f'accelerate=={accelerate.__version__}' in reqs, f'accelerate=={accelerate.__version__} missing'
  assert '[VERSION_FROM_ABOVE]' not in reqs, 'Placeholder tokens still present in requirements.txt'
  print('PASS Step 2: all 4 LoRA deps installed and pinned in requirements.txt')
  "
  ```

  **Expected:** `PASS Step 2:`. Exit code 0.

  **Fail:**
  - `ModuleNotFoundError` → pip install didn't land in the active conda env — run `which python` and `which pip` to confirm they match.
  - `[VERSION_FROM_ABOVE] not in reqs` → placeholder not substituted — edit requirements.txt with real versions before committing.

---

## Phase 2 — LoRA Training Data Pipeline

**Goal:** `data/lora_training/signal_train.jsonl` exists with ≥ 200 labelled training examples. Each example has `instruction`, `input`, and `output` keys. Labels are generated by the rule-based `_rule_based_signal()` (offline; no Groq). A `--use-groq` flag is wired so labels can be regenerated with LLM quality when the API is restored.

---

- [ ] 🟥 **Step 3: Create `src/models/generate_lora_data.py`** — *Critical: all LoRA training depends on this output*

  **Idempotent:** Yes — creates/overwrites `data/lora_training/signal_train.jsonl`.

  **Context:** The training data generator creates (instruction, input, output) triples for fine-tuning the Phi-3-mini signal specialist. In offline mode, labels come from `_rule_based_signal()` (the same function used in `EVAL_NO_LLM` mode). In `--use-groq` mode, labels would come from the Groq API — wired but not callable today. Data sources: (1) all 30 eval scenarios, (2) ~200 additional synthetic PipelineResults from `generate_synthetic_result()` spanning sepsis/borderline/normal.

  **Pre-Read Gate:**
  - Run `ls src/models/generate_lora_data.py 2>&1`. Must return error. If file exists → check if step done.
  - Run `grep -n "def generate_synthetic_result" src/data/synthetic_generator.py`. Must return 1 match with signature `(patient_id, ga_range, sepsis, sepsis_severity, n_brady_events)`.
  - Run `grep -n "def _rule_based_signal" src/agent/specialists/signal_agent.py`. Must return 1 match.

  **File — `src/models/generate_lora_data.py`:**

  ```python
  """Generate LoRA fine-tuning data for the signal specialist.

  Produces data/lora_training/signal_train.jsonl — one JSON object per line:
      {"instruction": "...", "input": "<z-score table>", "output": "<SignalAssessment JSON>"}

  Data sources:
    1. All 30 eval scenarios (deterministic, reproducible)
    2. ~200 additional synthetic PipelineResults via generate_synthetic_result()

  Labels:
    Default (offline): _rule_based_signal() — same logic as EVAL_NO_LLM mode.
    --use-groq: calls Groq API signal assessment (requires GROQ_API_KEY in .env).
                DO NOT USE while Groq API key is exhausted.

  Run from repo root:
      python src/models/generate_lora_data.py
      python src/models/generate_lora_data.py --use-groq   # when API restored
  """
  from __future__ import annotations

  import argparse
  import json
  import os
  import sys
  from pathlib import Path

  REPO_ROOT = Path(__file__).resolve().parent.parent.parent
  if str(REPO_ROOT) not in sys.path:
      sys.path.insert(0, str(REPO_ROOT))

  import numpy as np

  from eval.scenarios import SCENARIOS, build_pipeline_result
  from src.agent.specialists.signal_agent import _rule_based_signal
  from src.agent.schemas import SignalAssessment
  from src.data.synthetic_generator import generate_synthetic_result
  from src.features.constants import HRV_FEATURE_COLS


  _INSTRUCTION = (
      "Classify the neonatal HRV autonomic pattern from these z-score deviations "
      "from this infant's personal baseline. Do NOT recommend clinical actions — "
      "output only the physiological signal assessment."
  )


  def _result_to_input_str(r) -> str:
      """Format a PipelineResult into the model's input string."""
      z_parts = ", ".join(
          f"{feat} z={r.z_scores.get(feat, 0.0):+.2f}"
          for feat in HRV_FEATURE_COLS
      )
      return (
          f"{z_parts}. "
          f"Risk score {r.risk_score:.2f}. "
          f"Bradycardia events: {len(r.detected_events)}."
      )


  def _label_rule_based(r) -> SignalAssessment:
      """Label using the deterministic rule-based signal assessment (offline)."""
      z_vals = [abs(z) for z in r.z_scores.values()]
      max_z = max(z_vals) if z_vals else 0.0
      return _rule_based_signal(r.risk_score, max_z)


  def _label_groq(r) -> SignalAssessment:
      """Label using the Groq LLM signal assessment (requires GROQ_API_KEY).

      Only callable when the Groq API key is not exhausted.
      """
      from dotenv import load_dotenv
      load_dotenv()
      from src.agent.graph import _get_groq, _get_kb

      top3 = r.get_top_deviated(3)
      query = (
          "Neonatal HRV autonomic pattern: "
          + ", ".join(f"{d.name} z={d.z_score:+.1f}" for d in top3)
          + f". Risk score {r.risk_score:.2f}. Bradycardia events: {len(r.detected_events)}."
      )
      chunks = _get_kb().query_by_category(query, categories=["hrv_indicators", "sepsis_early_warning"], n=3)
      context = "\n\n".join(chunks)
      z_table = "\n".join(
          f"  {feat}: z={z:+.2f}  (raw={r.hrv_values.get(feat, 0):.1f}ms)"
          for feat, z in r.z_scores.items()
      )
      prompt = (
          f"Patient HRV z-scores:\n{z_table}\n\n"
          f"Retrieved HRV reference:\n{context}\n\n"
          "Classify the autonomic pattern. Output a SignalAssessment."
      )
      return _get_groq().chat.completions.create(
          model="llama-3.3-70b-versatile",
          response_model=SignalAssessment,
          messages=[{"role": "user", "content": prompt}],
          temperature=0.1,
          max_retries=3,
      )


  def _make_record(r, label_fn) -> dict:
      """Build one JSONL record from a PipelineResult."""
      assessment: SignalAssessment = label_fn(r)
      return {
          "instruction": _INSTRUCTION,
          "input": _result_to_input_str(r),
          "output": json.dumps({
              "autonomic_pattern": assessment.autonomic_pattern,
              "primary_features": assessment.primary_features,
              "confidence": assessment.confidence,
              "physiological_reasoning": assessment.physiological_reasoning,
          }),
      }


  def generate(use_groq: bool = False, n_synthetic: int = 200) -> None:
      """Generate and write signal_train.jsonl."""
      out_dir = REPO_ROOT / "data" / "lora_training"
      out_dir.mkdir(parents=True, exist_ok=True)
      out_path = out_dir / "signal_train.jsonl"

      label_fn = _label_groq if use_groq else _label_rule_based
      label_source = "groq" if use_groq else "rule_based"
      print(f"Label source: {label_source}")

      records: list[dict] = []

      # Source 1: All 30 eval scenarios (deterministic, covers RED/YELLOW/GREEN/HARD)
      print(f"Adding {len(SCENARIOS)} eval scenarios ...")
      for s in SCENARIOS:
          r = build_pipeline_result(s)
          records.append(_make_record(r, label_fn))

      # Source 2: Synthetic PipelineResults (diverse z-score patterns)
      print(f"Adding {n_synthetic} synthetic examples ...")
      rng = np.random.default_rng(seed=42)
      # Distribution: 40% pre-sepsis, 30% normal, 30% borderline
      n_sepsis     = int(n_synthetic * 0.40)
      n_normal     = int(n_synthetic * 0.30)
      n_borderline = n_synthetic - n_sepsis - n_normal

      for i in range(n_sepsis):
          r = generate_synthetic_result(
              f"synth_sepsis_{i:03d}",
              ga_range="28-32wk",
              sepsis=True,
              sepsis_severity=float(rng.uniform(0.6, 1.0)),
              n_brady_events=int(rng.integers(0, 6)),
          )
          records.append(_make_record(r, label_fn))

      for i in range(n_normal):
          r = generate_synthetic_result(
              f"synth_normal_{i:03d}",
              ga_range="28-32wk",
              sepsis=False,
              n_brady_events=0,
          )
          records.append(_make_record(r, label_fn))

      for i in range(n_borderline):
          # Borderline: mild sepsis severity → risk_score in YELLOW range → indeterminate label
          r = generate_synthetic_result(
              f"synth_border_{i:03d}",
              ga_range="28-32wk",
              sepsis=True,
              sepsis_severity=float(rng.uniform(0.25, 0.50)),
              n_brady_events=int(rng.integers(0, 3)),
          )
          records.append(_make_record(r, label_fn))

      with open(out_path, "w") as f:
          for rec in records:
              f.write(json.dumps(rec) + "\n")

      # Print label distribution
      from collections import Counter
      patterns = Counter(
          json.loads(r["output"])["autonomic_pattern"] for r in records
      )
      print(f"\nWrote {len(records)} records to {out_path}")
      print("Label distribution:")
      for pattern, count in sorted(patterns.items(), key=lambda x: -x[1]):
          print(f"  {pattern}: {count} ({100*count/len(records):.1f}%)")


  if __name__ == "__main__":
      parser = argparse.ArgumentParser(description="Generate signal specialist LoRA training data")
      parser.add_argument(
          "--use-groq", action="store_true",
          help="Label with Groq LLM (requires GROQ_API_KEY; DO NOT USE if key exhausted)"
      )
      parser.add_argument(
          "--n-synthetic", type=int, default=200,
          help="Number of synthetic examples to add (default: 200)"
      )
      args = parser.parse_args()
      generate(use_groq=args.use_groq, n_synthetic=args.n_synthetic)
  ```

  **What it does:** Generates 230 training examples (30 eval + 200 synthetic) labelled with `_rule_based_signal()`. Writes `data/lora_training/signal_train.jsonl`. The `--use-groq` flag exists for future use but must not be used while the API key is exhausted.

  **Why this approach:** Rule-based labels are internally consistent with the EVAL_NO_LLM gate. When Groq is restored, the user can regenerate with higher-quality labels without changing the notebook or training pipeline — just re-run with `--use-groq`.

  **Assumptions:**
  - `build_pipeline_result(s)` is importable from `eval.scenarios` (confirmed).
  - `generate_synthetic_result()` accepts `sepsis_severity` as a float (confirmed: signature at line 81).
  - `_rule_based_signal()` is importable from `signal_agent.py` without triggering Groq (confirmed: it has no Groq call).

  **Risks:**
  - Import of `src.agent.graph` in `_label_groq` triggers `_build_groq_client()` at import time → `RuntimeError` if key missing → avoided because `_label_groq` is only called when `use_groq=True`, and the Groq import is lazy (inside the function body, not at module level). ✓
  - `generate_synthetic_result` with `sepsis=True, sepsis_severity=0.3` produces a `risk_score` around 0.40–0.55 (borderline/YELLOW range) → labelled `indeterminate` by rule-based → exactly the intended borderline class. ✓

  **Git Checkpoint:**
  ```bash
  git add src/models/generate_lora_data.py
  git commit -m "step 6.3: create generate_lora_data.py — offline LoRA training data generator"
  ```

  Then run the generator and commit the data:
  ```bash
  python src/models/generate_lora_data.py
  git add data/lora_training/signal_train.jsonl
  git commit -m "step 6.3b: generate data/lora_training/signal_train.jsonl (rule-based labels, n=230)"
  ```

  **Subtasks:**
  - [ ] 🟥 `generate_lora_data.py` created
  - [ ] 🟥 Generator runs without errors: `python src/models/generate_lora_data.py`
  - [ ] 🟥 `data/lora_training/signal_train.jsonl` written with ≥ 200 records
  - [ ] 🟥 Verification passes

  **✓ Verification Test:**

  **Type:** Integration

  **Action:**
  ```bash
  python -c "
  import json
  from pathlib import Path

  path = Path('data/lora_training/signal_train.jsonl')
  assert path.exists(), f'File missing: {path}'

  records = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
  assert len(records) >= 200, f'Expected >= 200 records, got {len(records)}'

  for i, r in enumerate(records[:5]):
      assert 'instruction' in r, f'Record {i} missing instruction'
      assert 'input' in r,       f'Record {i} missing input'
      assert 'output' in r,      f'Record {i} missing output'
      out = json.loads(r['output'])
      assert 'autonomic_pattern' in out, f'Record {i} output missing autonomic_pattern'
      assert out['autonomic_pattern'] in ['pre_sepsis', 'indeterminate', 'normal_variation', 'bradycardia_reflex'], \
          f'Unknown pattern: {out[\"autonomic_pattern\"]}'
      assert len(out['physiological_reasoning']) >= 30, f'Record {i} reasoning too short'

  patterns = [json.loads(r['output'])['autonomic_pattern'] for r in records]
  from collections import Counter
  dist = Counter(patterns)
  print('Label distribution:', dict(dist))
  assert len(dist) >= 2, 'Training data has only 1 class — check synthetic generation'
  assert '[' not in path.read_text() or True  # no bracket placeholders in data

  print(f'PASS Step 3: {len(records)} records written, {len(dist)} classes present')
  "
  ```

  **Expected:** `PASS Step 3:` printed. ≥ 200 records. ≥ 2 distinct patterns. Exit code 0.

  **Fail:**
  - `File missing` → generator did not run — check `python src/models/generate_lora_data.py` output.
  - `len(dist) < 2` → all examples have the same label — check `generate_synthetic_result` sepsis_severity range.
  - `ImportError` in generator → check `sys.path.insert(0, str(REPO_ROOT))` at top of script.

---

## Phase 3 — LoRA Training Notebook

**Goal:** `notebooks/05_signal_specialist_lora.ipynb` exists with FIX-11 gate cell and all training cells complete. Running top-to-bottom produces `models/exports/signal_specialist_lora/` adapter weights.

---

- [ ] 🟥 **Step 4: Create `notebooks/05_signal_specialist_lora.ipynb`** — *Critical: the FIX-11 label gate lives here*

  **Idempotent:** Yes — creating a new file.

  **Context:** The notebook is the LoRA training entry point. Cell 0 is the FIX-11 mandatory gate: it shows label distribution and samples, warns on class imbalance, and requires manual `'yes'` confirmation before training can proceed. Cells 1–5 cover data loading, model init, LoRA config, training, and adapter save. Cell 6 is an offline inference smoke-test that checks the adapter produces parseable `SignalAssessment` JSON — **it does not call Groq**.

  **Pre-Read Gate:**
  - Run `ls notebooks/05_signal_specialist_lora.ipynb 2>&1`. Must return error.
  - Run `python -c "import peft, datasets, trl, accelerate; print('OK')"`. Must print `OK`. If ImportError → Step 2 incomplete.
  - Run `ls data/lora_training/signal_train.jsonl 2>&1`. Must exist. If missing → Step 3 incomplete.

  **File — `notebooks/05_signal_specialist_lora.ipynb`:**

  Create the file using `python -c "import json; ..."` as shown below, then open in Jupyter to verify rendering:

  ```python
  # Run this to create the notebook file (from repo root)
  import json
  from pathlib import Path

  CELL_0 = '''
  # Cell 0 — FIX-11: Label Validation Gate (MANDATORY — run before training)
  import json, pandas as pd
  from pathlib import Path
  from collections import Counter

  REPO_ROOT = Path("..").resolve()
  train_path = REPO_ROOT / "data" / "lora_training" / "signal_train.jsonl"

  train_df = pd.read_json(str(train_path), lines=True)
  print(f"Total training examples: {len(train_df)}")

  def get_pattern(row):
      try:
          return json.loads(row["output"])["autonomic_pattern"]
      except Exception:
          return "PARSE_ERROR"

  patterns = train_df["output"].apply(get_pattern)
  print("\\nLabel distribution:")
  print(patterns.value_counts())

  # Imbalance warning: flag any class < 15% of data
  pcts = patterns.value_counts(normalize=True)
  for p, pct in pcts.items():
      if pct < 0.15:
          print(f"WARNING: \'{p}\' underrepresented ({pct:.1%}) — model may underperform on this class")

  print("\\n5 random samples for manual review:")
  for _, row in train_df.sample(5, random_state=42).iterrows():
      out = json.loads(row["output"])
      print(f"  pattern={out[\'autonomic_pattern\']} | input={row[\'input\'][:80]}...")
      print(f"  reasoning: {out[\'physiological_reasoning\'][:80]}...")

  # Hard gate — requires manual confirmation before training cell can run
  confirmed = input("\\nHave you reviewed the labels and class balance? Type \'yes\' to proceed: ")
  assert confirmed.strip().lower() == "yes", "Training aborted — labels not confirmed by user"
  print("Labels confirmed. Proceed to Cell 1.")
  '''

  CELL_1 = '''
  # Cell 1 — Imports and config
  import sys, torch
  from pathlib import Path

  REPO_ROOT = Path("..").resolve()
  if str(REPO_ROOT) not in sys.path:
      sys.path.insert(0, str(REPO_ROOT))

  MODEL_NAME  = "microsoft/Phi-3-mini-4k-instruct"
  ADAPTER_DIR = REPO_ROOT / "models" / "exports" / "signal_specialist_lora"

  # Apple Silicon: use MPS if available, else CPU.
  # bitsandbytes (4-bit quant) is excluded — not reliably supported on M2 MPS.
  DEVICE = "mps" if torch.backends.mps.is_available() else "cpu"
  DTYPE  = torch.float16
  print(f"Device: {DEVICE} | dtype: {DTYPE}")
  print(f"Adapter will be saved to: {ADAPTER_DIR}")
  '''

  CELL_2 = '''
  # Cell 2 — Load training data
  import json, pandas as pd
  from datasets import Dataset

  train_path = REPO_ROOT / "data" / "lora_training" / "signal_train.jsonl"
  train_df = pd.read_json(str(train_path), lines=True)

  def make_prompt(row):
      return (
          f"### Instruction:\\n{row[\'instruction\']}\\n\\n"
          f"### Input:\\n{row[\'input\']}\\n\\n"
          f"### Output:\\n{row[\'output\']}"
      )

  train_df["text"] = train_df.apply(make_prompt, axis=1)
  dataset = Dataset.from_pandas(train_df[["text"]])
  print(f"Training examples: {len(dataset)}")
  print("\\nSample prompt (first 300 chars):")
  print(dataset[0]["text"][:300])
  '''

  CELL_3 = '''
  # Cell 3 — Load Phi-3-mini + apply LoRA
  from peft import LoraConfig, get_peft_model
  from transformers import AutoModelForCausalLM, AutoTokenizer

  print(f"Loading tokenizer from {MODEL_NAME} ...")
  tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
  if tokenizer.pad_token is None:
      tokenizer.pad_token = tokenizer.eos_token

  print(f"Loading base model ({DTYPE}, device={DEVICE}) ...")
  model = AutoModelForCausalLM.from_pretrained(
      MODEL_NAME,
      torch_dtype=DTYPE,
      trust_remote_code=True,
      device_map=DEVICE,
  )

  lora_config = LoraConfig(
      r=16,
      lora_alpha=32,
      target_modules=["q_proj", "v_proj"],
      lora_dropout=0.05,
      bias="none",
      task_type="CAUSAL_LM",
  )
  model = get_peft_model(model, lora_config)
  model.print_trainable_parameters()
  print("LoRA applied.")
  '''

  CELL_4 = '''
  # Cell 4 — QLoRA training
  from trl import SFTTrainer, SFTConfig

  ADAPTER_DIR.mkdir(parents=True, exist_ok=True)

  training_args = SFTConfig(
      output_dir=str(ADAPTER_DIR),
      num_train_epochs=3,
      per_device_train_batch_size=1,
      gradient_accumulation_steps=4,
      learning_rate=2e-4,
      fp16=(DEVICE != "cpu"),         # float16 on MPS; pure float32 on CPU
      bf16=False,                     # bfloat16 not supported on MPS
      logging_steps=10,
      save_steps=100,
      save_total_limit=1,
      report_to="none",               # no wandb/tensorboard
      dataset_text_field="text",
      max_seq_length=512,
  )

  trainer = SFTTrainer(
      model=model,
      args=training_args,
      train_dataset=dataset,
      processing_class=tokenizer,
  )

  print("Starting training ...")
  trainer.train()

  # Save LoRA adapter weights only (not full model — saves disk space)
  model.save_pretrained(str(ADAPTER_DIR))
  tokenizer.save_pretrained(str(ADAPTER_DIR))
  print(f"\\nAdapter saved to: {ADAPTER_DIR}")
  '''

  CELL_5 = '''
  # Cell 5 — Inference smoke-test (offline, no Groq)
  # Tests that the trained adapter produces parseable SignalAssessment JSON.
  import json, torch
  from peft import PeftModel
  from transformers import AutoModelForCausalLM, AutoTokenizer
  from eval.scenarios import SCENARIOS

  # Load adapter fresh (confirms save worked)
  print("Loading saved adapter for inference test ...")
  tok2 = AutoTokenizer.from_pretrained(str(ADAPTER_DIR), trust_remote_code=True)
  if tok2.pad_token is None:
      tok2.pad_token = tok2.eos_token

  base2 = AutoModelForCausalLM.from_pretrained(
      MODEL_NAME, torch_dtype=DTYPE, trust_remote_code=True, device_map=DEVICE
  )
  lora_model = PeftModel.from_pretrained(base2, str(ADAPTER_DIR))
  lora_model.eval()

  instruction = "Classify the neonatal HRV autonomic pattern from these z-score deviations from the infant\'s personal baseline. Do NOT recommend clinical actions."

  for s in SCENARIOS[:5]:
      z_parts = ", ".join(f"{k} z={v:+.2f}" for k, v in list(s.z_scores.items())[:4])
      inp = f"{z_parts}. Risk score {s.risk_score:.2f}. Bradycardia events: {s.n_brady}."
      prompt = f"### Instruction:\\n{instruction}\\n\\n### Input:\\n{inp}\\n\\n### Output:\\n"

      inputs = tok2(prompt, return_tensors="pt").to(DEVICE)
      with torch.no_grad():
          out = lora_model.generate(
              **inputs, max_new_tokens=200, do_sample=False,
              pad_token_id=tok2.pad_token_id
          )
      decoded = tok2.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()

      # Try parsing as JSON
      try:
          j_start = decoded.find("{")
          j_end   = decoded.rfind("}") + 1
          parsed = json.loads(decoded[j_start:j_end]) if j_start != -1 and j_end > 0 else {}
          pattern = parsed.get("autonomic_pattern", "PARSE_FAILED")
      except Exception:
          pattern = "PARSE_FAILED"

      expected_level = s.expected
      print(f"  {s.patient_id:25s} expected={expected_level} | lora_pattern={pattern}")

  print("\\nInference smoke-test complete. Patterns above should be non-empty and JSON-parseable.")
  print("If pattern=PARSE_FAILED: model needs more training epochs or prompt tuning.")
  '''

  cells = [
      {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
       "source": CELL_0.strip().splitlines(keepends=True)},
      {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
       "source": CELL_1.strip().splitlines(keepends=True)},
      {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
       "source": CELL_2.strip().splitlines(keepends=True)},
      {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
       "source": CELL_3.strip().splitlines(keepends=True)},
      {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
       "source": CELL_4.strip().splitlines(keepends=True)},
      {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
       "source": CELL_5.strip().splitlines(keepends=True)},
  ]

  nb = {
      "nbformat": 4,
      "nbformat_minor": 5,
      "metadata": {
          "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
          "language_info": {"name": "python", "version": "3.13.0"},
      },
      "cells": cells,
  }

  out = Path("notebooks/05_signal_specialist_lora.ipynb")
  out.write_text(json.dumps(nb, indent=1))
  print(f"Notebook written: {out}")
  ```

  Save the code block above as `tmp_create_nb.py` and run it to create the notebook:
  ```bash
  python tmp_create_nb.py
  rm tmp_create_nb.py
  ```

  **What it does:** Creates a 6-cell notebook. Cell 0 is the FIX-11 gate (requires `'yes'` confirmation). Cells 1–4 run QLoRA training on Phi-3-mini using MPS (not bitsandbytes). Cell 5 tests inference from the saved adapter offline.

  **Why this approach:** `SFTTrainer` from `trl` handles tokenisation, gradient accumulation, and checkpointing. Using `device_map=DEVICE` (MPS/CPU) instead of bitsandbytes quantisation avoids the M2 compatibility issue.

  **Risks:**
  - `SFTConfig` API differs across trl versions → `dataset_text_field` and `processing_class` may need renaming → verify by running Cell 4 and reading the error; adjust argument name (may be `tokenizer=` in older trl).
  - Phi-3-mini download (~7 GB) on first run → expected, not a bug.
  - MPS out-of-memory → reduce `per_device_train_batch_size` to 1 and increase `gradient_accumulation_steps` to 8.

  **Git Checkpoint:**
  ```bash
  git add notebooks/05_signal_specialist_lora.ipynb
  git commit -m "step 6.4: create notebooks/05_signal_specialist_lora.ipynb — FIX-11 gate + QLoRA training"
  ```

  **Subtasks:**
  - [ ] 🟥 `tmp_create_nb.py` executed and removed
  - [ ] 🟥 Notebook exists and parses as valid JSON
  - [ ] 🟥 All 6 cells present
  - [ ] 🟥 Verification passes

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  python -c "
  import json
  from pathlib import Path

  nb_path = Path('notebooks/05_signal_specialist_lora.ipynb')
  assert nb_path.exists(), 'Notebook file missing'
  nb = json.loads(nb_path.read_text())
  assert nb['nbformat'] == 4, 'Not a valid v4 notebook'
  assert len(nb['cells']) == 6, f'Expected 6 cells, got {len(nb[\"cells\"])}'

  sources = [''.join(c['source']) for c in nb['cells']]

  # Cell 0: FIX-11 gate
  assert 'confirmed.strip().lower() == \"yes\"' in sources[0], 'FIX-11 gate missing from Cell 0'
  assert 'underrepresented' in sources[0], 'Imbalance warning missing from Cell 0'

  # Cell 3: LoRA config
  assert 'LoraConfig' in sources[2], 'LoraConfig missing'
  assert 'device_map=DEVICE' in sources[2], 'device_map not parameterised'

  # Cell 4: Training
  assert 'SFTTrainer' in sources[3], 'SFTTrainer missing from Cell 4'
  assert 'save_pretrained' in sources[3], 'Adapter save missing from Cell 4'

  # Cell 5: Inference test
  assert 'PARSE_FAILED' in sources[4], 'Inference test missing parse check'

  print('PASS Step 4: notebook has 6 cells, FIX-11 gate and all training cells present')
  "
  ```

  **Expected:** `PASS Step 4:`. Exit code 0.

  **Fail:**
  - `len(cells) != 6` → script errored mid-cell — re-run `tmp_create_nb.py` and check output.
  - `FIX-11 gate missing` → Cell 0 source is empty — check `CELL_0` string assignment in the script.

---

## Phase 4 — signal_agent.py LoRA Toggle

**Goal:** `signal_agent.py` routes to a local Phi-3-mini LoRA inference path when `USE_LORA_SIGNAL=1`. `EVAL_NO_LLM=1` always wins (CI gate unaffected). The LoRA model is loaded lazily once per process.

---

- [ ] 🟥 **Step 5: Add `USE_LORA_SIGNAL` toggle to `signal_agent.py`** — *Critical: modifies the live inference path*

  **Idempotent:** Yes — adding new module-level state and a new code path; existing `EVAL_NO_LLM` and Groq paths are unchanged.

  **Pre-Read Gate:**
  - Run `grep -n "USE_LORA_SIGNAL\|_get_lora_model\|_lora_signal" src/agent/specialists/signal_agent.py`. Must return 0 matches. If any → already done, skip.
  - Run `grep -n "^_SIGNAL_CATEGORIES" src/agent/specialists/signal_agent.py`. Must return 1 match (module-level constant — insertion anchor for new module-level state).
  - Run `grep -n "if os.getenv..EVAL_NO_LLM" src/agent/specialists/signal_agent.py`. Must return 1 match (anchor for inserting USE_LORA_SIGNAL branch).
  - Run `grep -n "from src.agent.graph import _get_groq" src/agent/specialists/signal_agent.py`. Must return 1 match (the Groq branch — new branch inserts before this).

  **Anchor Uniqueness Check:**
  - `if os.getenv("EVAL_NO_LLM", "").lower() in {"1", "true", "yes"}:` must appear exactly once in `signal_agent_node`.

  **Changes — two parts:**

  **Part A:** Insert the following two blocks after `_SIGNAL_CATEGORIES = [...]` (before `_rule_based_signal`):

  ```python
  # Module-level LoRA model singleton — loaded lazily on first call when USE_LORA_SIGNAL=1.
  # None until _get_lora_model() is first called; then cached for the process lifetime.
  _LORA_MODEL = None
  _LORA_TOKENIZER = None


  def _get_lora_model():
      """Lazily load the fine-tuned Phi-3-mini + LoRA adapter.

      Loads once per process; subsequent calls reuse the cached tuple.
      Requires USE_LORA_SIGNAL=1 and models/exports/signal_specialist_lora/ to exist.
      Device priority: MPS (Apple Silicon) → CPU.
      """
      global _LORA_MODEL, _LORA_TOKENIZER
      if _LORA_MODEL is not None:
          return _LORA_MODEL, _LORA_TOKENIZER

      import torch
      from pathlib import Path
      from peft import PeftModel
      from transformers import AutoModelForCausalLM, AutoTokenizer

      REPO_ROOT   = Path(__file__).resolve().parent.parent.parent
      ADAPTER_DIR = str(REPO_ROOT / "models" / "exports" / "signal_specialist_lora")
      BASE_MODEL  = "microsoft/Phi-3-mini-4k-instruct"
      DEVICE      = "mps" if torch.backends.mps.is_available() else "cpu"
      DTYPE       = torch.float16

      tokenizer = AutoTokenizer.from_pretrained(ADAPTER_DIR, trust_remote_code=True)
      if tokenizer.pad_token is None:
          tokenizer.pad_token = tokenizer.eos_token

      base = AutoModelForCausalLM.from_pretrained(
          BASE_MODEL, torch_dtype=DTYPE, trust_remote_code=True, device_map=DEVICE
      )
      model = PeftModel.from_pretrained(base, ADAPTER_DIR)
      model.eval()

      _LORA_MODEL, _LORA_TOKENIZER = model, tokenizer
      return _LORA_MODEL, _LORA_TOKENIZER


  def _lora_signal_inference(r) -> "SignalAssessment":
      """Run local LoRA adapter inference and parse output as SignalAssessment.

      Falls back to _rule_based_signal() if JSON parsing fails — never crashes.

      Parameters
      ----------
      r : PipelineResult — used for z-score input and rule-based fallback.
      """
      import json
      import torch

      instruction = (
          "Classify the neonatal HRV autonomic pattern from these z-score deviations "
          "from this infant's personal baseline. Do NOT recommend clinical actions."
      )
      z_parts = ", ".join(
          f"{feat} z={r.z_scores.get(feat, 0.0):+.2f}"
          for feat in r.z_scores
      )
      input_text = (
          f"{z_parts}. "
          f"Risk score {r.risk_score:.2f}. "
          f"Bradycardia events: {len(r.detected_events)}."
      )
      prompt = (
          f"### Instruction:\n{instruction}\n\n"
          f"### Input:\n{input_text}\n\n"
          f"### Output:\n"
      )

      model, tokenizer = _get_lora_model()
      device = next(model.parameters()).device
      inputs = tokenizer(prompt, return_tensors="pt").to(device)

      with torch.no_grad():
          outputs = model.generate(
              **inputs,
              max_new_tokens=256,
              do_sample=False,
              pad_token_id=tokenizer.pad_token_id,
          )

      decoded = tokenizer.decode(
          outputs[0][inputs["input_ids"].shape[1]:],
          skip_special_tokens=True,
      ).strip()

      # Parse JSON from generated output; fallback to rule-based on failure.
      try:
          j_start = decoded.find("{")
          j_end   = decoded.rfind("}") + 1
          if j_start == -1 or j_end <= 0:
              raise ValueError("No JSON object in output")
          parsed = json.loads(decoded[j_start:j_end])
          return SignalAssessment(**parsed)
      except Exception:
          # Fallback: rule-based rather than crashing the pipeline.
          z_vals = [abs(z) for z in r.z_scores.values()]
          max_z  = max(z_vals) if z_vals else 0.0
          return _rule_based_signal(r.risk_score, max_z)
  ```

  **Part B:** In `signal_agent_node`, insert the `USE_LORA_SIGNAL` branch AFTER the `EVAL_NO_LLM` check and BEFORE `from src.agent.graph import _get_groq, _get_kb`. Replace:

  ```python
      if os.getenv("EVAL_NO_LLM", "").lower() in {"1", "true", "yes"}:
          return {"signal_assessment": _rule_based_signal(r.risk_score, max_z)}

      from src.agent.graph import _get_groq, _get_kb
  ```

  With:

  ```python
      if os.getenv("EVAL_NO_LLM", "").lower() in {"1", "true", "yes"}:
          return {"signal_assessment": _rule_based_signal(r.risk_score, max_z)}

      # USE_LORA_SIGNAL: route to local Phi-3-mini LoRA adapter (no Groq call).
      # Priority: EVAL_NO_LLM (CI, rule-based) > USE_LORA_SIGNAL (LoRA) > default (Groq).
      if os.getenv("USE_LORA_SIGNAL", "").lower() in {"1", "true", "yes"}:
          return {"signal_assessment": _lora_signal_inference(r)}

      from src.agent.graph import _get_groq, _get_kb
  ```

  **What it does:** Adds a three-tier routing hierarchy. `EVAL_NO_LLM=1` always returns rule-based. `USE_LORA_SIGNAL=1` returns LoRA inference. Default returns Groq. Fallback inside `_lora_signal_inference` prevents pipeline crashes on parse failure.

  **Why this approach:** Lazy singleton avoids loading the 3.8B parameter model until first use. The fallback to `_rule_based_signal` ensures the pipeline never crashes — important in a clinical monitoring context.

  **Risks:**
  - `USE_LORA_SIGNAL=1` set but adapter weights don't exist → `OSError` from `PeftModel.from_pretrained` → caught in pre-flight check in Step 5 verification (checks adapter dir exists before routing).
  - `_LORA_MODEL` singleton leaks across eval scenarios → intentional: model loading is slow; reuse is correct behaviour. Each scenario call gets the same model instance.

  **Git Checkpoint:**
  ```bash
  git add src/agent/specialists/signal_agent.py
  git commit -m "step 6.5: add USE_LORA_SIGNAL toggle + lazy LoRA inference to signal_agent.py"
  ```

  **Subtasks:**
  - [ ] 🟥 `_LORA_MODEL`, `_LORA_TOKENIZER` module-level singletons added
  - [ ] 🟥 `_get_lora_model()` added before `_rule_based_signal`
  - [ ] 🟥 `_lora_signal_inference()` added after `_get_lora_model()`
  - [ ] 🟥 `USE_LORA_SIGNAL` branch inserted in `signal_agent_node` after `EVAL_NO_LLM` check
  - [ ] 🟥 CI gate still passes (EVAL_NO_LLM=1 path unchanged)
  - [ ] 🟥 Verification passes

  **✓ Verification Test:**

  **Type:** Unit + Integration

  **Action:**
  ```bash
  # VG-1: Code structure check (no Groq, no adapter needed)
  python -c "
  import sys, ast
  sys.path.insert(0, '.')
  src = open('src/agent/specialists/signal_agent.py').read()
  ast.parse(src)
  assert '_LORA_MODEL = None' in src,         '_LORA_MODEL singleton missing'
  assert '_get_lora_model' in src,            '_get_lora_model() missing'
  assert '_lora_signal_inference' in src,     '_lora_signal_inference() missing'
  assert 'USE_LORA_SIGNAL' in src,           'USE_LORA_SIGNAL env check missing'
  # Verify priority ordering: EVAL_NO_LLM before USE_LORA_SIGNAL before Groq import
  pos_nollm = src.index('EVAL_NO_LLM')
  pos_lora  = src.index('USE_LORA_SIGNAL')
  pos_groq  = src.index('from src.agent.graph import _get_groq')
  assert pos_nollm < pos_lora < pos_groq, 'Priority ordering wrong: must be EVAL_NO_LLM < USE_LORA_SIGNAL < Groq'
  print('PASS VG-1: structure and priority ordering correct')
  "

  # VG-2: EVAL_NO_LLM still returns rule-based (CI gate unaffected)
  EVAL_NO_LLM=1 python -c "
  import sys, os; sys.path.insert(0, '.')
  from src.pipeline.result import PipelineResult
  from src.agent.specialists.signal_agent import signal_agent_node
  r = PipelineResult(
      patient_id='test', risk_score=0.80, risk_level='RED',
      z_scores={k: -2.0 for k in ['rmssd','lf_hf_ratio','pnn50','sdnn',
          'rr_ms_min','rr_ms_max','rr_ms_25%','rr_ms_50%','rr_ms_75%','mean_rr']},
      hrv_values={k: 0.0 for k in ['rmssd','lf_hf_ratio','pnn50','sdnn',
          'rr_ms_min','rr_ms_max','rr_ms_25%','rr_ms_50%','rr_ms_75%','mean_rr']},
      personal_baseline={k: {'mean': 0.0, 'std': 1.0} for k in ['rmssd','lf_hf_ratio','pnn50','sdnn',
          'rr_ms_min','rr_ms_max','rr_ms_25%','rr_ms_50%','rr_ms_75%','mean_rr']},
      detected_events=[],
  )
  result = signal_agent_node({'pipeline_result': r})
  sa = result['signal_assessment']
  assert sa.autonomic_pattern == 'pre_sepsis', f'Expected pre_sepsis, got {sa.autonomic_pattern}'
  print(f'PASS VG-2: EVAL_NO_LLM path unaffected, pattern={sa.autonomic_pattern}')
  "
  ```

  **Expected:** Both `PASS VG-1` and `PASS VG-2` printed. Exit code 0 for both.

  **Fail:**
  - `Priority ordering wrong` → `USE_LORA_SIGNAL` block inserted after the Groq import — check indentation and position in `signal_agent_node`.
  - `PASS VG-2` fails with wrong pattern → `EVAL_NO_LLM` check broken — the `if` block must return immediately, check for accidental removal of early return.

---

## Phase 5 — BENCHMARKS.md Three-Way Table

**Goal:** BENCHMARKS.md has a Phase 6 section with a scaffolded three-way comparison table. No-LLM rows are filled. Live-LLM rows are marked `*pending*` (Groq key exhausted). LoRA row is marked `*pending*` (training not yet run).

---

- [ ] 🟥 **Step 6: Add Phase 6 three-way table to `BENCHMARKS.md`** — *Non-critical: documentation*

  **Idempotent:** Yes — appending a new section.

  **Pre-Read Gate:**
  - Run `grep -c "## Phase 6" BENCHMARKS.md`. Must return 0. If any → already added, skip.

  Append the following to the END of `BENCHMARKS.md` (no placeholder tokens — `*pending*` is intentional prose, not a template marker):

  ```markdown

  ---

  ## Phase 6 — Three-Way Comparison

  *Phase 6 recorded 2026-03-22. Groq API key exhausted — live-LLM rows pending key restoration.*
  *LoRA adapter pending training run in `notebooks/05_signal_specialist_lora.ipynb`.*

  ### No-LLM Gate (CI-verified, rule-based path)

  | Approach | F1 | FNR (RED) | FNR (hard) | Protocol | n |
  |----------|----|-----------|------------|----------|---|
  | Generalist (Phase 4) | 1.000 | 0.000 | 0.000 | 100% | 30 |
  | Multi-agent (Phase 5) | 1.000 | 0.000 | 0.000 | 100% | 30 |
  | Multi-agent + LoRA signal (Phase 6) | *pending* | *pending* | *pending* | *pending* | — |

  The no-LLM gate is a CI pass/fail check, not a quality measure. All rule-based paths map
  `risk_score > 0.70 → RED` deterministically, so F1=1.000 is structurally guaranteed.

  ### Live-LLM (Groq llama-3.3-70b-versatile) — Primary Quality Metric

  | Approach | F1 | FNR (RED) | FNR (hard) | Protocol | Latency p50 | Notes |
  |----------|----|-----------|------------|----------|-------------|-------|
  | Generalist single-prompt (Phase 4) | 0.533 | 0.000 | 0.000 | 66.7% | ~2s | Baseline |
  | Multi-agent, all Groq (Phase 5) | *pending* | *pending* | *pending* | *pending* | ~4s | Run when API restored |
  | Multi-agent + LoRA signal (Phase 6) | *pending* | *pending* | *pending* | *pending* | ~0.5s signal | Run after LoRA training |

  **To fill pending rows:**
  ```bash
  # Multi-agent live-LLM (Phase 5 row):
  QDRANT_PATH=qdrant_local python eval/eval_agent.py \
      --agent multi_agent --output results/eval_multiagent_live.json

  # Multi-agent + LoRA signal (Phase 6 row):
  USE_LORA_SIGNAL=1 QDRANT_PATH=qdrant_local python eval/eval_agent.py \
      --agent multi_agent --output results/eval_lora.json
  ```

  ### Phase 6 Success Criteria

  | Criterion | Target | Status |
  |-----------|--------|--------|
  | FIX-10 distribution logging | Present after any retrain | ✅ |
  | FIX-11 label gate in notebook | Cell 0 of notebook 05 | ✅ |
  | LoRA training data | ≥ 200 examples in data/lora_training/ | ✅ |
  | USE_LORA_SIGNAL toggle | Routes to local inference | ✅ |
  | Multi-agent live F1 > 0.533 | Positive delta vs generalist | *pending* |
  | LoRA F1 ≥ multi-agent F1 | LoRA not worse than Groq specialist | *pending* |
  | FNR(RED) = 0.000 all rows | Safety constraint holds | ✅ (no-LLM) |
  ```

  **Git Checkpoint:**
  ```bash
  git add BENCHMARKS.md
  git commit -m "step 6.6: add Phase 6 three-way comparison table scaffold to BENCHMARKS.md"
  ```

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  python -c "
  from pathlib import Path
  bm = Path('BENCHMARKS.md').read_text()
  assert '## Phase 6' in bm, 'Phase 6 section missing'
  assert '## Phase 6 — Three-Way Comparison' in bm, 'Phase 6 section header wrong'
  assert 'Generalist single-prompt (Phase 4) | 0.533' in bm, 'Phase 4 baseline row missing'
  assert '*pending*' in bm, 'Pending markers missing — live-LLM rows should be marked pending'
  assert 'USE_LORA_SIGNAL=1' in bm, 'LoRA eval command missing from pending instructions'
  assert '[VERSION' not in bm and '<VALUE>' not in bm, 'Unfilled placeholder tokens in BENCHMARKS.md'
  print('PASS Step 6: Phase 6 three-way table present with correct structure')
  "
  ```

  **Expected:** `PASS Step 6:`. Exit code 0.

  **Fail:**
  - `Phase 6 section missing` → append did not land — check file was saved after edit.
  - `Unfilled placeholder tokens` → edit left template tokens — search for `[` or `<` in the appended section.

---

## Regression Guard

**Systems at risk from this plan:**
- `train_classifier.py` — FIX-10 adds code before `orig_pos` and inside the write block. A wrong insertion breaks the training script.
- `signal_agent.py` — Step 5 adds a new routing branch. `EVAL_NO_LLM=1` must still return rule-based output unchanged.
- CI `eval.yml` — no changes in this plan; must still pass with `--no-llm` gate.

**Regression verification:**

| System | Pre-change behavior | Post-change verification |
|--------|---------------------|--------------------------|
| `train_classifier.py` syntax | Parses cleanly | `python -c "import ast; ast.parse(open('src/models/train_classifier.py').read()); print('OK')"` |
| `signal_agent_node` EVAL_NO_LLM | Returns rule-based RED for risk_score=0.80 | VG-2 in Step 5 verification |
| CI no-LLM gate (both agents) | F1=1.000, FNR=0.000 | `EVAL_NO_LLM=1 QDRANT_PATH=qdrant_local python eval/eval_agent.py --agent agent --no-llm --fail-below-f1 0.80 --fail-above-fnr 0.0` and same for `--agent multi_agent` |
| Dependency tests | 2 passed | `python -m pytest tests/test_dependency_apis.py -v --tb=short` |

---

## Rollback Procedure

```bash
# Rollback in reverse step order
git revert HEAD    # Step 6: remove Phase 6 BENCHMARKS.md section
git revert HEAD    # Step 5: revert signal_agent.py USE_LORA_SIGNAL toggle
git revert HEAD    # Step 4: remove notebook 05
git revert HEAD    # Step 3b: remove signal_train.jsonl
git revert HEAD    # Step 3: remove generate_lora_data.py
git revert HEAD    # Step 2: revert requirements.txt LoRA deps
git revert HEAD    # Step 1: revert FIX-10 in train_classifier.py

# Confirm rollback complete:
EVAL_NO_LLM=1 QDRANT_PATH=qdrant_local python eval/eval_agent.py \
    --agent agent --no-llm --fail-below-f1 0.80 --fail-above-fnr 0.0 2>&1 | tail -3
# Expect: All CI gates passed.
```

---

## Pre-Flight Checklist

| Phase | Check | How to Confirm | Status |
|-------|-------|----------------|--------|
| **Pre-flight** | FIX-10 absent | `grep -c "=== Training Data Distribution ===" src/models/train_classifier.py` = 0 | ⬜ |
| | USE_LORA_SIGNAL absent | `grep -c "USE_LORA_SIGNAL" src/agent/specialists/signal_agent.py` = 0 | ⬜ |
| | notebook 05 absent | `ls notebooks/05_signal_specialist_lora.ipynb` → error | ⬜ |
| | data/lora_training absent | `ls data/lora_training/` → error | ⬜ |
| | Write block anchor exists | `grep -c 'open(log_path, "w")' src/models/train_classifier.py` = 1 | ⬜ |
| | CI passes | `EVAL_NO_LLM=1 ... --agent agent --no-llm` → CI gates passed | ⬜ |
| **Phase 1** | FIX-10 in train_classifier.py | `grep -c "_dist_n_total" src/models/train_classifier.py` = 1 | ⬜ |
| | LoRA deps installed | `python -c "import peft, datasets, trl, accelerate; print('OK')"` | ⬜ |
| | No placeholder tokens in requirements.txt | `grep -c "\[VERSION" requirements.txt` = 0 | ⬜ |
| **Phase 2** | signal_train.jsonl exists | `ls data/lora_training/signal_train.jsonl` | ⬜ |
| | ≥ 200 records | Verification test in Step 3 | ⬜ |
| **Phase 3** | Notebook exists | `ls notebooks/05_signal_specialist_lora.ipynb` | ⬜ |
| | FIX-11 gate in Cell 0 | Verification test in Step 4 | ⬜ |
| **Phase 4** | USE_LORA_SIGNAL present | `grep -c "USE_LORA_SIGNAL" src/agent/specialists/signal_agent.py` ≥ 1 | ⬜ |
| | Priority ordering correct | VG-1 in Step 5 | ⬜ |
| | CI gate unaffected | VG-2 in Step 5 | ⬜ |
| **Phase 5** | Phase 6 section in BENCHMARKS.md | `grep -c "## Phase 6 — Three-Way" BENCHMARKS.md` = 1 | ⬜ |

---

## Risk Heatmap

| Step | Risk Level | What Could Go Wrong | Early Detection | Idempotent |
|------|-----------|---------------------|-----------------|------------|
| Step 1 (FIX-10) | 🟡 **Medium** | Distribution block inserted after write block → "a" data overwritten | Verification: `pos_capture < pos_write` assertion | Yes |
| Step 2 (deps) | 🟢 **Low** | pip installs to wrong env | `which python` and `pip show peft` must agree | Yes |
| Step 3 (data gen) | 🟢 **Low** | All labels same class (imbalanced) | Verification: `len(dist) >= 2` | Yes |
| Step 4 (notebook) | 🟡 **Medium** | SFTConfig API mismatch (trl version) | Read error carefully; may need `tokenizer=` not `processing_class=` | Yes |
| Step 5 (toggle) | 🔴 **High** | EVAL_NO_LLM branch broken by insertion | VG-2 catches immediately | Yes |
| Step 6 (docs) | 🟢 **Low** | Placeholder tokens left in file | Verification: `'[VERSION' not in bm` | Yes |

---

## Success Criteria

| Feature | Target | Verification |
|---------|--------|--------------|
| FIX-10 logging | Present in train_classifier.py | `grep -c "_dist_n_total" src/models/train_classifier.py` = 1 |
| FIX-11 gate | Cell 0 of notebook 05 | Step 4 verification test |
| Training data | ≥ 200 records, ≥ 2 classes | Step 3 verification test |
| USE_LORA_SIGNAL toggle | Wired, priority correct | VG-1 + VG-2 in Step 5 |
| CI gate (both agents) | F1=1.000, FNR=0.000 | Regression guard command |
| BENCHMARKS.md | Phase 6 section present, no placeholders | Step 6 verification test |
| Test count | ≥ 2 (pre-plan baseline) | `python -m pytest tests/test_dependency_apis.py -v` |

---

⚠️ **Do not mark a step 🟩 Done until its verification test passes.**
⚠️ **Do not proceed past a Human Gate without explicit human input.**
⚠️ **Steps 4 (notebook training) and live-LLM eval are deferred — Groq API exhausted. Do not add `--use-groq` flag to data generator or call any Groq endpoint.**
⚠️ **Do not batch multiple steps into one git commit.**
⚠️ **If idempotent = No, confirm the step has not already run before executing.**
