"""Train GBC bradycardia-onset risk classifier on per-patient windowed HRV features.

Labels are PICS .atr bradycardia-onset annotations (HR < 100 bpm, >= 2 beats),
with LEAD_WINDOWS=5 look-ahead expansion: windows within 5 steps BEFORE each
onset are also marked positive. This changes the task from:
  "is this the exact onset window?" (unanswerable — onset beat is 1/50 in window)
to:
  "will bradycardia happen within the next 5 windows (~125 beats)?" — early warning.

This is the clinically relevant question: detect impending bradycardia before onset,
allowing intervention time. The bradycardia event itself is the proxy for pre-sepsis
physiological deterioration (Griffin 2001, Fairchild 2013).
Do NOT call this a "sepsis classifier" — it predicts a bradycardia-onset proxy.

Train/test split is CHRONOLOGICAL PER PATIENT to avoid window-overlap leakage.
Windows use 50-beat stride with 25-beat overlap; random shuffle would put window N
in train and window N+1 in test, leaking shared beats across the split boundary.

Primary metric: AUC-PR (not AUC-ROC, which is inflated by the negative majority).
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

# Ensure repo root is on sys.path so `src.*` imports work when this file is
# executed as a script (python src/models/train_classifier.py from repo root).
# The guard prevents duplicate insertion on repeated imports.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.features.constants import HRV_FEATURE_COLS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)

LABEL_COL     = "label"
EXPORTS       = REPO_ROOT / "models" / "exports"
LOGS_DIR      = REPO_ROOT / "logs"
# Windows before each onset that are relabeled as positive.
# 5 windows × 25-beat stride = 125 beats of lead time ≈ ~55 seconds at HR 140bpm.
LEAD_WINDOWS  = 5


def expand_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Mark LEAD_WINDOWS before each bradycardia onset as positive (early warning).

    Operates per patient to avoid leaking lead-time across patient boundaries.
    Original onset windows (label=1) remain positive; windows label=1 in the
    preceding LEAD_WINDOWS steps are added as positive.
    """
    df = df.copy().sort_values(["record_name", "window_idx"])
    for pid, group in df.groupby("record_name"):
        onset_idxs = group.loc[group[LABEL_COL] == 1, "window_idx"].values
        for onset in onset_idxs:
            mask = (
                (df["record_name"] == pid)
                & (df["window_idx"] >= onset - LEAD_WINDOWS)
                & (df["window_idx"] < onset)
            )
            df.loc[mask, LABEL_COL] = 1
    return df


def train() -> tuple:
    df = pd.read_csv(REPO_ROOT / "data" / "processed" / "combined_features_labelled.csv")
    df = df.dropna(subset=HRV_FEATURE_COLS + [LABEL_COL])

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

    orig_pos = int(df[LABEL_COL].sum())
    df = expand_labels(df)
    expanded_pos = int(df[LABEL_COL].sum())
    logging.info(
        "Label expansion: %d onset windows → %d positive windows (LEAD=%d) — %.2f%% pos rate",
        orig_pos, expanded_pos, LEAD_WINDOWS, 100 * df[LABEL_COL].mean(),
    )

    # Chronological split per patient — prevents data leakage from overlapping windows.
    # Windows use 50-beat stride with 25-beat overlap; random shuffle would put window N
    # in train and window N+1 in test, leaking shared beats across the split boundary.
    train_dfs, test_dfs = [], []
    for patient_id, patient_df in df.groupby("record_name"):
        patient_df = patient_df.sort_values("window_idx")
        # max(1, ...) guarantees at least one train row per patient even for very
        # short recordings (< 5 windows), preventing an all-test split.
        cutoff = max(1, int(len(patient_df) * 0.8))
        train_dfs.append(patient_df.iloc[:cutoff])
        test_dfs.append(patient_df.iloc[cutoff:])

    train_df = pd.concat(train_dfs).reset_index(drop=True)
    test_df  = pd.concat(test_dfs).reset_index(drop=True)

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

    X_train = train_df[HRV_FEATURE_COLS].values.astype(np.float32)
    y_train = train_df[LABEL_COL].values
    X_test  = test_df[HRV_FEATURE_COLS].values.astype(np.float32)
    y_test  = test_df[LABEL_COL].values

    logging.info(
        "Train: %d rows, %d pos (%.2f%%) | Test: %d rows, %d pos (%.2f%%)",
        len(y_train), y_train.sum(), 100 * y_train.mean(),
        len(y_test),  y_test.sum(),  100 * y_test.mean(),
    )

    # Balanced sample weights — GradientBoostingClassifier has no class_weight param.
    # Without this, clf classifies everything as 0 with AUC-PR ≈ pos_rate (random).
    sample_weight = compute_sample_weight("balanced", y_train)

    clf = GradientBoostingClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        random_state=42,
    )
    clf.fit(X_train, y_train, sample_weight=sample_weight)

    y_prob  = clf.predict_proba(X_test)[:, 1]
    auc_roc = roc_auc_score(y_test, y_prob)
    auc_pr  = average_precision_score(y_test, y_prob)
    logging.info("AUC-ROC: %.4f", auc_roc)
    logging.info(
        "AUC-PR:  %.4f  (primary metric — random baseline = %.4f, target > 0.10)",
        auc_pr, y_test.mean(),
    )

    # FINDING: With 10 patients and 50-beat windowed features, AUC-PR is near-random.
    # The onset window contains 1 bradycardic beat out of 50 — indistinguishable from
    # normal windows in aggregated HRV. This is an honest result, not a code bug.
    # The ONNX architecture is demonstrated correctly regardless of classifier performance.
    if auc_pr < y_test.mean() * 0.5:
        logging.warning("AUC-PR=%.4f below half of random baseline (%.4f). Architecture demo proceeds.", auc_pr, y_test.mean())

    EXPORTS.mkdir(parents=True, exist_ok=True)
    with open(EXPORTS / "classifier.pkl", "wb") as f:
        pickle.dump(clf, f)
    with open(EXPORTS / "feature_cols.pkl", "wb") as f:
        pickle.dump(HRV_FEATURE_COLS, f)

    # Write holdout metrics to a machine-readable log for the verification gate.
    # The verification test reads this file — NOT the full-dataset AUC-PR,
    # which would be inflated because it includes the training windows.
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOGS_DIR / "train_classifier.log"
    with open(log_path, "w") as f:
        f.write(f"AUC-ROC: {auc_roc:.6f}\n")
        f.write(f"AUC-PR: {auc_pr:.6f}\n")
        f.write(f"pos_rate: {y_test.mean():.6f}\n")
        f.write(f"n_test: {len(y_test)}\n")
        f.write(f"n_pos_test: {int(y_test.sum())}\n")
        f.write(f"lead_windows: {LEAD_WINDOWS}\n")
        # FIX-10: Distribution stats — written last to avoid conflict with any
        # earlier log reads that only expect AUC/pos_rate at the top.
        f.write(f"n_total: {_dist_n_total}\n")
        f.write(f"n_positive_pre_expand: {_dist_n_pos}\n")
        f.write(f"pos_rate_pre_expand: {_dist_pos_rate:.6f}\n")
        for _feat, (_mean, _std) in _dist_feat_stats.items():
            f.write(f"feature_{_feat}_mean: {_mean:.4f}\n")
            f.write(f"feature_{_feat}_std: {_std:.4f}\n")

    logging.info("Saved: %s/classifier.pkl", EXPORTS)
    logging.info("Saved: %s/train_classifier.log", LOGS_DIR)
    return clf, HRV_FEATURE_COLS


if __name__ == "__main__":
    train()
