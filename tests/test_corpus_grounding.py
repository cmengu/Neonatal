"""Grounding CI gates for the Tier 3 RAG corpus (#5).

Three gates from docs/research/rag-guideline-grounding-neonatal-sepsis.md §4, all
pure-Python over the corpus files + schema (no Qdrant / no LLM):

1. Corpus-lint     — every chunk carries a resolvable [Source: …] tag; no forbidden content.
2. Traceability    — the runtime gate that keeps only guideline-sourced chunks in an alert.
3. Action→source   — every APPROVED_ACTIONS item maps to a valid guideline source.
"""
import pytest

from src.agent.schemas import APPROVED_ACTIONS
from src.knowledge.sources import (
    ACTION_SOURCE_MAP,
    SOURCE_REGISTRY,
    chunk_source_ids,
    is_traceable,
    load_corpus_chunks,
    scan_forbidden,
    traceable_context,
)

CORPUS = load_corpus_chunks()


# --- Gate 1: corpus-lint --------------------------------------------------------


def test_corpus_is_non_empty():
    assert len(CORPUS) >= 20  # 5 files, several chunks each


@pytest.mark.parametrize("chunk", CORPUS, ids=lambda c: f"{c['file']}:{c['body'][:30]}")
def test_every_chunk_has_a_resolvable_source_tag(chunk):
    ids = chunk_source_ids(chunk["body"])
    assert ids, f"chunk in {chunk['file']} has no [Source: …] tag: {chunk['body'][:60]}"
    unknown = [i for i in ids if i not in SOURCE_REGISTRY]
    assert not unknown, f"chunk in {chunk['file']} cites unknown source(s) {unknown}"


@pytest.mark.parametrize("chunk", CORPUS, ids=lambda c: f"{c['file']}:{c['body'][:30]}")
def test_no_chunk_contains_forbidden_content(chunk):
    violations = scan_forbidden(chunk["body"])
    assert not violations, f"chunk in {chunk['file']} contains un-grounded content: {violations}"


# --- Gate 2: retrieval traceability --------------------------------------------


def test_every_corpus_chunk_is_traceable():
    assert all(is_traceable(c["body"]) for c in CORPUS)


def test_is_traceable_rejects_untagged_and_unknown():
    assert is_traceable("A clinical claim with no source tag.") is False
    assert is_traceable("[Source: MADE-UP-GUIDELINE] bogus.") is False
    assert is_traceable("[Source: NICE-NG195] apnoea is a red flag.") is True


def test_traceable_context_drops_unsourced_chunks():
    good = "[Source: HERO-GM-2001] reduced RMSSD is an adjunct risk trend."
    bad = "Free-form LLM claim with no citation."
    assert traceable_context([good, bad]) == [good]


# --- Gate 3: action → source map -----------------------------------------------


def test_action_source_map_covers_exactly_approved_actions():
    assert set(ACTION_SOURCE_MAP) == set(APPROVED_ACTIONS)


@pytest.mark.parametrize("action", APPROVED_ACTIONS)
def test_every_approved_action_maps_to_valid_sources(action):
    sources = ACTION_SOURCE_MAP.get(action)
    assert sources, f"{action!r} has no guideline source mapping"
    unknown = [s for s in sources if s not in SOURCE_REGISTRY]
    assert not unknown, f"{action!r} maps to unknown source(s) {unknown}"
