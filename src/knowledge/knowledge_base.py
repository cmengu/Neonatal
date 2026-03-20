"""ClinicalKnowledgeBase: hybrid dense+sparse retrieval with cross-encoder reranking.

All paths resolved relative to this file — CWD-independent.

Usage:
    kb = ClinicalKnowledgeBase()
    chunks = kb.query("RMSSD declining LF/HF rising", n=3, risk_tier="RED")
"""
from __future__ import annotations

import os
import pickle
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from qdrant_client import QdrantClient
from qdrant_client.models import (
    FieldCondition, Filter, Fusion, FusionQuery,
    MatchValue, Prefetch, SparseVector,
)
from sentence_transformers import SentenceTransformer
from flashrank import Ranker, RerankRequest


class ClinicalKnowledgeBase:
    """
    Hybrid retrieval pipeline:
      1. Dense (all-MiniLM-L6-v2) + Sparse (TF-IDF) vectors
      2. 10 candidates from each index, fused with Reciprocal Rank Fusion
      3. Re-ranked with FlashRank ms-marco-MiniLM-L-12-v2 cross-encoder
      4. Returns top n chunk texts

    Note: FlashRank downloads ~80MB model on first call — expected, not a failure.
    """

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
    ) -> None:
        _host = host or os.getenv("QDRANT_HOST", "localhost")
        _port = port or int(os.getenv("QDRANT_PORT", "6333"))
        self.client = QdrantClient(host=_host, port=_port)
        self.dense_model = SentenceTransformer("all-MiniLM-L6-v2")
        self.reranker    = Ranker(model_name="ms-marco-MiniLM-L-12-v2")

        tfidf_path = REPO_ROOT / "models" / "exports" / "tfidf_vectorizer.pkl"
        if not tfidf_path.exists():
            raise FileNotFoundError(
                f"TF-IDF vectorizer not found: {tfidf_path}. "
                "Run src/knowledge/build_knowledge_base.py first."
            )
        with open(tfidf_path, "rb") as f:
            self.tfidf = pickle.load(f)

    def query(
        self,
        text: str,
        n: int = 3,
        risk_tier: str | None = None,
    ) -> list[str]:
        """
        Retrieve top n most relevant clinical chunks for a query.

        Parameters
        ----------
        text      : Free-text query (feature names + z-scores + patient context).
        n         : Chunks to return after reranking.
        risk_tier : Optional filter — "RED", "YELLOW", "GREEN", or None for all tiers.
        """
        dense_vec  = self.dense_model.encode(text).tolist()
        sp         = self.tfidf.transform([text])
        sparse_vec = SparseVector(
            indices=sp.indices.tolist(),
            values=sp.data.tolist(),
        )

        filt = None
        if risk_tier:
            filt = Filter(must=[
                FieldCondition(key="risk_tier", match=MatchValue(value=risk_tier))
            ])

        results = self.client.query_points(
            collection_name="clinical_knowledge",
            prefetch=[
                Prefetch(query=dense_vec,  using="dense",  filter=filt, limit=10),
                Prefetch(query=sparse_vec, using="sparse", filter=filt, limit=10),
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            limit=20,
            with_payload=True,
        )

        candidates = [
            {"id": str(r.id), "text": r.payload["text"]}
            for r in results.points
        ]
        reranked = self.reranker.rerank(
            RerankRequest(query=text, passages=candidates)
        )
        # FlashRank returns dicts with a "text" key (verified against flashrank==0.2.x)
        return [r["text"] for r in reranked[:n]]
