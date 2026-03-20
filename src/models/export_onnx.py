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

EXPORTS   = REPO_ROOT / "models" / "exports"
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

    # Parity check — sklearn vs ONNX probabilities must agree within 1e-3
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
            f"ONNX parity failed: max_diff={max_diff:.2e} (threshold 1e-3)."
        )
    logging.info("ONNX export verified OK")


if __name__ == "__main__":
    export()
