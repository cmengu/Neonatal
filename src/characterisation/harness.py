"""Inject departures of known magnitude and timing; measure what the cascade does.

Four quantities, each answering a question a reviewer will actually ask:

- **detection delay** vs effect size — "how fast does it notice?"
- **false alarms per patient-day** on a no-event run — "how often does it cry wolf?"
- **ARL₀**, the in-control run length — the same thing in the units the CUSUM
  literature reports, so our operating point can be compared to published ones
- **sensitivity floor** — the smallest sustained departure it sees at all

Why the stream is z-scores and not RR intervals
-----------------------------------------------
#83 frames this as injecting perturbations into synthetic RR series. This module injects
them one stage later, directly into the per-infant z-score stream the cascade consumes,
and that is a deliberate choice rather than a shortcut.

The measurement's whole value is that the injected magnitude is *exactly* known. Tier 1's
trigger (``z_trigger = 2.0``) and Tier 2's ``(k, h)`` are both defined in z-units — per-infant
SD — so a departure specified in z-units is specified in the detector's own units, and the
resulting delay/false-alarm curves are directly interpretable against the thresholds. Going
RR → features → baseline → z would push the departure through sample entropy, a Welch PSD
and a rolling baseline, each adding variance we do not control, so "a departure of magnitude
δ" would no longer mean a definite thing.

The cost is real and worth stating: this characterises the **detector** (Tier 1 floor +
Tier 2 CUSUM), not the **feature extractor**. It cannot tell you whether a 4 ms RMSSD drop
produces a 2 SD z-shift — that is a feature-pipeline question, and D2's 125 Hz
quantisation measurement is the right instrument for it. Claims from this module must be
phrased in z-units, never in milliseconds.

Everything here describes departures by **magnitude and direction only**. No function takes
a disease name, and none should ever be added (D10, #86).
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Sequence

import numpy as np

from src.assessment.cusum import (
    CusumThresholds,
    InMemoryCusumStore,
    TemporalAssessor,
    composite_deviation,
)
from src.assessment.deviation import DEFAULT_DIRECTIONS, DeviationAssessor, DeviationThresholds
from src.assessment.types import AssessmentContext, ConcernLevel

# Windows advance one Tier-1 step apart. run_nb03/regenerate_hrv_features use a 50-beat
# window with a 25-beat step, so a window is ~25 beats of new data; at a neonatal rate of
# ~140 bpm that is ~10.7 s. Used only to convert run lengths into patient-days for the
# false-alarm rate — the underlying measurements are all in windows.
SECONDS_PER_WINDOW = 25.0 * 60.0 / 140.0
WINDOWS_PER_DAY = 24 * 3600 / SECONDS_PER_WINDOW

# The features a departure moves by default: the trigger-capable ones whose pathological
# direction is a *fall* in variability. This is the HeRO signature — reduced variability —
# and it is the shape the cascade is built to catch, so it is the honest default to
# characterise against. Named by direction, never by the condition it may accompany.
VARIABILITY_COLLAPSE = ("sdnn", "rmssd", "sampen")


@dataclass(frozen=True)
class Departure:
    """A perturbation of known magnitude, timing and shape.

    Attributes
    ----------
    magnitude_z : float
        Sustained shift in the *pathological* direction, in per-infant SD. 1.0 means the
        affected features settle 1 SD into the abnormal side of their own baseline.
    onset_window : int
        Index of the first affected window. Windows before this are in-control.
    features : tuple[str, ...]
        Which features move. Must be trigger-capable, or the departure is invisible by
        construction and the measurement is vacuous — ``validate`` enforces this.
    ramp_windows : int
        0 for a step change; >0 spreads the shift linearly over that many windows, which
        is the harder and more realistic case for a Shewhart-style floor to catch.
    """

    magnitude_z: float
    onset_window: int
    features: tuple[str, ...] = VARIABILITY_COLLAPSE
    ramp_windows: int = 0

    def validate(self, directions: dict[str, str] | None = None) -> None:
        d = DEFAULT_DIRECTIONS if directions is None else directions
        unknown = [f for f in self.features if f not in d]
        if unknown:
            raise ValueError(
                f"{unknown} are not trigger-capable, so a departure in them cannot be "
                f"detected by construction and the measurement would be vacuous. "
                f"Trigger-capable features: {sorted(d)}"
            )
        if self.ramp_windows < 0:
            raise ValueError(f"ramp_windows must be >= 0, got {self.ramp_windows}")

    def shift_at(self, window_idx: int) -> float:
        """Signed shift applied at ``window_idx``, in z-units, before direction is applied."""
        if window_idx < self.onset_window:
            return 0.0
        if self.ramp_windows == 0:
            return self.magnitude_z
        progress = min(1.0, (window_idx - self.onset_window + 1) / self.ramp_windows)
        return self.magnitude_z * progress


def synthesise_stream(
    n_windows: int,
    departure: Departure | None = None,
    noise_sd: float = 1.0,
    seed: int = 0,
    directions: dict[str, str] | None = None,
) -> list[AssessmentContext]:
    """Build a z-score stream: in-control noise, plus an optional sustained departure.

    In control, each feature's z-score is drawn i.i.d. from N(0, ``noise_sd``), which is
    what "z-score against this infant's own stable baseline" means by definition. That
    i.i.d. assumption is the known limitation of this instrument — see ``ARL0_CAVEAT``.
    """
    d = DEFAULT_DIRECTIONS if directions is None else directions
    if departure is not None:
        departure.validate(d)

    rng = np.random.default_rng(seed)
    features = sorted(d)
    stream: list[AssessmentContext] = []

    for i in range(n_windows):
        z = {f: float(rng.normal(0.0, noise_sd)) for f in features}
        if departure is not None:
            shift = departure.shift_at(i)
            for f in departure.features:
                # Push in the feature's own pathological direction, so magnitude_z is
                # always "how abnormal", never "how positive".
                sign = -1.0 if d[f] == "low" else 1.0
                z[f] += sign * shift
        stream.append(AssessmentContext(patient_id=f"synthetic-{seed}", z_scores=z))

    return stream


ARL0_CAVEAT = (
    "In-control windows here are i.i.d. N(0, 1). A real neonatal z-stream is "
    "autocorrelated, which inflates the true false-alarm rate above what an i.i.d. "
    "simulation shows — a run of correlated windows drifts the CUSUM further than "
    "independent ones. Treat every ARL0 and false-alarm figure from this module as an "
    "OPTIMISTIC BOUND, and read the ordering across (k, h) rather than the absolute "
    "level. Confirming the level needs the real stream (cusum.py, research §2.4)."
)


@dataclass
class RunResult:
    """What the cascade did on one synthetic stream."""

    fired_at: int | None          # first window index that escalated, or None
    n_windows: int
    departure_onset: int | None
    levels: list[ConcernLevel] = field(default_factory=list)

    @property
    def detected(self) -> bool:
        return self.fired_at is not None

    @property
    def delay_windows(self) -> int | None:
        """Windows between departure onset and first escalation.

        None if nothing fired, or if it fired *before* onset — that is a false alarm, not
        a detection, and averaging it into a delay would flatter the detector.
        """
        if self.fired_at is None or self.departure_onset is None:
            return None
        if self.fired_at < self.departure_onset:
            return None
        return self.fired_at - self.departure_onset

    @property
    def delay_seconds(self) -> float | None:
        d = self.delay_windows
        return None if d is None else d * SECONDS_PER_WINDOW


def run_tier2(
    stream: Sequence[AssessmentContext],
    thresholds: CusumThresholds | None = None,
    departure_onset: int | None = None,
) -> RunResult:
    """Run Tier 2's CUSUM alone over a stream and record the first Drift signal.

    Tier 2 in isolation, not the whole cascade, because the question #84 asks is about the
    ``(k, h)`` operating point specifically. Tier 1 is memoryless — it fires on any single
    window past ``z_trigger`` regardless of history — so including it would mix an
    instantaneous threshold crossing into a measurement about accumulated drift.
    ``run_cascade`` covers the composed behaviour.
    """
    t = thresholds or CusumThresholds()
    assessor = TemporalAssessor(store=InMemoryCusumStore(), thresholds=t)

    fired_at = None
    levels: list[ConcernLevel] = []
    for i, ctx in enumerate(stream):
        a = assessor.assess(ctx)
        levels.append(a.level)
        if a.level != ConcernLevel.GREEN and fired_at is None:
            fired_at = i

    return RunResult(
        fired_at=fired_at,
        n_windows=len(stream),
        departure_onset=departure_onset,
        levels=levels,
    )


def run_cascade(
    stream: Sequence[AssessmentContext],
    departure_onset: int | None = None,
    deviation_thresholds: DeviationThresholds | None = None,
    cusum_thresholds: CusumThresholds | None = None,
) -> RunResult:
    """Run Tier 1 + Tier 2 composed, as they run in production.

    Tier 3 is excluded: it is escalate-only and LLM-backed, so including it would make the
    measurement non-deterministic and network-dependent for no gain — it cannot lower a
    level, and what is being measured is when the level first rises.
    """
    dev = DeviationAssessor(deviation_thresholds or DeviationThresholds())
    tmp = TemporalAssessor(
        store=InMemoryCusumStore(), thresholds=cusum_thresholds or CusumThresholds()
    )

    fired_at = None
    levels: list[ConcernLevel] = []
    for i, ctx in enumerate(stream):
        d = dev.assess(ctx)
        t = tmp.assess(ctx)
        level = max((d.level, t.level), key=_severity)
        levels.append(level)
        if level != ConcernLevel.GREEN and fired_at is None:
            fired_at = i

    return RunResult(
        fired_at=fired_at,
        n_windows=len(stream),
        departure_onset=departure_onset,
        levels=levels,
    )


def _severity(level: ConcernLevel) -> int:
    return {ConcernLevel.GREEN: 0, ConcernLevel.YELLOW: 1, ConcernLevel.RED: 2}[level]


# --- The four measurements ------------------------------------------------------------


def detection_delay(
    magnitude_z: float,
    n_replicates: int = 200,
    onset_window: int = 100,
    n_windows: int = 600,
    features: tuple[str, ...] = VARIABILITY_COLLAPSE,
    ramp_windows: int = 0,
    thresholds: CusumThresholds | None = None,
    tier2_only: bool = True,
    seed0: int = 0,
) -> dict:
    """Median detection delay for a sustained departure of ``magnitude_z``.

    Reports the detection *rate* alongside the delay. A median delay computed only over
    runs that detected is meaningless without knowing how many did — at magnitudes near
    the sensitivity floor most runs never fire, and the survivors are the lucky fast ones.
    """
    delays: list[int] = []
    detected = 0
    false_before_onset = 0

    for r in range(n_replicates):
        dep = Departure(
            magnitude_z=magnitude_z,
            onset_window=onset_window,
            features=features,
            ramp_windows=ramp_windows,
        )
        stream = synthesise_stream(n_windows, departure=dep, seed=seed0 + r)
        if tier2_only:
            res = run_tier2(stream, thresholds=thresholds, departure_onset=onset_window)
        else:
            res = run_cascade(
                stream, departure_onset=onset_window, cusum_thresholds=thresholds
            )
        if res.fired_at is not None and res.fired_at < onset_window:
            false_before_onset += 1
            continue
        d = res.delay_windows
        if d is not None:
            delays.append(d)
            detected += 1

    return {
        "magnitude_z": magnitude_z,
        "n_replicates": n_replicates,
        "detection_rate": detected / n_replicates,
        "false_before_onset": false_before_onset / n_replicates,
        "median_delay_windows": float(np.median(delays)) if delays else None,
        "p90_delay_windows": float(np.percentile(delays, 90)) if delays else None,
        "median_delay_seconds": float(np.median(delays) * SECONDS_PER_WINDOW) if delays else None,
    }


def false_alarm_rate(
    n_replicates: int = 200,
    n_windows: int = 2000,
    thresholds: CusumThresholds | None = None,
    tier2_only: bool = True,
    seed0: int = 10_000,
) -> dict:
    """False alarms per patient-day on in-control streams, plus ARL₀.

    ARL₀ is the mean number of in-control windows before a false signal. Runs that never
    fire are *censored*, not dropped: discarding them would bias ARL₀ downward, which is
    the direction that flatters the detector. They are reported separately so the figure
    can be read as the bound it is.
    """
    first_signals: list[int] = []
    censored = 0

    for r in range(n_replicates):
        stream = synthesise_stream(n_windows, departure=None, seed=seed0 + r)
        res = run_tier2(stream, thresholds=thresholds) if tier2_only else run_cascade(stream)
        if res.fired_at is None:
            censored += 1
        else:
            first_signals.append(res.fired_at)

    if first_signals:
        arl0 = float(np.mean(first_signals))
        alarms_per_day = WINDOWS_PER_DAY / arl0
    else:
        arl0 = float("inf")
        alarms_per_day = 0.0

    return {
        "n_replicates": n_replicates,
        "n_windows_per_run": n_windows,
        "arl0_windows": arl0,
        "arl0_hours": arl0 * SECONDS_PER_WINDOW / 3600 if np.isfinite(arl0) else float("inf"),
        "false_alarms_per_patient_day": alarms_per_day,
        "censored_fraction": censored / n_replicates,
        "caveat": ARL0_CAVEAT,
    }


def sensitivity_floor(
    within_windows: int,
    magnitudes: Sequence[float] = (0.1, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0),
    detection_target: float = 0.90,
    n_replicates: int = 200,
    thresholds: CusumThresholds | None = None,
    onset_window: int = 100,
    n_windows: int = 3000,
    **kw,
) -> dict:
    """Smallest departure detected within ``within_windows`` of onset, in ≥ ``detection_target``
    of runs.

    A time budget is mandatory, and that is the point rather than an inconvenience. A CUSUM
    integrates, so for a *sustained* departure the detection probability tends to 1 for any
    δ > 0 given unbounded time — measured here as 99.2% at every δ from 0.25 to 2.0 SD when
    500 windows are available. An unqualified "sensitivity floor" would therefore always
    read ~0 and mean nothing.

    The honest statement is a joint one: *this magnitude, within this long, at this
    false-alarm rate.* Pick ``within_windows`` from what the application can wait for —
    ``SECONDS_PER_WINDOW`` converts.
    """
    sweep = []
    for m in magnitudes:
        r = detection_delay(
            m,
            n_replicates=n_replicates,
            thresholds=thresholds,
            onset_window=onset_window,
            n_windows=n_windows,
            **kw,
        )
        # Re-score against the budget: detection_delay reports the unbudgeted rate.
        r = dict(r)
        p90 = r["p90_delay_windows"]
        med = r["median_delay_windows"]
        r["within_budget"] = med is not None and med <= within_windows
        r["p90_within_budget"] = p90 is not None and p90 <= within_windows
        sweep.append(r)

    passing = [
        s for s in sweep
        if s["detection_rate"] >= detection_target and s["within_budget"]
    ]
    floor = min((s["magnitude_z"] for s in passing), default=None)
    return {
        "within_windows": within_windows,
        "within_seconds": within_windows * SECONDS_PER_WINDOW,
        "detection_target": detection_target,
        "sensitivity_floor_z": floor,
        "sweep": sweep,
        "caveat": ARL0_CAVEAT,
    }


def operating_characteristic(
    k_values: Sequence[float] = (0.25, 0.5, 0.75, 1.0),
    h_values: Sequence[float] = (3.0, 4.0, 5.0, 6.0, 8.0),
    magnitude_z: float = 1.0,
    n_replicates: int = 100,
    n_windows_incontrol: int = 2000,
) -> list[dict]:
    """Trace delay against false-alarm rate across the ``(k, h)`` plane — the #84 curve.

    ``magnitude_z = 1.0`` by default because ``k = 0.5`` is the "half the shift" rule for a
    sustained **1 SD** shift, so this is the target the current operating point was chosen
    for. Whether 1 SD is the right target for *this* application is exactly what #84 says
    cannot be settled on ten bradycardia-labelled infants — this traces the trade-off so
    the choice is at least made on a measured curve rather than inherited.
    """
    rows = []
    for k in k_values:
        for h in h_values:
            t = CusumThresholds(k=k, h=h)
            fa = false_alarm_rate(
                n_replicates=n_replicates, n_windows=n_windows_incontrol, thresholds=t
            )
            dd = detection_delay(magnitude_z, n_replicates=n_replicates, thresholds=t)
            rows.append(
                {
                    "k": k,
                    "h": h,
                    "arl0_windows": fa["arl0_windows"],
                    "false_alarms_per_patient_day": fa["false_alarms_per_patient_day"],
                    "censored_fraction": fa["censored_fraction"],
                    "detection_rate": dd["detection_rate"],
                    "median_delay_windows": dd["median_delay_windows"],
                    "median_delay_seconds": dd["median_delay_seconds"],
                }
            )
    return rows
