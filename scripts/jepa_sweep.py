"""JEPA config sweep — the honest scorecard over the handoff's method menu (#58).

Trains each config to its own checkpoint (fresh subprocess so MPS memory doesn't accrue),
then scores it with ``src.world_model.jepa_score``:

- ``novelty``  — pooled held-out AUC, JEPA embedding-novelty (Mahalanobis, per-infant) vs
                 the model-blind sustained-departure signal. THE demo metric ("leaves the cloud").
- ``surprise`` — pooled held-out AUC, horizon-aggregated JEPA surprise on the same split.
- ``VAR``      — the linear baseline on the identical split (honest reference).
- ``demo``     — raw embedding-separation rise on infant7's grounded window [1240,1419].
- ``embed_std``— collapse check from training (want ~1.0).

Everything is non-circular: "departure" is the raw ``||x_dev||`` excursion the JEPA never sees
as a label. Writes ``models/jepa/sweep/results.json`` + prints a table.

    PYTHONPATH=. python3 scripts/jepa_sweep.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import torch

from src.world_model.jepa import load_checkpoint
from src.world_model.jepa_score import departure_auc, pick_device, window_separation
from src.world_model.jepa_data import load_infant_sequences

REPO = Path(__file__).resolve().parent.parent
SWEEP = REPO / "models" / "jepa" / "sweep"
COMMON = ["--epochs", "25", "--limit-steps", "2800", "--stride", "4", "--batch", "256", "--var-coef", "1.5"]

# (tag, extra train args) — hypothesis-ordered from the handoff's method menu.
CONFIGS: list[tuple[str, list[str]]] = [
    ("h4_base",    ["--horizon", "4"]),                        # baseline, in-harness
    ("h16",        ["--horizon", "16"]),                       # #1 harder task: longer horizon
    ("h16_m50",    ["--horizon", "16", "--mask-ratio", "0.5"]),# #1 + denoising mask
    ("h24_m50",    ["--horizon", "24", "--mask-ratio", "0.5"]),# push horizon further
]


def train(tag: str, extra: list[str]) -> Path:
    out = SWEEP / f"{tag}.pt"
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "src.world_model.train_jepa", "--out", str(out), *COMMON, *extra]
    print(f"\n=== TRAIN {tag}: {' '.join(extra)} ===", flush=True)
    subprocess.run(cmd, cwd=REPO, check=True, env={"PYTHONPATH": str(REPO), "PATH": __import__("os").environ["PATH"]})
    return out


def score(tag: str, ckpt: Path, device: torch.device) -> dict:
    model = load_checkpoint(str(ckpt)).to(device)
    model.eval()
    seqs, _ = load_infant_sequences(str(REPO / "data/processed/all_patients_windowed.csv"))
    dr = departure_auc(model, str(REPO / "data/processed/all_patients_windowed.csv"),
                       device, whiten=True, surp_horizon=True)
    demo = window_separation(model, seqs["infant7"], 1240, 1419, device, infant="infant7", whiten=False)
    # train_jepa writes training_log.json beside --out; scored right after each train (before
    # the next run overwrites it), so embed_std is this config's.
    tlog_path = ckpt.parent / "training_log.json"
    embed_std = None
    if tlog_path.exists():
        embed_std = json.loads(tlog_path.read_text())["final"]["embed_std"]
    return {
        "tag": tag,
        "cfg": {"D": model.cfg.embed_dim, "Lc": model.cfg.context_len, "H": model.cfg.horizon,
                "mask": model.cfg.mask_ratio},
        "novelty_auc": round(dr.pooled_auc_novelty, 3),
        "surprise_auc": round(dr.pooled_auc_surprise, 3),
        "var_auc": round(dr.pooled_auc_var, 3),
        "demo_sep_rise": round(demo.sep_rise, 3),
        "demo_surp_rise": round(demo.surprise_rise, 4),
        "demo_dev_rise": round(demo.dev_rise, 3),
        "embed_std": round(embed_std, 3) if embed_std else None,
    }


def main() -> None:
    device = pick_device()
    rows = []
    for tag, extra in CONFIGS:
        ckpt = train(tag, extra)
        row = score(tag, ckpt, device)
        rows.append(row)
        print(f"\n[scored {tag}] {json.dumps(row)}", flush=True)
        (SWEEP / "results.json").write_text(json.dumps(rows, indent=2))

    print("\n\n================ SWEEP RESULTS ================")
    hdr = f"{'tag':10} {'H':>3} {'mask':>4} {'novelty':>8} {'surprise':>9} {'VAR':>5} {'demo_sep':>9} {'demo_surp':>10} {'estd':>5}"
    print(hdr)
    for r in rows:
        print(f"{r['tag']:10} {r['cfg']['H']:>3} {r['cfg']['mask']:>4} "
              f"{r['novelty_auc']:>8} {r['surprise_auc']:>9} {r['var_auc']:>5} "
              f"{r['demo_sep_rise']:>9} {r['demo_surp_rise']:>10} {r['embed_std'] or 0:>5}")
    print("results → models/jepa/sweep/results.json")


if __name__ == "__main__":
    main()
