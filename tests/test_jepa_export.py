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

from scripts.export_jepa_trace import (MIN_BASIS_POINTS, _captured_fraction, _pca_fit,
                                       _project, _whiten_fit, export_world_model)
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


# --- honesty metrics for the 3-D hero (the projection audit) ---------------------


def test_captured_fraction_is_one_when_the_axes_span_the_movement():
    """Sanity anchor: if all the movement lies in the plotted subspace, nothing is hidden."""
    rng = np.random.default_rng(3)
    comps = np.eye(3, 8)                       # plot the first 3 of 8 dims
    centered = np.zeros((50, 8))
    centered[:, :3] = rng.standard_normal((50, 3))
    assert _captured_fraction(centered, comps) == pytest.approx(1.0, abs=1e-6)


def test_captured_fraction_falls_when_movement_hides_off_axis():
    """The number must *drop* when the departure travels in unplotted directions —
    otherwise it would reassure the viewer exactly when it should warn them."""
    rng = np.random.default_rng(4)
    comps = np.eye(3, 8)
    centered = rng.standard_normal((200, 8))   # isotropic: 3 of 8 dims ⇒ ~sqrt(3/8)
    frac = _captured_fraction(centered, comps)
    assert 0.4 < frac < 0.8
    assert frac < 1.0


def test_whiten_fit_makes_the_calm_cloud_isotropic():
    """The whitened basis must actually whiten — unit covariance on the cloud it was fit to."""
    rng = np.random.default_rng(5)
    a = rng.standard_normal((400, 5)) @ np.diag([5.0, 3.0, 1.0, 0.4, 0.1])
    mu, w = _whiten_fit(a)
    cov = np.cov(((a - mu) @ w).T)
    assert np.allclose(cov, np.eye(5), atol=0.15)


def test_export_reports_basis_and_captured_fraction(artifacts):
    """Both honesty fields ride in the block, so the panel can state them (#60 addendum)."""
    ckpt, csv = artifacts
    block = export_world_model(ckpt, csv, "infantA", 20, 80, 25)
    assert block["pca"]["basis"] in ("raw", "whitened")
    assert 0.0 < block["pca"]["novelty_captured"] <= 1.0
    # the caption must disclose the selected-window caveat, not just the axes
    assert "selected example" in block["caption"]


# --- rank-deficient basis: the bug the recorder integration exposed ---------------


def test_pca_fit_always_returns_three_orthonormal_axes_even_from_two_points():
    """Two samples span a line, so the plain top-3 SVD returns a (2, D) basis — and every
    downstream ``pca3`` silently becomes a 2-tuple, which the trace contract declares as a
    3-tuple and the 3-D hero reads as ``undefined`` on z. Shape must survive rank deficiency.
    """
    rng = np.random.default_rng(11)
    emb = rng.standard_normal((2, 12))
    mu, comps, var = _pca_fit(emb)
    assert comps.shape == (3, 12)
    assert len(var) == 3
    assert np.allclose(comps @ comps.T, np.eye(3), atol=1e-6)  # genuinely orthonormal
    # the padded axes carry no variance, and say so rather than faking a number
    assert var[0] > 0 and var[2] == pytest.approx(0.0, abs=1e-12)
    assert _project(emb, mu, comps).shape == (2, 3)


def test_pca_fit_single_point_still_yields_a_usable_basis():
    """The degenerate limit: one sample has no direction at all."""
    _, comps, var = _pca_fit(np.zeros((1, 9)))
    assert comps.shape == (3, 9)
    assert np.allclose(comps @ comps.T, np.eye(3), atol=1e-6)
    assert list(var) == pytest.approx([0.0, 0.0, 0.0], abs=1e-12)


def test_export_falls_back_to_calm_cloud_when_the_window_barely_opens_calm(artifacts):
    """A recorded window need not open calm — the recorder's own does so for 2 windows.

    Fitting 3 axes on 2 points is meaningless, so the basis falls back to the infant's whole
    calm baseline. That is still label-free and still never the departure; the block records
    which was used so the panel can say it.
    """
    ckpt, csv = artifacts
    tiny = export_world_model(ckpt, csv, "infantA", 20, 80, normal_len=2)
    assert tiny["pca"]["fitted_on"] == "calm_cloud"
    assert "calm baseline" in tiny["caption"]

    ample = export_world_model(ckpt, csv, "infantA", 20, 80, normal_len=40)
    assert ample["pca"]["fitted_on"] == "normal"
    assert "normal phase only" in ample["caption"]
    assert MIN_BASIS_POINTS <= 40


def test_caption_keeps_every_disclosure_on_both_basis_branches(artifacts):
    """A caption that drops its caveats on one code path is worse than no caption."""
    ckpt, csv = artifacts
    for normal_len in (2, 40):
        cap = export_world_model(ckpt, csv, "infantA", 20, 80, normal_len)["caption"]
        assert "% of the departure" in cap
        assert "selected example window" in cap
        assert "no accuracy score" in cap


def test_every_exported_point_is_three_dimensional(artifacts):
    """The contract the 3-D hero indexes into, pinned end-to-end."""
    ckpt, csv = artifacts
    block = export_world_model(ckpt, csv, "infantA", 20, 80, normal_len=2)
    assert all(len(p["pca3"]) == 3 for p in block["trajectory"])
    assert all(len(p) == 3 for p in block["normal_cloud"])
    assert len(block["pca"]["variance_explained"]) == 3
