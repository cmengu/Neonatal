"""RAG retrieval eval for NeonatalGuard clinical knowledge base.

Measures MRR@3 for vector-only vs hybrid+rerank retrieval.
25 ground-truth (query, expected_keyword) pairs covering all 5 clinical text categories.
A query "hits" at rank k if the expected_keyword is a substring of the k-th retrieved chunk.

Run from repo root:
  QDRANT_PATH=qdrant_local python eval/eval_retrieval.py
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.knowledge.knowledge_base import ClinicalKnowledgeBase

# 25 (query, expected_keyword) ground-truth pairs.
# expected_keyword is a verbatim substring of the target chunk.
# Queries 6, 9, 14, 17, 25 are NUMERIC — contain exact values from chunk text
# to test BM25/TF-IDF keyword-matching advantage over pure vector search.
GROUND_TRUTH: list[tuple[str, str]] = [
    # hrv_indicators (5)
    ("RMSSD normal range premature neonates under 30 weeks",
     "6-8ms at baseline"),                                                        # hrv_indicators chunk 1
    ("LF/HF ratio normal premature neonate sympathetic parasympathetic",
     "1.2 to 1.8"),                                                               # hrv_indicators chunk 3
    ("SDNN declining trend hours physiological deterioration",
     "8-12 hours"),                                                               # hrv_indicators chunk 2
    ("pNN50 percentage 50ms consecutive RR intervals neonates",
     "under 2%"),                                                                 # hrv_indicators chunk 4
    ("RMSSD suppression pre-bradycardia pre-sepsis HRV signature",
     "pre-bradycardia and pre-sepsis"),                                           # hrv_indicators chunk 1
    # sepsis_early_warning (5)
    ("three concurrent HRV changes 12-24 hours before clinical sepsis",          # NUMERIC
     "three concurrent changes"),                                                 # sepsis_early_warning chunk 1
    ("RMSSD z-score -2.5 LF/HF z-score +2.0 simultaneously blood culture",
     "blood culture"),                                                            # sepsis_early_warning chunk 2
    ("recurrent bradycardia HRV suppression three events 6 hours immediate",
     "Three or more bradycardia events in a 6-hour window"),                     # sepsis_early_warning chunk 3
    ("CRP elevation lag 12-18 hours HRV changes early sepsis",                   # NUMERIC
     "CRP elevation lags"),                                                       # sepsis_early_warning chunk 4
    ("temperature instability absent hypothermia sepsis preterm 32 weeks",
     "Temperature instability may be absent"),                                    # sepsis_early_warning chunk 4
    # bradycardia_patterns (5)
    ("isolated bradycardia vagal reflex routine monitoring RMSSD stable",
     "normal vagal reflex"),                                                      # bradycardia_patterns chunk 1
    ("bradycardia cluster three episodes 60 minutes physician assessment",
     "three or more episodes within 60 minutes"),                                # bradycardia_patterns chunk 2
    ("bradycardia HRV suppression RMSSD below -2.0 immediate evaluation NEC",
     "necrotising enterocolitis"),                                                # bradycardia_patterns chunk 3
    ("bradycardia frequency doubling 4-hour blocks escalation early indicator",  # NUMERIC
     "doubling pattern"),                                                         # bradycardia_patterns chunk 5
    ("post-feeding bradycardia enteral feed vagal response gut distension",
     "vagal response to gut distension"),                                         # bradycardia_patterns chunk 6
    # intervention_thresholds (5)
    ("immediate clinical review RMSSD -2.5 LF/HF +2.5 two brady positive predictive",
     "positive predictive value of approximately 0.71"),                         # intervention_thresholds chunk 1
    ("reassess 2 hours single feature z-score deviation -2.0 -2.5",             # NUMERIC
     "Single-feature mild deviations"),                                           # intervention_thresholds chunk 2
    ("routine monitoring all HRV z-scores 1.5 standard deviations stable",
     "1.5 standard deviations"),                                                 # intervention_thresholds chunk 3
    ("increase monitoring frequency every 15 minutes directional trend",
     "every 15 minutes"),                                                         # intervention_thresholds chunk 4
    ("blood culture CBC differential 1 hour sepsis neonatal ICU",
     "Blood culture and CBC"),                                                    # intervention_thresholds chunk 1
    # baseline_interpretation (5)
    ("personalised baseline 30-40 percent infants outside population mean",
     "30-40%"),                                                                   # baseline_interpretation chunk 1
    ("LOOKBACK 10 windows burn-in period stable HRV z-score computation",
     "LOOKBACK=10"),                                                              # baseline_interpretation chunk 2
    ("26 weeks neonate RMSSD SDNN LF/HF gestational age baseline ranges",        # NUMERIC
     "26-week neonate"),                                                          # baseline_interpretation chunk 4
    ("standard deviation zero rolling baseline divide by zero guard",
     "dividing by zero"),                                                         # baseline_interpretation chunk 7
    ("RMSSD 6ms 8ms SDNN 10ms baseline neonates under 30 weeks gestation",       # NUMERIC
     "6-8ms at baseline"),                                                        # hrv_indicators chunk 1 — numeric match
]

assert len(GROUND_TRUTH) == 25, f"Expected 25 pairs, got {len(GROUND_TRUTH)}"


def mrr_at_k(retrieved: list[str], keyword: str, k: int = 3) -> float:
    """Return 1/rank of first hit (keyword appears in chunk), or 0 if not found in top k."""
    for rank, chunk in enumerate(retrieved[:k], start=1):
        if keyword.lower() in chunk.lower():
            return 1.0 / rank
    return 0.0


def run_retrieval_eval(kb_path: str) -> dict:
    kb = ClinicalKnowledgeBase(path=kb_path)

    mrr_vector_scores:  list[float] = []
    mrr_hybrid_scores:  list[float] = []
    recall_vector:      list[int]   = []
    recall_hybrid:      list[int]   = []

    for query, keyword in GROUND_TRUTH:
        vec_results    = kb.query_vector_only(query, n=3)
        hybrid_results = kb.query(query, n=3)

        v_score = mrr_at_k(vec_results,    keyword)
        h_score = mrr_at_k(hybrid_results, keyword)

        mrr_vector_scores.append(v_score)
        mrr_hybrid_scores.append(h_score)
        recall_vector.append(1 if v_score > 0 else 0)
        recall_hybrid.append(1 if h_score > 0 else 0)

        hit_v = "✓" if v_score > 0 else "✗"
        hit_h = "✓" if h_score > 0 else "✗"
        print(f"  [{hit_v}vec {hit_h}hyb] {query[:55]:<55}  kw={keyword[:25]!r}")

    n = len(GROUND_TRUTH)
    mrr_v  = sum(mrr_vector_scores) / n
    mrr_h  = sum(mrr_hybrid_scores) / n
    rec_v  = sum(recall_vector)      / n
    rec_h  = sum(recall_hybrid)      / n

    return {
        "n_queries":          n,
        "mrr_vector":         mrr_v,
        "mrr_hybrid":         mrr_h,
        "mrr_delta":          mrr_h - mrr_v,
        "recall_at3_vector":  rec_v,
        "recall_at3_hybrid":  rec_h,
    }


def main() -> None:
    import os
    kb_path = os.getenv("QDRANT_PATH", str(REPO_ROOT / "qdrant_local"))
    print(f"\nRAG Retrieval Eval — 25 queries — Qdrant: {kb_path}")
    print("-" * 70)

    results = run_retrieval_eval(kb_path)

    print("-" * 70)
    print(f"MRR@3  vector-only:   {results['mrr_vector']:.3f}")
    print(f"MRR@3  hybrid+rerank: {results['mrr_hybrid']:.3f}")
    delta = results['mrr_delta']
    sign = "+" if delta >= 0 else ""
    print(f"Delta:                {sign}{delta:.3f}")
    print(f"Recall@3 vector:      {results['recall_at3_vector'] * 100:.1f}%")
    print(f"Recall@3 hybrid:      {results['recall_at3_hybrid'] * 100:.1f}%")

    out_path = REPO_ROOT / "results" / "eval_retrieval.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults → {out_path}")


if __name__ == "__main__":
    main()
