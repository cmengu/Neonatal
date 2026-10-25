"""API integration tests — runs with EVAL_NO_LLM=1 and local Qdrant file-based.

EVAL_NO_LLM=1 must be set BEFORE importing api.main — all graph nodes check
this env var at call time, not at import time.

Run:
    EVAL_NO_LLM=1 QDRANT_PATH=qdrant_local pytest tests/test_api.py -v
"""
import os

# Must be set before any import that triggers src.agent.graph module loading.
os.environ["EVAL_NO_LLM"] = "1"
os.environ["QDRANT_PATH"] = "qdrant_local"

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health_returns_ok():
    """Health endpoint returns status=ok and includes qdrant + distribution fields."""
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "qdrant" in data
    assert "knowledge_base_docs" in data
    assert "prediction_distribution_last_100" in data
    assert "prediction_health" in data


def test_assess_routes_through_cascade(monkeypatch):
    """POST /assess now returns the full Verdict Cascade result behind the Safety Floor (#25):
    a Verdict with the tier trail, the effective floor, and — post-#23 — the traceable detail
    (recommended_action / primary_indicators / citations) the bare graph used to be bypassed for.

    The cascade is patched onto an in-memory CUSUM store so the test never mutates the real
    audit.db drift state (production still uses the persisted SqliteCusumStore)."""
    import api.main as main_mod
    from src.assessment.context import load_context
    from src.assessment.cusum import InMemoryCusumStore
    from src.assessment.runtime import default_cascade

    def _hermetic_assess(pid: str):
        return default_cascade(cusum_store=InMemoryCusumStore()).assess(load_context(pid))

    monkeypatch.setattr(main_mod, "assess_patient", _hermetic_assess)

    r = client.post("/assess/infant1")
    assert r.status_code == 200
    data = r.json()
    # Verdict shape — level (not concern_level), the floor, and the tier trail.
    assert data["level"] in ("RED", "YELLOW", "GREEN")
    assert data["patient_id"] == "infant1"
    assert data["safety_floor"] in ("RED", "YELLOW", "GREEN")
    assert len(data["assessments"]) >= 1
    assert data["assessments"][0]["source"] == "deviation"
    # The verdict is never below the floor (the FNR=0 guarantee applied in production).
    order = {"GREEN": 0, "YELLOW": 1, "RED": 2}
    assert order[data["level"]] >= order[data["safety_floor"]]
    # Post-#23 traceable detail is present on the Verdict (keys always serialised).
    assert "recommended_action" in data
    assert "primary_indicators" in data
    assert "citations" in data


def test_assess_unknown_patient_returns_404():
    """A patient with no processed CSVs yields 404, not a 500."""
    r = client.post("/assess/PATIENT_THAT_DOES_NOT_EXIST_XYZ")
    assert r.status_code == 404


def test_assess_generalist_returns_concern_level():
    """Generalist endpoint returns a valid concern_level."""
    r = client.post("/assess/infant1/generalist")
    assert r.status_code == 200
    data = r.json()
    assert "concern_level" in data
    assert data["concern_level"] in ("RED", "YELLOW", "GREEN")


def test_history_empty_for_unknown_patient():
    """History endpoint returns [] for a patient with no alert history."""
    r = client.get("/patient/PATIENT_THAT_DOES_NOT_EXIST_XYZ/history")
    assert r.status_code == 200
    assert r.json() == []


def test_stream_returns_event_stream_content_type():
    """Streaming endpoint returns text/event-stream, 200, and emits at least one SSE event."""
    with client.stream("GET", "/assess/infant1/stream") as r:
        assert r.status_code == 200
        assert "text/event-stream" in r.headers.get("content-type", ""), (
            f"Expected text/event-stream, got: {r.headers.get('content-type')}"
        )
        # Consume at least one chunk to verify the SSE generator actually emits events.
        # A broken _STAGE_MAP (wrong node key names) would produce zero events here.
        chunks = list(r.iter_lines())
        sse_data_lines = [c for c in chunks if c.startswith("data:")]
        assert len(sse_data_lines) > 0, (
            f"SSE generator emitted zero data: events — check _STAGE_MAP node keys match "
            f"build_multi_agent_graph() g.add_node() names. Got lines: {chunks[:5]}"
        )
