# Phase 7 Execution Plan — FastAPI + Docker + LangSmith + Monitoring

**Overall Progress:** `100% (6/6 steps done)`

---

## TLDR

Phase 7 wraps the Phase 5 multi-agent graph in a production FastAPI layer with blocking and SSE-streaming endpoints, containerises the system with Docker Compose (4 services), and adds FIX-12 (prediction distribution monitoring) and FIX-13 (chunk count verification) to the health endpoint. LangSmith tracing is already fully wired via existing `@traceable` decorators — no new instrumentation is needed. After this plan: `docker compose up` starts everything; `POST /assess/{patient_id}` returns a `NeonatalAlert`; `GET /assess/{patient_id}/stream` streams per-specialist progress as SSE events; the health endpoint flags silent prediction failures.

---

## Critical Decisions

- **SSE via `StreamingResponse` + `astream_events(v2)`** — No new dependency (`sse-starlette` excluded). FastAPI's `StreamingResponse` with `media_type="text/event-stream"` handles SSE natively. `multi_agent.astream_events(version="v2")` emits `on_chain_start`/`on_chain_end` events per node.
- **Sync `def` for blocking endpoints** — FastAPI runs sync route functions in a thread pool, avoiding event-loop blocking from `multi_agent.invoke()`. SSE endpoint is `async def` (needs `astream_events` async generator).
- **Empty `QDRANT_PATH` triggers networked Qdrant** — Docker API service sets `QDRANT_PATH=` (empty string). `ClinicalKnowledgeBase.__init__` already handles `path=""` via `if path:` (falsy), so networked mode works today. Step 7.1 replaces the implicit one-liner with an explicit three-way branch to make the contract readable and prevent future regressions from default-value changes.
- **`latency_ms` populated in API layer** — `NeonatalAlert.latency_ms` is optional and not populated by the graph. The API times `invoke()` and returns `alert.model_copy(update={"latency_ms": latency_ms})`.
- **All tests use `EVAL_NO_LLM=1`** — Groq API is exhausted. `os.environ["EVAL_NO_LLM"] = "1"` must be set **before** importing `api.main`.
- **`EXPECTED_CHUNK_COUNT = 34`** — Verified in pre-flight. Hardcoded in health endpoint per FIX-13.

---

## Clarification Gate

| Unknown | Required | Source | Blocking | Resolved |
|---------|----------|--------|----------|----------|
| Groq API availability | Exhausted — EVAL_NO_LLM=1 for all tests | Human (stated) | Step 7.5 | ✅ |
| `astream_events` version support | Requires LangGraph ≥ 0.2 | Pre-flight check | Step 7.2 | ✅ verify in pre-flight |
| EXPECTED_CHUNK_COUNT | Verify actual count against 34 | Pre-flight `kb.client.count(...)` | Step 7.2 | ✅ verify in pre-flight |
| Docker Qdrant KB population | `pre_flight.sh` must run `write_chunks.py` against Docker Qdrant | Codebase (`scripts/write_chunks.py` exists) | Step 7.6 | ✅ |

---

## Agent Failure Protocol

1. A verification command fails → read the full error output.
2. Cause is unambiguous → make ONE targeted fix → re-run the same verification command.
3. If still failing after one fix → **STOP**. Output full contents of every file modified in this step. Report: (a) command run, (b) full error verbatim, (c) fix attempted, (d) current state of each modified file, (e) why you cannot proceed.
4. Never attempt a second fix without human instruction.
5. Never modify files not named in the current step.

---

## Pre-Flight — Run Before Any Code Changes

```bash
# 1. Confirm api/main.py does not exist
ls api/main.py 2>&1
# Expect: No such file

# 2. Confirm _get_kb() uses os.getenv with default (the bug to fix)
grep -n "QDRANT_PATH" src/agent/graph.py
# Expect: line showing os.getenv("QDRANT_PATH", str(REPO_ROOT / "qdrant_local"))

# 3. Verify EXPECTED_CHUNK_COUNT
python -c "
from src.knowledge.knowledge_base import ClinicalKnowledgeBase
kb = ClinicalKnowledgeBase(path='qdrant_local')
count = kb.client.count('clinical_knowledge').count
print(f'Chunk count: {count}')
"
# Expect: 34. If different — update EXPECTED_CHUNK_COUNT in Step 7.2.

# 4. Verify astream_events available on installed LangGraph
python -c "
from src.agent.graph import multi_agent
assert hasattr(multi_agent, 'astream_events'), 'astream_events not available — upgrade langgraph'
print('astream_events: OK')
"

# 5. Confirm fastapi and uvicorn are installed (already in requirements.txt under "# API")
python -c "import fastapi, uvicorn; print('fastapi+uvicorn: OK')"
# Expect: fastapi+uvicorn: OK
# If fails: run `pip install -r requirements.txt` — they are listed under "# API" in requirements.txt.

# 6. Confirm data/processed/infant1_rr_clean.csv exists (needed for API tests)
ls data/processed/infant1_rr_clean.csv
# Expect: file exists

# 7. CI baseline still passes
EVAL_NO_LLM=1 QDRANT_PATH=qdrant_local python eval/eval_agent.py \
    --agent multi_agent 2>&1 | tail -2
# Expect: All CI gates passed.

# 8. Record test count
python -m pytest tests/test_dependency_apis.py tests/test_qdrant_parity.py \
    --ignore=tests/test_api.py -v --tb=short 2>&1 | tail -3
# Record: __ passed
```

**Baseline Snapshot (agent fills during pre-flight):**
```
api/main.py:            ____  (expect: does not exist)
_get_kb() anchor:       ____  (expect: line with os.getenv("QDRANT_PATH", str(...)))
chunk count:            ____  (expect: 34)
astream_events:         ____  (expect: OK)
fastapi+uvicorn:        ____  (expect: OK — if FAIL, add both to requirements.txt before Step 7.2)
infant1_rr_clean.csv:   ____  (expect: exists)
CI gate:                ____  (expect: All CI gates passed.)
test count:             ____
```

---

## Steps Analysis

```
Step 7.1 (_get_kb fix)           — Non-critical (defensive clarity; current empty-string path already works via ClinicalKnowledgeBase `if path:`; one consumer of _get_kb) — full code review — Idempotent: Yes
Step 7.2 (api/main.py)           — Critical (main deliverable; all endpoints depend on it)          — full code review — Idempotent: Yes (new file)
Step 7.3 (Dockerfile)            — Non-critical (new files; no existing code changed)               — verification only — Idempotent: Yes
Step 7.4 (docker-compose.yml)    — Non-critical (replaces existing 13-line file)                   — verification only — Idempotent: Yes
Step 7.5 (tests/test_api.py)     — Non-critical (new file; no existing code changed)               — verification only — Idempotent: Yes
Step 7.6 (.env.example + script) — Non-critical (new files; documentation + ops)                   — verification only — Idempotent: Yes
```

---

## Environment Matrix

| Step | Local (no Docker) | Docker | CI | Notes |
|------|-------------------|--------|----|-------|
| Step 7.1 | ✅ | ✅ | ✅ | Needed for Docker; harmless locally |
| Step 7.2 | ✅ | ✅ | ✅ | EVAL_NO_LLM=1 for CI/test |
| Step 7.3 | ✅ | ✅ | ✅ | Dockerfile only used if Docker installed |
| Step 7.4 | ✅ | ✅ | ❌ Skip | Docker Compose not in CI |
| Step 7.5 | ✅ | ✅ | ✅ | EVAL_NO_LLM=1; no Docker needed |
| Step 7.6 | ✅ | ✅ | ❌ Skip | Manual Docker pre-flight only |

---

## Phase 1 — Core API

**Goal:** `api/main.py` exists with all 5 endpoints. `_get_kb()` correctly handles Docker networked mode.

---

- [ ] 🟥 **Step 7.1: Fix `_get_kb()` in `src/agent/graph.py` for Docker networked Qdrant** — *Critical: without this, Docker API always uses on-disk file path and fails inside the container*

  **Idempotent:** Yes — replacing an existing function body. If already changed, grep confirms 0 matches for the old pattern.

  **Context:** `_get_kb()` currently calls `ClinicalKnowledgeBase(path=os.getenv("QDRANT_PATH", str(REPO_ROOT / "qdrant_local")))`. `ClinicalKnowledgeBase.__init__` uses `if path:` — so `path=""` (empty string) already triggers networked mode today. This step replaces the one-liner with an explicit three-way branch (`None` → local default; `""` → networked; non-empty string → specified path) to make the intent unambiguous in Docker configs. The current behavior is technically correct for empty-string, but the fix makes the routing explicit and self-documenting, eliminating any future risk of `os.getenv` default masking an unset variable.

  **Pre-Read Gate:**
  - Run `grep -n "QDRANT_PATH" src/agent/graph.py`. Must return exactly 1 match inside `_get_kb`. Record the exact line. If 0 or 2+ → STOP.
  - Run `grep -n "def _get_kb" src/agent/graph.py`. Must return exactly 1 match.

  **Anchor Uniqueness Check:**
  - Target: `_KB = ClinicalKnowledgeBase(\n            path=os.getenv("QDRANT_PATH", str(REPO_ROOT / "qdrant_local"))\n        )` — must appear exactly once in `_get_kb()`.

  Replace this block inside `_get_kb()`:

  ```python
          _KB = ClinicalKnowledgeBase(
              path=os.getenv("QDRANT_PATH", str(REPO_ROOT / "qdrant_local"))
          )
  ```

  With:

  ```python
          _qdrant_path = os.getenv("QDRANT_PATH")
          if _qdrant_path is not None and not _qdrant_path:
              # QDRANT_PATH="" (empty string) → networked mode (QDRANT_HOST/QDRANT_PORT from env)
              _KB = ClinicalKnowledgeBase()
          else:
              # QDRANT_PATH unset → local default; QDRANT_PATH=<path> → use that path
              _KB = ClinicalKnowledgeBase(path=_qdrant_path or str(REPO_ROOT / "qdrant_local"))
  ```

  **What it does:** Makes `_get_kb()` handle three cases: unset (→ local default), non-empty string (→ specified file path), empty string (→ networked Qdrant via QDRANT_HOST/PORT). The existing `ClinicalKnowledgeBase.__init__` already handles both modes; this is purely a routing fix in the caller.

  **Why this approach:** Minimal change — only the `_get_kb()` body changes. `ClinicalKnowledgeBase` is unmodified. All existing local-dev and CI usage (where `QDRANT_PATH` is unset or `"qdrant_local"`) is unchanged.

  **Assumptions:**
  - `_get_kb()` body has exactly one `ClinicalKnowledgeBase(...)` call.
  - `ClinicalKnowledgeBase()` (no args) reads `QDRANT_HOST`/`QDRANT_PORT` from env — confirmed from `knowledge_base.py`.

  **Risks:**
  - If `QDRANT_PATH` is unset in Docker → would use local path inside container (no `qdrant_local/` there) → `FileNotFoundError`. Mitigation: docker-compose must set `QDRANT_PATH=` explicitly (Step 7.4).

  **Git Checkpoint:**
  ```bash
  git add src/agent/graph.py
  git commit -m "step 7.1: fix _get_kb() to support QDRANT_PATH=empty for Docker networked Qdrant"
  ```

  **Subtasks:**
  - [ ] 🟥 Pre-Read Gate: 1 match for QDRANT_PATH in `_get_kb`
  - [ ] 🟥 Old single-line `ClinicalKnowledgeBase(path=os.getenv(...))` replaced
  - [ ] 🟥 Verification passes

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  python -c "
  import sys, ast
  sys.path.insert(0, '.')
  src = open('src/agent/graph.py').read()
  ast.parse(src)
  assert 'os.getenv(\"QDRANT_PATH\", str(REPO_ROOT' not in src, 'Old one-liner still present'
  assert '_qdrant_path = os.getenv(\"QDRANT_PATH\")' in src, 'Fix not present'
  assert 'ClinicalKnowledgeBase()' in src, 'Networked-mode branch missing'
  print('PASS Step 7.1: _get_kb fix present, old one-liner removed')
  "
  ```

  **Pass:** `PASS Step 7.1` printed. Exit code 0.

  **Fail:**
  - `Old one-liner still present` → Edit did not land — recheck anchor uniqueness, retry.
  - `SyntaxError` → indentation error — re-read file around edit.

---

- [ ] 🟥 **Step 7.2: Create `api/__init__.py` and `api/main.py`** — *Critical: main deliverable; all endpoints live here*

  **Idempotent:** Yes — creating new files. If `api/main.py` already exists, the pre-read gate catches it.

  **Context:** No API exists yet. All five endpoints are new. The graph singletons (`agent`, `multi_agent`) are imported at module level — FastAPI reuses them for every request. The KB is preloaded in a lifespan handler. Blocking endpoints are sync `def` (FastAPI thread pool). SSE streaming endpoint is `async def` using `multi_agent.astream_events(version="v2")`.

  **Pre-Read Gate:**
  - Run `ls api/main.py 2>&1`. Must fail with "No such file". If file exists → STOP.
  - Run `python -c "from src.agent.graph import agent, multi_agent; print('OK')"`. Must print OK.
  - Run `python -c "from src.agent.schemas import NeonatalAlert; print(list(NeonatalAlert.model_fields.keys()))"`. Confirm `latency_ms` is present in the output list.

  **File — `api/__init__.py`:** Create as empty file.

  **File — `api/main.py`:**

  ```python
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
      "supervisor":    "pipeline",
      "signal":        "signal",
      "brady":         "bradycardia",
      "clinical":      "reasoning",
      "protocol":      "reasoning",
      "assemble_multi": "complete",
  }


  async def _sse_generator(patient_id: str):
      """Async generator of SSE payloads, one per node start/end event."""
      async for event in multi_agent.astream_events(
          {"patient_id": patient_id}, version="v2"
      ):
          ev_type = event.get("event", "")
          name    = event.get("name", "")
          stage   = _STAGE_MAP.get(name)
          if stage is None:
              continue

          if ev_type == "on_chain_start":
              yield f"data: {json.dumps({'stage': stage, 'status': 'running'})}\n\n"

          elif ev_type == "on_chain_end":
              output  = event.get("data", {}).get("output", {})
              payload: dict = {"stage": stage, "status": "done"}

              if name == "supervisor":
                  pr = output.get("pipeline_result")
                  if pr:
                      payload["risk_score"] = pr.risk_score
                      payload["risk_level"]  = pr.risk_level

              elif name == "signal":
                  sa = output.get("signal_assessment")
                  if sa:
                      payload["pattern"]    = sa.autonomic_pattern
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
              "X-Accel-Buffering": "no",   # disable nginx proxy buffering
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
              "timestamp", "concern_level", "risk_score",
              "top_feature", "top_z_score",
              "signal_pattern", "brady_classification", "agent_version",
          ]
          return [dict(zip(cols, row)) for row in rows]
      except sqlite3.Error as exc:
          raise HTTPException(status_code=500, detail=f"Database error: {exc}")


  @app.get("/health")
  def health() -> dict:
      """System health check — FIX-12 (prediction distribution) + FIX-13 (chunk count)."""
      # FIX-13: Verify Qdrant chunk count at runtime.
      try:
          kb = _get_kb()
          doc_count   = kb.client.count("clinical_knowledge").count
          qdrant_status = (
              "ok"
              if doc_count == EXPECTED_CHUNK_COUNT
              else f"wrong_chunk_count_{doc_count}_expected_{EXPECTED_CHUNK_COUNT}"
          )
      except Exception as exc:
          doc_count     = 0
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
          dist       = {row[0]: row[1] for row in rows}
          total      = sum(dist.values())
          red_rate   = dist.get("RED",   0) / max(total, 1)
          green_rate = dist.get("GREEN", 0) / max(total, 1)
          if green_rate > 0.95:
              prediction_health = "suppressed_alerts_possible"
          elif red_rate > 0.20:
              prediction_health = "elevated_red_rate"
          else:
              prediction_health = "ok"
      except Exception:
          dist              = {}
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
  ```

  **What it does:** Exposes the multi-agent graph over HTTP with 5 endpoints. Preloads KB on startup. Times `invoke()` in the API layer and populates `latency_ms`. SSE endpoint streams one `data:` event per node start/end, giving clinicians real-time visibility into specialist reasoning.

  **Why this approach:** Sync `def` for blocking endpoints uses FastAPI's built-in thread pool — safest approach with sync LangGraph nodes. `astream_events(version="v2")` is the idiomatic LangGraph way to get per-node events without modifying node implementations. No extra SSE dependency.

  **Assumptions:**
  - `multi_agent.astream_events(version="v2")` is available (verified in pre-flight).
  - `alert.model_copy(update={"latency_ms": latency_ms})` creates a new Pydantic instance (Pydantic v2 API).
  - `alert_history` table exists with columns from schema v2.0 (confirmed from `src/agent/memory.py`).

  **Risks:**
  - `astream_events` event `name` field uses **graph registration keys** (`"supervisor"`, `"signal"`, `"brady"`, etc.), NOT `@traceable(name=...)` values — verified against `supervisor.py` `build_multi_agent_graph()`. `_STAGE_MAP` keys have been updated accordingly. If a new node is added to the graph, add its registration key (not function name) to `_STAGE_MAP`.
  - `model_copy` is Pydantic v2 only → if Pydantic v1, use `alert.copy(update=...)`. Mitigation: pre-flight confirms Pydantic version via `import pydantic; print(pydantic.VERSION)`.

  **Git Checkpoint:**
  ```bash
  git add api/__init__.py api/main.py
  git commit -m "step 7.2: create api/main.py — 5 endpoints, FIX-12, FIX-13, SSE streaming"
  ```

  **Subtasks:**
  - [ ] 🟥 `api/__init__.py` created (empty)
  - [ ] 🟥 `api/main.py` created with all 5 endpoints
  - [ ] 🟥 Verification passes (import check + health endpoint)

  **✓ Verification Test:**

  **Type:** Integration

  **Action:**
  ```bash
  # Structure check
  python -c "
  import os
  os.environ['EVAL_NO_LLM'] = '1'
  os.environ['QDRANT_PATH'] = 'qdrant_local'
  import ast
  from pathlib import Path

  src = Path('api/main.py').read_text()
  ast.parse(src)
  assert 'def assess(' in src, 'blocking endpoint missing'
  assert '_sse_generator' in src, 'SSE generator missing'
  assert 'EXPECTED_CHUNK_COUNT = 34' in src, 'FIX-13 constant missing'
  assert 'elevated_red_rate' in src, 'FIX-12 logic missing'
  assert 'model_copy' in src, 'model_copy not used for latency'
  print('PASS: api/main.py syntax and structure OK')
  "

  # Import check (confirms all graph imports resolve)
  EVAL_NO_LLM=1 QDRANT_PATH=qdrant_local python -c "
  import os; os.environ['EVAL_NO_LLM']='1'; os.environ['QDRANT_PATH']='qdrant_local'
  from api.main import app
  print(f'PASS: api.main imported OK, routes: {[r.path for r in app.routes]}')
  "
  ```

  **Pass:** Both `PASS` lines printed, routes list includes `/assess/{patient_id}`, `/health`, etc.

  **Fail:**
  - `ModuleNotFoundError: fastapi` → fastapi/uvicorn not installed — run pre-flight check #5; add to requirements.txt.
  - `ModuleNotFoundError: src.agent.graph` → `sys.path` not set — check `REPO_ROOT` resolution in `api/main.py`.
  - `ImportError: cannot import name 'agent'` → graph.py not compiled — run pre-flight CI gate check first.
  - `SyntaxError` → indentation error in code block — re-read file around error line.

---

## Phase 2 — Containerisation

**Goal:** `Dockerfile` exists; `docker-compose.yml` has 4 services; `docker compose up` starts the API.

---

- [ ] 🟥 **Step 7.3: Create `Dockerfile` and `.dockerignore`** — *Non-critical: new files only*

  **Idempotent:** Yes — creating new files.

  **Pre-Read Gate:**
  - Run `ls Dockerfile 2>&1`. Must fail. If exists → skip.

  **File — `Dockerfile`:**
  ```dockerfile
  # NeonatalGuard API — production image
  # Platform: linux/arm64 (Apple Silicon M2; build with --platform linux/arm64)
  FROM python:3.11-slim

  WORKDIR /app

  # Install dependencies before copying source — maximises Docker layer cache reuse.
  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt

  # Copy application source
  COPY . .

  # Pre-create directories that may be volume-mounted at runtime.
  RUN mkdir -p data logs models/exports

  EXPOSE 8000

  # Uvicorn with 1 worker (multi-agent graph holds process-level singletons;
  # multiple workers would each initialize separate KB + ONNX instances).
  CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
  ```

  **File — `.dockerignore`:**
  ```
  .git
  .env
  __pycache__/
  *.pyc
  *.pyo
  qdrant_local/
  data/raw/
  notebooks/
  *.ipynb
  models/exports/signal_specialist_lora/
  wget-log
  results/
  ```

  **Git Checkpoint:**
  ```bash
  git add Dockerfile .dockerignore
  git commit -m "step 7.3: add Dockerfile (python:3.11-slim, uvicorn 1 worker) and .dockerignore"
  ```

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  python -c "
  from pathlib import Path
  df = Path('Dockerfile').read_text()
  assert 'FROM python:3.11-slim' in df, 'Base image missing'
  assert 'COPY requirements.txt' in df, 'requirements.txt copy missing'
  assert 'uvicorn' in df, 'uvicorn CMD missing'
  assert 'EXPOSE 8000' in df, 'port not exposed'
  assert '--workers 1' in df, 'single-worker flag missing'
  di = Path('.dockerignore').read_text()
  assert '.env' in di, '.env not in dockerignore'
  assert 'qdrant_local' in di, 'qdrant_local not excluded'
  print('PASS Step 7.3: Dockerfile and .dockerignore present and valid')
  "
  ```

  **Pass:** `PASS Step 7.3` printed.

---

- [ ] 🟥 **Step 7.4: Replace `docker-compose.yml` with 4-service configuration** — *Non-critical: replaces entire 13-line file*

  **Idempotent:** Yes — replacing whole file.

  **Pre-Read Gate:**
  - Run `grep -c "services:" docker-compose.yml`. Must return 1 (file exists). Record current line count: `wc -l docker-compose.yml`.
  - The current file has only `qdrant` service — confirmed in exploration (13 lines).

  **Replace entire `docker-compose.yml` with:**

  ```yaml
  # NeonatalGuard — 4-service Docker Compose
  # Default: starts api + qdrant
  # Eval profile:  docker compose --profile eval up
  # LoRA profile:  docker compose --profile lora up
  services:

    neonatalguard-api:
      build: .
      ports:
        - "8000:8000"
      env_file: .env
      environment:
        # Empty QDRANT_PATH → _get_kb() uses networked Qdrant (QDRANT_HOST/PORT below)
        QDRANT_PATH: ""
        QDRANT_HOST: qdrant
        QDRANT_PORT: "6333"
      volumes:
        - ./data:/app/data          # audit.db persisted on host
        - ./logs:/app/logs
        - ./models/exports:/app/models/exports
      depends_on:
        qdrant:
          condition: service_healthy
      platform: linux/arm64
      restart: unless-stopped

    qdrant:
      image: qdrant/qdrant:latest
      ports:
        - "6333:6333"
        - "6334:6334"
      volumes:
        - qdrant_data:/qdrant/storage
      platform: linux/arm64
      restart: unless-stopped
      healthcheck:
        test: ["CMD", "curl", "-f", "http://localhost:6333/readyz"]
        interval: 10s
        timeout: 5s
        retries: 5

    eval-runner:
      build: .
      command: >
        python eval/run_all_evals.py --agent multi_agent
      environment:
        QDRANT_PATH: ""
        QDRANT_HOST: qdrant
        QDRANT_PORT: "6333"
      env_file: .env
      volumes:
        - ./data:/app/data
        - ./results:/app/results
      depends_on:
        neonatalguard-api:
          condition: service_started
        qdrant:
          condition: service_healthy
      profiles: ["eval"]
      platform: linux/arm64

    signal-specialist:
      image: ollama/ollama
      volumes:
        - ./models/exports/signal_specialist_lora:/models
      profiles: ["lora"]
      platform: linux/arm64

  volumes:
    qdrant_data:
  ```

  **Git Checkpoint:**
  ```bash
  git add docker-compose.yml
  git commit -m "step 7.4: expand docker-compose.yml to 4 services (api, qdrant, eval-runner, signal-specialist)"
  ```

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  python -c "
  import yaml
  from pathlib import Path
  dc = yaml.safe_load(Path('docker-compose.yml').read_text())
  svcs = dc.get('services', {})
  assert 'neonatalguard-api' in svcs, 'API service missing'
  assert 'qdrant' in svcs, 'Qdrant service missing'
  assert 'eval-runner' in svcs, 'eval-runner missing'
  assert 'signal-specialist' in svcs, 'signal-specialist missing'
  api = svcs['neonatalguard-api']
  assert api['environment'].get('QDRANT_PATH') == '', 'QDRANT_PATH not empty — Docker networked mode broken'
  assert api['environment'].get('QDRANT_HOST') == 'qdrant', 'QDRANT_HOST missing'
  assert 'eval' in svcs['eval-runner'].get('profiles', []), 'eval profile missing'
  assert 'lora' in svcs['signal-specialist'].get('profiles', []), 'lora profile missing'
  print('PASS Step 7.4: docker-compose.yml has 4 services with correct configuration')
  " 2>/dev/null || python3 -c "
  dc = open('docker-compose.yml').read()
  assert 'neonatalguard-api' in dc
  # Verify QDRANT_PATH is explicitly empty string — 'QDRANT_PATH: qdrant_local' must NOT pass.
  assert ('QDRANT_PATH: ""' in dc or "QDRANT_PATH: ''" in dc), 'QDRANT_PATH not empty — Docker networked mode broken'
  assert ('profiles:' in dc and 'eval' in dc), 'eval profile missing'
  print('PASS Step 7.4 (text check): docker-compose.yml structure OK')
  "
  ```

  **Pass:** `PASS Step 7.4` printed.

---

## Phase 3 — Tests & Docs

**Goal:** CI test suite covers the API. `.env.example` and pre-flight script are committed.

---

- [ ] 🟥 **Step 7.5: Create `tests/test_api.py`** — *Non-critical: new test file*

  **Idempotent:** Yes — new file.

  **Pre-Read Gate:**
  - Run `ls tests/test_api.py 2>&1`. Must fail. If exists → check if step already done.
  - Run `python -c "from fastapi.testclient import TestClient; print('OK')"`. Must print OK.

  **File — `tests/test_api.py`:**

  ```python
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

  import pytest
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
          sse_data_lines = [c for c in chunks if c.startswith("data:")]
          assert len(sse_data_lines) > 0, (
              f"SSE generator emitted zero data: events — check _STAGE_MAP node keys match "
              f"build_multi_agent_graph() g.add_node() names. Got lines: {chunks[:5]}"
          )
  ```

  **Git Checkpoint:**
  ```bash
  git add tests/test_api.py
  git commit -m "step 7.5: add tests/test_api.py — FastAPI TestClient, EVAL_NO_LLM=1"
  ```

  **✓ Verification Test:**

  **Type:** Integration

  **Action:**
  ```bash
  EVAL_NO_LLM=1 QDRANT_PATH=qdrant_local python -m pytest tests/test_api.py -v --tb=short 2>&1 | tail -10
  ```

  **Expected:** `5 passed`. Exit code 0.

  **Pass:** `5 passed` in pytest output.

  **Fail:**
  - `ModuleNotFoundError: fastapi` → not installed — see pre-flight check #5; add to requirements.txt.
  - `ModuleNotFoundError: api.main` → run from repo root, not tests/ directory.
  - `ONNX model not found` → `models/exports/neonatalguard_v1.onnx` missing — retrain with `python src/models/train_classifier.py && python src/models/export_onnx.py`.
  - `assert data['latency_ms'] is not None` → `model_copy` not applied in `_invoke_blocking` — recheck Step 7.2.

---

- [ ] 🟥 **Step 7.6: Create `.env.example` and `scripts/pre_flight.sh`** — *Non-critical: documentation + ops*

  **Idempotent:** Yes — new files.

  **File — `.env.example`:**
  ```bash
  # NeonatalGuard — environment variables
  # Copy to .env and fill in real values.

  # Groq LLM provider (llama-3.3-70b-versatile)
  # Get key at: https://console.groq.com
  GROQ_API_KEY=gsk_YOUR_KEY_HERE

  # LangSmith tracing (optional but recommended for production)
  # Get key at: https://smith.langchain.com
  LANGCHAIN_TRACING_V2=true
  LANGCHAIN_API_KEY=lsv2_pt_YOUR_KEY_HERE
  LANGCHAIN_PROJECT=neonatalguard-dev

  # Qdrant connection — local dev (default, uses on-disk file)
  QDRANT_PATH=qdrant_local

  # Qdrant connection — Docker/networked mode
  # Uncomment these and set QDRANT_PATH= (empty) to use networked Qdrant
  # QDRANT_HOST=localhost
  # QDRANT_PORT=6333

  # LoRA signal specialist — set to 1 after running notebooks/05_signal_specialist_lora.ipynb
  # USE_LORA_SIGNAL=1

  # CI / eval gate — set to 1 to skip all Groq calls (deterministic rule-based output)
  # EVAL_NO_LLM=1
  ```

  **File — `scripts/pre_flight.sh`:**
  ```bash
  #!/usr/bin/env bash
  # Phase 7 pre-flight — run ONCE before first docker compose up.
  # Starts Docker Qdrant, verifies local/networked Qdrant parity (FIX-14),
  # and populates Docker Qdrant with KB chunks.
  #
  # Usage: bash scripts/pre_flight.sh
  set -euo pipefail

  echo "=== NeonatalGuard Phase 7 Pre-Flight ==="

  # 1. Start only the Qdrant service
  echo "[1/4] Starting Docker Qdrant..."
  docker compose up qdrant -d
  echo "Waiting for Qdrant to become healthy..."
  sleep 8

  # 2. FIX-14: Parity test — verify local file-based and networked Qdrant return identical results
  echo "[2/4] FIX-14: Running Qdrant parity test..."
  QDRANT_HOST=localhost QDRANT_PORT=6333 python tests/test_qdrant_parity.py
  echo "Parity test PASSED."

  # 3. Populate Docker Qdrant with KB chunks
  # QDRANT_PATH="" triggers networked mode in _get_kb(); QDRANT_HOST points to Docker Qdrant.
  echo "[3/4] Populating Docker Qdrant with KB chunks..."
  QDRANT_PATH="" QDRANT_HOST=localhost QDRANT_PORT=6333 python scripts/write_chunks.py
  echo "KB populated."

  # 4. Verify chunk count
  echo "[4/4] Verifying chunk count..."
  python -c "
  import os; os.environ['QDRANT_PATH'] = ''
  os.environ['QDRANT_HOST'] = 'localhost'; os.environ['QDRANT_PORT'] = '6333'
  from src.knowledge.knowledge_base import ClinicalKnowledgeBase
  kb = ClinicalKnowledgeBase()
  count = kb.client.count('clinical_knowledge').count
  print(f'Docker Qdrant chunk count: {count}')
  assert count == 34, f'Expected 34 chunks, got {count}'
  print('Chunk count OK.')
  "

  echo ""
  echo "=== Pre-flight complete. Run: docker compose up ==="
  ```

  **Git Checkpoint:**
  ```bash
  chmod +x scripts/pre_flight.sh
  git add .env.example scripts/pre_flight.sh
  git commit -m "step 7.6: add .env.example and scripts/pre_flight.sh (FIX-14 Docker parity + KB population)"
  ```

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  python -c "
  from pathlib import Path
  ex = Path('.env.example').read_text()
  assert 'GROQ_API_KEY' in ex, 'GROQ_API_KEY missing'
  assert 'LANGCHAIN_API_KEY' in ex, 'LangSmith key missing'
  assert 'QDRANT_PATH' in ex, 'QDRANT_PATH missing'
  assert 'USE_LORA_SIGNAL' in ex, 'USE_LORA_SIGNAL missing'
  pf = Path('scripts/pre_flight.sh').read_text()
  assert 'test_qdrant_parity.py' in pf, 'parity test missing from pre_flight.sh'
  assert 'write_chunks.py' in pf, 'KB population missing from pre_flight.sh'
  print('PASS Step 7.6: .env.example and pre_flight.sh present with required content')
  "
  ```

  **Pass:** `PASS Step 7.6` printed.

---

## Regression Guard

**Systems at risk from this plan:**
- `src/agent/graph.py` `_get_kb()` — modified in Step 7.1; used by all agents and eval harness.
- `docker-compose.yml` — replaced in Step 7.4; previously had only Qdrant service.

**Regression verification:**

| System | Pre-change behaviour | Post-change verification |
|--------|----------------------|--------------------------|
| Multi-agent eval (no-LLM) | 30/30, All CI gates passed | `EVAL_NO_LLM=1 QDRANT_PATH=qdrant_local python eval/eval_agent.py --agent multi_agent 2>&1 \| tail -2` → `All CI gates passed.` |
| `_get_kb()` local mode | `ClinicalKnowledgeBase(path="qdrant_local")` | `QDRANT_PATH=qdrant_local python -c "from src.agent.graph import _get_kb; kb=_get_kb(); print('local OK')"` |
| `_get_kb()` default (unset) | Falls back to `<REPO_ROOT>/qdrant_local` | `python -c "from src.agent.graph import _get_kb; kb=_get_kb(); print('default OK')"` |
| Docker Qdrant service | Starts with `docker compose up qdrant` | `docker compose config --services \| grep qdrant` |

**Test count regression check:**
- Tests before plan (pre-flight): `____`
- After plan: `EVAL_NO_LLM=1 QDRANT_PATH=qdrant_local python -m pytest tests/ -v --tb=short 2>&1 | tail -3`
- Must be ≥ pre-flight baseline + 5 new API tests.

---

## Rollback Procedure

```bash
# Rollback in reverse commit order:
git revert HEAD   # Step 7.6: removes .env.example + pre_flight.sh
git revert HEAD   # Step 7.5: removes tests/test_api.py
git revert HEAD   # Step 7.4: restores original 13-line docker-compose.yml
git revert HEAD   # Step 7.3: removes Dockerfile + .dockerignore
git revert HEAD   # Step 7.2: removes api/main.py + api/__init__.py
git revert HEAD   # Step 7.1: restores original _get_kb() one-liner

# Confirm CI gate passes after rollback:
EVAL_NO_LLM=1 QDRANT_PATH=qdrant_local python eval/eval_agent.py --agent multi_agent 2>&1 | tail -2
# Must print: All CI gates passed.
```

---

## Pre-Flight Checklist

| Phase | Check | How to Confirm | Status |
|-------|-------|----------------|--------|
| **Pre-flight** | `api/main.py` does not exist | `ls api/main.py` → error | ⬜ |
| | `_get_kb()` has old one-liner | `grep "QDRANT_PATH.*qdrant_local" src/agent/graph.py` returns 1 match | ⬜ |
| | Chunk count = 34 | KB count script in pre-flight | ⬜ |
| | `astream_events` available | Attribute check in pre-flight | ⬜ |
| | `fastapi` + `uvicorn` importable | `python -c "import fastapi, uvicorn; print('OK')"` | ⬜ |
| | CI gate passes | `EVAL_NO_LLM=1 ... eval_agent.py \| tail -2` → passed | ⬜ |
| **Phase 1** | Step 7.1 complete | `PASS Step 7.1` printed | ⬜ |
| | Step 7.2 complete | Import check prints routes | ⬜ |
| **Phase 2** | Step 7.3 complete | `PASS Step 7.3` printed | ⬜ |
| | Step 7.4 complete | `PASS Step 7.4` printed | ⬜ |
| **Phase 3** | Step 7.5 complete | `5 passed` in pytest | ⬜ |
| | Step 7.6 complete | `PASS Step 7.6` printed | ⬜ |

---

## Risk Heatmap

| Step | Risk | What Could Go Wrong | Early Detection | Idempotent |
|------|------|---------------------|-----------------|------------|
| 7.1 | 🟢 Low | Wrong anchor → `_get_kb` edit misplaced | Pre-Read Gate grep returns 1 match; step is defensive (not a real bug fix) | Yes |
| 7.2 | 🟡 Medium | `astream_events` unavailable → SSE test fails loudly | Pre-flight `hasattr` check catches before Step 7.2 begins | Yes |
| 7.2 | 🟡 Medium | `_STAGE_MAP` key mismatch → SSE emits zero events | `test_stream_returns_event_stream_content_type` now asserts `len(sse_data_lines) > 0` | Yes |
| 7.2 | 🟡 Medium | `model_copy` is Pydantic v1 → `AttributeError` | `test_assess_blocking_infant1` catches this | Yes |
| 7.3 | 🟢 Low | Wrong base image for ARM | `docker build` fails → readable error | Yes |
| 7.4 | 🟡 Medium | `QDRANT_PATH: ""` overridden by `.env` file value | Verify with `docker compose config` before first up | Yes |
| 7.5 | 🟡 Medium | `EVAL_NO_LLM` not set before import → Groq call fails | `os.environ` assignment must be first line of file | Yes |
| 7.6 | 🟢 Low | `pre_flight.sh` uses wrong KB path | `assert count == 34` inside script catches it | Yes |

---

## Success Criteria

| Feature | Target | Verification |
|---------|--------|--------------|
| Blocking endpoint | Returns `NeonatalAlert` with `latency_ms` set | `POST /assess/infant1` → `concern_level` in ["RED","YELLOW","GREEN"], `latency_ms` float |
| SSE streaming | Returns `text/event-stream` content-type | `GET /assess/infant1/stream` → 200 + `content-type: text/event-stream` |
| Patient history | Returns JSON array from SQLite | `GET /patient/infant1/history` → list of dicts or `[]` |
| Generalist A/B | Returns `NeonatalAlert` from generalist graph | `POST /assess/infant1/generalist` → `concern_level` present |
| FIX-12 health | Prediction distribution visible | `GET /health` → `prediction_distribution_last_100` key present, `prediction_health` in response |
| FIX-13 health | Chunk count verified | `GET /health` → `qdrant == "ok"` if 34 chunks present |
| Docker networked mode | `QDRANT_PATH=""` → networked Qdrant | `_qdrant_path = ""` → `ClinicalKnowledgeBase()` branch taken |
| CI gate regression | Multi-agent eval still 30/30 | `EVAL_NO_LLM=1 ... eval_agent.py --agent multi_agent` → `All CI gates passed.` |
| Test count | Pre-flight count + 5 new API tests | `pytest tests/ -v` → count ≥ baseline + 5 |

---

⚠️ **Do not mark a step 🟩 Done until its verification test passes.**
⚠️ **Do not proceed past a Human Gate without explicit human input.**
⚠️ **If blocked, mark 🟨 In Progress and output the State Manifest before stopping.**
⚠️ **Do not batch multiple steps into one git commit.**
⚠️ **If idempotent = No, confirm the step has not already run before executing.**
