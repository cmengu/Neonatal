# Phase 8 Execution Plan — Emissions RAG Bridge

**Overall Progress:** `0% (0/7 steps done)`

---

## TLDR

Phase 8 builds an Emissions RAG bridge that proves the NeonatalGuard multi-agent architecture generalises to a new domain. The same supervisor → specialist → assemble pattern is applied to sustainability analysis for Unravel Carbon: a Scope analysis specialist decomposes Scope 1/2/3 emissions, a Reduction pathway specialist recommends GHG-Protocol-grounded actions, and a compliance validator checks SBTi / CSRD status. A 30-chunk GHG Protocol knowledge base indexed in a separate `emissions_knowledge` Qdrant collection serves hybrid retrieval. After this plan: `EVAL_NO_LLM=1 python emissions_rag/demo.py` prints `EmissionsAlert` for 3 synthetic companies in < 1s; `POST /emissions/assess/{company_id}` returns a JSON `EmissionsAlert` via the existing FastAPI server.

---

## Critical Decisions

- **Separate Qdrant collection** — `emissions_knowledge` lives alongside `clinical_knowledge` in the same `qdrant_local/` directory for CI/eval mode. Qdrant supports multiple *collections* per storage path; each collection is independent. **However, in live-LLM production mode, both KB singletons create separate `QdrantClient(path="qdrant_local")` instances which conflict on Qdrant's exclusive storage directory lock. Production deployment requires `QDRANT_PATH=` (Docker networked Qdrant) so both KBs share the same server connection without a file lock conflict.** CI/eval mode is unaffected because `_get_emissions_kb()` is never called in EVAL_NO_LLM=1.
- **Separate TF-IDF vectorizer** — `models/exports/emissions_tfidf.pkl` trained on GHG corpus. The clinical TF-IDF vocabulary is domain-specific and would degrade emissions retrieval.
- **`QDRANT_PATH` env var reused** — same pattern as `_get_kb()` in `graph.py`: `QDRANT_PATH=qdrant_local` for local dev, `QDRANT_PATH=""` for Docker networked mode.
- **`EVAL_NO_LLM=1` fully supported** — all three specialist agents have deterministic rule-based fallbacks. Demo and CI run without Groq key.
- **`final_alert` state key retained** — emissions graph stores final output under `"final_alert"` so the API layer can call `.get("final_alert")` identically for both agent types.
- **No changes to existing files except `api/main.py`** — all emissions code lives under `emissions_rag/`. Clinical codebase is untouched by Steps 8.1–8.6.
- **`build_kb.py` is self-contained** — embeds all 10 GHG text files as Python string literals (same pattern as `scripts/write_chunks.py`). One script writes files and indexes them.

---

## Clarification Gate

| Unknown | Required | Source | Blocking | Resolved |
|---------|----------|--------|----------|----------|
| Qdrant collection name | `emissions_knowledge` — separate from `clinical_knowledge` | Design decision | All steps | ✅ |
| TF-IDF path | `models/exports/emissions_tfidf.pkl` | Design decision | Step 8.3 | ✅ |
| `final_alert` state key | Same key as neonatal graph — avoids API layer changes | Design decision | Step 8.7 | ✅ |
| Company data source | Synthetic profiles in `emissions_rag/company_data.py` (3 companies) | Design decision | Step 8.4 | ✅ |
| CSRD threshold | > 250 employees OR > €40M turnover OR > €20M balance sheet (EU definition) | Domain knowledge | Step 8.5 | ✅ |

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
# 1. Confirm emissions_rag/ does not exist
ls emissions_rag/ 2>&1
# Expect: No such file or directory

# 2. Confirm clinical_knowledge collection exists and has 34 chunks (must not be affected)
QDRANT_PATH=qdrant_local python -c "
from src.knowledge.knowledge_base import ClinicalKnowledgeBase
kb = ClinicalKnowledgeBase(path='qdrant_local')
count = kb.client.count('clinical_knowledge').count
print(f'clinical_knowledge chunks: {count}')
assert count == 34, f'Expected 34, got {count}'
print('Clinical KB intact: OK')
"
# Expect: 34 chunks

# 3. Confirm CI gate still passes (neonatal unaffected)
EVAL_NO_LLM=1 QDRANT_PATH=qdrant_local python eval/eval_agent.py \
    --agent multi_agent 2>&1 | tail -2
# Expect: All CI gates passed.

# 4. Confirm parse_chunks is importable from build_knowledge_base (reused in Step 8.2)
python -c "from src.knowledge.build_knowledge_base import parse_chunks; print('parse_chunks: OK')"

# 5. Confirm flashrank and sentence-transformers importable (required by EmissionsKnowledgeBase in Step 8.3)
python -c "from flashrank import Ranker; from sentence_transformers import SentenceTransformer; print('flashrank+sentence-transformers: OK')"
# Expect: OK. If fails: pip install -r requirements.txt

# 6. Record baseline test count
python -m pytest tests/ --ignore=tests/test_api.py -v --tb=short 2>&1 | tail -3
# Record: __ passed
```

**Baseline Snapshot (agent fills during pre-flight):**
```
emissions_rag/:             ____  (expect: does not exist)
clinical_knowledge chunks:  ____  (expect: 34)
CI gate:                    ____  (expect: All CI gates passed.)
parse_chunks importable:    ____  (expect: OK)
flashrank+st importable:    ____  (expect: OK)
test count:                 ____
```

---

## Steps Analysis

```
Step 8.1 (scaffold + schemas + company_data) — Critical (schemas consumed by all agents)  — full code review — Idempotent: Yes
Step 8.2 (build_kb.py — write + index)       — Critical (KB must exist before agents run)  — full code review — Idempotent: Yes (deletes+recreates collection)
Step 8.3 (EmissionsKnowledgeBase)            — Critical (used by agents in 8.4+)           — full code review — Idempotent: Yes
Step 8.4 (scope_agent.py)                    — Critical (first specialist in graph)          — full code review — Idempotent: Yes
Step 8.5 (reduction_agent + compliance)      — Critical (second + third specialists)         — full code review — Idempotent: Yes
Step 8.6 (graph.py + demo.py)               — Critical (integration; triggers all agents)   — full code review — Idempotent: Yes
Step 8.7 (api/main.py extension)             — Non-critical (adds endpoint; no existing code changes) — verification only — Idempotent: Yes
```

---

## Environment Matrix

| Step | Local (no Docker) | Docker | CI | Notes |
|------|-------------------|--------|----|-------|
| 8.1 | ✅ | ✅ | ✅ | Pure Python — no services needed |
| 8.2 | ✅ | ✅ | ❌ Skip | Requires Qdrant; CI uses EVAL_NO_LLM |
| 8.3 | ✅ | ✅ | ✅ | Import check only for CI |
| 8.4 | ✅ | ✅ | ✅ | EVAL_NO_LLM=1 for CI |
| 8.5 | ✅ | ✅ | ✅ | EVAL_NO_LLM=1 for CI |
| 8.6 | ✅ | ✅ | ✅ | Demo uses EVAL_NO_LLM=1 |
| 8.7 | ✅ | ✅ | ✅ | EVAL_NO_LLM=1; no Docker needed |

---

## Phase 1 — Foundation: Schema + KB + Retrieval

**Goal:** `emissions_rag/` package exists with schemas, 30-chunk Qdrant collection, and `EmissionsKnowledgeBase` singleton.

---

- [ ] 🟥 **Step 8.1: Create package scaffold, schemas, and synthetic company data** — *Critical: schemas are the contract between all agents*

  **Idempotent:** Yes — creating new files. If directory exists, `ls emissions_rag/` in pre-flight fails and stops.

  **Context:** Three new files establish the data contracts for the entire Phase 8 system. `schemas.py` defines `ScopeAssessment` (scope specialist output), `ReductionOutput` (reduction specialist output), and `EmissionsAlert` (final alert returned by API). `company_data.py` provides 3 synthetic company emission profiles that drive the demo without real data.

  **Pre-Read Gate:**
  - Run `ls emissions_rag/ 2>&1`. Must fail with "No such file". If directory exists → STOP.
  - Run `python -c "from pydantic import BaseModel; print('pydantic OK')"`. Must print OK.

  **Files to create:**

  ```python
  # emissions_rag/__init__.py
  # (empty)
  ```

  ```python
  # emissions_rag/schemas.py
  """Pydantic schemas for the Emissions RAG multi-agent system.

  ScopeAssessment:  Scope analysis specialist output — Scope 1/2/3 breakdown.
  ReductionOutput:  Reduction pathway specialist output — recommended actions.
  EmissionsAlert:   Final alert returned by the graph and API.
  """
  from __future__ import annotations

  from datetime import datetime
  from typing import Literal

  from pydantic import BaseModel, field_validator


  class ScopeAssessment(BaseModel):
      """Structured output of the Scope Analysis specialist."""

      scope_1_tco2e: float
      scope_2_tco2e: float
      scope_3_tco2e: float
      scope_2_method: Literal["market_based", "location_based"]
      primary_sources: list[str]
      hot_spots: list[str]
      emission_intensity: float   # total tCO2e per $M revenue
      sector_delta: float         # % above/below sector average (negative = better)
      reasoning: str

      @field_validator("primary_sources", "hot_spots")
      @classmethod
      def at_least_one(cls, v: list[str]) -> list[str]:
          if not v:
              raise ValueError("must have at least one entry")
          return v


  class ReductionOutput(BaseModel):
      """Structured output of the Reduction Pathway specialist."""

      recommended_pathway: str
      near_term_actions: list[str]
      sbti_aligned: bool
      csrd_reportable: bool
      recommended_action: str
      confidence: float
      reasoning: str

      @field_validator("confidence")
      @classmethod
      def confidence_range(cls, v: float) -> float:
          if not 0.0 <= v <= 1.0:
              raise ValueError(f"confidence {v} out of range [0, 1]")
          return v


  class EmissionsAlert(BaseModel):
      """Final emissions assessment for a company — returned by graph and API."""

      company_id: str
      timestamp: datetime
      scope_breakdown: dict[str, float]
      primary_sources: list[str]
      reduction_pathway: str
      sbti_aligned: bool
      csrd_reportable: bool
      recommended_action: str
      confidence: float
      retrieved_context: list[str]
      latency_ms: float | None = None
  ```

  ```python
  # emissions_rag/company_data.py
  """Synthetic company emission profiles for demo and eval.

  Each company dict contains:
    scope_1/2/3_tco2e: tCO2e emissions per scope
    scope_2_method:     'market_based' or 'location_based'
    primary_sources:    top emission sources
    revenue_musd:       revenue in $M (for emission intensity)
    sector:             industry sector
    sector_avg_intensity: sector average tCO2e/$M revenue
    sbti_target:        True if company has SBTi-approved target
    employees:          headcount (for CSRD threshold check)
  """
  from __future__ import annotations

  _COMPANIES: dict[str, dict] = {
      "COMPANY-001": {
          "company_id": "COMPANY-001",
          "name": "Acme Tech Ltd",
          "sector": "Technology",
          "scope_1_tco2e": 1250.0,
          "scope_2_tco2e": 3847.0,
          "scope_3_tco2e": 28400.0,
          "scope_2_method": "market_based",
          "primary_sources": ["Scope 3 Cat 1 purchased goods", "Scope 2 grid electricity"],
          "revenue_musd": 150.0,
          "sector_avg_intensity": 120.0,  # tCO2e / $M revenue
          "sbti_target": False,
          "employees": 420,
      },
      "COMPANY-002": {
          "company_id": "COMPANY-002",
          "name": "Meridian Manufacturing",
          "sector": "Manufacturing",
          "scope_1_tco2e": 45000.0,
          "scope_2_tco2e": 12000.0,
          "scope_3_tco2e": 85000.0,
          "scope_2_method": "location_based",
          "primary_sources": ["Scope 1 industrial combustion", "Scope 3 Cat 1 raw materials"],
          "revenue_musd": 500.0,
          "sector_avg_intensity": 350.0,
          "sbti_target": True,
          "employees": 2100,
      },
      "COMPANY-003": {
          "company_id": "COMPANY-003",
          "name": "Verdant Retail Group",
          "sector": "Retail",
          "scope_1_tco2e": 2100.0,
          "scope_2_tco2e": 8500.0,
          "scope_3_tco2e": 125000.0,
          "scope_2_method": "market_based",
          "primary_sources": ["Scope 3 Cat 1 purchased goods", "Scope 3 Cat 11 product use"],
          "revenue_musd": 800.0,
          "sector_avg_intensity": 200.0,
          "sbti_target": False,
          "employees": 5800,
      },
  }


  def get_company_data(company_id: str) -> dict:
      """Return synthetic emission profile for a company_id.

      Raises KeyError with clear message if company_id not found.
      """
      if company_id not in _COMPANIES:
          raise KeyError(
              f"Company '{company_id}' not found. "
              f"Available: {list(_COMPANIES.keys())}"
          )
      return _COMPANIES[company_id]
  ```

  **What it does:** Establishes the data contracts (Pydantic schemas) and synthetic company emission profiles that drive the entire Phase 8 system without requiring real carbon accounting data.

  **Why this approach:** Pydantic v2 schemas with `field_validator` enforce data quality at LLM output time, identical to the clinical specialist pattern. Synthetic company data eliminates the need for external data sources while covering three distinct industry profiles (tech/manufacturing/retail).

  **Assumptions:**
  - Pydantic v2 is installed (already in requirements.txt as a dependency of fastapi/instructor).
  - `emissions_rag/` directory does not exist (confirmed by pre-flight).

  **Risks:**
  - `dict[str, float]` for `scope_breakdown` in `EmissionsAlert` requires Pydantic v2 — confirmed. If v1, use `Dict[str, float]` from `typing`.

  **Git Checkpoint:**
  ```bash
  git add emissions_rag/__init__.py emissions_rag/schemas.py emissions_rag/company_data.py
  git commit -m "step 8.1: add emissions_rag package scaffold, schemas, and synthetic company data"
  ```

  **Subtasks:**
  - [ ] 🟥 `emissions_rag/__init__.py` created (empty)
  - [ ] 🟥 `emissions_rag/schemas.py` created with 3 Pydantic models
  - [ ] 🟥 `emissions_rag/company_data.py` created with 3 company profiles
  - [ ] 🟥 Verification passes

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  python -c "
  import sys; sys.path.insert(0, '.')
  from emissions_rag.schemas import ScopeAssessment, ReductionOutput, EmissionsAlert
  from emissions_rag.company_data import get_company_data
  d = get_company_data('COMPANY-001')
  assert d['scope_1_tco2e'] == 1250.0
  assert d['sbti_target'] is False
  try:
      get_company_data('NONEXISTENT')
      assert False, 'Should have raised KeyError'
  except KeyError:
      pass
  print('PASS Step 8.1: schemas importable, company_data returns correct profiles, KeyError on unknown company')
  "
  ```

  **Pass:** `PASS Step 8.1` printed. Exit code 0.

  **Fail:**
  - `ModuleNotFoundError: emissions_rag` → `sys.path.insert(0, '.')` not working — run from repo root.
  - `ImportError: cannot import name 'ScopeAssessment'` → file not created — check `emissions_rag/schemas.py` exists.

---

- [ ] 🟥 **Step 8.2: Create `emissions_rag/build_kb.py`, write 30 GHG chunks, and index** — *Critical: KB must exist before any agent can retrieve*

  **Idempotent:** Yes — deletes and recreates `emissions_knowledge` collection on every run. Re-running overwrites cleanly.

  **Context:** Embeds all 10 GHG Protocol text files (3 chunks each = 30 total) as Python string literals, writes them to `emissions_rag/data/ghg_protocol/`, then indexes into `emissions_knowledge` Qdrant collection using the same dense+sparse vector pattern as the clinical KB. Saves `models/exports/emissions_tfidf.pkl`. The `parse_chunks()` function is imported from `src.knowledge.build_knowledge_base` — no duplication.

  **Pre-Read Gate:**
  - Run `python -c "from src.knowledge.build_knowledge_base import parse_chunks; print('OK')"`. Must print OK. If fails → `parse_chunks` was renamed, STOP.
  - Run `QDRANT_PATH=qdrant_local python -c "from src.knowledge.knowledge_base import ClinicalKnowledgeBase; kb=ClinicalKnowledgeBase(path='qdrant_local'); print(kb.client.count('clinical_knowledge').count)"`. Must print `34`. If not 34 → clinical KB is wrong, STOP.

  **File — `emissions_rag/build_kb.py`:**

  ```python
  """Build the GHG Protocol knowledge base for the Emissions RAG bridge.

  Writes 10 GHG text files to emissions_rag/data/ghg_protocol/, then indexes
  all 30 chunks into the 'emissions_knowledge' Qdrant collection with dense +
  sparse vectors. Saves models/exports/emissions_tfidf.pkl.

  Run from repo root:
      QDRANT_PATH=qdrant_local python emissions_rag/build_kb.py
      QDRANT_HOST=localhost QDRANT_PORT=6333 python emissions_rag/build_kb.py
  """
  from __future__ import annotations

  import datetime
  import logging
  import os
  import pickle
  import sys
  from pathlib import Path

  REPO_ROOT = Path(__file__).resolve().parent.parent
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

  from src.knowledge.build_knowledge_base import parse_chunks  # reuse existing parser

  CHUNKS_DIR = REPO_ROOT / "emissions_rag" / "data" / "ghg_protocol"
  EXPORTS    = REPO_ROOT / "models" / "exports"
  COLLECTION = "emissions_knowledge"

  # ── GHG Protocol text chunks ──────────────────────────────────────────────────
  # Format: paragraphs separated by blank lines.
  # Each paragraph ends with: Category: <name>. Risk tier: <HIGH|MEDIUM|LOW>.
  # parse_chunks() from build_knowledge_base.py extracts category and risk_tier.

  _GHG_FILES: dict[str, str] = {

  "scope_definitions.txt": """\
  Scope 1 emissions are direct greenhouse gas emissions from sources owned or controlled by an \
  organisation. These include combustion of fuels in boilers, furnaces, and vehicles; chemical \
  production processes; and fugitive emissions from equipment. Scope 1 is fully within \
  organisational control and represents the highest accountability for corporate emitters. \
  Science-based targets must address Scope 1 reductions through operational efficiency, \
  fuel switching, and process change.
  Category: scope_definitions. Risk tier: HIGH.

  Scope 2 emissions are indirect greenhouse gas emissions from the generation of purchased \
  electricity, steam, heat, or cooling consumed by the organisation. They are a consequence \
  of an organisation's energy use but occur at the facility of another entity. Scope 2 \
  accounting can use either the location-based method (average grid emission factors) or the \
  market-based method (contractual instruments including RECs, GOs, and PPAs). The market-based \
  method reflects actual procurement choices and is required for SBTi corporate targets.
  Category: scope_definitions. Risk tier: HIGH.

  Scope 3 emissions are all indirect emissions (not included in Scope 2) that occur in an \
  organisation's value chain, both upstream and downstream. The GHG Protocol defines 15 \
  categories: upstream categories 1–8 (purchased goods, capital goods, fuel & energy, \
  transportation, waste, business travel, employee commuting, upstream leased assets) and \
  downstream categories 9–15 (downstream transportation, processing of sold products, use of \
  sold products, end-of-life treatment, downstream leased assets, franchises, investments). \
  Scope 3 typically represents 70–90% of total corporate emissions for most sectors.
  Category: scope_definitions. Risk tier: HIGH.
  """,

  "scope2_methods.txt": """\
  The market-based Scope 2 accounting method calculates emissions using supplier-specific \
  emission factors or contractual instruments. Instruments include renewable energy certificates \
  (RECs in North America), guarantees of origin (GOs in Europe), green tariffs, and power \
  purchase agreements (PPAs). If a company has purchased RECs covering 100% of its electricity \
  consumption, it can report near-zero Scope 2 under the market-based method. SBTi requires \
  market-based Scope 2 reporting for setting and verifying 1.5°C-aligned targets.
  Category: scope2_methods. Risk tier: HIGH.

  The location-based Scope 2 accounting method uses average emission intensity factors for \
  the local grid or national grid where electricity is consumed. Factors are published annually \
  by national agencies (IEA, EPA eGRID, DEFRA). This method reflects the actual carbon content \
  of the grid and is required for reporting alongside the market-based method. Companies with \
  no contractual instruments (no RECs or PPAs) must report location-based Scope 2 as their \
  primary figure.
  Category: scope2_methods. Risk tier: MEDIUM.

  Companies must report both market-based and location-based Scope 2 figures under the GHG \
  Protocol Scope 2 Guidance (2015). The market-based figure reflects procurement choices; the \
  location-based figure reflects physical grid impact. Strategies to reduce Scope 2 include: \
  (1) procuring RECs/GOs to reduce market-based Scope 2 immediately; (2) signing long-term PPAs \
  for additionality credit; (3) on-site renewable generation for dual reduction across both \
  methods; (4) shifting load to low-carbon grid periods via demand response.
  Category: scope2_methods. Risk tier: MEDIUM.
  """,

  "scope3_categories.txt": """\
  Category 1 (Purchased Goods and Services) is typically the largest Scope 3 category for \
  most organisations. It covers all upstream emissions from production of purchased materials, \
  components, and services. Quantification uses the spend-based method (spend × emission \
  factor), the average-data method (mass/volume × emission factor), or supplier-specific \
  primary data. The GHG Protocol recommends prioritising Category 1 for supplier engagement \
  programmes because emission reductions achieved by suppliers flow directly into the buyer's \
  Scope 3 inventory.
  Category: scope3_categories. Risk tier: HIGH.

  Category 11 (Use of Sold Products) covers Scope 3 emissions from end-user operation of \
  products sold by the reporting company. It is particularly significant for energy-consuming \
  products (appliances, vehicles, electronics) and fuel/energy products. Category 11 is \
  calculated as: lifetime usage emissions per unit × units sold in the reporting year. \
  For software and digital services companies, Category 11 may include data centre energy \
  consumed by customers using the software. SBTi FLAG and SBTi for ICT sectors specify \
  mandatory Category 11 coverage for science-based targets.
  Category: scope3_categories. Risk tier: HIGH.

  Category 3 (Fuel- and Energy-Related Activities) covers upstream emissions from extraction, \
  production, and transportation of fuels and energy purchased by the company. It includes \
  transmission and distribution losses for purchased electricity (T&D losses). Category 4 \
  (Upstream Transportation and Distribution) covers third-party logistics used for inbound \
  goods and services. Category 6 (Business Travel) covers flights, hotels, and rail travel \
  by employees. These three categories are commonly material for service-sector organisations \
  that have small Scope 1 footprints but significant operational dependencies on transport \
  and purchased energy.
  Category: scope3_categories. Risk tier: MEDIUM.
  """,

  "ghg_protocol_standard.txt": """\
  The GHG Protocol Corporate Accounting and Reporting Standard is the globally accepted \
  framework for measuring and managing greenhouse gas emissions. Published in 2001 and \
  updated in 2004, it defines the principles of relevance, completeness, consistency, \
  transparency, and accuracy. The standard requires organisations to set an organisational \
  boundary (equity share or control approach) and an operational boundary (which Scopes to \
  include). All six Kyoto Protocol gases must be reported in CO2-equivalent (CO2e) using \
  100-year global warming potentials from the IPCC.
  Category: ghg_protocol. Risk tier: HIGH.

  The equity share approach to organisational boundary requires an organisation to account \
  for GHG emissions from operations according to its share of equity in the operation. The \
  financial control approach requires accounting for 100% of emissions from operations over \
  which the organisation has financial control. The operational control approach requires \
  100% of emissions from operations over which the organisation has operational control. \
  Most listed companies use the financial control approach for consistency with financial \
  reporting; the equity share approach is used where minority interests are significant.
  Category: ghg_protocol. Risk tier: MEDIUM.

  Verification and assurance of GHG inventories is required by frameworks including GRI, \
  TCFD, and CSRD. Limited assurance (negative assurance) is the minimum acceptable standard \
  and requires an auditor to confirm no material misstatements. Reasonable assurance (positive \
  assurance) provides higher confidence and is increasingly required by regulators. Verification \
  must be conducted by an accredited third party using ISO 14064-3 or equivalent standards. \
  Annual verification improves data quality through time and is recommended for all companies \
  with material Scope 3 exposure.
  Category: ghg_protocol. Risk tier: MEDIUM.
  """,

  "sbti_framework.txt": """\
  The Science Based Targets initiative (SBTi) provides a framework for companies to set \
  greenhouse gas reduction targets aligned with the Paris Agreement's goal of limiting \
  warming to 1.5°C above pre-industrial levels. The SBTi Corporate Net-Zero Standard \
  (2021) requires companies to set near-term targets (by 2030) covering at least 95% of \
  Scope 1 and 2 emissions and a significant share of Scope 3. Long-term net-zero targets \
  must achieve at least 90% absolute reduction across all scopes by no later than 2050. \
  Targets are validated and made public by the SBTi.
  Category: sbti_framework. Risk tier: HIGH.

  The 1.5°C pathway under SBTi requires companies to reduce absolute Scope 1 and 2 \
  emissions by at least 4.2% per year (linear pathway from 2020 baseline). For Scope 3, \
  a minimum 2.5% annual reduction or 90% absolute reduction by 2050 is required. Companies \
  in high-impact sectors (power, steel, cement, aviation, shipping) face sector-specific \
  decarbonisation pathways with more stringent requirements. The FLAG (Forest, Land and \
  Agriculture) supplement applies to companies with significant land-use emissions.
  Category: sbti_framework. Risk tier: HIGH.

  SBTi for SMEs provides a simplified pathway for companies with fewer than 500 employees \
  and revenues under $50M. SMEs can commit to net-zero by 2050 by signing the SME Climate \
  Commitment without immediately setting validated science-based targets. For large companies, \
  SBTi target submission requires 24 months of data, third-party verification, and \
  re-validation every 5 years. Companies that fail to meet validated targets are publicly \
  flagged by SBTi and removed from the committed companies list.
  Category: sbti_framework. Risk tier: MEDIUM.
  """,

  "csrd_requirements.txt": """\
  The EU Corporate Sustainability Reporting Directive (CSRD) entered into force in January \
  2023 and requires large EU companies (and non-EU companies with significant EU operations) \
  to report sustainability information under European Sustainability Reporting Standards \
  (ESRS). Large companies are defined as meeting two of three criteria: >250 employees, \
  >€40M net turnover, or >€20M balance sheet total. CSRD reporting starts in 2025 for \
  companies already subject to NFRD; 2026 for other large companies; 2027 for listed SMEs.
  Category: csrd_requirements. Risk tier: HIGH.

  ESRS E1 (Climate Change) under CSRD requires disclosure of: (1) transition plan aligned \
  with 1.5°C; (2) Scope 1, 2, and 3 GHG emissions with disclosure of material Scope 3 \
  categories; (3) absolute GHG reduction targets and progress; (4) climate-related risks \
  and opportunities per TCFD framework; (5) energy consumption and mix. ESRS E1 is the \
  most data-intensive CSRD topic and requires robust third-party verification. Companies \
  subject to CSRD that also have SBTi-validated targets satisfy most ESRS E1 target \
  disclosure requirements.
  Category: csrd_requirements. Risk tier: HIGH.

  Double materiality under CSRD requires companies to assess both impact materiality \
  (how the company's activities impact climate and society) and financial materiality \
  (how climate risks and opportunities affect the company's finances). A topic is material \
  if it meets either threshold. Impact materiality for climate is almost universally \
  material for companies above the CSRD threshold. Financial materiality requires a \
  company to assess physical risks (acute events, chronic change) and transition risks \
  (policy, technology, market, reputation) per TCFD taxonomy.
  Category: csrd_requirements. Risk tier: MEDIUM.
  """,

  "emission_factors.txt": """\
  DEFRA (UK Department for Environment, Food & Rural Affairs) publishes annual UK emission \
  conversion factors covering electricity, fuels, transport, and material flows. The 2024 \
  UK grid emission factor is approximately 0.207 kgCO2e/kWh (location-based). DEFRA factors \
  are widely used for UK Scope 1 and 2 reporting and are the default for UK companies \
  under SECR (Streamlined Energy and Carbon Reporting) regulations. DEFRA updates factors \
  annually; using outdated factors invalidates assurance and creates restatement obligations.
  Category: emission_factors. Risk tier: MEDIUM.

  The US EPA eGRID database provides sub-regional US electricity emission factors updated \
  annually. The national average US grid intensity is approximately 0.386 kgCO2e/kWh (2023). \
  Sub-regional factors range from <0.05 kgCO2e/kWh (Pacific Northwest hydro-heavy) to \
  >0.55 kgCO2e/kWh (coal-heavy regions). EPA also publishes Scope 1 emission factors for \
  stationary combustion (natural gas: 0.181 kgCO2e/MJ, diesel: 0.255 kgCO2e/MJ). These \
  factors are the default for US companies reporting under GHG Protocol.
  Category: emission_factors. Risk tier: MEDIUM.

  The IEA (International Energy Agency) publishes global and country-level electricity \
  emission factors annually. The 2023 global average grid intensity is 0.436 kgCO2e/kWh. \
  Country-specific factors range from near-zero (Iceland geothermal, Norway hydro) to \
  >0.7 kgCO2e/kWh (coal-dependent grids). For Scope 3 Category 3 (upstream energy), \
  well-to-gate emission factors for fossil fuels are available from the IPCC AR6 lifecycle \
  assessment appendix. Spend-based Scope 3 emission factors are available from Exiobase, \
  USEEIO, and the EPA's supply chain emission factor database.
  Category: emission_factors. Risk tier: LOW.
  """,

  "carbon_offsets.txt": """\
  Carbon offsets represent verified emission reductions or removals achieved outside an \
  organisation's value chain, used to compensate for residual emissions. Offsets are \
  categorised as avoidance/reduction (e.g., renewable energy projects preventing fossil \
  fuel use) or removal (e.g., reforestation, direct air capture). The SBTi Corporate \
  Net-Zero Standard explicitly prohibits the use of offsets to meet near-term or long-term \
  science-based targets; offsets may only contribute to 'beyond value chain mitigation' \
  beyond the 90% reduction floor.
  Category: carbon_offsets. Risk tier: HIGH.

  Quality criteria for carbon offsets include: additionality (emission reductions would not \
  have occurred without the project), permanence (reductions are not reversed), measurability \
  (verified by an accredited third party using recognised standards such as Verra VCS, Gold \
  Standard, or American Carbon Registry), no double counting (credits are uniquely owned and \
  retired). Projects with strong co-benefits (biodiversity, community development) command \
  premium prices and face less greenwashing scrutiny. Avoided deforestation (REDD+) projects \
  have faced significant permanence and additionality challenges.
  Category: carbon_offsets. Risk tier: HIGH.

  Permanence risk is the primary quality concern for nature-based carbon offsets. Forest \
  carbon is vulnerable to wildfires, drought, pests, and policy reversal. Permanence buffers \
  (typically 10–20% of credits withheld in a shared pool) are required by standards like VCS. \
  Geological storage (direct air capture stored in saline aquifers) has the highest permanence \
  (>1000 years). Enhanced weathering, biochar, and direct ocean alkalinity enhancement are \
  emerging removal approaches with variable permanence. Companies committing to net-zero \
  using removals must disclose permanence risk and reversal buffer approaches.
  Category: carbon_offsets. Risk tier: MEDIUM.
  """,

  "reduction_pathways.txt": """\
  Near-term emission reduction actions (deliverable by 2025–2027) include: (1) procuring \
  renewable electricity via RECs, GOs, or PPAs to reduce market-based Scope 2 immediately; \
  (2) fleet electrification or modal shift for Scope 1 transport emissions; (3) supplier \
  engagement and preferential sourcing for Scope 3 Category 1 hotspots; (4) energy \
  efficiency improvements in buildings and data centres for combined Scope 1 and 2 reduction. \
  Near-term actions should be prioritised by: emission reduction potential × cost-effectiveness \
  × implementation speed. RECs/PPAs typically offer the lowest cost per tonne for Scope 2.
  Category: reduction_pathways. Risk tier: HIGH.

  Long-term deep decarbonisation strategies (to achieve net-zero by 2040–2050) include: \
  (1) capital equipment replacement with zero-emission alternatives (electric boilers, heat \
  pumps, green hydrogen for industrial heat); (2) supply chain transformation — engaging top \
  50 suppliers (by spend) to set their own science-based targets; (3) product redesign to \
  reduce Category 11 (use-phase) emissions; (4) circular economy measures to reduce Category \
  1 (raw material) and Category 12 (end-of-life) emissions. Long-term strategies require \
  board-level commitment, capital allocation, and integration into 3–5 year capex planning.
  Category: reduction_pathways. Risk tier: HIGH.

  ROI-ranked emission reduction levers by typical cost-effectiveness (tCO2e per £ invested): \
  (1) energy efficiency in buildings and lighting: negative cost (saves money); (2) renewable \
  electricity procurement (RECs): £0–5/tCO2e; (3) EV fleet transition: £10–30/tCO2e; \
  (4) on-site solar PV: £15–40/tCO2e; (5) supplier engagement programmes: £20–60/tCO2e; \
  (6) green hydrogen: £80–200/tCO2e (current costs); (7) direct air capture: £200–400/tCO2e. \
  Cost curves for most technologies follow Wright's Law — costs halve with each doubling \
  of cumulative installed capacity.
  Category: reduction_pathways. Risk tier: MEDIUM.
  """,

  "lifecycle_assessment.txt": """\
  Life Cycle Assessment (LCA) quantifies environmental impacts across all stages of a \
  product's life: raw material extraction, manufacturing, transport, use, and end-of-life \
  disposal or recycling. For Scope 3 Category 1 reporting, cradle-to-gate LCA is the most \
  relevant approach — covering all upstream emissions from extraction to the point of \
  purchase. ISO 14040/14044 defines the LCA methodology; the GHG Protocol Product Standard \
  provides additional guidance specific to carbon footprinting. LCA databases include \
  ecoinvent (global), GaBi (industrial), and OpenLCA.
  Category: lifecycle_assessment. Risk tier: MEDIUM.

  Scope 3 Category 1 hotspot identification using LCA begins with a spend-based screening \
  assessment to rank purchased categories by estimated emissions. Spend × sector emission \
  intensity factor (from Exiobase or USEEIO) gives a first-pass ranking. Categories above \
  a materiality threshold (typically >1% of total Scope 3, or >10,000 tCO2e) are \
  prioritised for primary data collection from suppliers. Supplier-specific primary data \
  (bill of materials, process energy data, actual emission factors) replaces spend-based \
  estimates and reduces inventory uncertainty from ±50% to ±10%.
  Category: lifecycle_assessment. Risk tier: HIGH.

  Circular economy interventions reduce both Category 1 (upstream) and Category 12 \
  (end-of-life) Scope 3 emissions. Designing products for longevity (extended product life) \
  reduces replacement frequency and associated Category 1 manufacturing emissions. Designing \
  for disassembly enables high-quality material recovery at end-of-life, displacing virgin \
  material production (Category 1 of future products). Closed-loop recycling programmes \
  can achieve 30–60% reduction in Category 1 emissions for material-intensive products. \
  LCA is required to quantify and verify circular economy emission reduction claims.
  Category: lifecycle_assessment. Risk tier: MEDIUM.
  """,

  }  # end _GHG_FILES


  def write_text_files() -> None:
      """Write GHG Protocol text files to emissions_rag/data/ghg_protocol/."""
      CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
      for filename, content in _GHG_FILES.items():
          (CHUNKS_DIR / filename).write_text(content)
          logging.info("Wrote %s", filename)
      logging.info("Wrote %d text files to %s", len(_GHG_FILES), CHUNKS_DIR)


  def build() -> None:
      """Index all GHG chunks into Qdrant emissions_knowledge collection."""
      qdrant_path = os.getenv("QDRANT_PATH")
      if qdrant_path:
          client = QdrantClient(path=qdrant_path)
          logging.info("Using on-disk Qdrant at: %s", qdrant_path)
      else:
          host = os.getenv("QDRANT_HOST", "localhost")
          port = int(os.getenv("QDRANT_PORT", "6333"))
          client = QdrantClient(host=host, port=port)
          logging.info("Using networked Qdrant at %s:%d", host, port)

      dense_model = SentenceTransformer("all-MiniLM-L6-v2")

      chunks: list[dict] = []
      for txt_file in sorted(CHUNKS_DIR.glob("*.txt")):
          file_chunks = parse_chunks(txt_file)
          logging.info("  %s: %d chunks", txt_file.name, len(file_chunks))
          chunks.extend(file_chunks)
      logging.info("Total chunks: %d", len(chunks))

      if client.collection_exists(COLLECTION):
          client.delete_collection(COLLECTION)
          logging.info("Deleted existing '%s'", COLLECTION)

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
          sp = tfidf.transform([chunk["text"]])
          client.upsert(
              collection_name=COLLECTION,
              points=[PointStruct(
                  id=i,
                  vector={
                      "dense": dense_vec,
                      "sparse": SparseVector(
                          indices=sp.indices.tolist(),
                          values=sp.data.tolist(),
                      ),
                  },
                  payload={
                      "text": chunk["text"],
                      "category": chunk["category"],
                      "risk_tier": chunk["risk_tier"],
                      "embedding_model": "all-MiniLM-L6-v2",
                      "indexed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  },
              )],
          )

      EXPORTS.mkdir(parents=True, exist_ok=True)
      with open(EXPORTS / "emissions_tfidf.pkl", "wb") as f:
          pickle.dump(tfidf, f)

      count = client.count(COLLECTION).count
      logging.info("Done. %d chunks indexed.", count)
      logging.info("TF-IDF saved: %s/emissions_tfidf.pkl", EXPORTS)
      assert count == 30, f"Expected 30 chunks, got {count}"
      logging.info("Chunk count assertion passed: 30")


  if __name__ == "__main__":
      write_text_files()
      build()
  ```

  **Run the script immediately after creating it:**
  ```bash
  QDRANT_PATH=qdrant_local python emissions_rag/build_kb.py
  ```
  Expect log output ending with `Chunk count assertion passed: 30`.

  **What it does:** Writes 10 GHG Protocol text files (30 chunks total) then indexes them into a new `emissions_knowledge` Qdrant collection with dense+sparse vectors and a separate TF-IDF vectorizer.

  **Why this approach:** Reusing `parse_chunks()` from the clinical build script ensures identical chunk format handling. Embedding text files directly in the Python script (like `scripts/write_chunks.py`) makes the build reproducible without external file dependencies.

  **Assumptions:**
  - `qdrant_local/` directory exists (confirmed by pre-flight).
  - `sentence-transformers`, `qdrant-client`, `sklearn` are installed (all in requirements.txt).
  - `parse_chunks()` from `build_knowledge_base.py` handles the `Category: X. Risk tier: Y.` footer format.

  **Risks:**
  - Qdrant file lock from existing `ClinicalKnowledgeBase` singleton → run from a fresh Python process (not inside another script that imported `_get_kb()`). Mitigation: run as standalone script.
  - `clinical_knowledge` collection is NOT deleted — only `emissions_knowledge`. Verify clinical KB still has 34 chunks after run.

  **Git Checkpoint:**
  ```bash
  git add emissions_rag/build_kb.py emissions_rag/data/
  git commit -m "step 8.2: add build_kb.py with 30 GHG chunks; index emissions_knowledge collection"
  ```

  **Subtasks:**
  - [ ] 🟥 `emissions_rag/build_kb.py` created
  - [ ] 🟥 Script runs without error: `QDRANT_PATH=qdrant_local python emissions_rag/build_kb.py`
  - [ ] 🟥 `emissions_tfidf.pkl` exists in `models/exports/`
  - [ ] 🟥 Verification passes

  **✓ Verification Test:**

  **Type:** Integration

  **Action:**
  ```bash
  QDRANT_PATH=qdrant_local python -c "
  from src.knowledge.knowledge_base import ClinicalKnowledgeBase
  from qdrant_client import QdrantClient

  # Verify emissions_knowledge has 30 chunks
  client = QdrantClient(path='qdrant_local')
  emissions_count = client.count('emissions_knowledge').count
  clinical_count  = client.count('clinical_knowledge').count
  assert emissions_count == 30, f'Expected 30 emissions chunks, got {emissions_count}'
  assert clinical_count  == 34, f'Clinical KB disturbed: expected 34, got {clinical_count}'
  print(f'PASS Step 8.2: emissions_knowledge={emissions_count} chunks, clinical_knowledge={clinical_count} chunks')

  # Verify TF-IDF saved
  from pathlib import Path
  assert Path('models/exports/emissions_tfidf.pkl').exists(), 'emissions_tfidf.pkl not found'
  print('PASS Step 8.2: emissions_tfidf.pkl exists')
  "
  ```

  **Pass:** Both `PASS Step 8.2` lines printed. Exit code 0.

  **Fail:**
  - `emissions_count != 30` → build script exited early or assertion failed — re-read build log.
  - `clinical_count != 34` → clinical KB was accidentally deleted — re-run `QDRANT_PATH=qdrant_local python src/knowledge/build_knowledge_base.py` to rebuild.
  - `emissions_tfidf.pkl not found` → build script failed before pickle save — check `models/exports/` is writable.

---

- [ ] 🟥 **Step 8.3: Create `emissions_rag/knowledge_base.py`** — *Critical: singleton used by all specialist agents*

  **Idempotent:** Yes — new file.

  **Context:** `EmissionsKnowledgeBase` follows the same pattern as `ClinicalKnowledgeBase` but uses the `emissions_knowledge` collection and `emissions_tfidf.pkl`. The module-level `_get_emissions_kb()` singleton prevents reloading the 90MB SentenceTransformer model on every agent call.

  **Pre-Read Gate:**
  - Run `python -c "from pathlib import Path; assert Path('models/exports/emissions_tfidf.pkl').exists(); print('OK')"`. Must print OK. If fails → run Step 8.2 first.

  **File — `emissions_rag/knowledge_base.py`:**

  ```python
  """EmissionsKnowledgeBase: hybrid dense+sparse retrieval for GHG Protocol knowledge.

  Mirrors ClinicalKnowledgeBase from src/knowledge/knowledge_base.py but uses the
  'emissions_knowledge' Qdrant collection and models/exports/emissions_tfidf.pkl.

  Usage (local dev):
      kb = EmissionsKnowledgeBase(path=str(REPO_ROOT / "qdrant_local"))
      chunks = kb.query_by_category("Scope 3 Category 1 hotspots", categories=["scope3_categories"], n=3)

  Usage (Docker):
      kb = EmissionsKnowledgeBase()  # reads QDRANT_HOST / QDRANT_PORT env vars
  """
  from __future__ import annotations

  import os
  import pickle
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

  REPO_ROOT = Path(__file__).resolve().parent.parent

  # Module-level singleton — avoids reloading SentenceTransformer on every call.
  _KB: "EmissionsKnowledgeBase | None" = None


  class EmissionsKnowledgeBase:
      """Hybrid retrieval pipeline for the emissions_knowledge Qdrant collection."""

      COLLECTION = "emissions_knowledge"

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

          tfidf_path = REPO_ROOT / "models" / "exports" / "emissions_tfidf.pkl"
          if not tfidf_path.exists():
              raise FileNotFoundError(
                  f"Emissions TF-IDF not found: {tfidf_path}. "
                  "Run: QDRANT_PATH=qdrant_local python emissions_rag/build_kb.py"
              )
          with open(tfidf_path, "rb") as f:
              self.tfidf = pickle.load(f)

      def query_by_category(
          self,
          text: str,
          categories: list[str],
          n: int = 3,
      ) -> list[str]:
          """Hybrid retrieval filtered to specific GHG KB categories.

          Valid categories:
              'scope_definitions', 'scope2_methods', 'scope3_categories',
              'ghg_protocol', 'sbti_framework', 'csrd_requirements',
              'emission_factors', 'carbon_offsets', 'reduction_pathways',
              'lifecycle_assessment'
          """
          dense_vec = self.dense_model.encode(text).tolist()
          sp = self.tfidf.transform([text])
          sparse_vec = SparseVector(
              indices=sp.indices.tolist(),
              values=sp.data.tolist(),
          )
          category_filter = Filter(
              should=[
                  FieldCondition(key="category", match=MatchValue(value=cat))
                  for cat in categories
              ]
          )
          results = self.client.query_points(
              collection_name=self.COLLECTION,
              prefetch=[
                  Prefetch(query=dense_vec, using="dense", filter=category_filter, limit=10),
                  Prefetch(query=sparse_vec, using="sparse", filter=category_filter, limit=10),
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
          return [r["text"] for r in reranked[:n]]


  def _get_emissions_kb() -> EmissionsKnowledgeBase:
      """Return the EmissionsKnowledgeBase singleton, initialising on first call.

      QDRANT_PATH env var routing:
        unset or non-empty → on-disk path (local dev)
        empty string ("")  → networked Qdrant via QDRANT_HOST/QDRANT_PORT (Docker)
      """
      global _KB
      if _KB is None:
          _qdrant_path = os.getenv("QDRANT_PATH")
          if _qdrant_path is not None and not _qdrant_path:
              _KB = EmissionsKnowledgeBase()
          else:
              _KB = EmissionsKnowledgeBase(
                  path=_qdrant_path or str(REPO_ROOT / "qdrant_local")
              )
      return _KB
  ```

  **What it does:** Provides the hybrid RAG retrieval interface for the GHG Protocol knowledge base, with the same dense+sparse+rerank pipeline as the clinical KB.

  **Why this approach:** Separate class (not a subclass) avoids coupling to clinical KB internals. The singleton pattern matches `_get_kb()` in `graph.py` to prevent repeated SentenceTransformer loads.

  **Git Checkpoint:**
  ```bash
  git add emissions_rag/knowledge_base.py
  git commit -m "step 8.3: add EmissionsKnowledgeBase with singleton _get_emissions_kb()"
  ```

  **✓ Verification Test:**

  **Type:** Integration

  **Action:**
  ```bash
  QDRANT_PATH=qdrant_local python -c "
  import os; os.environ['QDRANT_PATH'] = 'qdrant_local'
  from emissions_rag.knowledge_base import _get_emissions_kb
  kb = _get_emissions_kb()
  chunks = kb.query_by_category(
      'Scope 3 Category 1 purchased goods supplier engagement',
      categories=['scope3_categories', 'reduction_pathways'],
      n=2,
  )
  assert len(chunks) == 2, f'Expected 2 chunks, got {len(chunks)}'
  assert len(chunks[0]) > 50, 'Chunk text suspiciously short'
  # Same singleton on second call
  kb2 = _get_emissions_kb()
  assert kb is kb2, 'Singleton not working — new instance created on second call'
  print(f'PASS Step 8.3: EmissionsKnowledgeBase returns {len(chunks)} chunks, singleton OK')
  print(f'  First chunk preview: {chunks[0][:80]}...')
  "
  ```

  **Pass:** `PASS Step 8.3` printed. Exit code 0.

  **Fail:**
  - `FileNotFoundError: emissions_tfidf.pkl` → Step 8.2 not complete — re-run `build_kb.py`.
  - `qdrant_client.qdrant_client.QdrantClientUnexpectedResponseError: Not found: Collection emissions_knowledge doesn't exist` → build_kb.py didn't index — re-run build.
  - `len(chunks) == 0` → category filter matched nothing — verify text file categories match `query_by_category` category strings.

---

## Phase 2 — Agents + Graph

**Goal:** Three specialist agents, a supervisor graph, and a working demo all pass `EVAL_NO_LLM=1` without Groq key.

---

- [ ] 🟥 **Step 8.4: Create `emissions_rag/agents/scope_agent.py`** — *Critical: first specialist; output consumed by reduction_agent*

  **Idempotent:** Yes — new file.

  **Context:** The Scope analysis specialist decomposes company Scope 1/2/3 emissions, computes emission intensity vs sector average, and identifies hot spots. In `EVAL_NO_LLM` mode it uses `_rule_based_scope()`. In live mode it retrieves from `scope_definitions`, `scope2_methods`, `scope3_categories` categories and calls Groq.

  **Pre-Read Gate:**
  - Run `ls emissions_rag/agents/ 2>&1`. Must fail (directory doesn't exist). If exists → check if step already done.
  - Run `python -c "from emissions_rag.schemas import ScopeAssessment; print('OK')"`. Must print OK.

  **Files to create:**

  ```python
  # emissions_rag/agents/__init__.py
  # (empty)
  ```

  ```python
  # emissions_rag/agents/scope_agent.py
  """Scope Analysis specialist node.

  Decomposes company emissions into Scope 1/2/3, computes emission intensity
  vs sector average, and identifies hot spots.

  In EVAL_NO_LLM mode: returns deterministic ScopeAssessment from company_data
  without any Groq call — CI gate works without API key.

  Retrieves from: 'scope_definitions', 'scope2_methods', 'scope3_categories'.
  """
  from __future__ import annotations

  import os

  from langsmith import traceable

  from emissions_rag.schemas import ScopeAssessment

  _SCOPE_CATEGORIES = ["scope_definitions", "scope2_methods", "scope3_categories"]


  def _rule_based_scope(data: dict) -> ScopeAssessment:
      """Deterministic scope assessment for EVAL_NO_LLM mode."""
      s1 = data["scope_1_tco2e"]
      s2 = data["scope_2_tco2e"]
      s3 = data["scope_3_tco2e"]
      total = s1 + s2 + s3
      revenue = max(data.get("revenue_musd", 1.0), 0.001)
      intensity = round(total / revenue, 2)
      sector_avg = data.get("sector_avg_intensity", 100.0)
      sector_delta = round((intensity - sector_avg) / max(sector_avg, 0.001) * 100.0, 1)

      hot_spots: list[str] = []
      for scope_label, val in [("Scope 3", s3), ("Scope 2", s2), ("Scope 1", s1)]:
          if total > 0 and val / total > 0.30:
              hot_spots.append(
                  f"{scope_label}: {val:.0f} tCO2e ({100 * val / total:.0f}% of total)"
              )

      return ScopeAssessment(
          scope_1_tco2e=s1,
          scope_2_tco2e=s2,
          scope_3_tco2e=s3,
          scope_2_method=data.get("scope_2_method", "market_based"),
          primary_sources=data.get("primary_sources", ["unspecified"]),
          hot_spots=hot_spots or [f"No single scope >30% of total ({total:.0f} tCO2e)"],
          emission_intensity=intensity,
          sector_delta=sector_delta,
          reasoning=(
              f"Rule-based: total {total:.0f} tCO2e at {intensity:.1f} tCO2e/$M revenue "
              f"({sector_delta:+.1f}% vs sector average of {sector_avg:.1f})."
          ),
      )


  @traceable(name="scope_agent_node")
  def scope_agent_node(state: dict) -> dict:
      """Decompose company emissions into Scope 1/2/3 and identify hot spots."""
      data = state["company_data"]

      if os.getenv("EVAL_NO_LLM", "").lower() in {"1", "true", "yes"}:
          return {"scope_assessment": _rule_based_scope(data)}

      from src.agent.graph import _get_groq
      from emissions_rag.knowledge_base import _get_emissions_kb

      s1, s2, s3 = data["scope_1_tco2e"], data["scope_2_tco2e"], data["scope_3_tco2e"]
      total = s1 + s2 + s3
      query = (
          f"Scope emissions decomposition and intensity: Scope 1={s1:.0f}, "
          f"Scope 2={s2:.0f}, Scope 3={s3:.0f} tCO2e. "
          f"Sector: {data.get('sector', 'unknown')}. "
          f"Scope 2 method: {data.get('scope_2_method', 'market_based')}."
      )
      chunks = _get_emissions_kb().query_by_category(query, categories=_SCOPE_CATEGORIES, n=3)
      context = "\n\n".join(chunks)

      prompt = f"""You are a GHG emissions analyst. Decompose and interpret these company emissions.

  Company: {data.get('company_id', 'unknown')} | Sector: {data.get('sector', 'unknown')}
  Revenue: ${data.get('revenue_musd', 0):.0f}M
  Scope 1: {s1:.0f} tCO2e (direct emissions)
  Scope 2: {s2:.0f} tCO2e (purchased electricity, {data.get('scope_2_method', 'market_based')})
  Scope 3: {s3:.0f} tCO2e (value chain)
  Total: {total:.0f} tCO2e
  Primary sources: {', '.join(data.get('primary_sources', []))}
  Sector average intensity: {data.get('sector_avg_intensity', 'unknown')} tCO2e/$M revenue

  GHG Protocol reference:
  {context}

  Classify the scope breakdown, compute emission intensity, identify hot spots, and flag any
  scope 2 method concerns. Output a ScopeAssessment."""

      result: ScopeAssessment = _get_groq().chat.completions.create(
          model="llama-3.3-70b-versatile",
          response_model=ScopeAssessment,
          messages=[{"role": "user", "content": prompt}],
          temperature=0.1,
          max_retries=3,
      )
      return {"scope_assessment": result}
  ```

  **What it does:** Decomposes emissions into Scope 1/2/3, computes intensity vs sector average, identifies hot spots, and flags scope 2 method issues. Both rule-based (CI) and Groq (live) paths return a `ScopeAssessment`.

  **Git Checkpoint:**
  ```bash
  git add emissions_rag/agents/__init__.py emissions_rag/agents/scope_agent.py
  git commit -m "step 8.4: add scope_agent.py — Scope 1/2/3 decomposition specialist"
  ```

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  EVAL_NO_LLM=1 QDRANT_PATH=qdrant_local python -c "
  import os
  os.environ['EVAL_NO_LLM'] = '1'
  os.environ['QDRANT_PATH'] = 'qdrant_local'
  from emissions_rag.company_data import get_company_data
  from emissions_rag.agents.scope_agent import scope_agent_node, _rule_based_scope

  for cid in ['COMPANY-001', 'COMPANY-002', 'COMPANY-003']:
      data = get_company_data(cid)
      result = scope_agent_node({'company_data': data})
      sa = result['scope_assessment']
      assert sa.scope_1_tco2e > 0
      assert sa.emission_intensity > 0
      assert len(sa.hot_spots) >= 1
      total = sa.scope_1_tco2e + sa.scope_2_tco2e + sa.scope_3_tco2e
      print(f'{cid}: {total:.0f} tCO2e, intensity={sa.emission_intensity}, delta={sa.sector_delta:+.1f}%')

  print('PASS Step 8.4: scope_agent_node returns valid ScopeAssessment for all 3 companies')
  "
  ```

  **Pass:** Three company lines printed then `PASS Step 8.4`. Exit code 0.

  **Fail:**
  - `ValidationError` on `ScopeAssessment` → rule-based function produces invalid data — check field constraints.
  - `KeyError: scope_1_tco2e` → `company_data.py` missing required key — check Step 8.1.

---

- [ ] 🟥 **Step 8.5: Create reduction specialist and compliance validator** — *Critical: last two specialists in the graph chain*

  **Idempotent:** Yes — new files.

  **Context:** `reduction_agent.py` receives `ScopeAssessment` from the previous node and recommends GHG-Protocol-grounded reduction pathways, SBTi alignment status, and CSRD reportability. `compliance_agent.py` is pure logic (no LLM, no retrieval) — it validates the `ReductionOutput` against company metadata (employee count, sbti_target flag) and applies protocol corrections, then assembles `EmissionsAlert`.

  **Pre-Read Gate:**
  - Run `python -c "from emissions_rag.agents.scope_agent import scope_agent_node; print('OK')"`. Must print OK. If fails → Step 8.4 not complete.

  **File — `emissions_rag/agents/reduction_agent.py`:**

  ```python
  """Reduction Pathway specialist node.

  Receives ScopeAssessment from scope_agent and recommends reduction pathways
  grounded in GHG Protocol and SBTi frameworks.

  In EVAL_NO_LLM mode: returns deterministic ReductionOutput based on
  emission intensity and SBTi target status.

  Retrieves from: 'sbti_framework', 'reduction_pathways', 'carbon_offsets'.
  """
  from __future__ import annotations

  import os

  from langsmith import traceable

  from emissions_rag.schemas import ReductionOutput

  _REDUCTION_CATEGORIES = ["sbti_framework", "reduction_pathways", "carbon_offsets"]


  def _rule_based_reduction(data: dict, sa) -> ReductionOutput:
      """Deterministic reduction output for EVAL_NO_LLM mode."""
      sbti_aligned = data.get("sbti_target", False)
      # CSRD: large company = >250 employees OR >€40M turnover OR >€20M balance sheet.
      # Proxy: employees > 250 OR revenue_musd > 40.
      csrd_reportable = (
          data.get("employees", 0) > 250
          or data.get("revenue_musd", 0) > 40
      )

      # Recommend based on scope hot spot and intensity
      hot_spot = sa.hot_spots[0] if sa.hot_spots else "Scope 3"
      if "Scope 3" in hot_spot:
          pathway = (
              "Supplier engagement programme for Scope 3 Category 1 hot spots, "
              "complemented by renewable electricity PPA to eliminate Scope 2."
          )
          near_term = [
              "Conduct spend-based Scope 3 screening to rank Category 1 suppliers",
              "Issue supplier questionnaire to top 20 suppliers by spend",
              "Procure RECs or sign PPA to reduce market-based Scope 2 to zero",
          ]
          action = "Set science-based target aligned with 1.5°C and launch supplier engagement"
      elif "Scope 1" in hot_spot:
          pathway = (
              "Fleet electrification and fuel switching for Scope 1 reduction, "
              "energy efficiency audit for buildings and process equipment."
          )
          near_term = [
              "Commission energy audit to identify efficiency opportunities",
              "Begin EV fleet transition for company vehicles",
              "Evaluate green hydrogen feasibility for industrial heat processes",
          ]
          action = "Set SBTi near-term target and begin Scope 1 operational decarbonisation"
      else:
          pathway = (
              "Renewable electricity procurement (RECs or on-site PPA) to reduce Scope 2, "
              "combined with operational energy efficiency improvements."
          )
          near_term = [
              "Procure RECs to reduce market-based Scope 2 immediately",
              "Negotiate long-term PPA for additionality credit",
              "Install sub-metering to identify energy efficiency opportunities",
          ]
          action = "Eliminate Scope 2 via renewable procurement and commit to SBTi"

      confidence = 0.80 if sbti_aligned else 0.70

      return ReductionOutput(
          recommended_pathway=pathway,
          near_term_actions=near_term,
          sbti_aligned=sbti_aligned,
          csrd_reportable=csrd_reportable,
          recommended_action=action,
          confidence=confidence,
          reasoning=(
              f"Rule-based: hot spot={hot_spot[:40]}, "
              f"sbti_aligned={sbti_aligned}, csrd_reportable={csrd_reportable}."
          ),
      )


  @traceable(name="reduction_agent_node")
  def reduction_agent_node(state: dict) -> dict:
      """Recommend reduction pathway grounded in GHG Protocol and SBTi."""
      data = state["company_data"]
      sa   = state["scope_assessment"]

      if os.getenv("EVAL_NO_LLM", "").lower() in {"1", "true", "yes"}:
          return {"reduction_output": _rule_based_reduction(data, sa)}

      from src.agent.graph import _get_groq
      from emissions_rag.knowledge_base import _get_emissions_kb

      query = (
          f"Emission reduction pathway for {data.get('sector', 'unknown')} company. "
          f"Hot spots: {', '.join(sa.hot_spots[:2])}. "
          f"Intensity {sa.emission_intensity:.1f} tCO2e/$M ({sa.sector_delta:+.1f}% vs sector)."
      )
      chunks = _get_emissions_kb().query_by_category(
          query, categories=_REDUCTION_CATEGORIES, n=3
      )
      context = "\n\n".join(chunks)

      prompt = f"""You are a corporate sustainability strategist specialising in GHG reduction pathways.

  Company: {data.get('company_id')} | Sector: {data.get('sector')}
  SBTi target committed: {data.get('sbti_target', False)}
  Employees: {data.get('employees', 'unknown')} | Revenue: ${data.get('revenue_musd', 0):.0f}M

  Scope Analysis:
  Scope 1: {sa.scope_1_tco2e:.0f} tCO2e | Scope 2: {sa.scope_2_tco2e:.0f} tCO2e ({sa.scope_2_method}) | Scope 3: {sa.scope_3_tco2e:.0f} tCO2e
  Emission intensity: {sa.emission_intensity:.1f} tCO2e/$M ({sa.sector_delta:+.1f}% vs sector)
  Hot spots: {', '.join(sa.hot_spots)}

  GHG Protocol and SBTi reference:
  {context}

  Recommend a reduction pathway, near-term actions, and assess SBTi alignment and CSRD reportability.
  Output a ReductionOutput."""

      result: ReductionOutput = _get_groq().chat.completions.create(
          model="llama-3.3-70b-versatile",
          response_model=ReductionOutput,
          messages=[{"role": "user", "content": prompt}],
          temperature=0.1,
          max_retries=3,
      )
      return {"reduction_output": result}
  ```

  **File — `emissions_rag/agents/compliance_agent.py`:**

  ```python
  """GHG Protocol / SBTi Compliance validator — pure logic, no LLM, no retrieval.

  Validates ReductionOutput against GHG Protocol rules and assembles EmissionsAlert.
  Runs last in the emissions graph chain. Always sets final_alert in state.

  Rules enforced:
    - Companies with sbti_target=True but csrd_reportable=False: flag inconsistency
      (SBTi-committed companies are almost always CSRD-reportable).
    - Companies with sbti_aligned=False and emission_intensity > 2× sector average:
      escalate recommended_action to include SBTi commitment language.
    - Offset language in recommended_action: flag if offsets suggested as primary pathway
      (SBTi prohibits offsets from counting toward near-term targets).
  """
  from __future__ import annotations

  from datetime import datetime

  from langsmith import traceable

  from emissions_rag.schemas import EmissionsAlert


  @traceable(name="compliance_agent_node")
  def compliance_agent_node(state: dict) -> dict:
      """Validate reduction output and assemble final EmissionsAlert. Pure logic."""
      data = state["company_data"]
      sa   = state["scope_assessment"]
      ro   = state["reduction_output"]

      action = ro.recommended_action

      # Rule 1: SBTi-committed companies are almost always CSRD-reportable.
      # If sbti_target=True but csrd_reportable=False, flag the inconsistency.
      if data.get("sbti_target") and not ro.csrd_reportable:
          action = (
              f"[COMPLIANCE FLAG: SBTi-committed company flagged as not CSRD-reportable "
              f"— verify employee count and revenue thresholds] {action}"
          )

      # Rule 2: High-intensity non-SBTi companies need stronger target language.
      sector_avg = data.get("sector_avg_intensity", 100.0)
      if not ro.sbti_aligned and sector_avg > 0 and sa.emission_intensity > 2 * sector_avg:
          action = (
              f"[COMPLIANCE: Emission intensity {sa.emission_intensity:.0f} tCO2e/$M is "
              f">{2 * sector_avg:.0f} (2× sector average) — SBTi commitment required] {action}"
          )

      # Rule 3: Offsets are not a substitute for SBTi near-term target reductions.
      if "offset" in action.lower() and not ro.sbti_aligned:
          action = (
              f"[COMPLIANCE FLAG: offsets cannot substitute for SBTi near-term reductions] "
              f"{action}"
          )

      total = sa.scope_1_tco2e + sa.scope_2_tco2e + sa.scope_3_tco2e
      scope_breakdown = {
          "scope_1": sa.scope_1_tco2e,
          "scope_2": sa.scope_2_tco2e,
          "scope_3": sa.scope_3_tco2e,
          "total":   total,
      }

      alert = EmissionsAlert(
          company_id=data["company_id"],
          timestamp=datetime.now(),
          scope_breakdown=scope_breakdown,
          primary_sources=sa.primary_sources,
          reduction_pathway=ro.recommended_pathway,
          sbti_aligned=ro.sbti_aligned,
          csrd_reportable=ro.csrd_reportable,
          recommended_action=action,
          confidence=ro.confidence,
          retrieved_context=[],  # populated by specialist nodes' RAG chunks in live mode
      )

      return {"final_alert": alert}
  ```

  **What it does:** `reduction_agent.py` recommends GHG-Protocol-grounded reduction pathways grounded in retrieved KB chunks. `compliance_agent.py` applies three pure-logic protocol rules and assembles the final `EmissionsAlert`.

  **Why this approach:** Compliance validation is pure logic (no hallucination risk from LLM), mirroring `protocol_agent.py` in the neonatal graph. Keeping assembly in `compliance_agent_node` means the graph always has a `final_alert` in state regardless of Groq availability.

  **Git Checkpoint:**
  ```bash
  git add emissions_rag/agents/reduction_agent.py emissions_rag/agents/compliance_agent.py
  git commit -m "step 8.5: add reduction_agent and compliance_agent (GHG Protocol validator + alert assembly)"
  ```

  **✓ Verification Test:**

  **Type:** Unit

  **Action:**
  ```bash
  EVAL_NO_LLM=1 QDRANT_PATH=qdrant_local python -c "
  import os
  os.environ['EVAL_NO_LLM'] = '1'
  os.environ['QDRANT_PATH'] = 'qdrant_local'
  from emissions_rag.company_data import get_company_data
  from emissions_rag.agents.scope_agent import scope_agent_node
  from emissions_rag.agents.reduction_agent import reduction_agent_node
  from emissions_rag.agents.compliance_agent import compliance_agent_node

  data = get_company_data('COMPANY-001')
  state = {'company_data': data}
  state.update(scope_agent_node(state))
  state.update(reduction_agent_node(state))
  state.update(compliance_agent_node(state))

  alert = state['final_alert']
  assert alert.company_id == 'COMPANY-001'
  assert alert.scope_breakdown['scope_3'] == 28400.0
  assert alert.recommended_action != ''
  assert isinstance(alert.sbti_aligned, bool)
  assert isinstance(alert.csrd_reportable, bool)
  print(f'PASS Step 8.5: full pipeline produces EmissionsAlert')
  print(f'  SBTi aligned: {alert.sbti_aligned}, CSRD reportable: {alert.csrd_reportable}')
  print(f'  Action: {alert.recommended_action[:80]}...')
  "
  ```

  **Pass:** `PASS Step 8.5` printed. Exit code 0.

  **Fail:**
  - `KeyError: scope_assessment` in `reduction_agent_node` → `scope_agent_node` output not merged into state — check `state.update(...)` pattern.
  - `ValidationError` on `EmissionsAlert` → `compliance_agent.py` passing wrong types — check `scope_breakdown` dict values are floats.

---

- [ ] 🟥 **Step 8.6: Create supervisor graph and demo script** — *Critical: integration; triggers all agents in sequence*

  **Idempotent:** Yes — new files.

  **Context:** `emissions_rag/graph.py` wires the four nodes (supervisor → scope → reduction → compliance) using LangGraph `StateGraph`. The supervisor node loads company data. `emissions_rag/demo.py` runs all 3 synthetic companies under `EVAL_NO_LLM=1` and prints a summary, proving end-to-end < 1s latency without Groq.

  **Pre-Read Gate:**
  - Run `python -c "from emissions_rag.agents.compliance_agent import compliance_agent_node; print('OK')"`. Must print OK. If fails → Step 8.5 not complete.
  - Run `python -c "from langgraph.graph import StateGraph, END; print('OK')"`. Must print OK.

  **File — `emissions_rag/graph.py`:**

  ```python
  """LangGraph supervisor graph for the Emissions RAG multi-agent system.

  Graph flow:
      emissions_supervisor → scope_agent → reduction_agent → compliance_agent → END

  The compliance_agent assembles the final EmissionsAlert and stores it under
  'final_alert' in state — same key as the neonatal graph for API layer reuse.

  Usage:
      from emissions_rag.graph import emissions_agent
      result = emissions_agent.invoke({"company_id": "COMPANY-001"})
      alert = result["final_alert"]
  """
  from __future__ import annotations

  from typing import Optional, TypedDict

  from langgraph.graph import END, StateGraph
  from langsmith import traceable

  from emissions_rag.agents.compliance_agent import compliance_agent_node
  from emissions_rag.agents.reduction_agent import reduction_agent_node
  from emissions_rag.agents.scope_agent import scope_agent_node
  from emissions_rag.schemas import EmissionsAlert, ReductionOutput, ScopeAssessment


  class EmissionsState(TypedDict):
      """State schema for the emissions multi-agent graph."""

      company_id: str
      company_data: Optional[dict]
      scope_assessment: Optional[ScopeAssessment]
      reduction_output: Optional[ReductionOutput]
      final_alert: Optional[EmissionsAlert]
      error: Optional[str]


  @traceable(name="emissions_supervisor_node")
  def emissions_supervisor_node(state: dict) -> dict:
      """Load company emission data and initialise graph state."""
      from emissions_rag.company_data import get_company_data
      company_data = get_company_data(state["company_id"])
      return {"company_data": company_data}


  def build_emissions_graph():
      """Compile the 4-node emissions multi-agent graph."""
      g = StateGraph(EmissionsState)

      g.add_node("supervisor", emissions_supervisor_node)
      g.add_node("scope",      scope_agent_node)
      g.add_node("reduction",  reduction_agent_node)
      g.add_node("compliance", compliance_agent_node)

      g.set_entry_point("supervisor")
      g.add_edge("supervisor", "scope")
      g.add_edge("scope",      "reduction")
      g.add_edge("reduction",  "compliance")
      g.add_edge("compliance", END)

      return g.compile()


  emissions_agent = build_emissions_graph()
  ```

  **File — `emissions_rag/demo.py`:**

  ```python
  """Emissions RAG demo — runs all 3 synthetic companies under EVAL_NO_LLM=1.

  Demonstrates end-to-end EmissionsAlert generation without Groq API key.
  Run from repo root:
      EVAL_NO_LLM=1 QDRANT_PATH=qdrant_local python emissions_rag/demo.py
  """
  import os
  import time

  # Must be set before importing graph (graph module loads specialists at import time).
  os.environ["EVAL_NO_LLM"] = os.environ.get("EVAL_NO_LLM", "1")
  os.environ["QDRANT_PATH"]  = os.environ.get("QDRANT_PATH", "qdrant_local")

  from emissions_rag.graph import emissions_agent


  def run_demo() -> None:
      print("=== NeonatalGuard Emissions RAG Bridge Demo ===\n")

      for company_id in ["COMPANY-001", "COMPANY-002", "COMPANY-003"]:
          t0 = time.perf_counter()
          result = emissions_agent.invoke({"company_id": company_id})
          latency_ms = (time.perf_counter() - t0) * 1000.0

          alert = result.get("final_alert")
          assert alert is not None, (
              f"emissions_agent.invoke() returned no final_alert for {company_id}. "
              f"State keys: {list(result.keys())}"
          )

          print(f"Company: {alert.company_id}")
          print(f"  Scope breakdown: {alert.scope_breakdown}")
          print(f"  Primary sources: {alert.primary_sources}")
          print(f"  Pathway: {alert.reduction_pathway[:80]}...")
          print(f"  SBTi aligned: {alert.sbti_aligned} | CSRD reportable: {alert.csrd_reportable}")
          print(f"  Action: {alert.recommended_action[:100]}")
          print(f"  Latency: {latency_ms:.0f}ms")
          assert latency_ms < 5000, f"Latency {latency_ms:.0f}ms exceeds 5000ms target"
          print()

      print("Demo complete. All assertions passed.")


  if __name__ == "__main__":
      run_demo()
  ```

  **What it does:** `graph.py` compiles the 4-node LangGraph supervisor graph and exports `emissions_agent` for direct use or API wrapping. `demo.py` validates the end-to-end pipeline latency target (< 5s) for all 3 synthetic companies.

  **Git Checkpoint:**
  ```bash
  git add emissions_rag/graph.py emissions_rag/demo.py
  git commit -m "step 8.6: add emissions LangGraph supervisor graph and demo script"
  ```

  **✓ Verification Test:**

  **Type:** Integration (E2E)

  **Action:**
  ```bash
  EVAL_NO_LLM=1 QDRANT_PATH=qdrant_local python emissions_rag/demo.py
  ```

  **Expected:**
  - Three company blocks printed
  - Each `Latency: Xms` line shows < 5000ms
  - `Demo complete. All assertions passed.` on last line
  - Exit code 0

  **Pass:** `Demo complete. All assertions passed.` printed. Exit code 0.

  **Fail:**
  - `KeyError: COMPANY-001` → `company_data.py` company IDs mismatch — check `_COMPANIES` dict in Step 8.1.
  - `AssertionError: Latency Xms exceeds 5000ms` → SentenceTransformer loading slowly — subsequent calls will be faster (singleton warms after first call); latency assertion only checks end-to-end wall time.
  - `ValidationError` on `EmissionsAlert` → compliance_agent field mismatch — re-read Step 8.5 file.
  - `ModuleNotFoundError: emissions_rag` → run from repo root, not `emissions_rag/` subdirectory.

---

## Phase 3 — API Integration

**Goal:** `POST /emissions/assess/{company_id}` endpoint returns `EmissionsAlert` from the existing FastAPI server.

---

- [ ] 🟥 **Step 8.7: Extend `api/main.py` with emissions endpoint** — *Non-critical: adds endpoint; no existing code changed*

  **Idempotent:** Yes — adding new imports and one new route. If already present, grep catches duplicate.

  **Pre-Read Gate:**
  - Run `grep -n "emissions" api/main.py`. Must return 0 matches. If any match → step already done, skip.
  - Run `python -c "from emissions_rag.graph import emissions_agent; print('OK')"`. Must print OK.
  - Run `grep -n "def assess(" api/main.py`. Must return exactly 1 match (existing blocking endpoint).

  **Anchor Uniqueness Check:**
  - Target: `from src.agent.graph import _get_kb, agent, multi_agent` — must appear exactly once in `api/main.py`.
  - Insert emissions imports immediately after this line.

  **Edits to `api/main.py`:**

  **Edit 1 — add emissions imports after the existing graph import line:**

  Replace:
  ```python
  from src.agent.graph import _get_kb, agent, multi_agent
  from src.agent.schemas import NeonatalAlert
  ```

  With:
  ```python
  from src.agent.graph import _get_kb, agent, multi_agent
  from src.agent.schemas import NeonatalAlert

  from emissions_rag.graph import emissions_agent
  from emissions_rag.schemas import EmissionsAlert
  ```

  **Edit 2 — add emissions endpoint at the end of the endpoint section, before the `health()` function:**

  Find the line `@app.get("/health")` and insert immediately before it:

  ```python
  @app.post("/emissions/assess/{company_id}", response_model=EmissionsAlert)
  def assess_emissions(company_id: str) -> EmissionsAlert:
      """Emissions RAG assessment — returns EmissionsAlert for a company_id.

      Raises 422 for unknown company_id (KeyError from get_company_data).
      Raises 500 if graph runs but produces no final_alert (should not occur).
      """
      try:
          t0 = time.perf_counter()
          state = emissions_agent.invoke({"company_id": company_id})
          latency_ms = (time.perf_counter() - t0) * 1000.0
      except KeyError as exc:
          raise HTTPException(
              status_code=422,
              detail=f"Unknown company_id: {exc}",
          ) from exc
      alert = state.get("final_alert")
      if alert is None:
          raise HTTPException(status_code=500, detail="Emissions agent did not produce a final alert")
      return alert.model_copy(update={"latency_ms": latency_ms})


  ```

  **What it does:** Exposes the emissions graph over HTTP, reusing FastAPI's thread pool (sync `def`) and the same `model_copy(update={"latency_ms": ...})` pattern as the neonatal blocking endpoint.

  **Why this approach:** Inline timing inside the endpoint (not `_invoke_blocking`) avoids modifying the existing helper's signature. New imports are additive — no existing code modified.

  **Risks:**
  - `emissions_rag.graph` import at API startup loads all specialist modules and `EmissionsKnowledgeBase` (SentenceTransformer). This adds ~2s to startup time. Mitigation: the `lifespan` handler already runs `_get_kb()` for the clinical KB; the emissions KB is loaded lazily on first call.
  - **Qdrant file lock in live (non-eval) mode:** `ClinicalKnowledgeBase` and `EmissionsKnowledgeBase` both create `QdrantClient(path="qdrant_local")`. Qdrant's local storage acquires an exclusive file lock per storage directory — two clients to the same path in the same process will raise `"Storage folder already accessed by another instance"`. **In EVAL_NO_LLM=1 mode (CI and all plan verification steps) this never occurs** because `_get_emissions_kb()` is never called. For production live-LLM deployment, both endpoints require `QDRANT_PATH=` (Docker networked Qdrant) where both KBs share the same server without a file lock conflict.

  **Git Checkpoint:**
  ```bash
  git add api/main.py
  git commit -m "step 8.7: add POST /emissions/assess/{company_id} to api/main.py"
  ```

  **Subtasks:**
  - [ ] 🟥 Pre-Read Gate: 0 matches for "emissions" in `api/main.py`
  - [ ] 🟥 Edit 1 applied: emissions imports added after the `NeonatalAlert` import line
  - [ ] 🟥 Edit 2 applied: `assess_emissions()` endpoint inserted before `@app.get("/health")`
  - [ ] 🟥 Verification passes (three PASS lines printed)

  **✓ Verification Test:**

  **Type:** Integration

  **Action:**
  ```bash
  EVAL_NO_LLM=1 QDRANT_PATH=qdrant_local python -c "
  import os
  os.environ['EVAL_NO_LLM'] = '1'
  os.environ['QDRANT_PATH'] = 'qdrant_local'
  from fastapi.testclient import TestClient
  from api.main import app

  client = TestClient(app)

  # Test emissions endpoint
  r = client.post('/emissions/assess/COMPANY-001')
  assert r.status_code == 200, f'Expected 200, got {r.status_code}: {r.text}'
  data = r.json()
  assert data['company_id'] == 'COMPANY-001'
  assert 'scope_breakdown' in data
  assert data['scope_breakdown']['scope_1'] == 1250.0
  assert data.get('latency_ms') is not None
  assert isinstance(data['latency_ms'], float)
  assert data['recommended_action'] != ''
  print(f'PASS Step 8.7: /emissions/assess/COMPANY-001 → {data[\"recommended_action\"][:60]}...')

  # Confirm existing neonatal endpoint still works (regression guard)
  r2 = client.post('/assess/infant1')
  assert r2.status_code == 200, f'Neonatal endpoint broken: {r2.status_code}'
  assert r2.json()['concern_level'] in ('RED', 'YELLOW', 'GREEN')
  print('PASS Step 8.7: neonatal /assess/infant1 still returns valid concern_level (regression OK)')

  # Test unknown company_id → 422 (explicit KeyError handler)
  r3 = client.post('/emissions/assess/UNKNOWN-999')
  assert r3.status_code == 422, f'Expected 422 for unknown company, got {r3.status_code}: {r3.text}'
  assert 'UNKNOWN-999' in r3.json().get('detail', '')
  print('PASS Step 8.7: unknown company_id returns 422')
  "
  ```

  **Pass:** Three `PASS Step 8.7` lines printed. Exit code 0.

  **Fail:**
  - `ModuleNotFoundError: emissions_rag.graph` → `api/main.py` import not added — re-check Edit 1.
  - `assert r.status_code == 200` but got 500 → check `r.text` for error; likely `EmissionsKnowledgeBase` can't find `emissions_tfidf.pkl` — confirm Step 8.2 ran.
  - `assert r3.status_code == 422` fails with 500 → `assess_emissions` missing `try/except KeyError` — re-check Edit 2.
  - `assert 'UNKNOWN-999' in r3.json()['detail']` fails → `HTTPException` detail format wrong — verify `str(exc)` contains the company_id string.
  - Neonatal endpoint broken → check `api/main.py` imports are additive (Edit 1 should not modify existing import lines).

---

## Regression Guard

**Systems at risk from this plan:**
- `clinical_knowledge` Qdrant collection — Step 8.2 runs a separate build script; must not touch `clinical_knowledge`.
- `api/main.py` — Step 8.7 adds imports and one route. Existing neonatal routes must be unaffected.
- CI eval gate — `EVAL_NO_LLM=1 python eval/eval_agent.py --agent multi_agent` must still pass.

**Regression verification:**

| System | Pre-change behaviour | Post-change verification |
|--------|----------------------|--------------------------|
| `clinical_knowledge` chunks | 34 chunks | `QDRANT_PATH=qdrant_local python -c "from qdrant_client import QdrantClient; c=QdrantClient(path='qdrant_local'); print(c.count('clinical_knowledge').count)"` → `34` |
| Multi-agent CI gate | All CI gates passed | `EVAL_NO_LLM=1 QDRANT_PATH=qdrant_local python eval/eval_agent.py --agent multi_agent 2>&1 \| tail -2` → `All CI gates passed.` |
| Neonatal API endpoints | Returns `NeonatalAlert` | `POST /assess/infant1` → `concern_level` in RED/YELLOW/GREEN |
| Test count | Pre-flight baseline | `pytest tests/ -v --tb=short` → count ≥ baseline |

**Test count regression check:**
- Tests before plan (pre-flight): `____`
- After plan: `EVAL_NO_LLM=1 QDRANT_PATH=qdrant_local python -m pytest tests/ -v --tb=short 2>&1 | tail -3`
- Must be ≥ pre-flight baseline (no existing tests deleted or broken).

---

## Rollback Procedure

```bash
# Step 8.7 rollback (most important — modifies existing api/main.py)
git revert HEAD   # removes emissions imports + /emissions/assess endpoint from api/main.py

# Step 8.6 rollback
git revert HEAD   # removes emissions_rag/graph.py + emissions_rag/demo.py

# Step 8.5 rollback
git revert HEAD   # removes reduction_agent.py + compliance_agent.py

# Step 8.4 rollback
git revert HEAD   # removes scope_agent.py + agents/__init__.py

# Step 8.3 rollback
git revert HEAD   # removes emissions_rag/knowledge_base.py

# Step 8.2 rollback (removes text files + build script; Qdrant collection remains)
git revert HEAD
# Manually drop emissions collection if needed:
# python -c "from qdrant_client import QdrantClient; c=QdrantClient(path='qdrant_local'); c.delete_collection('emissions_knowledge')"

# Step 8.1 rollback
git revert HEAD   # removes emissions_rag/__init__.py, schemas.py, company_data.py

# Confirm CI gate still passes:
EVAL_NO_LLM=1 QDRANT_PATH=qdrant_local python eval/eval_agent.py --agent multi_agent 2>&1 | tail -2
# Must print: All CI gates passed.
```

---

## Pre-Flight Checklist

| Phase | Check | How to Confirm | Status |
|-------|-------|----------------|--------|
| **Pre-flight** | `emissions_rag/` does not exist | `ls emissions_rag/` → error | ⬜ |
| | `clinical_knowledge` has 34 chunks | KB count script in pre-flight | ⬜ |
| | `parse_chunks` importable | `python -c "from src.knowledge.build_knowledge_base import parse_chunks; print('OK')"` | ⬜ |
| | CI gate passes | `EVAL_NO_LLM=1 ... eval_agent.py \| tail -2` → passed | ⬜ |
| **Phase 1** | Step 8.1 complete | `PASS Step 8.1` printed | ⬜ |
| | Step 8.2 complete | `emissions_knowledge` has 30 chunks, `emissions_tfidf.pkl` exists | ⬜ |
| | Step 8.3 complete | `PASS Step 8.3` printed | ⬜ |
| **Phase 2** | Step 8.4 complete | `PASS Step 8.4` printed | ⬜ |
| | Step 8.5 complete | `PASS Step 8.5` printed | ⬜ |
| | Step 8.6 complete | `Demo complete. All assertions passed.` | ⬜ |
| **Phase 3** | Step 8.7 complete | Three `PASS Step 8.7` lines printed | ⬜ |
| | Regression guard | `clinical_knowledge` still 34 chunks; CI gate passes | ⬜ |

---

## Risk Heatmap

| Step | Risk | What Could Go Wrong | Early Detection | Idempotent |
|------|------|---------------------|-----------------|------------|
| 8.1 | 🟢 Low | Schema field mismatch with later agents | Verification test imports and instantiates all schemas | Yes |
| 8.2 | 🟡 Medium | Qdrant file lock from existing singleton | Run as standalone script, not inside an existing import chain | Yes |
| 8.2 | 🟡 Medium | `clinical_knowledge` accidentally deleted | Verification asserts both collections' counts | Yes |
| 8.3 | 🟡 Medium | `emissions_tfidf.pkl` not found at agent query time | `FileNotFoundError` with clear message → run Step 8.2 | Yes |
| 8.3 | 🔴 High | **Qdrant file lock (live mode only):** `_get_emissions_kb()` + `_get_kb()` both open `qdrant_local/` in same process | Does not affect CI (EVAL_NO_LLM=1 never calls `_get_emissions_kb()`). Production: set `QDRANT_PATH=` (Docker Qdrant) | Yes |
| 8.4 | 🟢 Low | `_rule_based_scope` produces invalid `ScopeAssessment` | Verification runs all 3 companies under EVAL_NO_LLM=1 | Yes |
| 8.5 | 🟡 Medium | `compliance_agent` sets `final_alert` with wrong types | Verification runs full 3-node pipeline with all assertions | Yes |
| 8.6 | 🟡 Medium | `emissions_agent.invoke` doesn't return `final_alert` key | Demo asserts `alert is not None` before accessing fields — loud error, not silent | Yes |
| 8.7 | 🔴 High | New imports break existing neonatal endpoints | Regression check in verification test: `POST /assess/infant1` must still return 200 | Yes |

---

## Success Criteria

| Feature | Target | Verification |
|---------|--------|--------------|
| Scope analysis specialist | Valid `ScopeAssessment` for all 3 companies | **Do:** `EVAL_NO_LLM=1 python emissions_rag/demo.py` → all 3 companies print scope_breakdown |
| Reduction pathway reasoning | `near_term_actions` non-empty, `recommended_pathway` references KB domain | **Do:** demo output → `Pathway:` line is domain-specific |
| GHG Protocol compliance validator | Pure logic; no Groq call; `csrd_reportable` correctly set | **Do:** `COMPANY-001` (420 employees > 250) → `csrd_reportable: True` |
| Demo latency < 5s | Rule-based path completes in < 1s | **Do:** demo → each `Latency:` line < 5000ms |
| `POST /emissions/assess/{company_id}` | Returns `EmissionsAlert` JSON with `latency_ms` | **Do:** Step 8.7 test → status 200, `scope_breakdown.scope_1 == 1250.0` |
| Neonatal system unaffected | CI gate still passes 30/30 | **Do:** `EVAL_NO_LLM=1 ... eval_agent.py --agent multi_agent \| tail -2` → `All CI gates passed.` |
| `clinical_knowledge` collection intact | 34 chunks (unchanged) | **Do:** `QDRANT_PATH=qdrant_local python -c "..."` → `34` |

---

---

## Known Limitations (by design, not bugs)

| Limitation | Where | Impact | Mitigation |
|-----------|-------|--------|------------|
| `retrieved_context=[]` always empty | `compliance_agent.py` | In live-LLM mode, `EmissionsAlert.retrieved_context` is never populated — specialist nodes store KB chunks as local vars only | Future: write chunks to state (`"scope_chunks"`, `"reduction_chunks"`) and accumulate in compliance_agent |
| No persistent `tests/test_emissions.py` | Phase 3 | Emissions endpoint has no automated regression test; only inline Step 8.7 verification | Future: add `tests/test_emissions.py` with `test_emissions_assess_company001`, `test_emissions_unknown_returns_422`, `test_emissions_does_not_break_neonatal` |
| Qdrant local file lock in live mode | Steps 8.3, 8.7 | Both KB singletons open `qdrant_local/` — invalid for production same-process live mode | Use `QDRANT_PATH=` (Docker Qdrant) in production; CI/eval mode unaffected |

---

⚠️ **Do not mark a step 🟩 Done until its verification test passes.**
⚠️ **Do not proceed past a Human Gate without explicit human input.**
⚠️ **If blocked, mark 🟨 In Progress and output the State Manifest before stopping.**
⚠️ **Do not batch multiple steps into one git commit.**
⚠️ **If idempotent = No, confirm the step has not already run before executing.**
