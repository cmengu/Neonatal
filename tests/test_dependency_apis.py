"""FIX-3: API contract tests for flashrank and ONNX runtime.

These tests verify that the external API shapes we depend on have not drifted.
Run in CI (pytest tests/test_dependency_apis.py -v) before the agent eval suite.

flashrank contract: results[0] is a dict with a 'text' key (not an object attribute).
ONNX contract:      output[1] is ndarray with shape (n, 2) when zipmap=False.
"""
import numpy as np
import pytest


def test_flashrank_returns_dict_with_text_key():
    """Verify flashrank API contract — results[0]['text'] not results[0].text."""
    from flashrank import Ranker, RerankRequest

    ranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2", cache_dir="/tmp/flashrank_cache")
    results = ranker.rerank(
        RerankRequest(
            query="RMSSD neonatal sepsis",
            passages=[{"id": "1", "text": "RMSSD measures short-term HRV in premature neonates."}],
        )
    )
    assert len(results) > 0, "flashrank returned no results"
    assert isinstance(results[0], dict), (
        f"flashrank API changed — results[0] is {type(results[0])}, expected dict. "
        "Check flashrank release notes for breaking API changes."
    )
    assert "text" in results[0], (
        f"flashrank API changed — 'text' key missing from result dict. "
        f"Got keys: {list(results[0].keys())}"
    )


def test_onnx_output_format():
    """Verify ONNX output[1] is ndarray with shape (n, 2) when zipmap=False."""
    import onnxruntime as ort
    from pathlib import Path

    onnx_path = Path(__file__).resolve().parent.parent / "models" / "exports" / "neonatalguard_v1.onnx"
    if not onnx_path.exists():
        pytest.skip(f"ONNX model not found: {onnx_path} — run export_onnx.py first")

    sess = ort.InferenceSession(str(onnx_path))
    dummy = np.random.randn(3, 10).astype("float32")
    out = sess.run(None, {"hrv_features": dummy})

    assert isinstance(out[1], np.ndarray), (
        f"ONNX output[1] type changed: {type(out[1])}. "
        "Expected ndarray. Was the model re-exported with zipmap=True?"
    )
    assert out[1].shape == (3, 2), (
        f"ONNX output[1] shape changed: {out[1].shape}. "
        "Expected (3, 2). Was the model re-exported with a different number of classes?"
    )
