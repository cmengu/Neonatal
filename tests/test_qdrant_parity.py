"""FIX-9: Qdrant mode parity test — local-path vs Docker networked.

Run manually only — requires Docker:
    docker compose up qdrant -d
    python tests/test_qdrant_parity.py

NOT in CI (Docker not available in GitHub Actions eval workflow).
Verifies that local-path and networked Qdrant return identical query results
so development and production behaviour are provably the same.
"""
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.knowledge.knowledge_base import ClinicalKnowledgeBase

TEST_QUERIES = [
    "RMSSD declining sepsis premature neonate",
    "bradycardia cluster three episodes 60 minutes",
    "personalised baseline LOOKBACK rolling window",
]


def test_parity():
    qdrant_path = os.getenv("QDRANT_PATH", str(REPO_ROOT / "qdrant_local"))
    kb_local = ClinicalKnowledgeBase(path=qdrant_path)
    kb_remote = ClinicalKnowledgeBase(host="localhost", port=6333)

    for query in TEST_QUERIES:
        local_results = kb_local.query(query, n=3)
        remote_results = kb_remote.query(query, n=3)
        assert local_results == remote_results, (
            f"Parity failure for query: '{query}'\n"
            f"  Local:  {[r[:80] for r in local_results]}\n"
            f"  Remote: {[r[:80] for r in remote_results]}"
        )
        print(f"  OK: '{query[:50]}...' — 3 identical results")

    print("PASS FIX-9: local-path and networked Qdrant return identical results for all queries")


if __name__ == "__main__":
    test_parity()
