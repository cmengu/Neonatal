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


def test_assess_blocking_infant1():
    """Blocking endpoint returns a NeonatalAlert with concern_level and latency_ms."""
    r = client.post("/assess/infant1")
    assert r.status_code == 200
    data = r.json()
    assert data["concern_level"] in ("RED", "YELLOW", "GREEN"), (
        f"Unexpected concern_level: {data['concern_level']}"
    )
    assert data["patient_id"] == "infant1"
    assert data.get("latency_ms") is not None, "latency_ms not populated by API layer"
    assert isinstance(data["latency_ms"], float)


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
        sse_data_lines = [c for c in chunks if c.startswith(b"data:")]
        assert len(sse_data_lines) > 0, (
            f"SSE generator emitted zero data: events — check _STAGE_MAP node keys match "
            f"build_multi_agent_graph() g.add_node() names. Got lines: {chunks[:5]}"
        )
