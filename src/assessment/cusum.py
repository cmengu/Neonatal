"""Tier 2 (deterministic half) — the CUSUM Drift detector.

Issue #4. Catches *gradual* deterioration: a sustained, sub-threshold departure from
the infant's own baseline that no single window trips the Tier 1 floor on, but which
integrates over hours to a Drift alarm. This is the temporal complement to Tier 1's
instantaneous Shewhart-style floor — the textbook Shewhart-plus-CUSUM pairing.

Grounded in ``docs/research/cusum-drift-and-composition-validation.md`` (research gate
#11): a one-sided tabular (Page 1954) CUSUM, ``k = 0.5``, ``h = 5`` z-units, targeting a
sustained ``δ = 1 SD`` drift, run in the *pathological* direction only.

**The design fork this resolves (deliberately, not by default).** The stream fed to the
CUSUM is a *single direction-aware composite* of the personalised deviations — the mean
pathological magnitude across the direction-aware features present — **not** five parallel
per-feature CUSUMs. Parallel one-sided CUSUMs would inflate the aggregate false-alarm rate
exactly the way ``max|z|`` over co-equal features did before #8 fixed Tier 1; a single
composite avoids that and inherits Tier 1's direction map (reassuring deviations
contribute 0). See the issue #4 discussion + research §"Open questions" (per-feature vs
multivariate).

**Honesty guardrail.** A Drift alarm is a self-referenced *abnormality-departure* signal,
**not** HeRO's outcome-calibrated fold-risk. Firing maps to YELLOW (a developing-concern
early warning); RED remains Tier 1's authority for acute, concordant excursions.

**State.** CUSUM is stateful — the running sum ``C⁺`` *is* the accumulated evidence. It is
persisted per infant so drift detection survives restarts (``SqliteCusumStore`` →
``audit.db``), and reset to 0 after a signal (Page's scheme). ``InMemoryCusumStore`` is the
default for tests / ephemeral use.

**Deferred gaps (honest, carried forward — not silently missing).**

- *Warm-up.* The research gate wants the CUSUM to arm only once the Tier 1 baseline is
  stable; it also records this as ``[OPEN — engineering]`` with no published standard. Not
  implemented here — the detector arms from window 1 — because inventing a warm-up constant
  now would be a guess; it lands with the real-stream calibration below.
- *Operating point.* The ARL figures behind ``h`` assume i.i.d. samples; a real neonatal
  z-stream is autocorrelated, so ``(k, h)`` must ultimately be confirmed by simulation on
  real streams and the achieved false-alarms-per-infant-day recorded (research §2.4). The
  persisted state deliberately does **not** yet carry ``(k, h, δ)`` + measured ARL₀ — those
  are audit fields for after that simulation, and ``h``/``k``/``δ`` live in
  ``CusumThresholds`` (the config SSOT) meanwhile.
- *Wiring.* The default store is in-memory; ``audit.db`` persistence engages only when a
  caller injects ``SqliteCusumStore``. The cascade is still test-only (issue #7 wires the
  runtime), so nothing points this at ``data/audit.db`` yet — by design.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from src.assessment.deviation import DEFAULT_DIRECTIONS, Direction, pathological_magnitude
from src.assessment.types import Assessment, AssessmentContext, ConcernLevel

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Confidence a Drift Assessment reports. Below the deterministic floor's 1.0 on purpose:
# the CUSUM recursion is exact, but its operating point (ARL) has NOT yet been confirmed
# on the real autocorrelated neonatal stream (research §2.4), so the tier is honestly
# less than certain about the alarm it raises. A calibration on real data revises this.
_DETECTOR_CONFIDENCE = 0.9


def composite_deviation(
    z_scores: Mapping[str, float],
    directions: Mapping[str, Direction] = DEFAULT_DIRECTIONS,
) -> float:
    """Reduce a window's z-scores to one direction-aware scalar in z-units.

    The mean pathological magnitude over the direction-aware features *present* in
    ``z_scores`` (reassuring or display-only features contribute 0). A single composite,
    not a per-feature max, so the CUSUM cannot inflate false alarms by multiplicity —
    the temporal analogue of Tier 1's concordance gate (#8).
    """
    mags = [
        pathological_magnitude(directions, feature, z)
        for feature, z in z_scores.items()
        if feature in directions
    ]
    if not mags:
        return 0.0
    return sum(mags) / len(mags)


@dataclass(frozen=True)
class CusumThresholds:
    """The one config for the Drift detector, mirroring ``DeviationThresholds``.

    Defaults come straight from the research gate: ``k = 0.5`` (the "half the shift" rule
    that makes CUSUM optimal for a sustained 1 SD drift) and ``h = 5`` z-units (favours
    specificity for alarm-fatigue reduction; drop to 4 only if detection proves too slow).
    Injectable so a future calibration on real streams is a config change, not a rewrite.
    """

    k: float = 0.5
    h: float = 5.0
    directions: Mapping[str, Direction] = field(
        default_factory=lambda: dict(DEFAULT_DIRECTIONS)
    )


@dataclass(frozen=True)
class CusumState:
    """Per-infant, per-detector persisted state — the accumulated evidence itself.

    ``c_plus`` is the running one-sided sum; ``n_updates`` counts windows processed (a
    deterministic stand-in for a wall-clock timestamp); ``last_signal_at`` is the update
    index of the most recent fire (``None`` if never). Reset ``c_plus → 0`` after a signal.
    """

    c_plus: float = 0.0
    n_updates: int = 0
    last_signal_at: int | None = None


class CusumStateStore(Protocol):
    """Loads/saves per-infant CUSUM state. The seam that makes persistence swappable."""

    def load(self, patient_id: str) -> CusumState: ...
    def save(self, patient_id: str, state: CusumState) -> None: ...


class InMemoryCusumStore:
    """Default store — a dict. Ephemeral: state is lost when the process ends."""

    def __init__(self) -> None:
        self._states: dict[str, CusumState] = {}

    def load(self, patient_id: str) -> CusumState:
        return self._states.get(patient_id, CusumState())

    def save(self, patient_id: str, state: CusumState) -> None:
        self._states[patient_id] = state


class SqliteCusumStore:
    """Persists CUSUM state to a SQLite ``cusum_state`` table (``data/audit.db`` by
    default), so drift detection survives restarts. Pass ``db_path=':memory:'`` in tests.

    Follows the ``src.agent.memory`` convention (plain sqlite3, one table). Distinct table
    from ``alert_history``, so it neither depends on nor triggers that schema-version gate.
    """

    def __init__(self, db_path: str | None = None) -> None:
        if db_path is None:
            db_path = str(REPO_ROOT / "data" / "audit.db")
        self.db_path = db_path
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        # ':memory:' opens a fresh DB per connection, so a persistent handle is required
        # for it to behave like a single store across load/save calls.
        self._mem_conn = sqlite3.connect(":memory:") if self.db_path == ":memory:" else None
        self._init_schema()

    @contextmanager
    def _cursor(self) -> Iterator[sqlite3.Connection]:
        """One connection idiom for every method, commit-on-exit. Mirrors the
        ``with sqlite3.connect(...)`` pattern in ``src.agent.memory``, but reuses the
        persistent in-memory handle when ``db_path == ':memory:'`` (a fresh connect there
        would open an empty database and lose all state)."""
        conn = self._mem_conn if self._mem_conn is not None else sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            if self._mem_conn is None:
                conn.close()

    def _init_schema(self) -> None:
        with self._cursor() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cusum_state (
                    patient_id     TEXT PRIMARY KEY,
                    c_plus         REAL NOT NULL,
                    n_updates      INTEGER NOT NULL,
                    last_signal_at INTEGER
                )
                """
            )

    def load(self, patient_id: str) -> CusumState:
        with self._cursor() as conn:
            row = conn.execute(
                "SELECT c_plus, n_updates, last_signal_at FROM cusum_state WHERE patient_id = ?",
                (patient_id,),
            ).fetchone()
        if row is None:
            return CusumState()
        return CusumState(c_plus=row[0], n_updates=row[1], last_signal_at=row[2])

    def save(self, patient_id: str, state: CusumState) -> None:
        with self._cursor() as conn:
            conn.execute(
                """
                INSERT INTO cusum_state (patient_id, c_plus, n_updates, last_signal_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(patient_id) DO UPDATE SET
                    c_plus = excluded.c_plus,
                    n_updates = excluded.n_updates,
                    last_signal_at = excluded.last_signal_at
                """,
                (patient_id, state.c_plus, state.n_updates, state.last_signal_at),
            )


class TemporalAssessor:
    """Tier 2 (deterministic): one-sided CUSUM over the direction-aware composite.

    Each ``assess`` processes one window: it folds the window's composite into the persisted
    running sum ``C⁺ = max(0, C⁺ + composite − k)`` and fires a Drift (YELLOW) when
    ``C⁺ ≥ h``, resetting the sum afterwards. Deterministic: the same context sequence from
    the same starting state always yields the same escalation point.
    """

    def __init__(
        self,
        store: CusumStateStore | None = None,
        thresholds: CusumThresholds = CusumThresholds(),
    ) -> None:
        self._store = store if store is not None else InMemoryCusumStore()
        self._t = thresholds

    def assess(self, context: AssessmentContext) -> Assessment:
        composite = composite_deviation(context.z_scores, self._t.directions)
        prior = self._store.load(context.patient_id)

        c_plus = max(0.0, prior.c_plus + composite - self._t.k)
        n_updates = prior.n_updates + 1
        fired = c_plus >= self._t.h

        if fired:
            level = ConcernLevel.YELLOW
            risk = 1.0
            new_state = CusumState(c_plus=0.0, n_updates=n_updates, last_signal_at=n_updates)
        else:
            level = ConcernLevel.GREEN
            risk = min(c_plus / self._t.h, 1.0) if self._t.h > 0 else 0.0
            new_state = CusumState(
                c_plus=c_plus, n_updates=n_updates, last_signal_at=prior.last_signal_at
            )

        self._store.save(context.patient_id, new_state)

        if fired:
            recurrence = (
                "first sustained Drift for this infant"
                if prior.last_signal_at is None
                else f"recurring Drift (previous alarm at window {prior.last_signal_at})"
            )
            rationale = (
                f"CUSUM Drift ({level.value}): {recurrence} — accumulated pathological deviation "
                f"reached the decision interval (C⁺≥h={self._t.h:g}) at window {n_updates}, a "
                f"sustained sub-threshold departure from this infant's own baseline (k={self._t.k:g}, "
                f"δ=1 SD). Abnormality-departure signal over time, not a validated risk score; "
                f"RED remains the instantaneous floor's authority."
            )
        else:
            rationale = (
                f"No sustained Drift (C⁺={c_plus:.2f} < h={self._t.h:g}) at window {n_updates}: "
                f"the direction-aware deviation composite is not accumulating toward an alarm."
            )

        return Assessment(
            level=level,
            risk=risk,
            confidence=_DETECTOR_CONFIDENCE,
            rationale=rationale,
            source="temporal",
        )
