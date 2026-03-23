# Phase 3 Execution Plan: LangGraph Agent

**Overall Progress:** `0%`

## TLDR
Build the LangGraph agent for NeonatalGuard in five steps: create the `src/agent/` package and typed schemas, add SQLite episodic memory, prove state passing with a 2-node starter graph, upgrade to the full 6-node graph with local on-disk Qdrant retrieval from `qdrant_local/`, and verify LangSmith tracing. Phase 3 must not depend on Docker-backed Qdrant because Docker is currently unreliable on this machine.

## Critical Decisions
- **Decision 1:** All LLM outputs use `instructor` + Pydantic. No manual JSON parsing.
- **Decision 2:** SQLite at `data/audit.db` is the episodic memory store.
- **Decision 3:** The graph is built in two stages: 2-node starter first, then full 6-node graph.
- **Decision 4:** Outside eval mode, Groq configuration must fail closed. No silent fallback to rule-based output.
- **Decision 5:** Retrieval uses `qdrant_local/` through `ClinicalKnowledgeBase(path=...)` in Phase 3.
- **Decision 6:** LangSmith decorators are written directly into the final `src/agent/graph.py`. No post-hoc string rewrite script.

## Decisions Log
- **Resolved:** Step 3.4 now verifies the exact Step 3.3 starter graph shape before replacing it.
- **Resolved:** Step 3.4 updates `src/knowledge/knowledge_base.py` to support `path=`.
- **Resolved:** The no-LLM rule-based branch now produces `clinical_reasoning` longer than 30 characters.
- **Resolved:** Groq initialization no longer falls back silently in production mode.
- **Resolved:** Step 3.5 is verification-only. Decorators are part of the final graph file from Step 3.4.

## Clarification Gate
| Unknown | Required | Source | Blocking | Resolved |
|---------|----------|--------|----------|----------|
| Groq key | `.env` must contain a real `GROQ_API_KEY` | `.env` | Step 3.4 | ✅ |
| LangSmith key | `.env` must contain a real `LANGCHAIN_API_KEY` | `.env` | Step 3.5 | ✅ |

## Agent Failure Protocol
1. A verification command fails -> read the full error output.
2. Cause is unambiguous -> make ONE targeted fix -> re-run the same verification command.
3. If still failing after one fix -> **STOP**. Before stopping, output the full current contents of every file modified in this step. Report: (a) command run, (b) full error verbatim, (c) fix attempted, (d) current state of each modified file, (e) why you cannot proceed.
4. Never attempt a second fix without human instruction.
5. Never modify files not named in the current step.

## Pre-Flight - Run Before Any Code Changes

```
Read these files in full:
- src/pipeline/runner.py
- src/pipeline/result.py
- src/knowledge/knowledge_base.py

Then run these exact commands and show the full output:

python -c "from pathlib import Path; required=['models/exports/neonatalguard_v1.onnx','models/exports/feature_cols.pkl','models/exports/tfidf_vectorizer.pkl','qdrant_local/meta.json']; missing=[p for p in required if not Path(p).exists()]; assert not missing, f'Missing prerequisites: {missing}'; print('Phase 1/2 artifacts present')"

python -c "from dotenv import load_dotenv; load_dotenv(); import os; key=os.getenv('GROQ_API_KEY',''); assert key and key != 'your_groq_api_key_here', 'GROQ_API_KEY missing or placeholder'; print('GROQ_API_KEY present')"

python -c "from dotenv import load_dotenv; load_dotenv(); import os; key=os.getenv('LANGCHAIN_API_KEY',''); assert key and key != 'your_langchain_api_key_here', 'LANGCHAIN_API_KEY missing or placeholder'; print('LANGCHAIN_API_KEY present')"

python -c "from qdrant_client import QdrantClient; from pathlib import Path; client=QdrantClient(path=str(Path('qdrant_local').resolve())); info=client.get_collection('clinical_knowledge'); print(f'Local Qdrant OK: {info.points_count} points')"

Do not change anything. Show full output and wait.
```

**Baseline Snapshot (agent fills during pre-flight):**
```
PipelineResult fields: recorded
ClinicalKnowledgeBase.query signature: recorded
Phase 1/2 artifacts present: pass/fail
GROQ_API_KEY present: pass/fail
LANGCHAIN_API_KEY present: pass/fail
Local Qdrant collection present: pass/fail
```

**Automated checks (all must pass before Step 3.1):**
- [ ] `NeonatalPipeline.run` exists and takes `patient_id: str`
- [ ] `PipelineResult` contains `risk_score`, `risk_level`, `z_scores`, `hrv_values`, `personal_baseline`, `detected_events`, and `get_top_deviated`
- [ ] `ClinicalKnowledgeBase.query` exists and takes `text`, `n`, and `risk_tier`
- [ ] `models/exports/neonatalguard_v1.onnx` exists
- [ ] `models/exports/feature_cols.pkl` exists
- [ ] `models/exports/tfidf_vectorizer.pkl` exists
- [ ] `qdrant_local/meta.json` exists
- [ ] Local Qdrant collection `clinical_knowledge` opens successfully from disk

## Environment Matrix
| Step | Dev | Staging | Prod | Notes |
|------|-----|---------|------|-------|
| Step 3.1 | ✅ | ✅ | ✅ | Creates `src/agent/` package and schemas |
| Step 3.2 | ✅ | ✅ | ✅ | SQLite memory at `data/audit.db` |
| Step 3.3 | ✅ | ✅ | ✅ | 2-node starter graph |
| Step 3.4 | ✅ | ⚠️ | ⚠️ | Uses local `qdrant_local/` by default |
| Step 3.5 | ✅ | ✅ | ✅ | LangSmith verification only |

## Tasks

### Phase 3 - LangGraph Agent

**Goal:** A fully functional LangGraph agent that produces protocol-compliant clinical alerts from ONNX output, retrieved clinical context, and a self-check pass.

---

- [ ] 🟥 **Step 3.1: Create `src/agent/` package and schemas** - *Critical: all downstream graph code depends on these types.*

  **Idempotent:** Yes - `mkdir -p` and file overwrite are deterministic.

  **Context:** The repo currently has no `src/agent/` package. This step creates the package and defines the exact structure the LLM must produce.

  **Pre-Read Gate:**
  ```bash
  test -d src/agent && echo "src/agent exists" || echo "src/agent missing"
  test -f src/agent/schemas.py && echo "schemas.py exists" || echo "schemas.py missing"
  ```

  **Files to create:**
  - `src/agent/__init__.py`
  - `src/agent/schemas.py`

  **Code to write:**
  ```bash
  mkdir -p src/agent
  touch src/agent/__init__.py
  ```

  ```python
  # src/agent/schemas.py
  from datetime import datetime
  from typing import Literal

  from pydantic import BaseModel, field_validator, model_validator


  APPROVED_ACTIONS = [
      "Immediate clinical review",
      "Blood culture and CBC with differential",
      "Temperature and perfusion monitoring",
      "Continue routine monitoring",
      "Reassess in 2 hours",
      "Notify attending neonatologist",
      "Increase monitoring frequency to every 15 minutes",
      "Respiratory support assessment",
  ]


  class LLMOutput(BaseModel):
      concern_level: Literal["RED", "YELLOW", "GREEN"]
      primary_indicators: list[str]
      clinical_reasoning: str
      recommended_action: str
      confidence: float

      @field_validator("confidence")
      @classmethod
      def confidence_range(cls, v: float) -> float:
          if not 0.0 <= v <= 1.0:
              raise ValueError(f"confidence {v} must be between 0.0 and 1.0")
          return v

      @field_validator("primary_indicators")
      @classmethod
      def at_least_one_indicator(cls, v: list[str]) -> list[str]:
          if len(v) < 1:
              raise ValueError("must provide at least one primary indicator")
          return v[:3]

      @field_validator("clinical_reasoning")
      @classmethod
      def reasoning_substantive(cls, v: str) -> str:
          if len(v.strip()) < 30:
              raise ValueError("clinical_reasoning too short - LLM may have failed")
          return v

      @model_validator(mode="after")
      def enforce_protocol_compliance(self) -> "LLMOutput":
          compliant = any(
              approved.lower() in self.recommended_action.lower()
              for approved in APPROVED_ACTIONS
          )
          if not compliant:
              original = self.recommended_action
              self.recommended_action = (
                  f"[PROTOCOL FLAG: non-standard action '{original}'] "
                  "Notify attending neonatologist for immediate review."
              )
          return self


  class NeonatalAlert(BaseModel):
      patient_id: str
      timestamp: datetime
      concern_level: Literal["RED", "YELLOW", "GREEN"]
      risk_score: float
      primary_indicators: list[str]
      clinical_reasoning: str
      recommended_action: str
      confidence: float
      retrieved_context: list[str]
      self_check_passed: bool
      protocol_compliant: bool
      past_similar_events: int
      latency_ms: float | None = None
  ```

  **Git Checkpoint:**
  ```bash
  git add src/agent/__init__.py src/agent/schemas.py
  git commit -m "step 3.1: create agent package and schemas"
  ```

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  python -c "
  from src.agent.schemas import LLMOutput
  ok = LLMOutput(
      concern_level='RED',
      primary_indicators=['RMSSD', 'LF_HF'],
      clinical_reasoning='Sustained reduction in short-term HRV variability over 6 hours.',
      recommended_action='Immediate clinical review',
      confidence=0.85,
  )
  flagged = LLMOutput(
      concern_level='YELLOW',
      primary_indicators=['SDNN'],
      clinical_reasoning='Moderate deviation in variability suggests a possible issue.',
      recommended_action='Give the baby an aspirin',
      confidence=0.60,
  )
  assert 'PROTOCOL FLAG' not in ok.recommended_action
  assert 'PROTOCOL FLAG' in flagged.recommended_action
  print('Schemas OK')
  "
  ```

  **Expected:** Prints `Schemas OK`.

  **Observe:** Terminal output.

---

- [ ] 🟥 **Step 3.2: Create episodic memory** - *Non-critical*

  **Idempotent:** Yes - `CREATE TABLE IF NOT EXISTS` is safe to re-run.

  **Context:** The graph needs recent alerts for temporal context and audit history.

  **File to create:** `src/agent/memory.py`

  **Code to write:**
  ```python
  # src/agent/memory.py
  import sqlite3
  from dataclasses import dataclass
  from pathlib import Path

  from src.agent.schemas import NeonatalAlert


  REPO_ROOT = Path(__file__).resolve().parent.parent.parent


  @dataclass
  class PastAlert:
      timestamp: str
      concern_level: str
      risk_score: float
      top_feature: str
      top_z_score: float


  class EpisodicMemory:
      def __init__(self, db_path: str | None = None):
          if db_path is None:
              db_path = str(REPO_ROOT / "data" / "audit.db")
          self.db_path = db_path
          Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
          self._init_schema()

      def _init_schema(self) -> None:
          with sqlite3.connect(self.db_path) as conn:
              conn.execute(
                  """
                  CREATE TABLE IF NOT EXISTS alert_history (
                      id            INTEGER PRIMARY KEY AUTOINCREMENT,
                      patient_id    TEXT,
                      timestamp     TEXT,
                      concern_level TEXT,
                      risk_score    REAL,
                      top_feature   TEXT,
                      top_z_score   REAL
                  )
                  """
              )

      def get_recent(self, patient_id: str, n: int = 7) -> list[PastAlert]:
          with sqlite3.connect(self.db_path) as conn:
              rows = conn.execute(
                  """
                  SELECT timestamp, concern_level, risk_score, top_feature, top_z_score
                  FROM alert_history
                  WHERE patient_id = ?
                  ORDER BY timestamp DESC
                  LIMIT ?
                  """,
                  (patient_id, n),
              ).fetchall()
          return [PastAlert(*row) for row in rows]

      def count_similar(self, patient_id: str, level: str, hours: int = 72) -> int:
          with sqlite3.connect(self.db_path) as conn:
              count = conn.execute(
                  """
                  SELECT COUNT(*) FROM alert_history
                  WHERE patient_id = ?
                    AND concern_level = ?
                    AND timestamp > datetime('now', ? || ' hours')
                  """,
                  (patient_id, level, f"-{hours}"),
              ).fetchone()[0]
          return count

      def save(self, alert: NeonatalAlert, top_feature: str, top_z: float) -> None:
          with sqlite3.connect(self.db_path) as conn:
              conn.execute(
                  """
                  INSERT INTO alert_history
                  (patient_id, timestamp, concern_level, risk_score, top_feature, top_z_score)
                  VALUES (?, ?, ?, ?, ?, ?)
                  """,
                  (
                      alert.patient_id,
                      alert.timestamp.isoformat(),
                      alert.concern_level,
                      alert.risk_score,
                      top_feature,
                      top_z,
                  ),
              )
  ```

  **Git Checkpoint:**
  ```bash
  git add src/agent/memory.py
  git commit -m "step 3.2: create episodic memory"
  ```

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  rm -f data/test_audit.db
  python -c "
  from datetime import datetime
  from src.agent.memory import EpisodicMemory
  from src.agent.schemas import NeonatalAlert

  mem = EpisodicMemory('data/test_audit.db')
  alert = NeonatalAlert(
      patient_id='test1',
      timestamp=datetime.now(),
      concern_level='RED',
      risk_score=0.88,
      primary_indicators=['RMSSD'],
      clinical_reasoning='Testing SQLite persistence for the episodic memory layer.',
      recommended_action='Immediate clinical review',
      confidence=0.9,
      retrieved_context=[],
      self_check_passed=True,
      protocol_compliant=True,
      past_similar_events=0,
  )
  mem.save(alert, 'RMSSD', -3.1)
  recent = mem.get_recent('test1', 1)
  assert len(recent) == 1
  assert recent[0].concern_level == 'RED'
  print('Memory OK')
  "
  rm -f data/test_audit.db
  ```

  **Expected:** Prints `Memory OK`.

  **Observe:** Terminal output.

---

- [ ] 🟥 **Step 3.3: Create the 2-node starter graph** - *Critical: prove state passing before retrieval or LLM calls.*

  **Idempotent:** Yes - File overwrite is deterministic.

  **Context:** This step proves the graph can run the ONNX pipeline, assemble a `NeonatalAlert`, and persist memory before more nodes are added.

  **Pre-Read Gate:**
  ```bash
  pip show langgraph
  test -f src/agent/schemas.py && echo "schemas ready" || echo "schemas missing"
  test -f src/agent/memory.py && echo "memory ready" || echo "memory missing"
  ```

  **File to create:** `src/agent/graph.py`

  **Code to write:**
  ```python
  # src/agent/graph.py
  import os
  import sys
  from datetime import datetime
  from pathlib import Path
  from typing import Optional, TypedDict

  from langgraph.graph import END, StateGraph

  REPO_ROOT = Path(__file__).resolve().parent.parent.parent
  sys.path.insert(0, str(REPO_ROOT))

  from src.agent.memory import EpisodicMemory, PastAlert
  from src.agent.schemas import LLMOutput, NeonatalAlert
  from src.pipeline.result import PipelineResult
  from src.pipeline.runner import NeonatalPipeline


  class AgentState(TypedDict):
      patient_id: str
      pipeline_result: Optional[PipelineResult]
      rag_context: Optional[list[str]]
      rag_query: Optional[str]
      past_alerts: Optional[list[PastAlert]]
      llm_output: Optional[LLMOutput]
      self_check_passed: Optional[bool]
      final_alert: Optional[NeonatalAlert]
      error: Optional[str]


  def run_pipeline_node(state: AgentState) -> dict:
      synthetic = os.environ.get("_SYNTHETIC_RESULT")
      if synthetic:
          import pickle
          result = pickle.loads(bytes.fromhex(synthetic))
      else:
          result = NeonatalPipeline().run(state["patient_id"])
      past = EpisodicMemory().get_recent(state["patient_id"], n=7)
      return {"pipeline_result": result, "past_alerts": past}


  def assemble_alert_node(state: AgentState) -> dict:
      result = state.get("pipeline_result")
      if not result:
          raise RuntimeError("PipelineResult is missing in assemble node")

      top = result.get_top_deviated(3)
      indicators = [d.name for d in top]
      reasoning = f"Starter graph summary: risk_score={result.risk_score:.2f} with {len(indicators)} indicators."

      top_one = result.get_top_deviated(1)
      top_feature_name = top_one[0].name if top_one else "none"
      top_feature_z = top_one[0].z_score if top_one else 0.0

      alert = NeonatalAlert(
          patient_id=result.patient_id,
          timestamp=datetime.now(),
          concern_level=result.risk_level,
          risk_score=result.risk_score,
          primary_indicators=indicators,
          clinical_reasoning=reasoning,
          recommended_action="Continue routine monitoring",
          confidence=0.5,
          retrieved_context=[],
          self_check_passed=True,
          protocol_compliant=True,
          past_similar_events=len(state.get("past_alerts") or []),
      )

      EpisodicMemory().save(alert, top_feature_name, top_feature_z)
      return {"final_alert": alert}


  def build_graph():
      g = StateGraph(AgentState)
      g.add_node("pipeline", run_pipeline_node)
      g.add_node("assemble", assemble_alert_node)
      g.set_entry_point("pipeline")
      g.add_edge("pipeline", "assemble")
      g.add_edge("assemble", END)
      return g.compile()


  agent = build_graph()
  ```

  **Git Checkpoint:**
  ```bash
  git add src/agent/graph.py
  git commit -m "step 3.3: create 2-node starter graph"
  ```

  **✓ Verification Test:**

  **Type:** Integration

  **Action:**
  ```bash
  python -c "
  from src.agent.graph import agent
  from src.agent.memory import EpisodicMemory

  result = agent.invoke({'patient_id': 'infant1'})
  alert = result['final_alert']
  assert alert.patient_id == 'infant1'
  recent = EpisodicMemory().get_recent('infant1', 1)
  assert len(recent) >= 1, 'Alert was not written to memory'
  print(f'2-node graph OK: level={alert.concern_level}, risk={alert.risk_score:.3f}')
  "
  ```

  **Expected:** Prints `2-node graph OK: ...`.

  **Observe:** Terminal output.

---

- [ ] 🟥 **Step 3.4: Upgrade to the full 6-node graph and local Qdrant retrieval** - *Critical: this is the first complete agent run.*

  **Idempotent:** Yes - Both file replacements are deterministic.

  **Context:** This step does two coupled changes:
  1. Update `ClinicalKnowledgeBase` to support `path=`.
  2. Replace the starter graph with the full 6-node graph and point retrieval at `qdrant_local/`.

  **Pre-Read Gate:**
  Run all of these exact commands before editing:
  ```bash
  rg -n '^def run_pipeline_node|^def assemble_alert_node|^def build_graph' src/agent/graph.py
  rg -n 'build_rag_query_node|retrieve_context_node|llm_reasoning_node|self_check_node' src/agent/graph.py
  rg -n 'g.add_node\("pipeline", run_pipeline_node\)|g.add_node\("assemble", assemble_alert_node\)' src/agent/graph.py
  rg -n '^def __init__\(' src/knowledge/knowledge_base.py
  test -f models/exports/tfidf_vectorizer.pkl && echo "tfidf ready" || echo "tfidf missing"
  test -d qdrant_local && echo "qdrant_local ready" || echo "qdrant_local missing"
  ```

  **Expected gate output:**
  - `run_pipeline_node`, `assemble_alert_node`, and `build_graph` each appear once.
  - `build_rag_query_node`, `retrieve_context_node`, `llm_reasoning_node`, and `self_check_node` appear zero times.
  - `g.add_node("pipeline", run_pipeline_node)` appears once.
  - `g.add_node("assemble", assemble_alert_node)` appears once.
  - `tfidf ready`
  - `qdrant_local ready`

  If any output differs, **STOP**. Step 3.3 or Phase 2 artifacts are not in the expected state.

  **Files to modify:**
  - `src/knowledge/knowledge_base.py`
  - `src/agent/graph.py`

  **Code to write - replace `src/knowledge/knowledge_base.py` fully:**
  ```python
  # src/knowledge/knowledge_base.py
  from __future__ import annotations

  import os
  import pickle
  import sys
  from pathlib import Path

  from flashrank import Ranker, RerankRequest
  from qdrant_client import QdrantClient
  from qdrant_client.models import (
      FieldCondition,
      Filter,
      Fusion,
      FusionQuery,
      MatchValue,
      Prefetch,
      SparseVector,
  )
  from sentence_transformers import SentenceTransformer

  REPO_ROOT = Path(__file__).resolve().parent.parent.parent
  sys.path.insert(0, str(REPO_ROOT))


  class ClinicalKnowledgeBase:
      def __init__(
          self,
          host: str | None = None,
          port: int | None = None,
          path: str | None = None,
      ) -> None:
          if path:
              self.client = QdrantClient(path=path)
          else:
              _host = host or os.getenv("QDRANT_HOST", "localhost")
              _port = port or int(os.getenv("QDRANT_PORT", "6333"))
              self.client = QdrantClient(host=_host, port=_port)

          self.dense_model = SentenceTransformer("all-MiniLM-L6-v2")
          self.reranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2")

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
          dense_vec = self.dense_model.encode(text).tolist()
          sp = self.tfidf.transform([text])
          sparse_vec = SparseVector(
              indices=sp.indices.tolist(),
              values=sp.data.tolist(),
          )

          filt = None
          if risk_tier:
              filt = Filter(
                  must=[
                      FieldCondition(
                          key="risk_tier",
                          match=MatchValue(value=risk_tier),
                      )
                  ]
              )

          results = self.client.query_points(
              collection_name="clinical_knowledge",
              prefetch=[
                  Prefetch(query=dense_vec, using="dense", filter=filt, limit=10),
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
          # flashrank>=0.2.x returns plain dicts, not PassageResult objects.
          # Use r["text"] — not r.text. Verified against flashrank==0.2.10.
          return [r["text"] for r in reranked[:n]]
  ```

  **Code to write - replace `src/agent/graph.py` fully:**
  ```python
  # src/agent/graph.py
  import os
  import sys
  from datetime import datetime
  from pathlib import Path
  from typing import Literal, Optional, TypedDict

  import instructor
  from dotenv import load_dotenv
  from groq import Groq
  from langgraph.graph import END, StateGraph
  from langsmith import traceable
  from pydantic import BaseModel

  REPO_ROOT = Path(__file__).resolve().parent.parent.parent
  sys.path.insert(0, str(REPO_ROOT))

  from src.agent.memory import EpisodicMemory, PastAlert
  from src.agent.schemas import LLMOutput, NeonatalAlert
  from src.knowledge.knowledge_base import ClinicalKnowledgeBase
  from src.pipeline.result import PipelineResult
  from src.pipeline.runner import NeonatalPipeline

  load_dotenv()


  def _is_eval_mode() -> bool:
      """Per-call eval-mode check so programmatic os.environ changes in tests are respected."""
      return os.getenv("EVAL_NO_LLM", "").lower() in {"1", "true", "yes"}


  def _build_groq_client():
      api_key = os.getenv("GROQ_API_KEY", "")
      if not api_key or api_key == "your_groq_api_key_here":
          raise RuntimeError(
              "GROQ_API_KEY is missing or still set to the placeholder value. "
              "Set a real key in .env or export EVAL_NO_LLM=1 for non-LLM mode."
          )
      return instructor.from_groq(Groq(api_key=api_key), mode=instructor.Mode.JSON)


  # Groq client is initialised at import time. If EVAL_NO_LLM is set *after* import
  # (e.g. in Phase 4 programmatic tests), _GROQ is already a real client but the
  # per-call _is_eval_mode() checks inside each node will still gate every API call.
  _GROQ = None if _is_eval_mode() else _build_groq_client()


  class AgentState(TypedDict):
      patient_id: str
      pipeline_result: Optional[PipelineResult]
      rag_context: Optional[list[str]]
      rag_query: Optional[str]
      past_alerts: Optional[list[PastAlert]]
      llm_output: Optional[LLMOutput]
      self_check_passed: Optional[bool]
      final_alert: Optional[NeonatalAlert]
      error: Optional[str]


  class Verify(BaseModel):
      confirmed: bool
      revised_concern_level: Literal["RED", "YELLOW", "GREEN"]
      reason: str


  @traceable(name="run_pipeline_node")
  def run_pipeline_node(state: AgentState) -> dict:
      synthetic = os.environ.get("_SYNTHETIC_RESULT")
      if synthetic:
          import pickle
          result = pickle.loads(bytes.fromhex(synthetic))
      else:
          result = NeonatalPipeline().run(state["patient_id"])

      past = EpisodicMemory().get_recent(state["patient_id"], n=7)
      return {"pipeline_result": result, "past_alerts": past}


  @traceable(name="build_rag_query_node")
  def build_rag_query_node(state: AgentState) -> dict:
      r = state["pipeline_result"]
      top3 = r.get_top_deviated(3)
      query = (
          f"Premature neonate, {r.risk_level} risk. "
          f"HRV deviations from personal baseline: "
          + ", ".join(f"{d.name} z={d.z_score:+.1f}" for d in top3)
          + f". Bradycardia events: {len(r.detected_events)} in last 6h. "
          + f"Risk score: {r.risk_score:.2f}."
      )
      return {"rag_query": query}


  @traceable(name="retrieve_context_node")
  def retrieve_context_node(state: AgentState) -> dict:
      kb = ClinicalKnowledgeBase(
          path=os.getenv("QDRANT_PATH", str(REPO_ROOT / "qdrant_local"))
      )
      context = kb.query(
          state["rag_query"],
          n=3,
          risk_tier=state["pipeline_result"].risk_level,
      )
      return {"rag_context": context}


  @traceable(name="llm_reasoning_node")
  def llm_reasoning_node(state: AgentState) -> dict:
      r = state["pipeline_result"]

      if _is_eval_mode():
          return {
              "llm_output": LLMOutput(
                  concern_level=r.risk_level,
                  primary_indicators=[d.name for d in r.get_top_deviated(3)] or ["unknown"],
                  clinical_reasoning=(
                      f"Rule-based fallback: ONNX risk score {r.risk_score:.2f}, "
                      f"{len(r.detected_events)} bradycardia events, and structured HRV deviations from baseline."
                  ),
                  recommended_action=(
                      "Immediate clinical review"
                      if r.risk_level == "RED"
                      else "Reassess in 2 hours"
                      if r.risk_level == "YELLOW"
                      else "Continue routine monitoring"
                  ),
                  confidence=0.90 if r.risk_level == "RED" else 0.75 if r.risk_level == "YELLOW" else 0.90,
              )
          }

      context = "\n\n".join(state["rag_context"] or [])
      past = state.get("past_alerts") or []

      episodic = ""
      if past:
          episodic = "Patient history (last {} alerts):\n".format(len(past))
          episodic += "\n".join(
              f"  [{a.timestamp[:10]}] {a.concern_level} - {a.top_feature} z={a.top_z_score:.1f}"
              for a in past
          )

      prompt = f"""You are a clinical decision support system for neonatal intensive care.

Patient: {r.patient_id}
ONNX risk score: {r.risk_score:.3f}

HRV z-scores (deviation from THIS PATIENT's personal baseline):
{chr(10).join(f"  {feat}: z={z:+.2f}  (actual={r.hrv_values.get(feat, 0):.1f}ms, baseline_mean={r.personal_baseline.get(feat, {}).get('mean', 0):.1f}ms)" for feat, z in r.z_scores.items())}

Bradycardia events last 6h: {len(r.detected_events)}

{episodic}

Retrieved clinical context:
{context}

Generate a structured neonatal clinical alert. Be specific about which HRV values are abnormal and why. Recommended actions must follow standard NICU protocols."""

      output: LLMOutput = _GROQ.chat.completions.create(
          model="llama-3.3-70b-versatile",
          response_model=LLMOutput,
          messages=[{"role": "user", "content": prompt}],
          temperature=0.1,
          max_retries=3,
      )
      return {"llm_output": output}


  @traceable(name="self_check_node")
  def self_check_node(state: AgentState) -> dict:
      out = state["llm_output"]
      r = state["pipeline_result"]
      z_vals = [abs(z) for z in r.z_scores.values()]
      max_z = max(z_vals) if z_vals else 0.0

      if r.risk_score > 0.8 and max_z > 3.0 and out.concern_level != "RED":
          out.concern_level = "RED"
          out.confidence = max(out.confidence, 0.85)
          out.clinical_reasoning += " [OVERRIDDEN: rule-based RED threshold triggered]"

      if (not _is_eval_mode()) and (out.confidence < 0.7 or out.concern_level == "YELLOW"):
          v: Verify = _GROQ.chat.completions.create(
              model="llama-3.3-70b-versatile",
              response_model=Verify,
              messages=[
                  {
                      "role": "user",
                      "content": (
                          f"Review neonatal alert: level={out.concern_level}, "
                          f"confidence={out.confidence:.2f}, risk_score={r.risk_score:.2f}, "
                          f"max_z_score={max_z:.1f}. "
                          "Is the concern level correct? "
                          "Reply with confirmed (true/false), revised_concern_level, and reason."
                      ),
                  }
              ],
              temperature=0.1,
          )
          if not v.confirmed:
              out.concern_level = v.revised_concern_level

      return {"llm_output": out, "self_check_passed": True}


  @traceable(name="assemble_alert_node")
  def assemble_alert_node(state: AgentState) -> dict:
      result = state["pipeline_result"]
      llm_out = state["llm_output"]

      top_one = result.get_top_deviated(1)
      top_feature_name = top_one[0].name if top_one else "none"
      top_feature_z = top_one[0].z_score if top_one else 0.0

      alert = NeonatalAlert(
          patient_id=result.patient_id,
          timestamp=datetime.now(),
          concern_level=llm_out.concern_level,
          risk_score=result.risk_score,
          primary_indicators=llm_out.primary_indicators,
          clinical_reasoning=llm_out.clinical_reasoning,
          recommended_action=llm_out.recommended_action,
          confidence=llm_out.confidence,
          retrieved_context=state.get("rag_context") or [],
          self_check_passed=state.get("self_check_passed", True),
          protocol_compliant="PROTOCOL FLAG" not in llm_out.recommended_action,
          past_similar_events=len(state.get("past_alerts") or []),
      )

      EpisodicMemory().save(alert, top_feature_name, top_feature_z)
      return {"final_alert": alert}


  def build_graph():
      g = StateGraph(AgentState)
      g.add_node("pipeline", run_pipeline_node)
      g.add_node("build_query", build_rag_query_node)
      g.add_node("retrieve", retrieve_context_node)
      g.add_node("reason", llm_reasoning_node)
      g.add_node("self_check", self_check_node)
      g.add_node("assemble", assemble_alert_node)
      g.set_entry_point("pipeline")
      g.add_edge("pipeline", "build_query")
      g.add_edge("build_query", "retrieve")
      g.add_edge("retrieve", "reason")
      g.add_edge("reason", "self_check")
      g.add_edge("self_check", "assemble")
      g.add_edge("assemble", END)
      return g.compile()


  agent = build_graph()
  ```

  **Git Checkpoint:**
  ```bash
  git add src/knowledge/knowledge_base.py src/agent/graph.py
  git commit -m "step 3.4: add path-mode knowledge base and full 6-node graph"
  ```

  **✓ Verification Test 1:**

  **Type:** Integration

  **Action:** No-LLM smoke test using local Qdrant path.
  ```bash
  export EVAL_NO_LLM=1
  python -c "
  from src.agent.graph import agent
  res = agent.invoke({'patient_id': 'infant1'})
  alert = res['final_alert']
  assert len(res['rag_query']) > 20, 'RAG query was not built'
  assert 1 <= len(res['rag_context']) <= 3, 'RAG retrieval failed from local Qdrant'
  assert len(alert.clinical_reasoning) >= 30, 'Rule-based clinical_reasoning is too short'
  print('6-node no-LLM graph OK')
  "
  ```

  **Expected:** Prints `6-node no-LLM graph OK`.

  **Observe:** Terminal output.

  **✓ Verification Test 2:**

  **Type:** Integration

  **Action:** Live LLM smoke test. This must make one real Groq call and must not silently fall back. Run in a fresh shell where `EVAL_NO_LLM` is not set.
  ```bash
  unset EVAL_NO_LLM
  python -c "
  from src.agent.graph import agent
  res = agent.invoke({'patient_id': 'infant1'})
  alert = res['final_alert']
  assert len(alert.clinical_reasoning) >= 30, 'LLM clinical_reasoning too short'
  assert alert.recommended_action, 'LLM returned empty action'
  assert 'Rule-based fallback' not in alert.clinical_reasoning, 'LLM was not actually called - rule-based path ran instead'
  print('6-node live LLM graph OK')
  "
  ```

  **Expected:** Prints `6-node live LLM graph OK`.

  **Pass:** All three assertions hold, including the absence of `Rule-based fallback`.

  **Fail:**
  - If `'Rule-based fallback' in alert.clinical_reasoning` -> `EVAL_NO_LLM` was still set in the environment when Python started (check with `echo $EVAL_NO_LLM` before running), or `GROQ_API_KEY` is missing and `_build_groq_client()` raised at import time but was somehow bypassed.
  - If import fails with `GROQ_API_KEY is missing` -> `.env` is still placeholder -> fix `.env` and re-run.

  **Observe:** Terminal output.

---

- [ ] 🟥 **Step 3.5: Verify LangSmith tracing** - *Non-critical*

  **Idempotent:** Yes - Verification only, no file mutation.

  **Context:** Step 3.4 already wrote the final graph with six `@traceable` decorators. This step verifies that the decorators are present and that one run emits a trace.

  **Pre-Read Gate:**
  ```bash
  python -c "from dotenv import load_dotenv; load_dotenv(); import os; key=os.getenv('LANGCHAIN_API_KEY',''); assert key and key != 'your_langchain_api_key_here', 'LANGCHAIN_API_KEY missing or placeholder'; print('LANGCHAIN_API_KEY present')"
  ```

  **No file changes in this step.**

  **✓ Verification Test 1:**

  **Type:** Unit

  **Action:** Count exact decorators in `src/agent/graph.py`.
  ```bash
  python -c "
  from pathlib import Path
  text = Path('src/agent/graph.py').read_text()
  count = text.count('@traceable(name=')
  assert count == 6, f'Expected 6 @traceable decorators, found {count}'
  print('Decorator count OK')
  "
  ```

  **Expected:** Prints `Decorator count OK`.

  **Observe:** Terminal output.

  **✓ Verification Test 2:**

  **Type:** Unit

  **Action:** Confirm each function is wrapped.
  ```bash
  python -c "
  from src.agent.graph import (
      run_pipeline_node,
      build_rag_query_node,
      retrieve_context_node,
      llm_reasoning_node,
      self_check_node,
      assemble_alert_node,
  )
  fns = [
      run_pipeline_node,
      build_rag_query_node,
      retrieve_context_node,
      llm_reasoning_node,
      self_check_node,
      assemble_alert_node,
  ]
  assert all(hasattr(fn, '__wrapped__') for fn in fns), 'At least one node is not traceable-wrapped'
  print('Wrapped functions OK')
  "
  ```

  **Expected:** Prints `Wrapped functions OK`.

  **Observe:** Terminal output.

  **✓ Verification Test 3:**

  **Type:** Integration

  **Action:** Emit one traced run.
  ```bash
  export EVAL_NO_LLM=1
  python -c "
  from src.agent.graph import agent
  agent.invoke({'patient_id': 'infant1'})
  print('Traced run emitted')
  "
  ```

  **Expected:** Prints `Traced run emitted`.

  **Observe:** Terminal output and LangSmith UI. Within 30 seconds, one run should appear in project `neonatalguard` with six node spans.

---

## Regression Guard

**Systems at risk from this plan:**
- `src/pipeline/runner.py` - imported by the graph, must still return `PipelineResult`
- `src/knowledge/knowledge_base.py` - constructor is extended with `path=`, but host/port mode must still remain available

**Regression verification:**
| System | Pre-change behavior | Post-change verification |
|--------|---------------------|--------------------------|
| Pipeline | `NeonatalPipeline.run('infant1')` returns `PipelineResult` | `python -c "from src.pipeline.runner import NeonatalPipeline; r = NeonatalPipeline().run('infant1'); print(r.risk_level)"` |
| Knowledge base path mode | `ClinicalKnowledgeBase(path=...)` opens local store | `python -c "from pathlib import Path; from src.knowledge.knowledge_base import ClinicalKnowledgeBase; kb = ClinicalKnowledgeBase(path=str(Path('qdrant_local').resolve())); print(type(kb).__name__)"` |

## Rollback Procedure
```bash
git log --oneline

# Roll back Step 3.4
git revert <step-3.4-commit>

# Roll back Step 3.3
git revert <step-3.3-commit>

# Roll back Step 3.2
git revert <step-3.2-commit>

# Roll back Step 3.1
git revert <step-3.1-commit>

# Verify rollback:
python -c "from src.pipeline.runner import NeonatalPipeline; r = NeonatalPipeline().run('infant1'); print(r.risk_level)"
```

## Pre-Flight Checklist
| Phase | Check | How to Confirm | Status |
|-------|-------|----------------|--------|
| **Pre-flight** | `.env` keys are real | Exact Python key checks pass | ⬜ |
| | Phase 1 artifacts exist | ONNX, feature cols, TF-IDF files present | ⬜ |
| | Local Qdrant exists | `qdrant_local/meta.json` and collection open successfully | ⬜ |
| **Phase 3** | Agent package exists | `src/agent/__init__.py` present | ⬜ |
| | Schemas validate | Step 3.1 test passes | ⬜ |
| | Memory persists | Step 3.2 test passes | ⬜ |
| | Starter graph works | Step 3.3 test passes | ⬜ |
| | Full graph works in no-LLM mode | Step 3.4 test 1 passes | ⬜ |
| | Full graph works with live LLM | Step 3.4 test 2 passes | ⬜ |
| | Tracing verified | Step 3.5 tests pass | ⬜ |

## Risk Heatmap
| Step | Risk Level | What Could Go Wrong | Early Detection | Idempotent |
|------|-----------|---------------------|-----------------|------------|
| Step 3.1 | 🟢 Low | Schema typo or validator mismatch | Schema test fails immediately | Yes |
| Step 3.2 | 🟢 Low | SQLite path or persistence issue | Save/read test fails immediately | Yes |
| Step 3.3 | 🟡 Medium | State passing or memory write issue | Starter graph invoke fails | Yes |
| Step 3.4 | 🔴 High | Retrieval crashes, Groq misconfig, or schema mismatch | No-LLM or live LLM smoke tests fail | Yes |
| Step 3.5 | 🟡 Medium | Decorators missing or traces not emitted | Decorator count or wrapped-function check fails | Yes |

## Success Criteria
| Feature | Target | Verification |
|---------|--------|--------------|
| Agent package | `src/agent/` exists with typed schemas and memory | **Do:** import `src.agent.schemas` and `src.agent.memory` -> **Expect:** no errors -> **Look:** stdout |
| Starter graph | 2-node graph returns a `final_alert` and writes memory | **Do:** run Step 3.3 test -> **Expect:** `2-node graph OK` -> **Look:** stdout |
| Local retrieval | Full graph retrieves from `qdrant_local/` without Docker | **Do:** run Step 3.4 no-LLM test -> **Expect:** non-empty `rag_context` -> **Look:** assertion output |
| Live LLM reasoning | Full graph makes one real Groq call and returns a structured alert | **Do:** run Step 3.4 live test -> **Expect:** `6-node live LLM graph OK` -> **Look:** stdout |
| Protocol guardrail | Invalid action is flagged by schema | **Do:** run Step 3.1 schema test -> **Expect:** `PROTOCOL FLAG` present for invalid action -> **Look:** assertion output |
| Observability | Six `@traceable` decorators exist and one run appears in LangSmith | **Do:** run Step 3.5 tests -> **Expect:** `Decorator count OK`, `Wrapped functions OK`, and one trace in LangSmith -> **Look:** stdout and LangSmith UI |
