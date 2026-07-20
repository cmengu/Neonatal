"""Tier 2 (learned half) — the observational JEPA Surprise assessor.

Issue #59 (map #56, decision 4): the trained JEPA world model (`src/world_model/jepa.py`,
scorecard in ``docs/research/world-model-jepa-result.md``) enters the cascade seam as a
*real* Assessor — and a strictly **observational** one. It watches; it never steers:

- ``level`` is always GREEN, so via ``most_severe`` it can never escalate a verdict;
- ``may_quiet`` is always ``False``, so it can never quiet the SOFT floor (ADR-0003:
  the only quiet in the cascade stays Tier 2's *deterministic* CUSUM quiet);
- ``soft_floor`` is always ``False`` — it is not a floor tier.

Why observational: the scorecard's numbers (onset-anticipation AUC 0.772, held-out,
label-free) make the signal *promising*, but they are a 10-infant result with no
calibrated alarm operating point — exactly the situation where a learned model has
earned a seat at the table (its Surprise rides in every Verdict's ``assessments`` for
the trace and the demo) but not a hand on the wheel.

**What the signal is.** Per infant, the assessor buffers the last ``Lc + H`` windows of
the same 10 personalised-deviation features the model trained on. Each window it scores
the *horizon-aggregated* prediction error (``JEPA.surprise_horizon``): how badly the
context that ended ``H`` windows ago predicted the latents of the stretch ending *now*.
That is the formulation the scorecard validated as anticipatory — a single +1-step error
is trivially predictable on autocorrelated HRV. The raw error is standardised against
this infant's *own running surprise distribution* (Welford), so ``risk`` reads "the last
~H windows were unusually unpredictable *for this infant*" — self-referenced, never an
outcome-calibrated probability, and the rationale says so.

**State.** In-memory per infant, like the CUSUM's ``InMemoryCusumStore`` default — but
deliberately with no persistence seam: the buffer spans ~20 min of stream, so a restart
merely re-warms; there is no accumulated evidence worth surviving a restart (that is the
CUSUM's job).
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import torch

from src.assessment.types import Assessment, AssessmentContext, ConcernLevel
from src.world_model.jepa import JEPA, load_checkpoint
from src.world_model.jepa_data import CLIP, FEATURES

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CHECKPOINT = REPO_ROOT / "models" / "jepa" / "jepa.pt"

# Surprise-z at which risk saturates to 1.0 — mirrors deviation._RISK_SATURATION (3 SD).
# Scales the continuous risk scalar only; nothing gates on it (the tier cannot gate).
_RISK_SATURATION_Z = 3.0
# Surprises observed before the running mean/std is trusted enough to report nonzero risk.
_MIN_CALIBRATION = 8
# Absolute floor on the running std (surprise is O(0.1–1)); guards the degenerate
# near-constant stream from turning numerical jitter into a saturated z.
_SD_FLOOR = 1e-3
# Honest confidence: a real trained model, validated held-out (scorecard AUC ≈ 0.7–0.76),
# but on 10 infants with no calibrated operating point — below the CUSUM's 0.9.
_OBSERVATIONAL_CONFIDENCE = 0.6


@dataclass
class _InfantState:
    """Rolling feature buffer + Welford accumulator of this infant's surprise history."""

    buffer: deque[np.ndarray]
    count: int = 0
    mean: float = 0.0
    m2: float = 0.0

    def zscore_then_update(self, s: float) -> float | None:
        """z of ``s`` against the *prior* running distribution (None while calibrating),
        then fold ``s`` in — same read-before-update discipline as the CUSUM's quiet gate."""
        z: float | None = None
        if self.count >= _MIN_CALIBRATION:
            sd = math.sqrt(self.m2 / (self.count - 1)) if self.count > 1 else 0.0
            z = (s - self.mean) / max(sd, _SD_FLOOR)
        self.count += 1
        delta = s - self.mean
        self.mean += delta / self.count
        self.m2 += delta * (s - self.mean)
        return z


class JepaSurpriseAssessor:
    """Observational learned tier: JEPA horizon-surprise, self-referenced per infant.

    Loads the shipped checkpoint by default; tests inject a tiny model. The ``source``
    attribute is declared on the *class* so the cascade can identify the tier without
    invoking it (the same structural mechanism the rag short-circuit uses).
    """

    source = "jepa_surprise"
    #: Renounces the vote (``Observational``): the cascade keeps this tier's Assessment in the
    #: trace but excludes it from the floor, the level, ``escalated_by`` and the headline. The
    #: GREEN / ``may_quiet=False`` discipline below keeps it out of the *level*; this keeps it
    #: out of the *rationale* a clinician reads, which the level alone does not.
    observational = True

    def __init__(
        self,
        model: JEPA | None = None,
        checkpoint_path: str | Path | None = None,
        device: str = "cpu",
    ) -> None:
        if model is None:
            model = load_checkpoint(str(checkpoint_path or DEFAULT_CHECKPOINT), map_location=device)
        if model.cfg.n_features != len(FEATURES):
            raise ValueError(
                f"JEPA expects {model.cfg.n_features} features but the assessment stream "
                f"carries {len(FEATURES)} ({', '.join(FEATURES)})"
            )
        self._model = model.to(device).eval()
        self._device = torch.device(device)
        self._need = model.cfg.context_len + model.cfg.horizon
        self._states: dict[str, _InfantState] = {}

    # --- feature plumbing ---------------------------------------------------------

    def _features(self, z_scores: dict[str, float]) -> np.ndarray:
        """Window vector in training order. ``z_scores`` carries the personalised
        deviations under bare names (``runner.py`` maps ``f"{col}_dev"`` → ``col``);
        an absent feature reads 0.0 — "at this infant's own baseline" — and values are
        sanitised exactly as in training (nan→0, clip ±CLIP)."""
        vals = [float(z_scores.get(f.removesuffix("_dev"), 0.0)) for f in FEATURES]
        x = np.asarray(vals, dtype=np.float32)
        x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
        return np.clip(x, -CLIP, CLIP)

    # --- the seam -----------------------------------------------------------------

    def assess(self, context: AssessmentContext) -> Assessment:
        state = self._states.setdefault(
            context.patient_id, _InfantState(buffer=deque(maxlen=self._need))
        )
        state.buffer.append(self._features(context.z_scores))

        if len(state.buffer) < self._need:
            return self._observation(
                risk=0.0,
                rationale=(
                    f"JEPA Surprise warming up ({len(state.buffer)}/{self._need} windows "
                    f"buffered) — observational only; the verdict is untouched."
                ),
            )

        arr = np.stack(state.buffer)  # (Lc+H, F)
        lc = self._model.cfg.context_len
        ctx_t = torch.from_numpy(arr[:lc]).unsqueeze(0).to(self._device)
        fut_t = torch.from_numpy(arr[lc:]).unsqueeze(0).to(self._device)
        surprise = float(self._model.surprise_horizon(ctx_t, fut_t).item())

        z = state.zscore_then_update(surprise)
        if z is None:
            return self._observation(
                risk=0.0,
                rationale=(
                    f"JEPA Surprise calibrating ({state.count}/{_MIN_CALIBRATION} surprises "
                    f"observed for this infant) — observational only; the verdict is untouched."
                ),
            )

        risk = min(max(z, 0.0) / _RISK_SATURATION_Z, 1.0)
        trend = "more" if z > 0 else "no less"
        return self._observation(
            risk=risk,
            rationale=(
                f"JEPA Surprise (observational): the last {self._model.cfg.horizon} windows were "
                f"{trend} predictable than usual for this infant — horizon prediction error "
                f"{z:+.1f} SD vs its own running distribution (raw {surprise:.3f}). "
                f"Self-referenced world-model signal, not a calibrated risk; it never moves "
                f"the verdict."
            ),
        )

    def _observation(self, risk: float, rationale: str) -> Assessment:
        """The only Assessment shape this tier can emit: GREEN, never quieting."""
        return Assessment(
            level=ConcernLevel.GREEN,
            risk=risk,
            confidence=_OBSERVATIONAL_CONFIDENCE,
            rationale=rationale,
            source=self.source,
            soft_floor=False,
            may_quiet=False,
        )
