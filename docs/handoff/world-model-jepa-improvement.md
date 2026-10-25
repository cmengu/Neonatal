# Handoff — Make the NeonatalGuard World Model (JEPA) honestly promising

**For:** the next agent picking up wayfinder ticket [#58](https://github.com/cmengu/Neonatal/issues/58) on map [#56](https://github.com/cmengu/Neonatal/issues/56).
**Written:** 2026-07-18 (handing off to preserve a fresh context window).
**Working copy:** git worktree `.claude/worktrees/wf-53-showtime`, branch `docs/map-22-summary`. All the JEPA work below is **uncommitted** here.

---

## 0. Your mission, and the honesty bar (read first)

**Mission:** iterate the world model through *every legitimate method* — research the frontier first, then experiment — until its numbers are **honestly promising**: a meaningful embedding departure from "normal" during deterioration, and/or a **rising surprise** around real bradycardia events, and/or a respectable **leave-one-infant-out (LOIO) AUC**. Converge on the single best configuration.

**The honesty bar (non-negotiable, owner's explicit instruction):**
- **No faking.** No fabricated metrics, no hand-authored trajectories, no overfitting-to-look-good. The *demo* will cinematically amplify a **real** trajectory (owner's "decision 3"), but the underlying model numbers must be real and reproducible.
- **"Promising," not SOTA, is the target.** A fully acceptable outcome: *"On a small 10-infant cohort with per-infant fitting, the world model's surprise separates deterioration from baseline at AUC ≈ X; next we scale to more patients."* The owner has **explicitly OK'd** the small-cohort / best-fitting / "more patients next time" caveat.
- **Last resort only:** if after genuine iteration the numbers stay weak, say so plainly — then we fall back to cinematically amplifying the real (subtle) trajectory. Don't reach for this until you've actually tried the methods in §4.

---

## 1. What this world model is FOR (the agent summary)

NeonatalGuard is a three-tier neonatal early-warning **cascade** (see `CONTEXT.md` + `docs/adr/`). **Tier 2** has two halves: a *deterministic* half (CUSUM drift) and a **learned** half — the world model. ADR-0002 retired a supervised classifier (it scored **at random** on held-out infants — 10 infants, 0.4% base rate can't support supervised learning) in favor of a **per-infant, self-supervised** model that learns each infant's *own* normal cardiac dynamics and flags departures. That sidesteps label scarcity: no shared population weights to overfit.

We are building a **JEPA** (Joint-Embedding Predictive Architecture) as that learned half, for two coupled reasons:

1. **The pitch/demo centerpiece** (map #56; spec `docs/design/demo-showtime-spec.md`): a **3-D embedding that warps across a shared timeline** — the infant's state visibly drifting out of its "learned-normal cloud" as deterioration sets in. A JEPA yields a *genuine learned embedding trajectory*, richer and more cinematic than the linear VAR forecaster's scalar innovation.
2. **The architecture story:** the JEPA also becomes a real `Assessor` in the cascade seam (Tier 2's learned half, **observational** — `may_quiet=false`, can't move the verdict), so "a real learned tier in the pipeline" is literally true.

**What the demo needs from you:** the embedding to *visibly move* (and ideally surprise to *rise*) during deterioration, on a real recorded window. **That is the number we're trying to make promising.** Right now it's too subtle (see §2).

---

## 2. Current state — what's built, and the exact problem

### Built (all in `src/world_model/`)
- **`jepa.py`** — a next-latent-prediction JEPA, pure PyTorch:
  - **Encoder** `f_θ`: Transformer over a context of HRV-deviation windows → per-window embedding `z ∈ R^D`.
  - **Predictor** `g_φ`: predicts the *target-encoder* embeddings of the next `H` windows from encoded context (no decoder).
  - **Target encoder** `f_ξ`: EMA copy of the encoder, stop-gradient (I-JEPA-style).
  - **Anti-collapse:** EMA + stop-grad **plus VICReg** variance + covariance terms. *This is working* — see numbers below.
  - `JEPAConfig` defaults: `n_features=10, embed_dim=48, context_len=24, horizon=4, n_heads=4, encoder_layers=3, predictor_layers=2, ffn_dim=128, ema_base=0.996→ema_final=0.9995, var_coef=1.0, cov_coef=0.5`. **113k params.**
  - Inference API: `model.encode(tokens)` (per-window embeddings from the stable target encoder), `model.predict_surprise(context, actual_next)` (predictive error = the JEPA "surprise").
- **`jepa_data.py`** — loads `data/processed/all_patients_windowed.csv` (per-infant **personalised-deviation** `_dev` features + bradycardia `label`), slides `(context, full)` training pairs. `FEATURES` = the 10 `_dev` columns.
- **`train_jepa.py`** — training loop (AdamW, cosine LR, EMA momentum schedule, grad-clip), logs `embed_std` each step to watch for collapse. Saves `models/jepa/jepa.pt` + `training_log.json`.

### Trained checkpoint (`models/jepa/jepa.pt`)
Command used: `PYTHONPATH=. python3 -m src.world_model.train_jepa --epochs 25 --limit-steps 2800 --stride 4 --batch 256 --var-coef 1.5`
Final: `loss 0.69, pred 0.62, var 0.008, cov 0.11, embed_std 1.02` → **healthy, no collapse** (embed_std ≈ 1 means every embedding dim is at unit variance; VICReg satisfied; dims decorrelated).

### The problem (validation finding)
On the demo subject `infant7`, using each window's *own* first-third as the "normal" baseline:

| Window | normal→sustained dist (SD) | separation rise | surprise rise |
|---|---|---|---|
| `[1240,1419]` (spec's current pick) | 0.93 → 1.08 | **+0.15** | −0.01 (flat) |
| `[2098,2277]` (best in the whole record) | 0.85 → 1.12 | **+0.28** | ~flat |
| `[113,292]` (fallback) | 0.85 → 0.82 | **−0.04** | flat |

**Max embedding separation anywhere in infant7 ≈ 0.28 SD, and predictive surprise stays flat.** The embedding drifts, but subtly — not the dramatic "leaves the cloud" you'd want to *show*.

### Why it's weak (diagnosis — hypotheses to attack in §4)
1. **The task is too easy.** `H=4` next-step latent prediction on HRV, which is highly autocorrelated → the model predicts the near future trivially → the embedding stays smooth and doesn't reorganize at deterioration, and surprise never spikes. **(Likely the #1 lever — make prediction harder.)**
2. **Population fit, not per-infant.** The JEPA trains *across* all infants, so "normal" is population-relative. ADR-0002's whole thesis is *per-infant* normal. Deterioration is most separable relative to *that infant's own* baseline. **(Likely the #2 lever.)**
3. **The signal is genuinely subtle.** Deterioration in this cohort is gradual and noisy; bradycardia labels are even isolated single windows (data-integrity artifact, issue #18 — brady events were scrubbed/mislabeled upstream). Some of the weakness is the data, not the model — hence the honest small-cohort caveat is legitimate.
4. **Impoverished feature set.** Only the 10 base `_dev` HRV features. The physiologically strongest signals aren't in the JEPA's input: **respiration / apnea–bradycardia coupling** (`*_resp_features.csv`; #3 found coupling 11.4× above chance) and the **HeRO signature** features `sampen` + `sample_asymmetry` (#13) are absent from `all_patients_windowed.csv`.

---

## 3. How to measure success (build this harness first)

You cannot iterate without a fast, honest scorecard. Two metrics:

**(A) The demo metric — embedding separation on a window** (run this to reproduce §2):
```python
import numpy as np, torch
from sklearn.decomposition import PCA
from src.world_model.jepa import load_checkpoint
from src.world_model.jepa_data import load_infant_sequences
ck = load_checkpoint("models/jepa/jepa.pt"); cfg = ck.cfg; L, Lc, D = cfg.seq_len, cfg.context_len, cfg.embed_dim
seqs, labels = load_infant_sequences("data/processed/all_patients_windowed.csv")
x = seqs["infant7"]; xt = torch.tensor(x, dtype=torch.float32); W0, W1 = 2098, 2277
ts = range(W0, W1 + 1); Z, S = [], []
for t in ts:
    Z.append(ck.encode(xt[t-L+1:t+1].unsqueeze(0))[0, -1].numpy())
    S.append(float(ck.predict_surprise(xt[t-Lc:t].unsqueeze(0), xt[t:t+1].unsqueeze(0))[0]))
Z, S = np.array(Z), np.array(S); third = len(Z)//3
mu, sd = Z[:third].mean(0), Z[:third].std(0)+1e-6
dist = np.sqrt((((Z-mu)/sd)**2).mean(1))          # per-window novelty in SD units
print("separation rise:", np.median(dist[-third:]) - np.median(dist[:third]))
print("surprise rise:  ", np.median(S[-third:]) - np.median(S[:third]))
```
Target: separation rise **≥ ~1.0 SD** (clearly visible drift), surprise rise clearly **> 0**. (Decision-3 amplification can carry a bit less, but push the real number up.)

**(B) The pitch metric — LOIO surprise-vs-event AUC.** Adapt the existing `src/world_model/loio.py` harness (built for the VAR forecaster) to the JEPA: leave one infant out, score per-window surprise, and compute AUC of surprise against the bradycardia events + lead-time before onset. **The VAR forecaster baseline is AUC ≈ 0.635** (`docs/research/world-model-surprise-loio-result.md`). **"Promising" ≥ ~0.65–0.70.** This is the honest number that goes on the pitch slide, with the small-cohort caveat.

---

## 4. Methods to try — research first, then experiment (prioritized)

**Process:** run `/research` (or `/deep-research`) on the frontier methods below, write a short plan (consider `/prototype` or a design-it-twice), then iterate configs, scoring each against §3. Keep a small results table. Frontier reading anchors: **TS-JEPA** (Ennadir et al. 2025, "Joint Embeddings Go Temporal" arXiv:2509.25449), **LeNEPA** next-latent (arXiv:2607.00958), **I-JEPA** (masking + EMA), **C-JEPA** (VICReg + JEPA), **VICReg** (Bardes 2022), and time-series anomaly/personalization via JEPA.

Ordered by my estimate of payoff:

1. **Make prediction harder (biggest bet).** Raise the horizon `H` (e.g. 12–32 windows) and/or multi-step latent rollout; adopt **high masking ratios (>70%)** and I-JEPA multi-block target sampling instead of a single future block. A harder task forces the embedding to encode *regime/trajectory* → separation + surprise spike at deterioration.
2. **Per-infant fitting/adaptation.** The model is population-trained; ADR-0002 wants per-infant. Try: per-infant fine-tuning of the encoder; an infant-id conditioning/FiLM layer; or a per-infant normalization of embeddings (whiten against that infant's own normal-window covariance) so surprise/distance is Mahalanobis in *this infant's* latent. Compare to the per-infant VAR forecaster (`forecaster.py`).
3. **Richer, more physiological features.** Regenerate the windowed input to include **respiration / apnea–bradycardia coupling** (`scripts/run_respiration.py`, `*_resp_features.csv`) and the **HeRO signature** `sampen` + `sample_asymmetry` (#13, `src/features/hrv.py`). More separable physiology in → more separable states out. (Watch fs heterogeneity — see the #3/#18 notes: read fs from headers, align in seconds.)
4. **Sharpen the surprise definition.** Current surprise = mean-squared predicted-vs-target latent error. Try Mahalanobis in latent space (whiten by the innovation covariance, mirroring the VAR forecaster's NLL), aggregate over a horizon, or use predictor uncertainty. Compare directly against the VAR forecaster's Mahalanobis surprise — it may separate *more* (it's the raw deviation innovation); an **ensemble/blend** of JEPA-embedding + VAR-surprise may be the strongest honest signal.
5. **Capacity + training budget.** Bigger encoder (layers/heads), `embed_dim` 64–96, longer training — but VICReg + EMA + the 10-infant limit mean guard against overfitting (LOIO is the honest check, not train loss).
6. **Anti-collapse is already good** (`embed_std ≈ 1.0`) — but sweep the **EMA momentum schedule** and **VICReg var/cov coefficients** (C-JEPA balance); a livelier space can sharpen separation.

**My starting hypothesis if you want a fast first experiment:** #1 (horizon 16 + high masking) combined with #2 (per-infant whitening of the surprise) is the most likely to move the numbers. Start there, score with §3, then branch.

---

## 5. Environment & commands

- **Torch 2.10 with Apple MPS available** (fast on-device training; ~7 min for 2800 steps at the current size). numpy 2.4, pandas 2.3, sklearn 1.8.
- Run from the worktree root with `PYTHONPATH=.`.
- Train: `PYTHONPATH=. python3 -m src.world_model.train_jepa --epochs 25 --limit-steps 2800 --stride 4 --batch 256 --var-coef 1.5` (CLI overrides exist: `--var-coef --cov-coef --embed-dim --horizon`? — note `horizon` is currently a `JEPAConfig` field, add a CLI flag if you tune it).
- Data: `data/processed/all_patients_windowed.csv` (10 infants, ~145k windows, 10 `_dev` features + `label`). Per-infant raw: `data/processed/infant*_features.csv`, `*_resp_features.csv`. `combined_features_labelled.csv` = raw features + label.
- Checkpoint: `models/jepa/jepa.pt` (+ `training_log.json`).

## 6. Situational context (what else is going on)

- **Map #56** (this effort) — SSOT. **#57 (spec) is APPROVED** (`docs/design/demo-showtime-spec.md`): scenario `infant7` (spec pick `[1240,1419]`, but per §2 use `[2098,2277]` — infant7's best — and re-record the trace if you change it), clinical-noir visual, 3-D-hero + HUD layout, real-spine + cinematic-amplification.
- **#61 (immersive shell) is DONE** — `dashboard/app/showtime/[id]/page.tsx` + `dashboard/components/showtime/ShowtimeShell.tsx`. Full-page clinical-noir stage, shared playhead, tier rails + agent theater, honest slot-markers for #62/#63/#64. Typecheck + `next build` clean; renders at `/showtime/infant7`. The 3-D hero currently shows a placeholder marker driven by a **CUSUM surrogate** labelled "(surrogate)" — **#62 replaces it with the real JEPA embedding once your numbers are good and #60 exports the trajectory.**
- **Downstream tickets** waiting on you: **#60** (export the real embedding trajectory + surprise → extend the #30 trace contract with a `world_model` block), then **#62** (the 3-D warp), and **#59** (the `JepaSurpriseAssessor` in the cascade seam).
- **Open decision you inherit:** the owner chose *iterate the model first* (this handoff) over immediately amplifying the subtle trajectory. Only fall back to amplification if §4 genuinely doesn't pan out.

## 7. Key pointers
- `CONTEXT.md` (domain vocab), `docs/adr/0002` (world model replaces classifier — the *why*), `docs/adr/0003`.
- `src/world_model/forecaster.py` (the VAR(1) baseline + Mahalanobis surprise), `src/world_model/loio.py` (LOIO harness to adapt), `docs/research/world-model-surprise-loio-result.md` (the 0.635 baseline + the #18 data caveat).
- Map [#56](https://github.com/cmengu/Neonatal/issues/56), ticket [#58](https://github.com/cmengu/Neonatal/issues/58).
