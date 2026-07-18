"""Unit tests for the JEPA world model's core math (`src/world_model/jepa.py`).

Covers the pieces the assessor / scorecard / exporter all rest on but never test directly: the
forward loss + anti-collapse diagnostics, the two Surprise read-outs' shapes, the VICReg terms'
behaviour (the guards that keep the latent space alive), the EMA momentum schedule, and
checkpoint round-tripping. Tiny config, CPU, deterministic — fast.
"""
import numpy as np
import torch

from src.world_model.jepa import (
    JEPA,
    JEPAConfig,
    covariance_loss,
    ema_momentum,
    load_checkpoint,
    save_checkpoint,
    sinusoidal_positions,
    variance_loss,
)
from src.world_model.jepa_data import FEATURES


def _cfg(**kw) -> JEPAConfig:
    base = dict(
        n_features=len(FEATURES),
        embed_dim=8,
        context_len=6,
        horizon=3,
        n_heads=2,
        encoder_layers=1,
        predictor_layers=1,
        ffn_dim=16,
        dropout=0.0,
    )
    base.update(kw)
    return JEPAConfig(**base)


def _batch(cfg: JEPAConfig, b: int = 4):
    torch.manual_seed(0)
    full = torch.randn(b, cfg.seq_len, cfg.n_features)
    context = full[:, : cfg.context_len]
    return context, full


# --- forward + diagnostics -------------------------------------------------------


def test_forward_returns_finite_loss_and_live_embedding():
    cfg = _cfg()
    model = JEPA(cfg).train()
    context, full = _batch(cfg)
    out = model(context, full)
    assert out["loss"].requires_grad
    assert torch.isfinite(out["loss"])
    for k in ("loss_pred", "loss_var", "loss_cov", "embed_std"):
        assert torch.isfinite(out[k])
    assert out["embed_std"] > 0  # the space is not collapsed


def test_forward_backward_produces_gradients():
    cfg = _cfg()
    model = JEPA(cfg).train()
    context, full = _batch(cfg)
    model(context, full)["loss"].backward()
    grads = [p.grad for p in model.encoder.parameters() if p.grad is not None]
    assert grads and all(torch.isfinite(g).all() for g in grads)
    # the EMA target encoder is stop-grad — it must never accumulate gradients
    assert all(p.grad is None for p in model.target_encoder.parameters())


# --- surprise read-outs ----------------------------------------------------------


def test_surprise_horizon_shape_and_finite():
    cfg = _cfg()
    model = JEPA(cfg).eval()
    ctx = torch.randn(5, cfg.context_len, cfg.n_features)
    fut = torch.randn(5, cfg.horizon, cfg.n_features)
    s = model.surprise_horizon(ctx, fut)
    assert s.shape == (5,)
    assert torch.isfinite(s).all()


def test_predict_surprise_shape_and_finite():
    cfg = _cfg()
    model = JEPA(cfg).eval()
    ctx = torch.randn(5, cfg.context_len, cfg.n_features)
    nxt = torch.randn(5, 1, cfg.n_features)
    s = model.predict_surprise(ctx, nxt)
    assert s.shape == (5,)
    assert torch.isfinite(s).all()


def test_encode_uses_stable_target_shape():
    cfg = _cfg()
    model = JEPA(cfg).eval()
    tokens = torch.randn(3, 9, cfg.n_features)
    z = model.encode(tokens)
    assert z.shape == (3, 9, cfg.embed_dim)


# --- VICReg anti-collapse terms --------------------------------------------------


def test_variance_loss_penalises_collapse_not_healthy_spread():
    healthy = torch.randn(256, 8)  # ~unit std per dim
    collapsed = torch.full((256, 8), 0.3)  # zero variance
    assert variance_loss(healthy) < 0.1
    assert variance_loss(collapsed) > 0.9  # hinge saturates toward 1


def test_covariance_loss_penalises_correlated_dims():
    rng = torch.Generator().manual_seed(1)
    decorrelated = torch.randn(400, 6, generator=rng)
    correlated = decorrelated.clone()
    correlated[:, 1] = correlated[:, 0]  # duplicate a dimension
    correlated[:, 2] = correlated[:, 0]
    assert covariance_loss(correlated) > covariance_loss(decorrelated)


# --- schedules + helpers ---------------------------------------------------------


def test_ema_momentum_anneals_base_to_final_monotonically():
    cfg = _cfg()
    total = 100
    ms = [ema_momentum(s, total, cfg) for s in range(total)]
    assert ms[0] == np.float32(cfg.ema_base) or abs(ms[0] - cfg.ema_base) < 1e-6
    assert abs(ms[-1] - cfg.ema_final) < 1e-6
    assert all(b >= a - 1e-9 for a, b in zip(ms, ms[1:]))  # non-decreasing


def test_sinusoidal_positions_shape():
    pe = sinusoidal_positions(12, 8, torch.device("cpu"))
    assert pe.shape == (12, 8)
    assert torch.isfinite(pe).all()


def test_update_target_moves_target_toward_online():
    cfg = _cfg()
    model = JEPA(cfg).train()
    # push the online encoder away, then EMA the target a step toward it
    with torch.no_grad():
        for p in model.encoder.parameters():
            p.add_(1.0)
    before = [t.clone() for t in model.target_encoder.parameters()]
    model.update_target(momentum=0.9)
    for b, (o, t) in zip(before, zip(model.encoder.parameters(), model.target_encoder.parameters())):
        # moved, and stayed between the old target and the online weights
        assert not torch.equal(b, t)
        assert torch.all((t - b).abs() <= (o - b).abs() + 1e-6)


# --- checkpoint round-trip -------------------------------------------------------


def test_checkpoint_roundtrip_preserves_config_and_output(tmp_path):
    cfg = _cfg(embed_dim=12, horizon=4)
    model = JEPA(cfg).eval()
    path = str(tmp_path / "m.pt")
    save_checkpoint(path, model)
    reloaded = load_checkpoint(path)
    assert reloaded.cfg == cfg
    ctx = torch.randn(2, cfg.context_len, cfg.n_features)
    fut = torch.randn(2, cfg.horizon, cfg.n_features)
    assert torch.allclose(model.surprise_horizon(ctx, fut), reloaded.surprise_horizon(ctx, fut), atol=1e-6)
