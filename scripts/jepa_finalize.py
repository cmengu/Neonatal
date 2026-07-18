"""Decide the winning JEPA config on the two *strongest honest* metrics (#58).

Runs on the sweep contenders:
- ``onset_anticipation_auc`` — non-circular, temporal: does novelty/surprise rise in the lead
  windows *before* an independent ``||x_dev||`` departure onset (reusing the validated loio.py)?
- ``demo_trajectory`` — the honest "leaves the cloud" number: novelty vs the infant's FULL calm
  baseline (robust covariance), on both candidate demo windows.

    PYTHONPATH=. python3 scripts/jepa_finalize.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from src.world_model.jepa import load_checkpoint
from src.world_model.jepa_score import (
    demo_trajectory, onset_anticipation_auc, pick_device,
)
from src.world_model.jepa_data import load_infant_sequences

REPO = Path(__file__).resolve().parent.parent
DATA = str(REPO / "data/processed/all_patients_windowed.csv")
CONTENDERS = ["h4_base", "h16", "h16_m50"]
WINDOWS = [(1240, 1419), (2098, 2277)]


def main() -> None:
    device = pick_device()
    seqs, _ = load_infant_sequences(DATA)
    out = {}
    for tag in CONTENDERS:
        ck = REPO / "models/jepa/sweep" / f"{tag}.pt"
        model = load_checkpoint(str(ck)).to(device)
        model.eval()
        anti = onset_anticipation_auc(model, DATA, device)
        demos = {}
        for w0, w1 in WINDOWS:
            dt = demo_trajectory(model, seqs["infant7"], w0, w1, device, infant="infant7")
            demos[f"{w0}_{w1}"] = {
                "sep_rise_calmSD": round(dt.sep_rise, 2),
                "peak_novelty": round(float(dt.novelty.max()), 2),
                "cloud_edge_p95": round(dt.baseline_p95, 2),
                "peak_over_edge": round(float(dt.novelty.max()) / dt.baseline_p95, 2),
                "surprise_rise_z": round(float(np.median(dt.surprise[-len(dt.surprise)//3:])
                                               - np.median(dt.surprise[:len(dt.surprise)//3])), 2),
            }
        out[tag] = {"anticipation": anti, "demo": demos}
        print(f"\n### {tag}")
        print("  onset-anticipation:", json.dumps(anti))
        for k, v in demos.items():
            print(f"  demo[{k}]:", json.dumps(v))
        (REPO / "models/jepa/sweep/finalize.json").write_text(json.dumps(out, indent=2))

    print("\n================ CONTENDER SUMMARY ================")
    print(f"{'tag':10} {'antic_nov':>9} {'antic_surp':>10}  {'demo1240 sep(peak/edge)':>24}")
    for tag in CONTENDERS:
        a = out[tag]["anticipation"]; d = out[tag]["demo"]["1240_1419"]
        print(f"{tag:10} {a['novelty_pooled_auc']:>9} {a['surprise_pooled_auc']:>10}  "
              f"{d['sep_rise_calmSD']:>8} ({d['peak_over_edge']:>4}x edge)")


if __name__ == "__main__":
    main()
