"""Guideline source registry + grounding gates for the Tier 3 RAG corpus (#5).

The research gate ``docs/research/rag-guideline-grounding-neonatal-sepsis.md`` requires
every clinical claim Tier 3 retrieves to be traceable to a cited source, and forbids the
un-grounded content the audit flagged (the ``pre-sepsis`` label, invented monitoring
cadences, and fabricated performance numbers). This module is the machine-checkable
backbone of those gates:

- ``SOURCE_REGISTRY`` — the only source IDs a corpus chunk may cite.
- ``chunk_source_ids`` / ``is_traceable`` — resolve a chunk's in-band ``[Source: …]`` tag.
- ``load_corpus_chunks`` — parse the corpus the same way ``build_knowledge_base`` does.
- ``FORBIDDEN_CORPUS_PATTERNS`` — content that must not appear in the corpus.
- ``ACTION_SOURCE_MAP`` — every ``APPROVED_ACTIONS`` item mapped to its grounding source.

Chunks tag their source *in-band* (a leading ``[Source: NICE-NG195]``) rather than in the
trailing ``Category:/Risk tier:`` metadata line, because ``build_knowledge_base.parse_chunks``
strips that metadata line out of the indexed body — so an in-band tag is the only way the
provenance survives into the retrieved text a clinician (and this gate) actually sees.
"""
from __future__ import annotations

import re
from pathlib import Path

CLINICAL_TEXTS_DIR = Path(__file__).resolve().parent / "clinical_texts"

#: The closed set of sources a corpus chunk may cite. See the research asset's reference list.
SOURCE_REGISTRY: dict[str, str] = {
    "NICE-NG195": "NICE NG195 — Neonatal infection: antibiotics for prevention and treatment "
                  "(2021, updated 2026).",
    "AAP-PRETERM-2018": "AAP/COFN — Management of Neonates Born at <=34 6/7 wk With Suspected or "
                        "Proven Early-Onset Sepsis (Puopolo et al. 2018, PMID 30455344).",
    "AAP-TERM-2018": "AAP/COFN — Management of Neonates Born at >=35 0/7 wk With Suspected or "
                     "Proven Early-Onset Sepsis (Puopolo et al. 2018, PMID 30455342).",
    "HERO-GM-2001": "Griffin & Moorman 2001 — abnormal heart-rate characteristics precede "
                    "neonatal sepsis (PMID 11134441).",
    "HERO-FAIRCHILD-2010": "Fairchild & O'Shea 2010 — HeRO monitoring; abnormal HRC as an "
                           "adjunct risk trend (PMID 20813272).",
    "NG-METHOD": "NeonatalGuard personalised-baseline methodology "
                 "(docs/research/detection-methodology.md; clinical-evidence-hrv-sepsis.md).",
}

_SOURCE_TAG_RE = re.compile(r"\[Source:\s*([^\]]+)\]", re.IGNORECASE)


def chunk_source_ids(text: str) -> list[str]:
    """Extract the source IDs from a chunk's in-band ``[Source: A; B]`` tag(s)."""
    ids: list[str] = []
    for match in _SOURCE_TAG_RE.findall(text):
        ids += [part.strip() for part in re.split(r"[;,]", match) if part.strip()]
    return ids


def is_traceable(text: str) -> bool:
    """True iff the chunk carries at least one source ID and every ID is in the registry."""
    ids = chunk_source_ids(text)
    return bool(ids) and all(i in SOURCE_REGISTRY for i in ids)


def traceable_context(chunks: list[str]) -> list[str]:
    """Keep only chunks that resolve to a cited source — the runtime traceability gate.

    An alert never cites a chunk with no resolvable source (research asset §4.3).
    """
    return [c for c in chunks if is_traceable(c)]


def load_corpus_chunks() -> list[dict]:
    """Parse every clinical_texts/*.txt into chunk bodies, matching build_knowledge_base.

    Returns dicts of ``{"file", "body"}`` where ``body`` is exactly the text indexed into
    Qdrant (the trailing ``Category:/Risk tier:`` metadata line removed).
    """
    chunks: list[dict] = []
    for txt in sorted(CLINICAL_TEXTS_DIR.glob("*.txt")):
        raw = [c.strip() for c in txt.read_text().split("\n\n") if c.strip()]
        for chunk in raw:
            lines = chunk.split("\n")
            meta_line = lines[-1] if "Category:" in lines[-1] else ""
            body = chunk.replace(meta_line, "").strip() if meta_line else chunk
            if body:
                chunks.append({"file": txt.name, "body": body})
    return chunks


#: Content the corpus audit ruled un-grounded: (regex, why). The lint fails if any appears.
FORBIDDEN_CORPUS_PATTERNS: list[tuple[str, str]] = [
    (r"pre[-_ ]?sepsis", "the un-grounded 'pre-sepsis' label — rename to abnormal-HRC / increased risk"),
    (r"reassess in 2 hours", "invented 2-hour reassessment cadence (no guideline source)"),
    (r"every 15 minutes", "invented 15-minute monitoring cadence (no guideline source)"),
    (r"within 1 hour", "invented 1-hour blood-culture cadence (no guideline source)"),
    (r"0\.71", "fabricated PPV 0.71 (unverifiable on unlabelled data)"),
    (r"\b78%", "fabricated sensitivity 78%"),
    (r"\b82%", "fabricated specificity 82%"),
    (r"exceeds 60%|60% in infants", "fabricated '>60% probability' figure"),
]


def scan_forbidden(text: str) -> list[str]:
    """Return the 'why' of every forbidden pattern present in ``text`` (empty = clean)."""
    return [
        why for pattern, why in FORBIDDEN_CORPUS_PATTERNS
        if re.search(pattern, text, re.IGNORECASE)
    ]


#: Every APPROVED_ACTIONS item → the guideline source(s) that ground it (research §2).
ACTION_SOURCE_MAP: dict[str, list[str]] = {
    "Immediate clinical review": ["NICE-NG195", "AAP-TERM-2018"],
    "Blood culture and CBC with differential": ["AAP-PRETERM-2018", "AAP-TERM-2018", "NICE-NG195"],
    "Temperature and perfusion monitoring": ["NICE-NG195"],
    "Continue routine monitoring": ["NICE-NG195"],
    "Continue observation on a newborn early-warning system": ["NICE-NG195"],
    "Notify attending neonatologist": ["NICE-NG195", "AAP-TERM-2018"],
    "Increase monitoring frequency": ["NICE-NG195"],
    "Respiratory support assessment": ["NICE-NG195"],
}
