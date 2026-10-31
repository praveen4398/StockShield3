# StockShield 2.0 — Agentic Stock Analysis and Risk Intelligence

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![Google ADK](https://img.shields.io/badge/Google_ADK-2.13.0-4285F4.svg)](https://pypi.org/project/google-adk/)
[![CrewAI](https://img.shields.io/badge/CrewAI-1.15.33-FF4B4B.svg)](https://crewai.com)
[![MCP](https://img.shields.io/badge/MCP-1.30.0-8A2BE2.svg)](https://modelcontextprotocol.io)
[![Tests](https://img.shields.io/badge/Tests-54%20Passed-success.svg)]()

> **Phase 2 Academic Prototype & Dynamic NSE Engine:** Clean-room, multi-agent financial intelligence and deterministic risk governance system for Indian equities. Supports offline institutional fixtures (`TCS.NS`, `INFY.NS`, `RELIANCE.NS`) as well as dynamic real-time market analysis for all valid NSE/BSE tickers (`HDFCBANK.NS`, `WIPRO.NS`, `ICICIBANK.NS`, `SBIN.NS`, `ITC.NS`, etc.) via Yahoo Finance.

---

## 1. System Architecture Overview

StockShield 2.0 implements a modular, compliant multi-agent system combining **Google ADK** (`Runner.run_async`), **CrewAI** (`Crew.kickoff`), **MCP (Model Context Protocol)** (`mcp.client.session.ClientSession` over stdio), and **A2A (`a2a-sdk` v1.3.0)** centered around a typed, Pydantic-validated **Blackboard Architecture**:

```
+-----------------------------------------------------------------------------------------+
|                                StockShield 2.0 Architecture                             |
+-----------------------------------------------------------------------------------------+
|                                                                                         |
|   [ User / HTTP Request ]                                                               |
|             |                                                                           |
|             v                                                                           |
|   +-------------------+                                                                 |
|   | Guardrails Engine |  <--- 8-Persona Defense Gate (Prompt Injection, Toxicity, Size) |
|   +-------------------+                                                                 |
|             |                                                                           |
|             v                                                                           |
|   +=================================================================================+   |
|   ||                     CANONICAL BLACKBOARD (Thread-Safe)                        ||   |
|   ||  - Market Data State (OHLCV)               - Technical Findings State         ||   |
|   ||  - Fundamental Findings (Ratios/Docs)      - Deterministic Risk Findings      ||   |
|   ||  - Immutable Provenance & Lineage Trail    - Execution Events & Timings       ||   |
|   +=================================================================================+   |
|             ^                                 ^                         ^               |
|             |                                 |                         |               |
|   +--------------------+            +-------------------+     +---------------------+   |
|   | MCP Server & Tools |            | Google ADK Agent  |     |  Deterministic Risk |   |
|   |  - Tool 1: Market  |            |  - SMA/EMA/MACD   |     |  - Data Sufficiency |   |
|   |  - Tool 2: Ratios  |            |  - RSI / BB / ATR |     |  - Max Drawdown     |   |
|   +--------------------+            +-------------------+     |  - Volatility Bounds|   |
|             ^                                 ^               +---------------------+   |
|             |                                 |                                         |
|             +-------- [ A2A Protocol ] -------+                                         |
|               (Protobuf AgentCard & Resolver)                                           |
|                                                                                         |
+-----------------------------------------------------------------------------------------+
```

---

## 2. The 11 Mandatory Academic Criteria

1. **Blackboard Architecture:** Centralized `StockShieldBlackboard` with state updates, field-level provenance, status lifecycles (`pending`, `available`, `unavailable`, `failed`), and asyncio locking. (`Demonstrated`)
2. **MCP Integration:** Two callable FastMCP tools (`get_historical_market_data` and `compute_financial_ratios`) invoked through a genuine MCP client session over stdio transport. (`Demonstrated`)
3. **Structured Outputs:** Pydantic-validated data schemas and structured JSON / Markdown reports. (`Demonstrated`)
4. **Architecture Evaluation:** Sequential, Parallel, and Hierarchical execution workflows with empirical comparisons and Welch's t-test hypothesis evaluation. (`Demonstrated`)
5. **Monitoring & Callbacks:** `ObservabilityCallbackManager` recording timings, component lifecycles, and JSONL audit traces. (`Demonstrated`)
6. **A2A Inter-Agent Protocol:** Google ADK Technical Agent acts as an A2A server publishing Protobuf AgentCard at `/.well-known/agent-card.json`; client discovers via `A2ACardResolver` from `a2a-sdk`. (`Demonstrated`)
7. **Both Frameworks:** True execution participation by Google ADK (`Runner.run_async`) and CrewAI (`Crew.kickoff`). (`Demonstrated`)
8. **Security Guardrails:** 8-persona test matrix (`config/personas.json`), prompt injection defense, document isolation, and size limits. (`Demonstrated`)
9. **Observability & Provenance:** Traceability, source lineage, audit trails, and per-agent operational heatmap. (`Demonstrated`)
10. **Performance Evaluation:** 40 controlled runs across 6 configuration groups, token/cost estimation model, boxplots, and heatmap. (`Demonstrated`)
11. **Cloud Deployment:** Production `Dockerfile`, `render.yaml`, `docker-compose.yml`, verified FastAPI endpoints locally; pending live external deployment. (`In Progress`)

---

## 3. Quickstart & Installation (Windows 11)

### 3.1 Clone and Environment Setup
```powershell
cd D:\StockShield3
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3.2 Run Automated Tests (Unit, Integration & Live Suites)
```powershell
$env:PYTHONPATH="src"
.\.venv\Scripts\pytest.exe -v
```
*Result: 54 passed in ~33s (including offline fixtures, live stdio MCP client session, A2A card resolver, and live Yahoo Finance retrieval).*

### 3.3 Run Code Linting & Formatting
```powershell
.\.venv\Scripts\ruff.exe check src tests
```
*Result: All checks passed!*

### 3.4 Dynamic Market Data Provider Modes
StockShield 2.0 supports three market-data provider modes via `MarketDataProvider` and the MCP tool `get_historical_market_data`:

| Mode | Behavior | Source Lineage | Use Case |
|---|---|---|---|
| `auto` (default) | Uses offline fixture if `data/fixtures/{ticker}.json` exists; otherwise fetches live from Yahoo Finance. | `fixture` or `yahoo_finance` | General development and API usage. |
| `fixture` | Strictly loads from local fixture JSON. Never accesses the network. Rejects un-whitelisted tickers. | `fixture` | 100% deterministic academic evaluations and offline testing. |
| `live` | Directly retrieves 2-year OHLCV and fundamental ratios via `yfinance`. | `yahoo_finance` | Production dynamic equity analysis for any NSE ticker (e.g. `HDFCBANK.NS`, `WIPRO.NS`). |

**In-Memory Caching:** Live requests are cached in-memory with a 30-minute TTL to prevent rate-limiting and duplicate network calls.
**No Data Fabrication:** Banking and non-reporting equities omit missing fundamental metrics (such as Debt-to-Equity or Current Ratio) with explicit `unavailable` status rather than dummy defaults.

---

## 4. Reconciled 40-Run Empirical Evaluation

To reproduce the 40 controlled evaluation runs and regenerate the boxplots and heatmap:
```powershell
$env:PYTHONPATH="src"
.\.venv\Scripts\python.exe scripts/run_academic_evaluation.py
```
*(The original raw run logs are preserved as `evaluation_results/runs_v1_raw.jsonl` and `runs_v1_raw.csv`.)*

### Corrected Summary Table (40 Controlled Runs)
| Configuration | Runs | Completed | Expected Blocks | Unexpected Fails | Completion Rate | Schema Validity | Mean Latency (ms) [Completed] | Distinct MCP Tools [Completed] | Mean Cost (USD) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **single_agent** | 6 | 6 | 0 | 0 | 100.0% | 100.0% | 1.14 ± 0.44 | 1 | $0.000000 |
| **multi_agent** | 5 | 5 | 0 | 0 | 100.0% | 100.0% | 12.31 ± 3.65 | 1 | $0.000000 |
| **stockshield_hierarchical** | 8 | 4 | 4 | 0 | 50.0% | 100.0% | 57.92 ± 2.23 | 2 | $0.000000 |
| **stockshield_parallel** | 8 | 4 | 4 | 0 | 50.0% | 100.0% | 83.08 ± 38.52 | 2 | $0.000000 |
| **stockshield_sequential** | 8 | 4 | 4 | 0 | 50.0% | 100.0% | 370.04 ± 463.74 | 2 | $0.000000 |
| **no_callbacks (ablation)** | 5 | 5 | 0 | 0 | 100.0% | 100.0% | 63.39 ± 14.61 | 2 | $0.000000 |

### Key Audit Findings:
- **Parallel vs. Sequential:** Sequential completed runs mean is 370.0 ms, Parallel is 83.1 ms. A Welch's t-test ($t=1.23, df=3.0, p > 0.20$) indicates this difference is **not statistically significant** at $\alpha = 0.05$ due to small sample size ($N=4$ completed runs) and high variance.
- **Tool-Call Count Reconciliation:** Completed StockShield runs execute 2 distinct tools (`get_historical_market_data` and `compute_financial_ratios`). Blocked runs execute 0 tools because guardrails intercept them before tool dispatch. In v1, averaging $(2 \times 4 + 0 \times 4) / 8 = 1.0$ produced an apparent discrepancy with `no_callbacks` (which tested only `neutral_analyst` and thus averaged 2.0).
- **Framework Realism:** Real Google ADK `Runner.run_async` and CrewAI `Crew.kickoff` execution yields realistic latencies (50–370 ms).

---

## 5. Data Disclosure & Verification Requirements

### Document Extracts & Price Fixtures
- All text extracts under `data/reports/` (`TCS_Annual_Report_FY24.txt`, `INFY_Annual_Report_FY24.txt`) are clearly marked as:
  `[SYNTHETIC SAMPLE TEXT - NOT VERIFIED OFFICIAL FILING - PENDING ORIGINAL PDF UPLOAD]`
- All price history under `data/fixtures/` (`TCS_NS.json`, `INFY_NS.json`, `RELIANCE_NS.json`) is marked with `"data_quality_status": "SYNTHETIC_GENERATED_FIXTURE"` and `"source": "synthetic_fixture"`.
- **To replace synthetic data with official filings for Phase 3, the evaluator must supply:**
  1. Source URL of the official annual report PDF from BSE/NSE.
  2. The official PDF document itself.
  3. Exact page numbers containing the audited Income Statement, Balance Sheet, and Segment Revenue tables.

---

## 6. Running the FastAPI Application

Start the local server:
```powershell
$env:PYTHONPATH="src"
.\.venv\Scripts\uvicorn.exe stockshield.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Endpoints:
- **Liveness Probe:** `GET http://localhost:8000/health`
- **A2A AgentCard Discovery:** `GET http://localhost:8000/.well-known/agent-card.json` (and `agent.json`)
- **Analysis Execution:** `POST http://localhost:8000/analyze`
  ```json
  {
    "ticker": "HDFCBANK.NS",
    "user_prompt": "Analyze HDFC Bank technical indicators and solvency.",
    "lookback_days": 200,
    "workflow_mode": "sequential",
    "provider_mode": "auto"
  }
  ```
  *(Works with any valid NSE/BSE ticker e.g. `TCS.NS`, `INFY.NS`, `RELIANCE.NS`, `WIPRO.NS`, `ICICIBANK.NS`, `SBIN.NS`, `ITC.NS`)*

---

## 7. Cloud Deployment (Criterion 11: In Progress)

### 7.1 Local Container Verification (Verified)
```powershell
docker-compose up --build
curl http://localhost:8000/health
```

### 7.2 Remaining Steps for Live Cloud Deployment (Render / Cloud Run)
1. **Platform Options:**
   - **Render Web Service (Recommended Free Tier):** Connect GitHub repo, configure `render.yaml` or use Docker environment.
   - **Google Cloud Run:**
     ```bash
     gcloud builds submit --tag gcr.io/PROJECT_ID/stockshield:latest
     gcloud run deploy stockshield --image gcr.io/PROJECT_ID/stockshield:latest --platform managed --allow-unauthenticated --port 8000
     ```
2. **Required Environment Variables:**
   - `ENVIRONMENT=production`
   - `HOST=0.0.0.0`
   - `PORT=8000`
   - `LOG_LEVEL=INFO`
3. **Health Check Verification:**
   - `curl -f https://<DEPLOYED_URL>/health` (expected: `{"status": "healthy", ...}`)
4. **Sample Analyze Verification Request:**
   - `curl -X POST https://<DEPLOYED_URL>/analyze -H "Content-Type: application/json" -d '{"ticker": "TCS.NS", "user_prompt": "Analyze TCS"}'`
5. **Criterion 11 status remains `In Progress`** until the live URL response is verified.

---

## 8. Academic Documentation Matrix
- **[PROJECT_PLAN.md](file:///d:/StockShield3/PROJECT_PLAN.md)**: 11 criteria tracking and milestone roadmap.
- **[DECISIONS.md](file:///d:/StockShield3/DECISIONS.md)**: Architectural Decision Records (ADRs).
- **[docs/COVERAGE_MATRIX.md](file:///d:/StockShield3/docs/COVERAGE_MATRIX.md)**: Comprehensive requirement-to-code mapping.
- **[docs/PROGRESS_REPORT.md](file:///d:/StockShield3/docs/PROGRESS_REPORT.md)**: Planned vs. actual progress report.
- **[docs/EVALUATION_METHOD.md](file:///d:/StockShield3/docs/EVALUATION_METHOD.md)**: Methodology, run design, and formulas.
- **[docs/VIVA_NOTES.md](file:///d:/StockShield3/docs/VIVA_NOTES.md)**: Oral examination defense notes.

