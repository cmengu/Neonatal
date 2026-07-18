"""Train the next-latent-prediction JEPA on the per-infant HRV deviation stream.

    python -m src.world_model.train_jepa --epochs 12 --limit-steps 2500

Watches ``embed_std`` every log step — the mean per-dimension standard deviation of the
embeddings. If it holds near ~1 the latent space is alive; if it slides toward 0 the model is
collapsing and the VICReg weights need raising. Saves ``models/jepa/jepa.pt`` (+ a
``training_log.json`` of the honest final metrics).
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import time
from pathlib import Path

import torch
from torch.utils.data import DataLoader

from src.world_model.jepa import (
    JEPA,
    JEPAConfig,
    ema_momentum,
    save_checkpoint,
)
from src.world_model.jepa_data import JEPADataset, load_infant_sequences


def pick_device(requested: str) -> torch.device:
    if requested != "auto":
        return torch.device(requested)
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/processed/all_patients_windowed.csv")
    ap.add_argument("--out", default="models/jepa/jepa.pt")
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--weight-decay", type=float, default=1e-4)
    ap.add_argument("--stride", type=int, default=4)
    ap.add_argument("--limit-steps", type=int, default=0, help="0 = no cap")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--log-every", type=int, default=50)
    ap.add_argument("--var-coef", type=float, default=None)
    ap.add_argument("--cov-coef", type=float, default=None)
    ap.add_argument("--embed-dim", type=int, default=None)
    ap.add_argument("--horizon", type=int, default=None, help="H — windows of future to predict")
    ap.add_argument("--context-len", type=int, default=None)
    ap.add_argument("--encoder-layers", type=int, default=None)
    ap.add_argument("--predictor-layers", type=int, default=None)
    ap.add_argument("--mask-ratio", type=float, default=None,
                    help="fraction of context windows to mask (I-JEPA-style harder task)")
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    device = pick_device(args.device)
    overrides = {
        k: v
        for k, v in {
            "var_coef": args.var_coef,
            "cov_coef": args.cov_coef,
            "embed_dim": args.embed_dim,
            "horizon": args.horizon,
            "context_len": args.context_len,
            "encoder_layers": args.encoder_layers,
            "predictor_layers": args.predictor_layers,
            "mask_ratio": args.mask_ratio,
        }.items()
        if v is not None
    }
    cfg = dataclasses.replace(JEPAConfig(), **overrides)

    seqs, _labels = load_infant_sequences(args.data)
    ds = JEPADataset(seqs, cfg.context_len, cfg.horizon, stride=args.stride)
    loader = DataLoader(ds, batch_size=args.batch, shuffle=True, drop_last=True, num_workers=0)
    steps_per_epoch = len(loader)
    total_steps = steps_per_epoch * args.epochs
    if args.limit_steps:
        total_steps = min(total_steps, args.limit_steps)

    print(
        f"[jepa] device={device} infants={len(seqs)} samples={len(ds)} "
        f"steps/epoch={steps_per_epoch} total_steps={total_steps} D={cfg.embed_dim} "
        f"Lc={cfg.context_len} H={cfg.horizon}",
        flush=True,
    )

    model = JEPA(cfg).to(device)
    opt = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad],
        lr=args.lr,
        weight_decay=args.weight_decay,
    )
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(total_steps, 1))

    model.train()
    step = 0
    t0 = time.time()
    last = {"loss": 0.0, "loss_pred": 0.0, "embed_std": 0.0}
    done = False
    for epoch in range(args.epochs):
        if done:
            break
        for context, full in loader:
            context = context.to(device)
            full = full.to(device)
            out = model(context, full)
            loss = out["loss"]
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            model.update_target(ema_momentum(step, total_steps, cfg))

            last = {
                "loss": float(out["loss"]),
                "loss_pred": float(out["loss_pred"]),
                "loss_var": float(out["loss_var"]),
                "loss_cov": float(out["loss_cov"]),
                "embed_std": float(out["embed_std"]),
            }
            if step % args.log_every == 0:
                print(
                    f"[jepa] step {step:5d}/{total_steps} "
                    f"loss={last['loss']:.4f} pred={last['loss_pred']:.4f} "
                    f"var={last['loss_var']:.4f} cov={last['loss_cov']:.4f} "
                    f"embed_std={last['embed_std']:.3f} "
                    f"({(time.time()-t0):.0f}s)",
                    flush=True,
                )
            step += 1
            if args.limit_steps and step >= args.limit_steps:
                done = True
                break

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    save_checkpoint(str(out_path), model)

    log = {
        "steps_trained": step,
        "final": last,
        "config": {
            "embed_dim": cfg.embed_dim,
            "context_len": cfg.context_len,
            "horizon": cfg.horizon,
            "encoder_layers": cfg.encoder_layers,
            "predictor_layers": cfg.predictor_layers,
            "mask_ratio": cfg.mask_ratio,
            "var_coef": cfg.var_coef,
            "cov_coef": cfg.cov_coef,
        },
        "collapse_check": (
            "healthy" if last["embed_std"] > 0.5 else "WARNING: embed_std low — raising var_coef advised"
        ),
        "wall_seconds": round(time.time() - t0, 1),
    }
    (out_path.parent / "training_log.json").write_text(json.dumps(log, indent=2))
    print(f"[jepa] saved {out_path} | {json.dumps(log['final'])} | {log['collapse_check']}", flush=True)


if __name__ == "__main__":
    main()
