"""Index clinical text chunks into Qdrant with dense + sparse vectors.

Run from repo root: python src/knowledge/build_knowledge_base.py
Requires Qdrant running on localhost:6333 (docker compose up qdrant -d).
All paths resolved relative to this file — CWD-independent.
"""
import datetime
import logging
import os
import pickle
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, PointStruct, SparseVector,
    SparseVectorParams, VectorParams,
)
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer

EXPORTS    = REPO_ROOT / "models" / "exports"
CHUNKS_DIR = REPO_ROOT / "src" / "knowledge" / "clinical_texts"
COLLECTION = "clinical_knowledge"


def parse_chunks(file_path: Path) -> list[dict]:
    """Parse a txt file into chunks with category/risk_tier metadata extracted."""
    raw    = [c.strip() for c in file_path.read_text().split("\n\n") if c.strip()]
    parsed = []
    for chunk in raw:
        lines     = chunk.split("\n")
        meta_line = lines[-1] if "Category:" in lines[-1] else ""
        body      = chunk.replace(meta_line, "").strip()
        category  = "general"
        risk_tier = "ALL"
        if "Category:" in meta_line:
            category = meta_line.split("Category:")[1].split(".")[0].strip()
        if "Risk tier:" in meta_line:
            risk_tier = meta_line.split("Risk tier:")[1].strip().rstrip(".")
        if not body:
            logging.warning("Empty chunk body in %s — skipping", file_path.name)
            continue
        parsed.append({"text": body, "category": category, "risk_tier": risk_tier})
    return parsed


def load_all_chunks() -> list[dict]:
    chunks = []
    for txt_file in sorted(CHUNKS_DIR.glob("*.txt")):
        file_chunks = parse_chunks(txt_file)
        logging.info("  %s: %d chunks", txt_file.name, len(file_chunks))
        chunks.extend(file_chunks)
    return chunks


def build() -> None:
    qdrant_host = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
    logging.info("Connecting to Qdrant at %s:%d...", qdrant_host, qdrant_port)
    client      = QdrantClient(host=qdrant_host, port=qdrant_port)
    dense_model = SentenceTransformer("all-MiniLM-L6-v2")

    chunks = load_all_chunks()
    logging.info("Total chunks: %d", len(chunks))

    if client.collection_exists(COLLECTION):
        client.delete_collection(COLLECTION)
        logging.info("Deleted existing collection '%s'", COLLECTION)

    client.create_collection(
        collection_name=COLLECTION,
        vectors_config={"dense": VectorParams(size=384, distance=Distance.COSINE)},
        sparse_vectors_config={"sparse": SparseVectorParams()},
    )
    logging.info("Created collection '%s'", COLLECTION)

    all_texts = [c["text"] for c in chunks]
    tfidf = TfidfVectorizer(max_features=10000)
    tfidf.fit(all_texts)

    for i, chunk in enumerate(chunks):
        dense_vec = dense_model.encode(chunk["text"]).tolist()
        sp        = tfidf.transform([chunk["text"]])
        client.upsert(
            collection_name=COLLECTION,
            points=[PointStruct(
                id=i,
                vector={
                    "dense":  dense_vec,
                    "sparse": SparseVector(
                        indices=sp.indices.tolist(),
                        values=sp.data.tolist(),
                    ),
                },
                payload={
                    "text":            chunk["text"],
                    "category":        chunk["category"],
                    "risk_tier":       chunk["risk_tier"],
                    "embedding_model": "all-MiniLM-L6-v2",
                    "indexed_at":      datetime.datetime.now(datetime.timezone.utc).isoformat(),
                },
            )],
        )

    EXPORTS.mkdir(parents=True, exist_ok=True)
    with open(EXPORTS / "tfidf_vectorizer.pkl", "wb") as f:
        pickle.dump(tfidf, f)

    logging.info("Done. %d chunks indexed.", len(chunks))
    logging.info("TF-IDF saved: %s/tfidf_vectorizer.pkl", EXPORTS)
    logging.info("Collection info: %s", client.get_collection(COLLECTION))


if __name__ == "__main__":
    build()
