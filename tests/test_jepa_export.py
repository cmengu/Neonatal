"""Tests for the demo world-model exporter (`scripts/export_jepa_trace.py`, #60).

The exporter produces the ONE real thing in the otherwise-synthesised demo trace — the JEPA
embedding trajectory, novelty, and surprise on the shared grid. This pins its contract so the
demo's real spine can't silently regress: the PCA basis helpers, and an end-to-end export on a
tiny model + tiny synthetic record asserting every `world_model`-block invariant (#60 addendum)
plus determinism.
"""
import numpy as np
import pandas as pd
import pytest
import torch

from scripts.export_jepa_trace import _pca_fit, _project, export_world_model
from src.world_model.jepa import JEPA, JEPAConfig, save_checkpoint
from src.world_model.jepa_data import FEATURES


# --- PCA helpers -----------------------------------------------------------------


def test_pca_fit_components_are_orthonormal_and_ordered():
    rng = np.random.default_rng(0)
    emb = rng.standard_normal((120, 8))
    mu, comps, var = _pca_fit(emb)
    assert mu == pytest.approx(emb.mean(0))
    assert comps.shape == (3, 8)
    # right-singular vectors: unit-norm and mutually orthogonal
    assert np.allclose(np.linalg.norm(comps, axis=1), 1.0, atol=1e-6)
    assert np.allclose(comps @ comps.T, np.eye(3), atol=1e-6)
    # variance-explained is a descending fraction
    assert var[0] >= var[1] >= var[2] > 0
    assert 0 < var.sum() <= 1.0 + 1e-9


def test_project_centres_the_mean_to_origin():
    rng = np.random.default_rng(1)
    emb = rng.standard_normal((60, 6))
    mu, comps, _ = _pca_fit(emb)
    origin = _project(mu[None, :], mu, comps)
    assert origin.shape == (1, 3)
    assert np.allclose(origin, 0.0, atol=1e-6)


# --- end-to-end export on a tiny model ------------------------------------------


def _tiny_checkpoint(path: str) -> None:
    torch.manual_seed(0)
    model = JEPA(
        JEPAConfig(
            n_features=len(FEATURES),
            embed_dim=8,
            context_len=8,
            horizon=4,
            n_heads=2,
            encoder_layers=1,
            predictor_layers=1,
            ffn_dim=16,
            dropout=0.0,
        )
    )
    save_checkpoint(path, model)


def _tiny_csv(path: str, infants=("infantA", "infantB"), n=150) -> None:
    rng = np.random.default_rng(7)
    rows = []
    for name in infants:
        base = rng.standard_normal((n, len(FEATURES))).astype(np.float32) * 0.3
        base[90:120] += 4.0  # a departure episode so calm/departure split is non-degenerate
        for w in range(n):
            row = {"record_name": name, "window_idx": w, "label": 0}
            for f, v in zip(FEATURES, base[w]):
                row[f] = float(v)
            rows.append(row)
    pd.DataFrame(rows).to_csv(path, index=False)


@pytest.fixture()
def artifacts(tmp_path):
    ckpt = tmp_path / "tiny.pt"
    csv = tmp_path / "windowed.csv"
    _tiny_checkpoint(str(ckpt))
    _tiny_csv(str(csv))
    return str(ckpt), str(csv)


def test_export_block_invariants(artifacts):
    ckpt, csv = artifacts
    w0, w1, normal_len = 20, 80, 25
    block = export_world_model(ckpt, csv, "infantA", w0, w1, normal_len)
    n = w1 - w0 + 1

    assert block["real"] is True
    assert block["window"] == [w0, w1]
    assert block["embed_dim"] == 8

    # trajectory: one point per grid window, idx sequential, every field finite
    traj = block["trajectory"]
    assert len(traj) == n
    assert [t["idx"] for t in traj] == list(range(n))
    for t in traj:
        assert len(t["pca3"]) == 3 and all(np.isfinite(t["pca3"]))
        assert np.isfinite(t["novelty"]) and t["novelty"] >= 0
        assert np.isfinite(t["surprise"])

    # PCA metadata
    ve = block["pca"]["variance_explained"]
    assert block["pca"]["fitted_on"] == "normal"
    assert len(ve) == 3 and ve[0] >= ve[1] >= ve[2] and sum(ve) <= 1.0 + 1e-6

    # surprise series + normal cloud + cloud edge
    assert len(block["surprise"]["series"]) == n
    assert len(block["normal_cloud"]) > 0
    assert all(len(p) == 3 for p in block["normal_cloud"])
    assert block["novelty_baseline_p95"] > 0


def test_export_is_deterministic(artifacts):
    ckpt, csv = artifacts
    a = export_world_model(ckpt, csv, "infantA", 20, 80, 25)
    b = export_world_model(ckpt, csv, "infantA", 20, 80, 25)
    # pure inference in eval mode → byte-identical block on a re-run
    assert a == b


def test_export_rejects_unknown_infant(artifacts):
    ckpt, csv = artifacts
    with pytest.raises(SystemExit):
        export_world_model(ckpt, csv, "infantZ", 20, 80, 25)
