"""A next-latent-prediction JEPA — the *learned* world model for Tier 2 (the demo build).

Where ``forecaster.py`` fits a linear VAR(1) and reads Surprise off the one-step
innovation, this module learns a **representation**: a Joint-Embedding Predictive
Architecture (LeCun 2022; I-JEPA 2023; the TS-JEPA / next-latent line, Ennadir et al. 2025,
"Joint Embeddings Go Temporal" arXiv:2509.25449, LeNEPA arXiv:2607.00958). The clinical
narrative it serves:

    An infant's cardiac dynamics have a *shape* in a learned latent space. Health is a
    tight, stable neighbourhood of that space; deterioration is the trajectory leaving it.
    The model never reconstructs the raw signal — it predicts the *embedding* of the near
    future from the recent past, and **Surprise = how wrong that embedding prediction was.**

Three pieces, no decoder:

- **Encoder** ``f_θ`` — a lightweight Transformer over a context of past HRV windows →
  a per-window embedding ``z ∈ R^D``.
- **Predictor** ``g_φ`` — predicts the *target-encoder* embeddings of the next ``H`` windows
  from the encoded context. This is the "world model": it rolls the latent forward.
- **Target encoder** ``f_ξ`` — an EMA copy of the encoder, stop-gradient. It supplies the
  prediction targets, so the objective is self-referential (predict your own future
  representation) rather than pixel/signal reconstruction.

**Representational collapse** — the failure mode where every window maps to the same point,
which would make the whole latent space (and the demo) dead — is held off three ways, exactly
as the 2025/2026 literature prescribes:

1. **Asymmetry + EMA + stop-gradient** (I-JEPA's primary guard): targets come from a slowly
   moving average of the online weights, never back-propagated through.
2. **VICReg variance term** (Bardes et al. 2022; C-JEPA 2024): a hinge that forces each
   embedding dimension to keep unit standard deviation across the batch.
3. **VICReg covariance term**: decorrelates the dimensions so they carry independent
   information rather than duplicating one axis.

Everything here is plain ``torch`` — no lightning, no timm. Trains on Apple MPS or CPU.
"""
from __future__ import annotations

import copy
import math
from dataclasses import asdict, dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass(frozen=True)
class JEPAConfig:
    """Every knob the model needs, in one serialisable place (rides in the checkpoint)."""

    n_features: int = 10          # the personalised-deviation (`_dev`) HRV columns
    embed_dim: int = 48           # D — the latent the trajectory lives in
    context_len: int = 24         # Lc — windows of history the encoder sees (~12 min @ 30 s)
    horizon: int = 16             # H — windows of future whose embedding we predict (see #58 sweep:
                                  #     H=16 + masking makes Surprise anticipatory; H=4 left it flat)
    n_heads: int = 4
    encoder_layers: int = 3
    predictor_layers: int = 2
    ffn_dim: int = 128
    dropout: float = 0.1
    # anti-collapse
    ema_base: float = 0.996       # target-encoder momentum at step 0
    ema_final: float = 0.9995     # …annealed toward this
    var_coef: float = 1.0         # VICReg variance weight
    cov_coef: float = 0.5         # VICReg covariance weight
    # harder-task knobs (handoff method #1) — make next-latent prediction non-trivial so the
    # embedding must encode *regime/trajectory* and Surprise spikes at genuine novelty.
    mask_ratio: float = 0.5       # fraction of context windows zeroed each step (denoising);
                                  #     #58 sweep: 0.5 lifted anticipation-surprise AUC 0.67→0.76

    @property
    def seq_len(self) -> int:
        return self.context_len + self.horizon


def sinusoidal_positions(n: int, d: int, device: torch.device) -> torch.Tensor:
    """Standard fixed sinusoidal positional encoding, shape ``(n, d)``.

    Positions index *windows* (uniform cadence), so a fixed encoding is the honest choice —
    there is nothing to learn about "where in the sequence" beyond ordinal distance.
    """
    pos = torch.arange(n, device=device, dtype=torch.float32).unsqueeze(1)
    i = torch.arange(0, d, 2, device=device, dtype=torch.float32)
    denom = torch.exp(-(math.log(10000.0) / d) * i)
    pe = torch.zeros(n, d, device=device)
    pe[:, 0::2] = torch.sin(pos * denom)
    pe[:, 1::2] = torch.cos(pos * denom)
    return pe


class SequenceEncoder(nn.Module):
    """Context of window feature-vectors ``(B, L, F)`` → per-window embeddings ``(B, L, D)``."""

    def __init__(self, cfg: JEPAConfig) -> None:
        super().__init__()
        self.cfg = cfg
        self.input_proj = nn.Linear(cfg.n_features, cfg.embed_dim)
        layer = nn.TransformerEncoderLayer(
            d_model=cfg.embed_dim,
            nhead=cfg.n_heads,
            dim_feedforward=cfg.ffn_dim,
            dropout=cfg.dropout,
            batch_first=True,
            activation="gelu",
            norm_first=True,
        )
        self.transformer = nn.TransformerEncoder(layer, num_layers=cfg.encoder_layers)
        self.norm = nn.LayerNorm(cfg.embed_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        _, length, _ = x.shape
        h = self.input_proj(x)
        h = h + sinusoidal_positions(length, self.cfg.embed_dim, x.device).unsqueeze(0)
        h = self.transformer(h)
        return self.norm(h)


class Predictor(nn.Module):
    """Encoded context ``(B, Lc, D)`` → predicted future embeddings ``(B, H, D)``.

    The context reps are held in place as memory; ``H`` learned mask tokens, tagged with
    their future positions, attend over context + each other and are read out as the
    predicted latents. This is ``g_φ`` — the part that actually "rolls the world forward."
    """

    def __init__(self, cfg: JEPAConfig) -> None:
        super().__init__()
        self.cfg = cfg
        self.mask_token = nn.Parameter(torch.randn(cfg.embed_dim) * 0.02)
        layer = nn.TransformerEncoderLayer(
            d_model=cfg.embed_dim,
            nhead=cfg.n_heads,
            dim_feedforward=cfg.ffn_dim,
            dropout=cfg.dropout,
            batch_first=True,
            activation="gelu",
            norm_first=True,
        )
        self.transformer = nn.TransformerEncoder(layer, num_layers=cfg.predictor_layers)
        self.head = nn.Linear(cfg.embed_dim, cfg.embed_dim)

    def forward(self, context_reps: torch.Tensor) -> torch.Tensor:
        b, lc, d = context_reps.shape
        h = self.cfg.horizon
        masks = self.mask_token.view(1, 1, d).expand(b, h, d)
        x = torch.cat([context_reps, masks], dim=1)               # (B, Lc+H, D)
        x = x + sinusoidal_positions(lc + h, d, x.device).unsqueeze(0)
        x = self.transformer(x)
        return self.head(x[:, lc:, :])                            # (B, H, D)


def variance_loss(z: torch.Tensor, eps: float = 1e-4) -> torch.Tensor:
    """VICReg variance term: hinge that keeps every dim's std ≥ 1 (the anti-collapse guard)."""
    std = torch.sqrt(z.var(dim=0) + eps)
    return torch.mean(F.relu(1.0 - std))


def covariance_loss(z: torch.Tensor) -> torch.Tensor:
    """VICReg covariance term: push the off-diagonal of the feature covariance toward 0."""
    n, d = z.shape
    z = z - z.mean(dim=0, keepdim=True)
    cov = (z.T @ z) / max(n - 1, 1)
    off_diag = cov - torch.diag(torch.diag(cov))
    return off_diag.pow(2).sum() / d


class JEPA(nn.Module):
    """Online encoder + predictor + EMA target encoder, with the VICReg-regularised loss.

    ``forward(context, full)`` returns a dict with the total ``loss`` and the diagnostics the
    training loop watches to *prove the latent space stayed alive* — ``embed_std`` is the mean
    per-dimension standard deviation; if it slides toward 0 the model is collapsing.
    """

    def __init__(self, cfg: JEPAConfig) -> None:
        super().__init__()
        self.cfg = cfg
        self.encoder = SequenceEncoder(cfg)
        self.predictor = Predictor(cfg)
        self.target_encoder = copy.deepcopy(self.encoder)
        for p in self.target_encoder.parameters():
            p.requires_grad_(False)

    def forward(self, context: torch.Tensor, full: torch.Tensor) -> dict[str, torch.Tensor]:
        cfg = self.cfg
        if self.training and cfg.mask_ratio > 0.0:
            # Denoising mask: zero a random fraction of context windows (→ the infant's own
            # baseline) so the encoder can't lean on the most-recent window and must integrate
            # the whole context to predict the future. Targets stay clean (from ``full``).
            keep = (torch.rand(context.shape[:2], device=context.device) >= cfg.mask_ratio)
            context = context * keep.unsqueeze(-1).to(context.dtype)
        context_reps = self.encoder(context)                      # (B, Lc, D)
        pred = self.predictor(context_reps)                       # (B, H, D)

        with torch.no_grad():
            target_full = self.target_encoder(full)               # (B, Lc+H, D)
            target = target_full[:, cfg.context_len:, :]          # (B, H, D)
            target = F.layer_norm(target, (cfg.embed_dim,))       # I-JEPA target normalisation

        pred_flat = pred.reshape(-1, cfg.embed_dim)
        target_flat = target.reshape(-1, cfg.embed_dim)
        ctx_flat = context_reps.reshape(-1, cfg.embed_dim)

        loss_pred = F.smooth_l1_loss(pred_flat, target_flat)
        loss_var = variance_loss(pred_flat) + variance_loss(ctx_flat)
        loss_cov = covariance_loss(pred_flat) + covariance_loss(ctx_flat)
        loss = loss_pred + cfg.var_coef * loss_var + cfg.cov_coef * loss_cov

        with torch.no_grad():
            embed_std = torch.sqrt(ctx_flat.var(dim=0) + 1e-6).mean()

        return {
            "loss": loss,
            "loss_pred": loss_pred.detach(),
            "loss_var": loss_var.detach(),
            "loss_cov": loss_cov.detach(),
            "embed_std": embed_std,
        }

    @torch.no_grad()
    def update_target(self, momentum: float) -> None:
        """EMA step: ``ξ ← m·ξ + (1−m)·θ``. The stop-gradient guard against collapse."""
        for online, target in zip(self.encoder.parameters(), self.target_encoder.parameters()):
            target.mul_(momentum).add_(online.detach(), alpha=1.0 - momentum)
        for online, target in zip(self.encoder.buffers(), self.target_encoder.buffers()):
            target.copy_(online)

    @torch.no_grad()
    def encode(self, tokens: torch.Tensor) -> torch.Tensor:
        """Inference embeddings from the (stable) target encoder: ``(B, L, F) → (B, L, D)``."""
        self.eval()
        return self.target_encoder(tokens)

    @torch.no_grad()
    def predict_surprise(self, context: torch.Tensor, actual_next: torch.Tensor) -> torch.Tensor:
        """Per-sample Surprise: distance between the predicted next latent and the real one.

        ``context`` is ``(B, Lc, F)``; ``actual_next`` is ``(B, 1, F)`` — the window we want a
        surprise for. Returns ``(B,)`` — the JEPA analogue of the VAR innovation NLL, but in a
        *learned* embedding space rather than a linear one.
        """
        self.eval()
        context_reps = self.encoder(context)
        pred = self.predictor(context_reps)[:, 0, :]              # predicted latent for +1
        target = self.target_encoder(
            torch.cat([context, actual_next], dim=1)
        )[:, -1, :]                                               # true latent of that window
        target = F.layer_norm(target, (self.cfg.embed_dim,))
        return (pred - target).pow(2).mean(dim=-1)               # (B,)

    @torch.no_grad()
    def surprise_horizon(self, context: torch.Tensor, actual_future: torch.Tensor) -> torch.Tensor:
        """Horizon-aggregated Surprise: mean predicted-vs-true latent error over all ``H``
        future windows (handoff method #4).

        A single +1 step is trivially predictable on autocorrelated HRV (flat Surprise); the
        error *over the whole horizon* rises when the near future becomes genuinely
        unpredictable — i.e. it **anticipates** a regime change rather than just reacting to it.
        ``context`` is ``(B, Lc, F)``; ``actual_future`` is ``(B, H, F)``. Returns ``(B,)``.
        """
        self.eval()
        cfg = self.cfg
        reps = self.encoder(context)
        pred = self.predictor(reps)                              # (B, H, D)
        target = self.target_encoder(
            torch.cat([context, actual_future], dim=1)
        )[:, cfg.context_len:, :]                                # (B, H, D)
        target = F.layer_norm(target, (cfg.embed_dim,))
        return (pred - target).pow(2).mean(dim=(1, 2))           # (B,)


def ema_momentum(step: int, total_steps: int, cfg: JEPAConfig) -> float:
    """Cosine-anneal the target momentum from ``ema_base`` up to ``ema_final`` (I-JEPA schedule)."""
    if total_steps <= 1:
        return cfg.ema_final
    frac = min(step / (total_steps - 1), 1.0)
    return cfg.ema_final - (cfg.ema_final - cfg.ema_base) * (0.5 * (1 + math.cos(math.pi * frac)))


def save_checkpoint(path: str, model: JEPA) -> None:
    torch.save({"config": asdict(model.cfg), "state_dict": model.state_dict()}, path)


def load_checkpoint(path: str, map_location: str = "cpu") -> JEPA:
    blob = torch.load(path, map_location=map_location)
    model = JEPA(JEPAConfig(**blob["config"]))
    model.load_state_dict(blob["state_dict"])
    model.eval()
    return model
