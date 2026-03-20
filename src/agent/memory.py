"""SQLite-backed episodic memory for the NeonatalGuard agent.

Stores the last N alerts per patient so the LLM reasoning node can provide
temporal context ("this patient had 3 yellow alerts in the past 24 h").

Uses a plain SQLite file at data/audit.db.  Pass db_path=':memory:' in tests.
"""
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

    def _init_schema(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS alert_history (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id    TEXT,
                    timestamp     TEXT,
                    concern_level TEXT,
                    risk_score    REAL,
                    top_feature   TEXT,
                    top_z_score   REAL
                )
                """
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

    def save(self, alert: NeonatalAlert, top_feature: str, top_z: float) -> None:
        """Persist a finalised alert to the audit log."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO alert_history
                (patient_id, timestamp, concern_level, risk_score, top_feature, top_z_score)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    alert.patient_id,
                    alert.timestamp.isoformat(),
                    alert.concern_level,
                    alert.risk_score,
                    top_feature,
                    top_z,
                ),
            )
