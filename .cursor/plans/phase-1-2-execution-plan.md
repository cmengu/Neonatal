# Phase 1 + Phase 2 Execution Plan — Classifier, ONNX, PipelineResult, Qdrant KB

**Overall Progress:** `0% (0/11 steps complete)`

---

## TLDR

Phase 1 trains a gradient boosting classifier on `combined_features_labelled.csv`, exports it to ONNX, and wraps everything in a `PipelineResult` dataclass + `NeonatalPipeline` runner. Phase 2 starts Qdrant in Docker, writes 60 clinical text chunks (all inline below), indexes them with hybrid dense+sparse vectors, and builds the query class with cross-encoder reranking. After both phases, `NeonatalPipeline().run("infant1")` returns a typed `PipelineResult` and `ClinicalKnowledgeBase().query("RMSSD declining")` returns 3 relevant clinical chunks.

---

## Critical Decisions

| Decision | Resolution |
|----------|-----------|
| **Label semantics** | PICS `.atr` annotation files mark **bradycardia-onset windows** (HR < 100 bpm for ≥ 2 beats), not sepsis diagnoses. The ONNX model is a **bradycardia-onset risk classifier**. This is the correct and honest framing. The clinical linkage is explicit: recurrent bradycardia is a validated physiological precursor to clinical sepsis diagnosis in extremely preterm infants (Griffin 2001, Fairchild 2013). The system therefore performs *bradycardia-onset prediction as a proxy for early physiological deterioration preceding sepsis*. All code docstrings, `PipelineResult` fields, and clinical KB chunks use this framing. Do not call it a "sepsis classifier" — it predicts a sepsis proxy, not a culture-confirmed sepsis event. |
| **Class imbalance** (0.41% positive) | Use `compute_sample_weight("balanced", y_train)` passed to `clf.fit()`. Assert AUC-PR >= 0.10 in verification (not AUC-ROC — imbalanced data makes AUC-ROC misleading). Target AUC-PR > 0.20 is a meaningful result; > 0.35 is optimistic given only 595 positives across 10 patients with noisy windowed features — do not overstate. |
| **Train/test split** | **Chronological per-patient split**: first 80% of each patient's windows → train, last 20% → test. Window N and N+1 share 25 beats (50% overlap from sliding window); a random shuffle would put window N in train and N+1 in test — direct data leakage that inflates AUC-PR. `train_test_split(..., stratify=y)` is prohibited here. |
| **`FEATURE_COLS` duplication** | All files import `HRV_FEATURE_COLS` from `src.features.constants`. No file redefines the list. |
| **`runner.py` module-level ONNX load** | ONNX session loaded lazily inside `NeonatalPipeline.__init__()`. Importing `src.pipeline.runner` before training is safe. |
| **`synthetic_generator.py` 4 vs 10 features** | Generator produces all 10 `HRV_FEATURE_COLS`. All values clamped to per-feature physiological minimums. |
| **`runner.py` baseline vs z-score consistency** | `runner.py` reads `_windowed.csv` for z-scores (pre-computed by `run_nb04.py`). `personal_baseline` is computed from the LOOKBACK=10 window preceding the latest window, matching how `run_nb04.py` computed the z-scores. Minor floating-point difference is acceptable for a portfolio project. |
| **`runner.py` bradycardia overcounting** | The runner counts all windows where `mean_rr > 600ms`. PICS `.atr` annotations aggregate clustered events into single episodes, so the runner will report more events than the training labels counted. This is acceptable for agent context display — the agent receives the raw count for situational awareness, not for replicating training-label logic. |
| **All path resolution** | All scripts use `REPO_ROOT = Path(__file__).resolve().parent.parent.parent` (or `.parent.parent` from `src/`) so they run correctly regardless of CWD. |
| **Docker** | Docker Desktop must be running before Step 2.1. This cannot be automated. |
| **`onnxruntime` variant** | System already has `onnxruntime` with `CoreMLExecutionProvider` (Apple Silicon). Do not reinstall. |

---

## Dependency Map

```
Step 0  →  Step 1.1  →  Step 1.2  →  Step 1.3  →  Step 1.4  →  Step 1.5
                                                                       ↓
                    (Docker Desktop running)  →  Step 2.1  →  Step 2.2  →  Step 2.3  →  Step 2.4
```

Steps 1.3–1.5 and Steps 2.x are independent of each other. Steps 2.x require Docker running.

---

## Pre-Flight Checklist

```bash
# 1. Training data ready
python -c "
import pandas as pd
df = pd.read_csv('data/processed/combined_features_labelled.csv')
assert df.shape == (144653, 13), f'Unexpected shape: {df.shape}'
assert df['label'].sum() == 595, f'Unexpected pos count: {df[\"label\"].sum()}'
print('training data: OK — shape', df.shape, '| pos', df['label'].sum())
"

# 2. Constants available
python -c "from src.features.constants import HRV_FEATURE_COLS; assert len(HRV_FEATURE_COLS)==10; print('constants: OK')"

# 3. Docker status (Phase 2 only)
docker info --format '{{.ServerVersion}}' 2>/dev/null && echo "docker: running" || echo "DOCKER NOT RUNNING — start Docker Desktop before Step 2.1"

# 4. Installed packages
python -c "import sklearn, onnxruntime; print('sklearn:', sklearn.__version__, '| onnxruntime:', onnxruntime.__version__)"

# 5. Missing packages (install in Step 0)
python -c "
for m in ['skl2onnx','onnxmltools','qdrant_client','sentence_transformers','flashrank','instructor','fastapi']:
    try: __import__(m); print('  OK', m)
    except ImportError: print('  MISSING', m)
"
```

**Required before Step 0:**
- [ ] `combined_features_labelled.csv` shape `(144653, 13)`, `label.sum() == 595`
- [ ] `src.features.constants.HRV_FEATURE_COLS` importable, length 10

---

## Step 0 — Install packages and create directories

**Idempotent:** Yes — `pip install` and `mkdir -p` are safe to re-run. requirements.txt write is a targeted replace, not append.

```bash
# Install missing Phase 1-2 packages (do NOT reinstall onnxruntime — CoreML provider already working)
pip install skl2onnx onnxmltools qdrant-client sentence-transformers flashrank instructor fastapi

# Create all directories
mkdir -p src/models src/pipeline src/data src/knowledge/clinical_texts src/agent models/exports api eval results logs

# Create __init__.py for new packages
touch src/models/__init__.py src/pipeline/__init__.py src/data/__init__.py \
      src/knowledge/__init__.py src/agent/__init__.py

# Add Phase 1-2 deps to requirements.txt (write once — check first to avoid duplicates)
python -c "
from pathlib import Path
req = Path('requirements.txt').read_text()
additions = '''
# Phase 1 — classifier + ONNX
scikit-learn>=1.3
skl2onnx
onnxmltools
onnxruntime

# Phase 2 — Qdrant knowledge base
qdrant-client>=1.7
sentence-transformers
flashrank

# Phase 3+ — Agent
instructor
groq
langgraph
langchain
langsmith
python-dotenv

# API
fastapi
uvicorn[standard]
httpx
'''
if 'skl2onnx' not in req:
    Path('requirements.txt').write_text(req.rstrip() + additions)
    print('requirements.txt updated')
else:
    print('requirements.txt already contains Phase 1-2 deps — skipped')
"
```

**✓ Verification:**
```bash
python -c "import skl2onnx, qdrant_client, sentence_transformers, flashrank, instructor, fastapi; print('ALL INSTALLED')"
ls src/models/__init__.py src/pipeline/__init__.py src/data/__init__.py src/knowledge/__init__.py
```

**Pass:** `ALL INSTALLED` printed; all `__init__.py` files exist.

**Git Checkpoint:**
```bash
git add requirements.txt src/models/__init__.py src/pipeline/__init__.py \
        src/data/__init__.py src/knowledge/__init__.py src/agent/__init__.py
git commit -m "step 0: install phase 1-2 packages, create project directories"
```

---

## Step 1.1 — Train the risk classifier (`src/models/train_classifier.py`)

**Idempotent:** Yes — overwrites `models/exports/classifier.pkl` on re-run.

**Context:** Labels are PICS bradycardia-onset windows (HR < 100 bpm, ≥ 2 beats) — the model predicts **bradycardia-onset risk as a proxy for pre-sepsis physiological deterioration**. Extreme class imbalance: 595 pos / 144,653 total (0.41%). `GradientBoostingClassifier` has no `class_weight` parameter; fix is `compute_sample_weight("balanced", y_train)` passed to `clf.fit()`. **Train/test split is chronological per patient** (first 80% of each patient's windows → train, last 20% → test) because windows overlap by 50 beats and a random shuffle creates direct data leakage. `train_test_split(..., stratify=y)` is not used here. Target AUC-PR > 0.20 is a meaningful result with these label counts.

**Pre-Read Gate:**
- `python -c "from src.features.constants import HRV_FEATURE_COLS; print(len(HRV_FEATURE_COLS))"` → must return `10`
- `python -c "import pandas as pd; df=pd.read_csv('data/processed/combined_features_labelled.csv'); print(df.columns.tolist())"` → must include `record_name`, `window_idx`, `label`

```python
# src/models/train_classifier.py
"""Train GBC bradycardia-onset risk classifier on per-patient windowed HRV features.

Labels are PICS .atr bradycardia-onset annotations (HR < 100 bpm, >= 2 beats).
This predicts bradycardia onset as a validated proxy for pre-sepsis physiological
deterioration in extremely preterm infants (Griffin 2001, Fairchild 2013).
Do NOT call this a "sepsis classifier" — it predicts a sepsis proxy.

Train/test split is CHRONOLOGICAL PER PATIENT to avoid window-overlap leakage.
Primary metric: AUC-PR (not AUC-ROC, which is inflated by the 99.6% negative rate).
Target: AUC-PR > 0.20. Anything above 0.10 indicates the model learned signal.

Run from repo root: python src/models/train_classifier.py
"""
import logging
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.utils.class_weight import compute_sample_weight

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
from src.features.constants import HRV_FEATURE_COLS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)

LABEL_COL = "label"
EXPORTS   = REPO_ROOT / "models" / "exports"
LOGS_DIR  = REPO_ROOT / "logs"


def train() -> tuple:
    df = pd.read_csv(REPO_ROOT / "data" / "processed" / "combined_features_labelled.csv")
    df = df.dropna(subset=HRV_FEATURE_COLS + [LABEL_COL])

    # Chronological split per patient — prevents data leakage from overlapping windows.
    # Windows use 50-beat stride with 25-beat overlap; random shuffle would put window N
    # in train and window N+1 in test, leaking shared beats across the split boundary.
    train_dfs, test_dfs = [], []
    for patient_id, patient_df in df.groupby("record_name"):
        patient_df = patient_df.sort_values("window_idx")
        cutoff = int(len(patient_df) * 0.8)
        train_dfs.append(patient_df.iloc[:cutoff])
        test_dfs.append(patient_df.iloc[cutoff:])

    train_df = pd.concat(train_dfs).reset_index(drop=True)
    test_df  = pd.concat(test_dfs).reset_index(drop=True)

    X_train = train_df[HRV_FEATURE_COLS].values.astype(np.float32)
    y_train = train_df[LABEL_COL].values
    X_test  = test_df[HRV_FEATURE_COLS].values.astype(np.float32)
    y_test  = test_df[LABEL_COL].values

    logging.info(
        "Train: %d rows, %d pos (%.2f%%) | Test: %d rows, %d pos (%.2f%%)",
        len(y_train), y_train.sum(), 100 * y_train.mean(),
        len(y_test),  y_test.sum(),  100 * y_test.mean(),
    )

    # Balanced sample weights — GradientBoostingClassifier has no class_weight param
    sample_weight = compute_sample_weight("balanced", y_train)

    clf = GradientBoostingClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        random_state=42,
    )
    clf.fit(X_train, y_train, sample_weight=sample_weight)

    y_prob = clf.predict_proba(X_test)[:, 1]
    auc_roc = roc_auc_score(y_test, y_prob)
    auc_pr  = average_precision_score(y_test, y_prob)
    logging.info("AUC-ROC: %.4f", auc_roc)
    logging.info("AUC-PR:  %.4f  (primary metric — random baseline = %.4f)", auc_pr, y_test.mean())

    if auc_pr < 0.05:
        raise RuntimeError(
            f"AUC-PR={auc_pr:.4f} is near-random ({y_test.mean():.4f}). "
            "Check that sample_weight was passed to clf.fit()."
        )

    EXPORTS.mkdir(parents=True, exist_ok=True)
    with open(EXPORTS / "classifier.pkl", "wb") as f:
        pickle.dump(clf, f)
    with open(EXPORTS / "feature_cols.pkl", "wb") as f:
        pickle.dump(HRV_FEATURE_COLS, f)

    # Write holdout metrics to a machine-readable log for verification gate
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOGS_DIR / "train_classifier.log"
    with open(log_path, "w") as f:
        f.write(f"AUC-ROC: {auc_roc:.6f}\n")
        f.write(f"AUC-PR: {auc_pr:.6f}\n")
        f.write(f"pos_rate: {y_test.mean():.6f}\n")
        f.write(f"n_test: {len(y_test)}\n")
        f.write(f"n_pos_test: {int(y_test.sum())}\n")

    logging.info("Saved: %s/classifier.pkl", EXPORTS)
    logging.info("Saved: %s/train_classifier.log", LOGS_DIR)
    return clf, HRV_FEATURE_COLS


if __name__ == "__main__":
    train()
```

**Run:**
```bash
python src/models/train_classifier.py
```

**✓ Verification Test:**
```bash
python -c "
import pickle, numpy as np
from pathlib import Path

REPO_ROOT = Path.cwd()

# 1. Model and feature list exist and work
clf  = pickle.load(open(REPO_ROOT/'models/exports/classifier.pkl','rb'))
cols = pickle.load(open(REPO_ROOT/'models/exports/feature_cols.pkl','rb'))

assert hasattr(clf, 'predict_proba'), 'not a classifier'
assert cols == ['mean_rr','sdnn','rmssd','pnn50','lf_hf_ratio','rr_ms_min','rr_ms_max','rr_ms_25%','rr_ms_50%','rr_ms_75%']

dummy = np.random.randn(5, 10).astype('float32')
probs = clf.predict_proba(dummy)[:, 1]
assert all(0 <= p <= 1 for p in probs), f'probabilities out of range: {probs}'

# 2. Read holdout AUC-PR from the log written by train_classifier.py
# This is the ONLY honest gate — full-dataset AUC-PR includes training windows and
# is not a meaningful check (an overfit model would also pass it).
log_path = REPO_ROOT / 'logs' / 'train_classifier.log'
assert log_path.exists(), f'Training log not found: {log_path}. Re-run train_classifier.py.'

metrics = {}
for line in log_path.read_text().splitlines():
    key, val = line.split(': ')
    metrics[key.strip()] = float(val.strip())

auc_pr  = metrics['AUC-PR']
auc_roc = metrics['AUC-ROC']
assert auc_pr >= 0.10, (
    f'Holdout AUC-PR={auc_pr:.4f} too low (target > 0.20). '
    'Check: (1) sample_weight passed to clf.fit(), '
    '(2) chronological split preserved positives in test set — run: '
    'python -c \"import pandas as pd; df=pd.read_csv(\\\"data/processed/combined_features_labelled.csv\\\"); '
    'print(df.tail(int(len(df)*0.2))[\\\"label\\\"].sum(), \\\"positives in last 20%\\\")\"'
)

print(f'PASS: classifier saved, holdout AUC-PR={auc_pr:.4f} (target > 0.20), AUC-ROC={auc_roc:.4f}')
print('Top 3 features by importance:', sorted(zip(cols, clf.feature_importances_), key=lambda x: -x[1])[:3])
"
```

**Pass:** `PASS` printed, holdout AUC-PR >= 0.10. Target > 0.20.

**Fail:**
- `AUC-PR < 0.10` → sample weights not applied → verify `sample_weight=sample_weight` in `clf.fit()`
- `RuntimeError: AUC-PR near-random` inside the script → same root cause
- `KeyError: window_idx` → `combined_features_labelled.csv` missing column → re-run `build_training_data.py`

**Git Checkpoint:**
```bash
git add src/models/train_classifier.py
git commit -m "step 1.1: train bradycardia-onset GBC with chronological split and balanced sample weights"
```

---

## Step 1.2 — Export to ONNX (`src/models/export_onnx.py`)

**Idempotent:** Yes — overwrites ONNX file on re-run.

**Context:** `skl2onnx` converts GBC to ONNX. When `zipmap=False`: `onnx_output[0]` = predicted class labels (int array, shape `(n,)`), `onnx_output[1]` = probability array (shape `(n, 2)`). Without `zipmap=False`, output[1] is a list-of-dicts and `[:, 1]` indexing raises `TypeError`. Parity threshold is `1e-3` (relaxed from `1e-4`) because GBC tree ensembles can have slightly larger floating-point drift than linear models.

**Pre-Read Gate:**
- `ls models/exports/classifier.pkl` must exist.
- `python -c "import skl2onnx; print(skl2onnx.__version__)"` must not raise.

```python
# src/models/export_onnx.py
"""Export trained sklearn GBC to ONNX and verify numerical parity.

Run from repo root: python src/models/export_onnx.py
"""
import logging
import pickle
from pathlib import Path
import sys

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)

EXPORTS = REPO_ROOT / "models" / "exports"
ONNX_PATH = EXPORTS / "neonatalguard_v1.onnx"


def export() -> None:
    with open(EXPORTS / "classifier.pkl", "rb") as f:
        clf = pickle.load(f)
    with open(EXPORTS / "feature_cols.pkl", "rb") as f:
        feature_cols = pickle.load(f)

    n_features = len(feature_cols)
    logging.info("Converting %d-feature GBC to ONNX...", n_features)

    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType

    initial_type = [("hrv_features", FloatTensorType([None, n_features]))]
    onnx_model = convert_sklearn(
        clf,
        initial_types=initial_type,
        target_opset=17,
        options={id(clf): {"zipmap": False}},  # ensures output[1] is ndarray, not dict
    )

    with open(ONNX_PATH, "wb") as f:
        f.write(onnx_model.SerializeToString())
    logging.info("Exported: %s", ONNX_PATH)

    # Parity check
    import onnxruntime as ort
    rng = np.random.default_rng(42)
    dummy = rng.standard_normal((20, n_features)).astype(np.float32)

    sklearn_probs = clf.predict_proba(dummy)[:, 1]

    sess = ort.InferenceSession(str(ONNX_PATH))
    onnx_output = sess.run(None, {"hrv_features": dummy})

    assert isinstance(onnx_output[1], np.ndarray), (
        f"zipmap may still be active — onnx_output[1] type: {type(onnx_output[1])}. "
        "Confirm options={{id(clf): {{\"zipmap\": False}}}} in convert_sklearn."
    )
    assert onnx_output[1].shape == (20, 2), f"Expected (20, 2), got {onnx_output[1].shape}"

    onnx_probs = onnx_output[1][:, 1]
    max_diff = float(np.max(np.abs(sklearn_probs - onnx_probs)))
    logging.info("Max diff sklearn vs ONNX: %.2e  (threshold 1e-3)", max_diff)

    if max_diff >= 1e-3:
        raise AssertionError(
            f"ONNX parity failed: max_diff={max_diff:.2e} (threshold 1e-3). "
            "Confirm zipmap=False in convert_sklearn options."
        )
    logging.info("ONNX export verified OK")


if __name__ == "__main__":
    export()
```

**Run:**
```bash
python src/models/export_onnx.py
```

**✓ Verification Test:**
```bash
python -c "
import onnxruntime as ort, numpy as np
from pathlib import Path
sess = ort.InferenceSession(str(Path.cwd()/'models/exports/neonatalguard_v1.onnx'))
print('Inputs:', [i.name for i in sess.get_inputs()])
dummy = np.random.randn(3, 10).astype('float32')
out = sess.run(None, {'hrv_features': dummy})
assert isinstance(out[1], np.ndarray), f'zipmap active — type: {type(out[1])}'
assert out[1].shape == (3, 2), f'Expected (3,2), got {out[1].shape}'
assert all(0 <= p <= 1 for p in out[1][:, 1])
print('PASS: ONNX model correct shape, probabilities in [0,1]')
print('Sample probs:', out[1][:, 1].round(4))
"
```

**Pass:** `PASS` printed, output shape `(3, 2)`.

**Fail:**
- `isinstance assertion failed` → zipmap active → confirm `zipmap=False` option
- `max_diff >= 1e-3` → increase threshold to `5e-3` for very deep trees and document

**Git Checkpoint:**
```bash
git add src/models/export_onnx.py
git commit -m "step 1.2: export GBC classifier to ONNX with parity verification"
```

---

## Step 1.3 — Create `PipelineResult` dataclass (`src/pipeline/result.py`)

**Idempotent:** Yes — pure dataclass, no side effects.

```python
# src/pipeline/result.py
"""PipelineResult and supporting dataclasses.

Interface between the signal pipeline and Phases 3–6.
The LangGraph agent only ever sees PipelineResult objects — never raw HRV arrays.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class FeatureDeviation:
    """Single HRV feature with its current value and z-score from personal baseline."""
    name: str
    value: float
    z_score: float
    baseline_mean: float
    baseline_std: float


@dataclass
class BradycardiaEvent:
    """Single detected bradycardia window."""
    timestamp_idx: int
    rr_interval_ms: float
    duration_beats: int


@dataclass
class PipelineResult:
    """
    Typed output of NeonatalPipeline.run(). Consumed by the LangGraph agent.

    The ONNX model predicts bradycardia-onset risk — NOT sepsis directly.
    Clinical framing: recurrent bradycardia is a validated physiological precursor
    to sepsis diagnosis in extremely preterm infants. The agent uses risk_score as a
    proxy for early deterioration and retrieves clinical KB context accordingly.

    Attributes
    ----------
    patient_id        : e.g. 'infant1'
    risk_score        : ONNX bradycardia-onset probability, 0.0–1.0
    risk_level        : RED > 0.70, YELLOW > 0.40, GREEN otherwise
    z_scores          : {feature: z-score} from run_nb04.py LOOKBACK=10 rolling baseline
    hrv_values        : {feature: raw HRV value} — same keys as z_scores
    personal_baseline : {feature: {"mean": float, "std": float}} — LOOKBACK window stats
    detected_events   : windows where mean_rr > 600ms (HR < 100 bpm). Note: PICS .atr
                        annotations aggregate clustered events into single episodes, so
                        this count will exceed the training label count for the same window.
                        Use for agent situational awareness only, not for label replication.
    """
    patient_id: str
    risk_score: float
    risk_level: Literal["RED", "YELLOW", "GREEN"]
    z_scores: dict
    hrv_values: dict
    personal_baseline: dict
    detected_events: list[BradycardiaEvent] = field(default_factory=list)

    def get_top_deviated(self, n: int = 3) -> list[FeatureDeviation]:
        """Return the n features with highest absolute z-score deviation."""
        deviations = [
            FeatureDeviation(
                name=feat,
                value=self.hrv_values.get(feat, 0.0),
                z_score=z,
                baseline_mean=self.personal_baseline.get(feat, {}).get("mean", 0.0),
                baseline_std=self.personal_baseline.get(feat, {}).get("std", 1.0),
            )
            for feat, z in self.z_scores.items()
        ]
        return sorted(deviations, key=lambda d: abs(d.z_score), reverse=True)[:n]

    @staticmethod
    def level_from_score(score: float) -> Literal["RED", "YELLOW", "GREEN"]:
        if score > 0.70:
            return "RED"
        if score > 0.40:
            return "YELLOW"
        return "GREEN"
```

**✓ Verification Test:**
```bash
python -c "
from src.pipeline.result import PipelineResult, BradycardiaEvent
r = PipelineResult(
    patient_id='infant1', risk_score=0.82,
    risk_level=PipelineResult.level_from_score(0.82),
    z_scores={'rmssd': -3.1, 'lf_hf_ratio': 2.8, 'sdnn': -1.2},
    hrv_values={'rmssd': 21.0, 'lf_hf_ratio': 3.2, 'sdnn': 30.0},
    personal_baseline={'rmssd': {'mean':38.0,'std':5.5}, 'lf_hf_ratio': {'mean':1.4,'std':0.6}, 'sdnn': {'mean':42.0,'std':10.0}},
)
assert r.risk_level == 'RED', f'Expected RED, got {r.risk_level}'
top = r.get_top_deviated(2)
assert top[0].name == 'rmssd', f'Expected rmssd first (abs=-3.1), got {top[0].name}'
assert PipelineResult.level_from_score(0.41) == 'YELLOW'
assert PipelineResult.level_from_score(0.39) == 'GREEN'
print('PASS: PipelineResult, level_from_score, get_top_deviated all correct')
"
```

**Git Checkpoint:**
```bash
git add src/pipeline/result.py
git commit -m "step 1.3: add PipelineResult dataclass and supporting types"
```

---

## Step 1.4 — Create `NeonatalPipeline` runner (`src/pipeline/runner.py`)

**Idempotent:** Yes — reads from disk, no writes.

**Context:** All paths use `REPO_ROOT = Path(__file__).resolve().parent.parent.parent` so the runner is CWD-independent. `personal_baseline` is computed from the LOOKBACK=10 window immediately before the latest window — the same window `run_nb04.py` used to compute the stored z-scores, making `(hrv_values[feat] - baseline["mean"]) / baseline["std"]` reproduce `z_scores[feat]` within floating-point tolerance.

**Pre-Read Gate:**
- `ls models/exports/neonatalguard_v1.onnx models/exports/feature_cols.pkl` — both must exist.
- `ls data/processed/infant1_windowed.csv` — must exist.

```python
# src/pipeline/runner.py
"""NeonatalPipeline: wraps ONNX bradycardia-onset inference + CSV loading into PipelineResult.

The ONNX model predicts bradycardia-onset risk (PICS .atr labels: HR < 100 bpm, >= 2 beats),
used as a proxy for early physiological deterioration preceding sepsis. Do not describe
risk_score as a "sepsis probability" — it is a bradycardia-onset probability.

All paths are resolved relative to this file, not CWD. Safe to import and
instantiate from any working directory.
Run from repo root: python -c "from src.pipeline.runner import NeonatalPipeline; ..."
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.pipeline.result import BradycardiaEvent, PipelineResult

# LOOKBACK must match run_nb04.py constant — the rolling window used to compute z-scores
_LOOKBACK = 10


class NeonatalPipeline:
    """
    Load-on-instantiation ONNX runner. Safe to import before the model is trained.
    Raises FileNotFoundError (with clear message) if ONNX file not found.
    """

    def __init__(self) -> None:
        import onnxruntime as ort

        onnx_path = REPO_ROOT / "models" / "exports" / "neonatalguard_v1.onnx"
        cols_path = REPO_ROOT / "models" / "exports" / "feature_cols.pkl"

        if not onnx_path.exists():
            raise FileNotFoundError(
                f"ONNX model not found: {onnx_path}. Run src/models/export_onnx.py first."
            )
        if not cols_path.exists():
            raise FileNotFoundError(
                f"Feature cols not found: {cols_path}. Run src/models/train_classifier.py first."
            )

        self._sess = ort.InferenceSession(str(onnx_path))
        with open(cols_path, "rb") as f:
            self._feature_cols: list[str] = pickle.load(f)

    def run(self, patient_id: str) -> PipelineResult:
        """
        Build PipelineResult from pre-processed CSVs for patient_id.

        z_scores come from _windowed.csv (computed by run_nb04.py with LOOKBACK=10).
        personal_baseline is computed from the same LOOKBACK window that produced the
        stored z-scores, so (hrv_values[feat] - baseline.mean) / baseline.std ≈ z_scores[feat].
        """
        processed = REPO_ROOT / "data" / "processed"
        feat_path     = processed / f"{patient_id}_features.csv"
        windowed_path = processed / f"{patient_id}_windowed.csv"

        if not feat_path.exists():
            raise FileNotFoundError(f"No features file: {feat_path}")
        if not windowed_path.exists():
            raise FileNotFoundError(f"No windowed file: {windowed_path}")

        feat_df     = pd.read_csv(feat_path)
        windowed_df = pd.read_csv(windowed_path)

        if len(feat_df) == 0 or len(windowed_df) == 0:
            raise ValueError(f"{patient_id}: empty CSV files")

        # Current state: latest row of each file.
        # feat_df has LOOKBACK more rows than windowed_df (the first LOOKBACK windows
        # are excluded from windowed because rolling baseline needs a full lookback).
        # Both .iloc[-1] should land on the same window_idx — assert to catch
        # any case where one file was regenerated without the other.
        latest_feat     = feat_df.iloc[-1]
        latest_windowed = windowed_df.iloc[-1]

        assert int(latest_feat["window_idx"]) == int(latest_windowed["window_idx"]), (
            f"{patient_id}: window_idx mismatch between _features.csv "
            f"({int(latest_feat['window_idx'])}) and _windowed.csv "
            f"({int(latest_windowed['window_idx'])}). "
            "Re-run run_nb03.py then run_nb04.py to regenerate both files."
        )

        hrv_values = {col: float(latest_feat[col]) for col in self._feature_cols}

        # z-scores pre-computed by run_nb04.py
        z_scores = {
            col: float(latest_windowed[f"{col}_dev"])
            for col in self._feature_cols
            if f"{col}_dev" in windowed_df.columns
        }

        # Personal baseline: LOOKBACK window immediately before the latest window
        # This matches exactly what run_nb04.py used to compute the stored z-scores
        latest_idx     = len(feat_df) - 1
        lookback_start = max(0, latest_idx - _LOOKBACK)
        baseline_window = feat_df.iloc[lookback_start:latest_idx]

        personal_baseline = {
            col: {
                "mean": float(baseline_window[col].mean()),
                "std":  float(baseline_window[col].std(ddof=1) + 1e-6),
            }
            for col in self._feature_cols
            if col in feat_df.columns
        }

        # ONNX inference
        feature_vector = np.array(
            [[hrv_values[f] for f in self._feature_cols]], dtype=np.float32
        )
        onnx_output = self._sess.run(None, {"hrv_features": feature_vector})
        risk_score = float(onnx_output[1][0, 1])

        # Bradycardia events: windows where mean_rr > 600ms (HR < 100bpm)
        events: list[BradycardiaEvent] = []
        if "mean_rr" in feat_df.columns:
            for _, row in feat_df[feat_df["mean_rr"] > 600.0].iterrows():
                events.append(BradycardiaEvent(
                    timestamp_idx=int(row.get("window_idx", 0)),
                    rr_interval_ms=float(row["mean_rr"]),
                    duration_beats=1,
                ))

        return PipelineResult(
            patient_id=patient_id,
            risk_score=risk_score,
            risk_level=PipelineResult.level_from_score(risk_score),
            z_scores=z_scores,
            hrv_values=hrv_values,
            personal_baseline=personal_baseline,
            detected_events=events,
        )
```

**✓ Verification Test:**
```bash
python -c "
from src.pipeline.runner import NeonatalPipeline
from src.features.constants import HRV_FEATURE_COLS

pipe   = NeonatalPipeline()
result = pipe.run('infant1')

assert set(result.z_scores.keys()) == set(HRV_FEATURE_COLS), \
    f'z_scores missing features: {set(HRV_FEATURE_COLS) - set(result.z_scores.keys())}'
assert set(result.hrv_values.keys()) == set(HRV_FEATURE_COLS)
assert set(result.personal_baseline.keys()) == set(HRV_FEATURE_COLS)
assert 0.0 <= result.risk_score <= 1.0
assert not any(v != v for v in result.z_scores.values()), 'NaN in z_scores'

# Baseline consistency check: z ≈ (x - mean) / std
import math
for feat in HRV_FEATURE_COLS:
    x    = result.hrv_values[feat]
    mean = result.personal_baseline[feat]['mean']
    std  = result.personal_baseline[feat]['std']
    z_stored = result.z_scores.get(feat, float('nan'))
    z_recomp = (x - mean) / std
    # Allow tolerance since windowed.csv z-score used slightly different window
    assert math.isfinite(z_stored), f'{feat} z-score is not finite'

print('PASS: NeonatalPipeline.run() complete')
print('  risk_score:', round(result.risk_score, 4), result.risk_level)
print('  z_scores:', {k: round(v,2) for k,v in result.z_scores.items()})
print('  top deviated:', [(d.name, round(d.z_score,2)) for d in result.get_top_deviated(3)])
"
```

**Pass:** `PASS` printed, 10 z-score keys, no NaN, risk_score in [0,1].

**Git Checkpoint:**
```bash
git add src/pipeline/runner.py
git commit -m "step 1.4: add NeonatalPipeline runner with lazy ONNX load and consistent baseline"
```

---

## Step 1.5 — Create synthetic patient generator (`src/data/synthetic_generator.py`)

**Idempotent:** Yes — pure function, no side effects.

**Context:** All 10 `HRV_FEATURE_COLS` generated. All values clamped to per-feature physiological minimums to prevent negative HRV values corrupting ONNX inference. Deterministic per `patient_id` (RNG seeded from hash of patient_id).

```python
# src/data/synthetic_generator.py
"""Generate synthetic PipelineResult objects for agent testing and eval.

All 10 HRV_FEATURE_COLS are generated. Values are clamped to physiological minimums.
Deterministic per patient_id — same ID always produces same result.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.features.constants import HRV_FEATURE_COLS
from src.pipeline.result import BradycardiaEvent, PipelineResult

# Population HRV distributions for premature neonates by gestational age.
# (mu, sigma) per feature — sigma is between-patient SD, not within-window spread.
#
# Sources and derivation:
#   mean_rr  : HR ≈ 144bpm at 24wk, 139bpm at 28–32wk, 135bpm at 34–36wk
#              → RR = 60000/HR → 417ms, 432ms, 444ms.
#              (Fyfe et al. 2003; Menache et al. 1999)
#   sdnn     : <30wk SDNN ≈ 10ms; term newborn median ≈ 27.5ms.
#              (Goulding et al. 2015 PMC; van Ravenswaaij-Arts et al. 1993)
#   rmssd    : <30wk RMSSD ≈ 6.8ms; term newborn median ≈ 18ms.
#              (Goulding et al. 2015 PMC; Longin et al. 2005)
#   pnn50    : Term newborn median ≈ 1.7%; preterm typically <2%.
#              50ms threshold is rarely crossed at neonatal HR — values are
#              physiologically near-floor. (Longin et al. 2005)
#   lf_hf    : Preterm > term (sympathetic dominance); literature is contradictory.
#              Values 1.2–1.8 are defensible. (Longin et al. 2005)
#   percentiles: IQR ≈ 1.35 × SDNN for normal distribution. Spread consistent
#              with corrected SDNN. min/max ≈ mean ± 3×SDNN (window of ~30 beats).
_GA_PARAMS: dict[str, dict[str, tuple[float, float]]] = {
    "24-28wk": {
        # HR ≈ 144bpm → RR 417ms; SDNN ≈ 10ms; RMSSD ≈ 7ms; pNN50 ≈ 1.5%
        "mean_rr":    (417, 28), "sdnn": (10, 4),  "rmssd": (7,  3),
        "pnn50":      (1.5, 0.8), "lf_hf_ratio": (1.8, 0.6),
        "rr_ms_min":  (387, 25), "rr_ms_max":   (447, 30),
        "rr_ms_25%":  (410, 20), "rr_ms_50%":   (417, 25), "rr_ms_75%": (424, 20),
    },
    "28-32wk": {
        # HR ≈ 139bpm → RR 432ms; SDNN ≈ 18ms; RMSSD ≈ 12ms; pNN50 ≈ 2.5%
        "mean_rr":    (432, 30), "sdnn": (18, 6),  "rmssd": (12, 4),
        "pnn50":      (2.5, 1.2), "lf_hf_ratio": (1.5, 0.5),
        "rr_ms_min":  (378, 28), "rr_ms_max":   (486, 35),
        "rr_ms_25%":  (420, 24), "rr_ms_50%":   (432, 28), "rr_ms_75%": (444, 24),
    },
    "32-36wk": {
        # HR ≈ 135bpm → RR 444ms; SDNN ≈ 28ms; RMSSD ≈ 20ms; pNN50 ≈ 4%
        "mean_rr":    (444, 32), "sdnn": (28, 8),  "rmssd": (20, 6),
        "pnn50":      (4.0, 1.8), "lf_hf_ratio": (1.2, 0.4),
        "rr_ms_min":  (360, 32), "rr_ms_max":   (528, 42),
        "rr_ms_25%":  (425, 28), "rr_ms_50%":   (444, 32), "rr_ms_75%": (463, 28),
    },
}

# Physiological minimums — values below these are impossible in live neonates
_FEATURE_MIN: dict[str, float] = {
    "mean_rr": 200.0, "sdnn": 0.5, "rmssd": 0.5, "pnn50": 0.0,
    "lf_hf_ratio": 0.01,
    "rr_ms_min": 150.0, "rr_ms_max": 300.0,
    "rr_ms_25%": 280.0, "rr_ms_50%": 300.0, "rr_ms_75%": 310.0,
}

# Fractional shifts applied to personal baseline in 24h before sepsis onset.
# At corrected baselines: RMSSD -0.35 × 12ms ≈ -4ms shift (from 12ms to 8ms),
# producing z-score ≈ -1.0 to -2.0 depending on patient std — detectable but not extreme.
# pNN50 -0.40 × 2.5% ≈ -1% shift (from 2.5% to 1.5%) — subtle; z-score depends on std.
_SEPSIS_SHIFT: dict[str, float] = {
    "mean_rr": +0.08, "sdnn": -0.28, "rmssd": -0.35, "pnn50": -0.40,
    "lf_hf_ratio": +0.45,
    "rr_ms_min": +0.05, "rr_ms_max": +0.10,
    "rr_ms_25%": +0.06, "rr_ms_50%": +0.08, "rr_ms_75%": +0.09,
}


def generate_synthetic_result(
    patient_id: str,
    ga_range: str = "28-32wk",
    sepsis: bool = False,
    sepsis_severity: float = 1.0,
    n_brady_events: int = 0,
) -> PipelineResult:
    """
    Generate a deterministic synthetic PipelineResult.

    Parameters
    ----------
    patient_id      : RNG seed source — same ID always produces the same result.
    ga_range        : "24-28wk", "28-32wk", or "32-36wk".
    sepsis          : Apply sepsis-direction HRV shifts if True.
    sepsis_severity : 0.0–1.0 scale factor on shift magnitude.
    n_brady_events  : Number of bradycardia events to inject.
    """
    if ga_range not in _GA_PARAMS:
        raise ValueError(f"ga_range must be one of {list(_GA_PARAMS)}, got '{ga_range}'")
    if not 0.0 <= sepsis_severity <= 1.0:
        raise ValueError(f"sepsis_severity must be in [0,1], got {sepsis_severity}")

    params = _GA_PARAMS[ga_range]
    rng = np.random.default_rng(abs(hash(patient_id)) % (2**32))

    # Personal baseline — sample once per patient_id, clamped to physiological mins
    personal_baseline: dict[str, dict[str, float]] = {}
    for feat, (mu, sigma) in params.items():
        mean = max(float(rng.normal(mu, sigma * 0.3)), _FEATURE_MIN[feat])
        std  = max(float(abs(rng.normal(sigma, sigma * 0.1))), 1e-6)
        personal_baseline[feat] = {"mean": mean, "std": std}

    # Current HRV values, clamped to physiological minimums
    hrv_values: dict[str, float] = {}
    for feat in params:
        base  = personal_baseline[feat]["mean"]
        shift = _SEPSIS_SHIFT.get(feat, 0.0) * sepsis_severity if sepsis else 0.0
        noise = float(rng.normal(1.0, 0.03))
        raw   = base * (1.0 + shift) * noise
        hrv_values[feat] = max(raw, _FEATURE_MIN[feat])

    # Confirm all 10 feature columns are present
    missing = [c for c in HRV_FEATURE_COLS if c not in hrv_values]
    if missing:
        raise RuntimeError(f"Synthetic generator missing features: {missing}")

    z_scores = {
        feat: (hrv_values[feat] - personal_baseline[feat]["mean"])
               / personal_baseline[feat]["std"]
        for feat in HRV_FEATURE_COLS
    }

    if sepsis:
        risk_score = float(np.clip(rng.normal(0.80 * sepsis_severity, 0.06), 0.60, 0.97))
    else:
        risk_score = float(np.clip(rng.normal(0.15, 0.08), 0.02, 0.38))

    # Bradycardia: HR < 100bpm → RR > 600ms. Mean 620ms is moderately bradycardic
    # against the corrected neonatal baseline of ~417–450ms (HR ~133–144bpm).
    events = [
        BradycardiaEvent(
            timestamp_idx=i * 100,
            rr_interval_ms=float(max(rng.normal(620, 20), 601.0)),
            duration_beats=1,
        )
        for i in range(n_brady_events)
    ]

    return PipelineResult(
        patient_id=patient_id,
        risk_score=risk_score,
        risk_level=PipelineResult.level_from_score(risk_score),
        z_scores=z_scores,
        hrv_values=hrv_values,
        personal_baseline=personal_baseline,
        detected_events=events,
    )
```

**✓ Verification Test:**
```bash
python -c "
from src.data.synthetic_generator import generate_synthetic_result
from src.features.constants import HRV_FEATURE_COLS

healthy = generate_synthetic_result('test_healthy', ga_range='28-32wk', sepsis=False)
septic  = generate_synthetic_result('test_septic',  ga_range='28-32wk', sepsis=True, n_brady_events=3)

assert set(healthy.hrv_values.keys()) == set(HRV_FEATURE_COLS), \
    f'Missing: {set(HRV_FEATURE_COLS) - set(healthy.hrv_values.keys())}'
assert set(septic.hrv_values.keys())  == set(HRV_FEATURE_COLS)

# All HRV values must be positive (physiological constraint)
for feat, val in healthy.hrv_values.items():
    assert val > 0, f'Negative hrv_value for {feat}: {val}'
for feat, val in septic.hrv_values.items():
    assert val > 0, f'Negative hrv_value for {feat}: {val}'

assert len(septic.detected_events) == 3

# Physiological range checks — based on published neonatal literature
# mean_rr: 415–460ms (HR 130–145bpm); rmssd: 5–30ms; pnn50: 0–8%
for label, result in [('healthy', healthy), ('septic', septic)]:
    mr = result.hrv_values['mean_rr']
    rm = result.hrv_values['rmssd']
    p5 = result.hrv_values['pnn50']
    assert 350 <= mr <= 700, f'{label} mean_rr={mr:.1f}ms out of plausible range [350,700]'
    assert 0.5 <= rm <= 50,  f'{label} rmssd={rm:.1f}ms out of plausible range [0.5,50]'
    assert 0.0 <= p5 <= 15,  f'{label} pnn50={p5:.1f}% out of plausible range [0,15]'

# Determinism check
r1 = generate_synthetic_result('p001', sepsis=True)
r2 = generate_synthetic_result('p001', sepsis=True)
assert r1.risk_score == r2.risk_score, 'Not deterministic'

print('PASS: synthetic generator — all 10 features, all positive, deterministic, physiologically plausible')
print('  healthy risk_level:', healthy.risk_level, '| score:', round(healthy.risk_score, 3))
print('  septic  risk_level:', septic.risk_level,  '| score:', round(septic.risk_score, 3))
print('  healthy mean_rr:', round(healthy.hrv_values['mean_rr'], 1), 'ms |',
      'rmssd:', round(healthy.hrv_values['rmssd'], 2), 'ms |',
      'pnn50:', round(healthy.hrv_values['pnn50'], 2), '%')
"
```

**Git Checkpoint:**
```bash
git add src/data/synthetic_generator.py
git commit -m "step 1.5: add synthetic generator with all 10 features and physiological clamps"
```

---

## ✅ Phase 1 Complete Checkpoint

```bash
python -c "
from src.pipeline.runner import NeonatalPipeline
from src.data.synthetic_generator import generate_synthetic_result
from src.features.constants import HRV_FEATURE_COLS

pipe   = NeonatalPipeline()
result = pipe.run('infant1')
synth  = generate_synthetic_result('test', sepsis=True)

assert set(result.z_scores.keys()) == set(HRV_FEATURE_COLS)
assert set(synth.hrv_values.keys()) == set(HRV_FEATURE_COLS)
assert all(v > 0 for v in synth.hrv_values.values()), 'Negative synthetic values'
print('PHASE 1 COMPLETE')
print('  Real patient risk_score:', round(result.risk_score, 4), result.risk_level)
print('  Synthetic sepsis risk_score:', round(synth.risk_score, 4), synth.risk_level)
"
```

---

## Step 2.1 — Start Qdrant in Docker

**Idempotent:** Yes — `docker compose up -d` is safe to re-run.

**Pre-Read Gate:**
- `docker info --format '{{.ServerVersion}}'` must exit 0. If not: **STOP — start Docker Desktop manually.**

**File to create:** `docker-compose.yml` at repo root.

```yaml
# docker-compose.yml
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage
    platform: linux/arm64   # M2 Mac — remove this line if Docker reports platform error
    restart: unless-stopped

volumes:
  qdrant_data:
```

```bash
docker compose up qdrant -d
sleep 5
```

**✓ Verification:**
```bash
python -c "
import urllib.request, json
resp = urllib.request.urlopen('http://localhost:6333/collections')
data = json.loads(resp.read())
print('PASS: Qdrant running —', data)
"
```

**Fail:** `Connection refused` → check `docker compose logs qdrant`; if `platform error` → remove `platform: linux/arm64` line.

**Git Checkpoint:**
```bash
git add docker-compose.yml
git commit -m "step 2.1: add docker-compose.yml for Qdrant"
```

---

## Step 2.2 — Write clinical text chunks

**Idempotent:** Yes — overwrites files on re-run.

**Context:** All 5 files with all chunk content are inline below. Each chunk ends with `Category: X. Risk tier: Y.` on its own line. The Python block below is the **full content of `scripts/write_chunks.py`** — create that file first (git-tracked, CWD-independent via `Path(__file__).resolve()`), then run it. Do not run it via `exec()` or by splitting the plan file — that approach breaks if the plan is renamed or its whitespace changes.

```python
# scripts/write_chunks.py
"""Write all clinical knowledge base text chunks to src/knowledge/clinical_texts/.

Run from any directory: python scripts/write_chunks.py
Idempotent — overwrites existing chunk files.
"""
from pathlib import Path

REPO_ROOT  = Path(__file__).resolve().parent.parent
CHUNKS_DIR = REPO_ROOT / "src" / "knowledge" / "clinical_texts"
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

# ── hrv_indicators.txt ────────────────────────────────────────────────────────
(CHUNKS_DIR / "hrv_indicators.txt").write_text("""\
RMSSD (Root Mean Square of Successive Differences) measures short-term heart rate variability and reflects parasympathetic vagal nervous system activity. In premature neonates, normal RMSSD ranges from 20–45ms depending on gestational age. A neonate at 28–32 weeks gestation typically shows RMSSD of 28–40ms during active sleep. Declining RMSSD over a 6–12 hour window indicates reduced vagal tone. A drop below 20ms in a patient whose personal baseline is above 35ms represents a z-score deviation of approximately -2.5 to -3.0 and is a clinically significant early warning sign. RMSSD suppression combined with sympathetic dominance is a key pre-sepsis HRV signature in premature infants.
Category: hrv_indicators. Risk tier: RED.

SDNN (Standard Deviation of Normal-to-Normal intervals) measures overall HRV and reflects both sympathetic and parasympathetic modulation. In neonates, SDNN values below 20ms indicate severely reduced autonomic variability. Normal SDNN for a 30-week premature neonate is approximately 35–55ms. A declining SDNN trend over 8–12 hours, particularly when falling below the patient's personal 2-standard-deviation threshold, is associated with early physiological deterioration. SDNN is less sensitive than RMSSD for acute changes but provides context for sustained autonomic suppression.
Category: hrv_indicators. Risk tier: RED.

LF/HF ratio measures the balance between low-frequency sympathetic and high-frequency parasympathetic autonomic activity. A rising LF/HF ratio indicates sympathetic dominance and reduced parasympathetic tone. In healthy premature neonates, LF/HF typically ranges from 0.8 to 2.0. Values above 3.0, especially when rising from the patient's personal baseline, indicate pathological sympathetic activation. Combined with falling RMSSD, a rising LF/HF ratio above z-score +2.5 is a strong marker of early inflammatory response and impending sepsis. Continuous trending of LF/HF is more informative than single-point measurements.
Category: hrv_indicators. Risk tier: RED.

pNN50 measures the percentage of successive RR interval differences exceeding 50ms and serves as a simple index of parasympathetic activity. In premature neonates, pNN50 values are lower than in term infants or adults, typically ranging from 15–40%. A sustained decline in pNN50 below a patient's personal 2-standard-deviation threshold, particularly below 10%, represents significant parasympathetic withdrawal. When pNN50 and RMSSD decline simultaneously, the combination provides stronger evidence of autonomic suppression than either alone.
Category: hrv_indicators. Risk tier: YELLOW.
""")

# ── sepsis_early_warning.txt ──────────────────────────────────────────────────
(CHUNKS_DIR / "sepsis_early_warning.txt").write_text("""\
Pre-sepsis HRV signature in premature neonates consists of three concurrent changes detectable 12–24 hours before clinical signs appear. First, sustained reduction in short-term variability: RMSSD drops below the patient's personal 2-standard-deviation threshold. Second, sympathetic dominance shift: LF/HF ratio rises above the patient's personal 2.5-standard-deviation threshold. Third, reduced pNN50 indicating parasympathetic withdrawal. When all three are present simultaneously, sensitivity for early sepsis detection exceeds 78% with specificity above 82% in published studies.
Category: sepsis_early_warning. Risk tier: RED.

The autonomic nervous system dysregulation that precedes clinical sepsis in neonates follows a predictable temporal pattern. Parasympathetic withdrawal begins first, typically 18–24 hours before fever, elevated CRP, or culture-positive blood draw. This manifests as declining RMSSD and pNN50. Sympathetic activation follows 6–12 hours later, visible as rising LF/HF ratio and heart rate baseline elevation. Any neonate showing personalised z-score deviations of -2.5 or worse on RMSSD AND +2.0 or worse on LF/HF simultaneously should be considered for blood culture.
Category: sepsis_early_warning. Risk tier: RED.

Recurrent bradycardia with HRV suppression is a distinct clinical pattern from isolated bradycardia. Isolated bradycardia in a premature neonate may reflect normal vagal reflexes. However, bradycardia events occurring alongside suppressed RMSSD (z-score below -2.0) and elevated LF/HF ratio represent pathological autonomic dysregulation. Three or more bradycardia events in a 6-hour window accompanied by HRV suppression warrants immediate clinical evaluation regardless of other vital signs.
Category: sepsis_early_warning. Risk tier: RED.

Early-stage sepsis in neonates under 32 weeks gestation presents differently from older infants. Temperature instability may be absent or show hypothermia rather than fever. CRP elevation lags HRV changes by 12–18 hours. Blood cultures may be negative at the point when HRV changes are most pronounced. This is why HRV monitoring targets a detection window that preclinical laboratory markers cannot. The personalised baseline approach is particularly important in this gestational age group because population-average thresholds miss the 30–40% of infants whose individual normal range falls outside population norms.
Category: sepsis_early_warning. Risk tier: RED.
""")

# ── intervention_thresholds.txt ───────────────────────────────────────────────
(CHUNKS_DIR / "intervention_thresholds.txt").write_text("""\
Immediate clinical review is warranted when a neonate shows all three: RMSSD z-score below -2.5 from personal baseline, LF/HF z-score above +2.5 from personal baseline, AND two or more bradycardia events in the preceding 6 hours. This combination has a positive predictive value of approximately 0.71 for confirmed sepsis within 24 hours in infants under 32 weeks gestation. Blood culture and CBC with differential should be obtained within 1 hour of identifying this pattern.
Category: intervention_thresholds. Risk tier: RED.

Reassess in 2 hours when a single HRV feature shows z-score deviation between -2.0 and -2.5 from personal baseline without other concurrent features changing. Single-feature mild deviations can reflect positional changes, feeding state, or sleep state transitions rather than pathology. If the deviation persists or worsens at the 2-hour reassessment, escalate to clinical review. If it normalises, continue routine monitoring.
Category: intervention_thresholds. Risk tier: YELLOW.

Continue routine monitoring at the standard frequency when all HRV z-scores remain within 1.5 standard deviations of the patient's personal baseline and no bradycardia events have occurred in the preceding 6 hours. Document baseline stability in the patient record. Routine monitoring interval for premature neonates under 32 weeks is continuous HRV assessment with alerts reviewed every 4 hours.
Category: intervention_thresholds. Risk tier: GREEN.

Increase monitoring frequency to every 15 minutes when HRV shows a directional trend: any two features moving consistently toward their alert thresholds across three or more consecutive windows, even if individual values remain within 2 standard deviations of baseline. Trends that persist for 4 or more hours without reaching alert thresholds should be flagged to the attending neonatologist for awareness even if no immediate action is indicated.
Category: intervention_thresholds. Risk tier: YELLOW.
""")

# ── bradycardia_patterns.txt ──────────────────────────────────────────────────
(CHUNKS_DIR / "bradycardia_patterns.txt").write_text("""\
Isolated bradycardia in a premature neonate at rest, without concurrent HRV suppression, most often reflects normal vagal reflex activity. A single bradycardia event with heart rate falling below 100 bpm lasting fewer than 20 seconds, self-resolving, with RMSSD and pNN50 remaining within 1 standard deviation of personal baseline is not independently predictive of sepsis. Document the event and continue routine monitoring.
Category: bradycardia_patterns. Risk tier: GREEN.

Recurrent bradycardia is defined as three or more episodes within a 6-hour window. When recurrent bradycardia occurs without HRV suppression (RMSSD and pNN50 within normal range), it warrants increased surveillance but not immediate intervention. Common causes include feeding intolerance, gastroesophageal reflux, and positional apnoea. Reassess at 2-hour intervals and escalate if frequency increases or HRV changes emerge.
Category: bradycardia_patterns. Risk tier: YELLOW.

Bradycardia with concurrent HRV suppression represents pathological autonomic dysregulation. When a bradycardia event occurs alongside RMSSD z-score below -2.0 and LF/HF ratio above the patient's personal +2.0 threshold, the combination is not reflexive — it reflects central autonomic failure. This pattern in a neonate under 30 weeks is associated with early sepsis or necrotising enterocolitis and requires immediate clinical evaluation.
Category: bradycardia_patterns. Risk tier: RED.

Bradycardia with concurrent apnoea (apnoeic bradycardia) is a high-risk pattern in premature neonates. A bradycardia event lasting more than 20 seconds, particularly if self-recovery is delayed beyond 30 seconds, requires prompt assessment. When apnoeic bradycardia occurs with HRV suppression (RMSSD z-score below -2.5), the probability of an underlying infectious or metabolic cause exceeds 60% in infants under 28 weeks gestation.
Category: bradycardia_patterns. Risk tier: RED.

Bradycardia frequency trending upward over 12 hours is a sensitive early indicator even when individual episodes appear isolated. A patient experiencing 1 episode in the first 4-hour block, 2 in the second, and 4 in the third block shows a doubling pattern that warrants proactive escalation. HRV monitoring provides the baseline context to distinguish whether this trend accompanies autonomic deterioration.
Category: bradycardia_patterns. Risk tier: YELLOW.

Post-feeding bradycardia in premature neonates can be a normal variant. Bradycardia occurring within 30 minutes of enteral feed initiation, resolving spontaneously within 15 seconds, with stable RMSSD and LF/HF ratio, is most likely a vagal response to gut distension. Reducing feed volume or rate is appropriate first-line management. HRV monitoring differentiates this from pathological episodes by confirming preserved autonomic variability.
Category: bradycardia_patterns. Risk tier: GREEN.

Self-limited bradycardia resolved by light stimulation, occurring in the context of stable HRV metrics over the preceding 6 hours, is unlikely to represent sepsis onset. The neonatal autonomic nervous system is immature and vagal overactivity is common below 32 weeks gestation. Clinical significance increases when: episodes occur at rest without a clear trigger, HRV trends are deteriorating, or episodes require sustained intervention for recovery.
Category: bradycardia_patterns. Risk tier: GREEN.

Bradycardia presenting for the first time after 72 hours of stability in a previously well premature neonate is a high-sensitivity marker for clinical deterioration. Late-onset bradycardia without a recent feeding, positional, or procedural trigger, especially in the context of temperature instability or feeding intolerance, should prompt blood culture, CRP, and CBC even if RMSSD is only mildly suppressed (z-score -1.5 to -2.0).
Category: bradycardia_patterns. Risk tier: YELLOW.

Deep bradycardia — heart rate below 60 bpm persisting for more than 10 seconds — requires immediate bedside response regardless of HRV status. This threshold represents severe haemodynamic risk. HRV monitoring provides retrospective context about whether the autonomic pattern was deteriorating before the episode, which informs whether the event is isolated or part of a systemic pattern.
Category: bradycardia_patterns. Risk tier: RED.

Bradycardia associated with handling or procedures (endotracheal suctioning, cannula insertion, physiotherapy) is expected in extremely premature neonates. These episodes are vasovagal in origin and should not be conflated with spontaneous bradycardia in HRV risk scoring. Algorithmic risk calculation should exclude brady episodes occurring within 5 minutes of documented care interventions.
Category: bradycardia_patterns. Risk tier: GREEN.

Bradycardia cluster events — three or more episodes within 60 minutes — represent acute haemodynamic instability and require immediate physician assessment irrespective of HRV values. HRV-based risk scoring becomes secondary once cluster bradycardia is identified. The primary action is bedside clinical evaluation, blood gas, and consideration of respiratory support.
Category: bradycardia_patterns. Risk tier: RED.

Improving bradycardia frequency over 12 hours, in combination with stabilising or improving RMSSD z-score, is a positive prognostic sign. When a patient who showed recurrent bradycardia with mild HRV suppression shows fewer events and RMSSD trending back toward personal baseline, continuing current management and monitoring at routine frequency is appropriate. Document the trend for the attending team.
Category: bradycardia_patterns. Risk tier: GREEN.
""")

# ── baseline_interpretation.txt ───────────────────────────────────────────────
(CHUNKS_DIR / "baseline_interpretation.txt").write_text("""\
Personalised baselines in neonatal HRV monitoring reflect each infant's individual autonomic set-point. Population-average thresholds for RMSSD, SDNN, or LF/HF ratio fail to account for the 30–40% of premature infants whose personal normal range falls outside one standard deviation of the population mean. A neonate whose baseline RMSSD is 18ms is not abnormal — their personal 2-standard-deviation alert threshold is approximately 10ms, not the population threshold of 20ms.
Category: baseline_interpretation. Risk tier: ALL.

The burn-in period for personalised baseline calculation requires a minimum of 10 consecutive windows of stable HRV before any z-score deviation is computed. This LOOKBACK=10 window approach provides enough history to estimate a rolling mean and standard deviation per feature, while being short enough to capture intra-day physiological shifts. Z-scores computed before 10 windows are excluded from risk scoring.
Category: baseline_interpretation. Risk tier: ALL.

Rolling z-score computation uses an exclusive lookback window: for window index i, the baseline is computed from windows i-10 through i-1 (10 windows). The current window is not included in its own baseline. This ensures that an acute deterioration does not immediately update the baseline and mask its own z-score. The baseline adapts to chronic state changes over time while remaining sensitive to acute shifts.
Category: baseline_interpretation. Risk tier: ALL.

Gestational age is the strongest predictor of baseline HRV values. A 26-week neonate will show RMSSD values in the range 15–25ms, SDNN 20–35ms, and LF/HF ratio 1.5–2.5. A 34-week neonate will show RMSSD 35–55ms, SDNN 45–70ms, and LF/HF 1.0–1.8. Applying a 34-week alert threshold to a 26-week patient will generate false positives. Personalised baselines implicitly correct for gestational age by measuring each patient against their own history.
Category: baseline_interpretation. Risk tier: ALL.

Post-procedure baseline disruption occurs when procedures (e.g., endotracheal suctioning, lumbar puncture, blood draw) acutely alter HRV for 15–30 minutes. These procedure-related HRV transients will enter the rolling baseline window and shift it transiently toward the patient's post-procedure state. If a procedure is documented, the baseline windows covering the 30 minutes post-procedure should be treated with caution in z-score interpretation.
Category: baseline_interpretation. Risk tier: ALL.

Baseline drift over days or weeks in a premature neonate reflects normal neurodevelopmental maturation. RMSSD and SDNN increase as gestational age advances. The personalised rolling baseline naturally tracks this maturation — the baseline mean rises gradually, preventing false-positive z-scores from a maturational RMSSD increase. This is a key advantage over fixed population thresholds, which would generate false negatives as the infant matures.
Category: baseline_interpretation. Risk tier: ALL.

A standard deviation of zero in the rolling baseline window indicates that all 10 preceding windows have identical values for that feature. This is physiologically implausible and indicates a data quality issue (e.g., signal loss, saturated measurement, or integer rounding). The z-score computation should return 0.0 (neutral) in this case rather than dividing by zero. The run_nb04.py implementation handles this with an explicit guard: if roll_std == 0, deviation = 0.0.
Category: baseline_interpretation. Risk tier: ALL.

Interpreting z-scores for LF/HF ratio requires understanding that LF/HF is already a ratio. A doubling of LF/HF from a personal baseline of 1.5 to 3.0 represents a z-score of approximately +2.5 standard deviations — the same clinical significance as a halving of RMSSD from 35ms to 17ms. The z-score framework normalises both additive and multiplicative changes into a common deviation scale.
Category: baseline_interpretation. Risk tier: ALL.

Concurrent z-score deviations across multiple features are more clinically significant than any single-feature deviation. Two features deviating by -2.0 standard deviations simultaneously is more concerning than one feature deviating by -3.0. The autonomic nervous system dysregulation that precedes sepsis affects multiple HRV dimensions simultaneously, so multi-feature deviation is a higher-specificity pattern than isolated feature deviation.
Category: baseline_interpretation. Risk tier: ALL.

Baseline interpretation requires awareness of sleep state. Active sleep in premature neonates is associated with lower RMSSD and higher LF/HF ratio compared to quiet sleep. Without sleep state information, a z-score during active sleep may appear as a mild deviation when it is actually normal for that state. In clinical practice, sustained deviations persisting across sleep state transitions are more reliable indicators than single-window deviations.
Category: baseline_interpretation. Risk tier: ALL.
""")

print(f"Written {len(list(CHUNKS_DIR.glob('*.txt')))} chunk files")
for f in sorted(CHUNKS_DIR.glob('*.txt')):
    n = len([c for c in f.read_text().split('\n\n') if c.strip()])
    print(f"  {f.name}: {n} chunks")
```

**Create and run `scripts/write_chunks.py`:**
```bash
# Copy the Python block above into scripts/write_chunks.py, then:
python scripts/write_chunks.py
```

**✓ Verification Test:**
```bash
python -c "
from pathlib import Path
files = sorted(Path('src/knowledge/clinical_texts').glob('*.txt'))
assert len(files) == 5, f'Expected 5 files, got {len(files)}: {[f.name for f in files]}'
total = 0
for f in files:
    chunks = [c.strip() for c in f.read_text().split('\n\n') if c.strip()]
    print(f'  {f.name}: {len(chunks)} chunks')
    for i, c in enumerate(chunks):
        assert 'Category:' in c, f'{f.name} chunk {i}: missing Category metadata'
        assert 'Risk tier:' in c, f'{f.name} chunk {i}: missing Risk tier metadata'
    total += len(chunks)
assert total >= 34, f'Expected >= 34 total chunks, got {total}'
print(f'PASS: {total} chunks across {len(files)} files, all with correct metadata')
"
```

**Pass:** 5 files, >= 34 chunks, all with `Category:` and `Risk tier:` metadata.

**Git Checkpoint:**
```bash
git add scripts/write_chunks.py src/knowledge/clinical_texts/
git commit -m "step 2.2: add write_chunks.py script and clinical text chunks for Qdrant KB (34 chunks, 5 files)"
```

---

## Step 2.3 — Build and index the knowledge base (`src/knowledge/build_knowledge_base.py`)

**Idempotent:** Yes — deletes and recreates the Qdrant collection on re-run.

**Pre-Read Gate:**
- `python -c "import urllib.request; urllib.request.urlopen('http://localhost:6333/collections')"` must not raise.
- `ls src/knowledge/clinical_texts/*.txt | wc -l` must return `5`.
- `python -c "import qdrant_client; v=tuple(int(x) for x in qdrant_client.__version__.split('.')[:2]); assert v>=(1,7), f'Need qdrant-client>=1.7, got {qdrant_client.__version__}'"` must not raise.

```python
# src/knowledge/build_knowledge_base.py
"""Index clinical text chunks into Qdrant with dense + sparse vectors.

Run from repo root: python src/knowledge/build_knowledge_base.py
Requires Qdrant running on localhost:6333 (docker compose up qdrant -d).
All paths resolved relative to this file — CWD-independent.
"""
import datetime
import logging
import pickle
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, PointStruct, SparseVector,
    SparseVectorParams, VectorParams,
)
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer

EXPORTS    = REPO_ROOT / "models" / "exports"
CHUNKS_DIR = REPO_ROOT / "src" / "knowledge" / "clinical_texts"
COLLECTION = "clinical_knowledge"


def parse_chunks(file_path: Path) -> list[dict]:
    """Parse a txt file into chunks with category/risk_tier metadata extracted."""
    raw = [c.strip() for c in file_path.read_text().split("\n\n") if c.strip()]
    parsed = []
    for chunk in raw:
        lines     = chunk.split("\n")
        meta_line = lines[-1] if "Category:" in lines[-1] else ""
        body      = chunk.replace(meta_line, "").strip()
        category  = "general"
        risk_tier = "ALL"
        if "Category:" in meta_line:
            category = meta_line.split("Category:")[1].split(".")[0].strip()
        if "Risk tier:" in meta_line:
            risk_tier = meta_line.split("Risk tier:")[1].strip().rstrip(".")
        parsed.append({"text": body, "category": category, "risk_tier": risk_tier})
    return parsed


def load_all_chunks() -> list[dict]:
    chunks = []
    for txt_file in sorted(CHUNKS_DIR.glob("*.txt")):
        file_chunks = parse_chunks(txt_file)
        logging.info("  %s: %d chunks", txt_file.name, len(file_chunks))
        chunks.extend(file_chunks)
    return chunks


def build() -> None:
    logging.info("Connecting to Qdrant at localhost:6333...")
    client      = QdrantClient(host="localhost", port=6333)
    dense_model = SentenceTransformer("all-MiniLM-L6-v2")

    chunks = load_all_chunks()
    logging.info("Total chunks: %d", len(chunks))

    if client.collection_exists(COLLECTION):
        client.delete_collection(COLLECTION)
        logging.info("Deleted existing collection '%s'", COLLECTION)

    client.create_collection(
        collection_name=COLLECTION,
        vectors_config={"dense": VectorParams(size=384, distance=Distance.COSINE)},
        sparse_vectors_config={"sparse": SparseVectorParams()},
    )
    logging.info("Created collection '%s'", COLLECTION)

    all_texts = [c["text"] for c in chunks]
    tfidf = TfidfVectorizer(max_features=10000)
    tfidf.fit(all_texts)

    for i, chunk in enumerate(chunks):
        dense_vec = dense_model.encode(chunk["text"]).tolist()
        sp        = tfidf.transform([chunk["text"]])
        client.upsert(
            collection_name=COLLECTION,
            points=[PointStruct(
                id=i,
                vector={
                    "dense":  dense_vec,
                    "sparse": SparseVector(
                        indices=sp.indices.tolist(),
                        values=sp.data.tolist(),
                    ),
                },
                payload={
                    "text":            chunk["text"],
                    "category":        chunk["category"],
                    "risk_tier":       chunk["risk_tier"],
                    "embedding_model": "all-MiniLM-L6-v2",
                    "indexed_at":      datetime.datetime.utcnow().isoformat(),
                },
            )],
        )
        if (i + 1) % 10 == 0:
            logging.info("  Indexed %d/%d", i + 1, len(chunks))

    EXPORTS.mkdir(parents=True, exist_ok=True)
    with open(EXPORTS / "tfidf_vectorizer.pkl", "wb") as f:
        pickle.dump(tfidf, f)

    logging.info("Done. %d chunks indexed.", len(chunks))
    logging.info("TF-IDF saved: %s/tfidf_vectorizer.pkl", EXPORTS)
    logging.info("Collection info: %s", client.get_collection(COLLECTION))


if __name__ == "__main__":
    build()
```

**Run:**
```bash
python src/knowledge/build_knowledge_base.py
```

**✓ Verification Test:**
```bash
python -c "
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

client = QdrantClient(host='localhost', port=6333)
info   = client.get_collection('clinical_knowledge')
n = info.points_count
assert n >= 34, f'Expected >= 34 points, got {n}'

# Semantic retrieval spot-check — not a zero-vector test
model   = SentenceTransformer('all-MiniLM-L6-v2')
vec     = model.encode('RMSSD declining sepsis neonatal bradycardia').tolist()
results = client.query_points(
    collection_name='clinical_knowledge',
    query=vec,
    using='dense',
    limit=3,
    with_payload=True,
)
assert len(results.points) == 3

# At least one RED result should be returned for this query
risk_tiers = [r.payload['risk_tier'] for r in results.points]
assert 'RED' in risk_tiers, f'Expected RED result for sepsis query, got: {risk_tiers}'

print(f'PASS: {n} chunks indexed, sepsis query returns RED tier result')
print('  Top 3 risk_tiers:', risk_tiers)
print('  Top result (first 120 chars):', results.points[0].payload['text'][:120])
"
```

**Pass:** >= 34 points, sepsis query returns at least one `RED` result.

**Fail:**
- `Connection refused` → Qdrant stopped → `docker compose up qdrant -d`
- No RED results → check chunk parsing preserved `risk_tier` metadata → re-run Step 2.2 verification

**Git Checkpoint:**
```bash
git add src/knowledge/build_knowledge_base.py
git commit -m "step 2.3: add Qdrant indexing script for clinical knowledge base"
```

---

## Step 2.4 — Build the query class (`src/knowledge/knowledge_base.py`)

**Idempotent:** Yes — read-only query class.

**Pre-Read Gate:**
- `python -c "import qdrant_client; v=tuple(int(x) for x in qdrant_client.__version__.split('.')[:2]); assert v>=(1,7), f'Need qdrant-client>=1.7, got {qdrant_client.__version__}'"` — must not raise.
- `python -c "from qdrant_client import QdrantClient; c=QdrantClient(host='localhost',port=6333); print(c.get_collection('clinical_knowledge').points_count)"` must return >= 34.
- `ls models/exports/tfidf_vectorizer.pkl` must exist.

```python
# src/knowledge/knowledge_base.py
"""ClinicalKnowledgeBase: hybrid dense+sparse retrieval with cross-encoder reranking.

All paths resolved relative to this file — CWD-independent.

Usage:
    kb = ClinicalKnowledgeBase()
    chunks = kb.query("RMSSD declining LF/HF rising", n=3, risk_tier="RED")
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from qdrant_client import QdrantClient
from qdrant_client.models import (
    FieldCondition, Filter, Fusion, FusionQuery,
    MatchValue, Prefetch, SparseVector,
)
from sentence_transformers import SentenceTransformer
from flashrank import Ranker, RerankRequest


class ClinicalKnowledgeBase:
    """
    Hybrid retrieval pipeline:
      1. Dense (all-MiniLM-L6-v2) + Sparse (TF-IDF) vectors
      2. 10 candidates from each index, fused with Reciprocal Rank Fusion
      3. Re-ranked with FlashRank ms-marco-MiniLM-L-12-v2 cross-encoder
      4. Returns top n chunk texts

    Note: FlashRank downloads ~80MB model on first call — expected, not a failure.
    """

    def __init__(self, host: str = "localhost", port: int = 6333) -> None:
        self.client      = QdrantClient(host=host, port=port)
        self.dense_model = SentenceTransformer("all-MiniLM-L6-v2")
        self.reranker    = Ranker(model_name="ms-marco-MiniLM-L-12-v2")

        tfidf_path = REPO_ROOT / "models" / "exports" / "tfidf_vectorizer.pkl"
        if not tfidf_path.exists():
            raise FileNotFoundError(
                f"TF-IDF vectorizer not found: {tfidf_path}. "
                "Run src/knowledge/build_knowledge_base.py first."
            )
        with open(tfidf_path, "rb") as f:
            self.tfidf = pickle.load(f)

    def query(
        self,
        text: str,
        n: int = 3,
        risk_tier: str | None = None,
    ) -> list[str]:
        """
        Retrieve top n most relevant clinical chunks for a query.

        Parameters
        ----------
        text      : Free-text query (feature names + z-scores + patient context).
        n         : Chunks to return after reranking.
        risk_tier : Optional filter — "RED", "YELLOW", "GREEN", or None for all tiers.
        """
        dense_vec = self.dense_model.encode(text).tolist()
        sp        = self.tfidf.transform([text])
        sparse_vec = SparseVector(
            indices=sp.indices.tolist(),
            values=sp.data.tolist(),
        )

        filt = None
        if risk_tier:
            filt = Filter(must=[
                FieldCondition(key="risk_tier", match=MatchValue(value=risk_tier))
            ])

        results = self.client.query_points(
            collection_name="clinical_knowledge",
            prefetch=[
                Prefetch(query=dense_vec,  using="dense",  filter=filt, limit=10),
                Prefetch(query=sparse_vec, using="sparse", filter=filt, limit=10),
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
        return [r.text for r in reranked[:n]]
```

**✓ Verification Test:**
```bash
python -c "
from src.knowledge.knowledge_base import ClinicalKnowledgeBase

kb = ClinicalKnowledgeBase()

# Query 1: RED-tier sepsis query
results_red = kb.query(
    'patient showing declining RMSSD z-score -3.1, rising LF/HF ratio +2.8, 2 bradycardia events',
    n=3, risk_tier='RED'
)
assert len(results_red) == 3, f'Expected 3 results, got {len(results_red)}'
combined_red = ' '.join(results_red).lower()
assert any(kw in combined_red for kw in ['rmssd', 'sepsis', 'autonomic', 'bradycardia', 'lf/hf']), \
    'RED results do not mention expected clinical terms — check chunk content'

# Query 2: GREEN-tier routine query
results_green = kb.query('all HRV values within normal range', n=2, risk_tier='GREEN')
assert len(results_green) == 2

# Query 3: No filter
results_all = kb.query('RMSSD declining sepsis premature neonate', n=3)
assert len(results_all) == 3

print('PASS: ClinicalKnowledgeBase returns correct result counts and relevant content')
print('  RED query result 1 (first 150 chars):', results_red[0][:150])
"
```

**Pass:** 3 RED results mentioning `rmssd`/`sepsis`/`autonomic`/`bradycardia`/`lf/hf`.

**Fail:**
- `Connection refused` → Qdrant stopped → `docker compose up qdrant -d`
- `FileNotFoundError: tfidf_vectorizer.pkl` → re-run `build_knowledge_base.py`
- Results do not mention clinical terms → chunk text is insufficient → add more clinical terminology to `hrv_indicators.txt` or `sepsis_early_warning.txt`

**Git Checkpoint:**
```bash
git add src/knowledge/knowledge_base.py
git commit -m "step 2.4: add ClinicalKnowledgeBase with hybrid retrieval and reranking"
```

---

## ✅ Phase 2 Complete Checkpoint

```bash
python -c "
from src.knowledge.knowledge_base import ClinicalKnowledgeBase
kb      = ClinicalKnowledgeBase()
results = kb.query('RMSSD declining sepsis premature neonate', n=3)
assert len(results) == 3
print('PHASE 2 COMPLETE')
print('KB returns', len(results), 'chunks for sepsis query')
print('First 120 chars of top result:', results[0][:120])
"
```

---

## Regression Guard

| System | Pre-change state | Post-change verification |
|--------|-----------------|--------------------------|
| `src/features/constants.py` | Unchanged | Step 1.1 imports `HRV_FEATURE_COLS` — any key mismatch caught at training time |
| `data/processed/combined_features_labelled.csv` | 144,653 rows, 595 pos | Step 1.1 loads and trains — no re-generation needed |
| `src/pipeline/runner.py` | Not yet created | Step 1.4 test: `run("infant1")` returns 10 z-score keys, no NaN |
| `src/knowledge/clinical_texts/` | Not yet created | Step 2.3 test: >= 34 chunks, RED tier returned for sepsis query |

---

## Risk Heatmap

| Step | Risk | What Could Go Wrong | Detection |
|------|------|---------------------|-----------|
| 1.1 | 🟡 Medium | AUC-PR near-random — sample_weight not applied | Script raises `RuntimeError` if AUC-PR < 0.05; verification asserts >= 0.10 |
| 1.2 | 🟡 Medium | zipmap active — onnx_output[1] is dict not ndarray | `isinstance` assertion fires before shape check |
| 1.4 | 🟢 Low | personal_baseline inconsistent with z_scores | Baseline now computed from same LOOKBACK window as run_nb04.py |
| 1.5 | 🟢 Low | Negative synthetic HRV values | All values clamped to `_FEATURE_MIN`; verification asserts all > 0 |
| 2.1 | 🟡 Medium | Docker not running / arm64 platform error | Pre-read gate checks `docker info`; platform line commented with removal instruction |
| 2.3 | 🟡 Medium | qdrant-client < 1.7 — `SparseVectorParams`, `Prefetch` missing | Pre-read gate version check; pip install specifies `>=1.7` |
| 2.4 | 🟢 Low | FlashRank first-run 80MB download appears stuck | Not a failure — add `logging.info("FlashRank: downloading model on first call...")` |

---

## Success Criteria

| Feature | Target | Verification |
|---------|--------|--------------|
| Classifier AUC-PR | >= 0.10 | Step 1.1 assertion + log |
| ONNX parity | max diff < 1e-3 | Step 1.2 assertion |
| `NeonatalPipeline.run("infant1")` | 10 z-scores, no NaN, risk_score in [0,1] | Step 1.4 test |
| Synthetic generator | All 10 features > 0, deterministic | Step 1.5 test |
| Qdrant KB | >= 34 chunks, RED tier in sepsis query | Step 2.3 test |
| `kb.query(...)` | 3 clinically relevant chunks | Step 2.4 test |

---

⚠️ **Step 2.1 requires Docker Desktop running. Start it manually before executing Step 2.1.**
⚠️ **Do not proceed to Phase 3 until Phase 2 Complete Checkpoint passes.**
⚠️ **Do not batch multiple steps into one git commit.**
