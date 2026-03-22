"""SQLite-backed episodic memory for the NeonatalGuard agent.

Stores the last N alerts per patient so the LLM reasoning node can provide
temporal context ("this patient had 3 yellow alerts in the past 24 h").

Uses a plain SQLite file at data/audit.db.  Pass db_path=':memory:' in tests.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from src.agent.schemas import NeonatalAlert


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass
class PastAlert:
    """Lightweight representation of a historical alert row."""

    timestamp: str
    concern_level: str
    risk_score: float
    top_feature: str
    top_z_score: float


class EpisodicMemory:
    """Persist and retrieve past alerts for a given patient."""

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = str(REPO_ROOT / "data" / "audit.db")
        self.db_path = db_path
        # Create parent directory for the default on-disk path.
        # Skip for ':memory:' — Path(':memory:').parent would be '.'.
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
        self._check_schema_version()

    def _init_schema(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS alert_history (
                    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id           TEXT,
                    timestamp            TEXT,
                    concern_level        TEXT,
                    risk_score           REAL,
                    top_feature          TEXT,
                    top_z_score          REAL,
                    z_scores_json        TEXT,
                    hrv_values_json      TEXT,
                    signal_pattern       TEXT,
                    signal_confidence    REAL,
                    brady_classification TEXT,
                    brady_weight         TEXT,
                    agent_version        TEXT
                )
                """
            )
            # Migrate existing tables (Phase 4 added z_scores_json/hrv_values_json;
            # Phase 5 adds specialist columns + schema_meta).
            # ALTER TABLE ADD COLUMN raises OperationalError on re-run — try/except is safe.
            for col_def in (
                "z_scores_json        TEXT",
                "hrv_values_json      TEXT",
                "signal_pattern       TEXT",
                "signal_confidence    REAL",
                "brady_classification TEXT",
                "brady_weight         TEXT",
                "agent_version        TEXT",
            ):
                try:
                    conn.execute(f"ALTER TABLE alert_history ADD COLUMN {col_def}")
                except Exception:
                    pass  # column already present — safe to ignore

            # FIX-6: Schema version table — tracks which migration level this db is at.
            # Allows Phase 6 to detect and reject un-migrated Phase 3/4 databases.
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key   TEXT PRIMARY KEY,
                    value TEXT
                )
                """
            )
            conn.execute(
                "INSERT OR REPLACE INTO schema_meta (key, value) VALUES ('version', '2.0')"
            )

    def _check_schema_version(self) -> None:
        """Raise RuntimeError if audit.db schema version is not 2.0.

        Protects against accidentally using a Phase 3/4 database that lacks
        the specialist output columns added in Phase 5.
        Skips for :memory: (each connect creates a fresh DB; used in tests).
        """
        if self.db_path == ":memory:":
            return
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT value FROM schema_meta WHERE key='version'"
            ).fetchone()
        if not row or row[0] != "2.0":
            raise RuntimeError(
                f"audit.db schema version mismatch: expected '2.0', got {row[0] if row else 'None'}. "
                "Run: python -c \"from src.agent.memory import EpisodicMemory; EpisodicMemory()\" "
                "to apply the Phase 5 migration."
            )

    def get_recent(self, patient_id: str, n: int = 7) -> list[PastAlert]:
        """Return the n most recent alerts for a patient, newest first."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT timestamp, concern_level, risk_score, top_feature, top_z_score
                FROM alert_history
                WHERE patient_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (patient_id, n),
            ).fetchall()
        return [PastAlert(*row) for row in rows]

    def count_similar(self, patient_id: str, level: str, hours: int = 72) -> int:
        """Count how many alerts of a given level were generated in the last N hours."""
        with sqlite3.connect(self.db_path) as conn:
            count = conn.execute(
                """
                SELECT COUNT(*) FROM alert_history
                WHERE patient_id = ?
                  AND concern_level = ?
                  AND timestamp > datetime('now', ? || ' hours')
                """,
                (patient_id, level, f"-{hours}"),
            ).fetchone()[0]
        return count

    def save(
        self,
        alert: NeonatalAlert,
        top_feature: str,
        top_z: float,
        z_scores: dict | None = None,
        hrv_values: dict | None = None,
        signal_pattern: str | None = None,
        signal_confidence: float | None = None,
        brady_classification: str | None = None,
        brady_weight: str | None = None,
        agent_version: str = "generalist",
    ) -> None:
        """Persist a finalised alert to the audit log.

        Phase 4 (FIX-2): z_scores and hrv_values trace model inputs.
        Phase 5 (FIX-7): specialist outputs (signal_pattern, signal_confidence,
        brady_classification, brady_weight, agent_version) trace multi-agent decisions.
        All specialist kwargs default to None so existing generalist callers are unaffected.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO alert_history
                (patient_id, timestamp, concern_level, risk_score,
                 top_feature, top_z_score, z_scores_json, hrv_values_json,
                 signal_pattern, signal_confidence,
                 brady_classification, brady_weight, agent_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alert.patient_id,
                    alert.timestamp.isoformat(),
                    alert.concern_level,
                    alert.risk_score,
                    top_feature,
                    top_z,
                    json.dumps(z_scores) if z_scores is not None else None,
                    json.dumps(hrv_values) if hrv_values is not None else None,
                    signal_pattern,
                    signal_confidence,
                    brady_classification,
                    brady_weight,
                    agent_version,
                ),
            )
