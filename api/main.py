"""NeonatalGuard FastAPI — production API layer.

Endpoints:
    POST /assess/{patient_id}            — blocking multi-agent alert (populates latency_ms)
    GET  /assess/{patient_id}/stream     — SSE streaming per-specialist progress
    GET  /patient/{patient_id}/history   — last N alerts from SQLite audit.db
    POST /assess/{patient_id}/generalist — generalist agent for A/B comparison
    GET  /health                         — FIX-12 distribution + FIX-13 chunk count

Startup: preloads ClinicalKnowledgeBase singleton before first request.
Latency: timed in API layer; populated in NeonatalAlert.latency_ms before response.
LangSmith: all graph nodes are @traceable — no additional instrumentation needed.
EVAL_NO_LLM: set to '1' for CI/test mode (no Groq calls, no API key required).
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.agent.graph import _get_kb, agent, multi_agent
from src.agent.schemas import NeonatalAlert

DB_PATH = REPO_ROOT / "data" / "audit.db"

# FIX-13: Expected KB chunk count. Update if KB is rebuilt with more chunks.
# Verified in pre-flight: python -c "from src.knowledge.knowledge_base import
# ClinicalKnowledgeBase; kb=ClinicalKnowledgeBase(path='qdrant_local');
# print(kb.client.count('clinical_knowledge').count)"
EXPECTED_CHUNK_COUNT = 34


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-load KB singleton on startup — warms SentenceTransformer + Qdrant connection."""
    try:
        _get_kb()
        logging.info("KB singleton loaded successfully at startup.")
    except Exception as exc:
        # App starts even if KB unavailable — health endpoint will surface the error.
        logging.warning("KB init failed at startup (health endpoint will report): %s", exc)
    yield


app = FastAPI(
    title="NeonatalGuard API",
    description="Multi-agent neonatal sepsis early-warning system",
    version="2.0",
    lifespan=lifespan,
)


# ─────────────────────────── helpers ────────────────────────────

def _invoke_blocking(graph, patient_id: str) -> NeonatalAlert:
    """Invoke a LangGraph agent synchronously and populate latency_ms."""
    t0 = time.perf_counter()
    state = graph.invoke({"patient_id": patient_id})
    latency_ms = (time.perf_counter() - t0) * 1000.0
    alert = state.get("final_alert")
    if alert is None:
        raise HTTPException(status_code=500, detail="Agent did not produce a final alert")
    return alert.model_copy(update={"latency_ms": latency_ms})


# Graph node key → SSE stage label.
# Keys MUST match g.add_node() registration names in supervisor.py, NOT @traceable names.
# supervisor.py: g.add_node("supervisor", ...), g.add_node("signal", ...), etc.
# astream_events(version="v2") emits event["name"] = graph key, not @traceable(name=...).
_STAGE_MAP: dict[str, str] = {
    "supervisor": "pipeline",
    "signal": "signal",
    "brady": "bradycardia",
    "clinical": "reasoning",
    "protocol": "reasoning",
    "assemble_multi": "complete",
}


async def _sse_generator(patient_id: str):
    """Async generator of SSE payloads, one per node start/end event."""
    async for event in multi_agent.astream_events(
        {"patient_id": patient_id}, version="v2"
    ):
        ev_type = event.get("event", "")
        name = event.get("name", "")
        stage = _STAGE_MAP.get(name)
        if stage is None:
            continue

        if ev_type == "on_chain_start":
            yield f"data: {json.dumps({'stage': stage, 'status': 'running'})}\n\n"

        elif ev_type == "on_chain_end":
            output = event.get("data", {}).get("output", {})
            payload: dict = {"stage": stage, "status": "done"}

            if name == "supervisor":
                pr = output.get("pipeline_result")
                if pr:
                    payload["risk_score"] = pr.risk_score
                    payload["risk_level"] = pr.risk_level

            elif name == "signal":
                sa = output.get("signal_assessment")
                if sa:
                    payload["pattern"] = sa.autonomic_pattern
                    payload["confidence"] = sa.confidence

            elif name == "brady":
                ba = output.get("bradycardia_assessment")
                if ba:
                    payload["classification"] = ba.classification

            elif name == "assemble_multi":
                alert = output.get("final_alert")
                if alert:
                    payload["stage"] = "complete"
                    payload["alert"] = alert.model_dump(mode="json")

            yield f"data: {json.dumps(payload, default=str)}\n\n"


# ─────────────────────────── endpoints ──────────────────────────

@app.post("/assess/{patient_id}", response_model=NeonatalAlert)
def assess(patient_id: str) -> NeonatalAlert:
    """Blocking multi-agent assessment. Returns full NeonatalAlert JSON."""
    return _invoke_blocking(multi_agent, patient_id)


@app.post("/assess/{patient_id}/generalist", response_model=NeonatalAlert)
def assess_generalist(patient_id: str) -> NeonatalAlert:
    """Blocking generalist assessment for A/B comparison with multi-agent."""
    return _invoke_blocking(agent, patient_id)


@app.get("/assess/{patient_id}/stream")
async def assess_stream(patient_id: str) -> StreamingResponse:
    """SSE streaming assessment — emits one event per specialist node start and end."""
    return StreamingResponse(
        _sse_generator(patient_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable nginx proxy buffering
        },
    )


@app.get("/patient/{patient_id}/history")
def patient_history(patient_id: str, n: int = 10) -> list[dict]:
    """Return the last N alerts for a patient from SQLite alert_history."""
    if not DB_PATH.exists():
        return []
    try:
        with sqlite3.connect(str(DB_PATH)) as conn:
            rows = conn.execute(
                """
                SELECT timestamp, concern_level, risk_score,
                       top_feature, top_z_score,
                       signal_pattern, brady_classification, agent_version
                FROM alert_history
                WHERE patient_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (patient_id, n),
            ).fetchall()
        cols = [
            "timestamp",
            "concern_level",
            "risk_score",
            "top_feature",
            "top_z_score",
            "signal_pattern",
            "brady_classification",
            "agent_version",
        ]
        return [dict(zip(cols, row)) for row in rows]
    except sqlite3.Error as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc


@app.get("/health")
def health() -> dict:
    """System health check — FIX-12 (prediction distribution) + FIX-13 (chunk count)."""
    # FIX-13: Verify Qdrant chunk count at runtime.
    try:
        kb = _get_kb()
        doc_count = kb.client.count("clinical_knowledge").count
        qdrant_status = (
            "ok"
            if doc_count == EXPECTED_CHUNK_COUNT
            else f"wrong_chunk_count_{doc_count}_expected_{EXPECTED_CHUNK_COUNT}"
        )
    except Exception as exc:
        doc_count = 0
        qdrant_status = f"error: {exc}"

    # FIX-12: Prediction distribution from last 100 alerts.
    try:
        with sqlite3.connect(str(DB_PATH)) as conn:
            rows = conn.execute(
                """
                SELECT concern_level, COUNT(*) as n
                FROM (
                    SELECT concern_level FROM alert_history
                    ORDER BY timestamp DESC LIMIT 100
                )
                GROUP BY concern_level
                """
            ).fetchall()
        dist = {row[0]: row[1] for row in rows}
        total = sum(dist.values())
        red_rate = dist.get("RED", 0) / max(total, 1)
        green_rate = dist.get("GREEN", 0) / max(total, 1)
        if green_rate > 0.95:
            prediction_health = "suppressed_alerts_possible"
        elif red_rate > 0.20:
            prediction_health = "elevated_red_rate"
        else:
            prediction_health = "ok"
    except Exception:
        dist = {}
        prediction_health = "unknown"

    return {
        "status": "ok",
        "qdrant": qdrant_status,
        "knowledge_base_docs": doc_count,
        "prediction_distribution_last_100": dist,
        "prediction_health": prediction_health,
        "schema_version": "2.0",
        "retrieval": "hybrid_dense_sparse_rrf_reranked",
        "guardrails": "instructor_pydantic_v2",
        "episodic_memory": "sqlite_v2.0",
    }
