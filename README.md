# StockShield 2.0 — Agentic Stock Analysis and Risk Intelligence

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![Google ADK](https://img.shields.io/badge/Google_ADK-2.13.0-4285F4.svg)](https://pypi.org/project/google-adk/)
[![CrewAI](https://img.shields.io/badge/CrewAI-1.15.33-FF4B4B.svg)](https://crewai.com)
[![MCP](https://img.shields.io/badge/MCP-1.30.0-8A2BE2.svg)](https://modelcontextprotocol.io)
[![Tests](https://img.shields.io/badge/Tests-31%20Passed-success.svg)]()

> **Phase 2 Academic Prototype:** Clean-room, multi-agent financial intelligence and deterministic risk governance system for Indian equities (NSE: `TCS.NS`, `INFY.NS`, `RELIANCE.NS`).

---

## 1. System Architecture Overview

StockShield 2.0 implements a modular, compliant multi-agent system combining **Google ADK**, **CrewAI**, **MCP (Model Context Protocol)**, and **A2A (Agent-to-Agent Protocol)** centered around a typed, Pydantic-validated **Blackboard Architecture**:

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
|               (AgentCard Discovery & Tasks)                                             |
|                                                                                         |
+-----------------------------------------------------------------------------------------+
```

---

## 2. The 11 Mandatory Academic Criteria

1. **Blackboard Architecture:** Centralized `StockShieldBlackboard` with state updates, field-level provenance, status lifecycles (`pending`, `available`, `unavailable`, `failed`), and asyncio locking.
2. **MCP Integration:** Two callable FastMCP tools (`get_historical_market_data` and `compute_financial_ratios`) invoked through an MCP client.
3. **Structured Outputs:** Pydantic-validated data schemas and structured JSON / Markdown reports.
4. **Architecture Evaluation:** Sequential, Parallel, and Hierarchical execution workflows with empirical comparisons.
5. **Monitoring & Callbacks:** `ObservabilityCallbackManager` recording timings, component lifecycles, and JSONL audit traces.
6. **A2A Inter-Agent Protocol:** Google ADK Technical Agent acts as an A2A server publishing `/.well-known/agent.json`; CrewAI client discovers capabilities and transmits structured tasks.
7. **Both Frameworks:** True execution participation by Google ADK (Technical Agent) and CrewAI (Workflow Orchestrator).
8. **Security Guardrails:** 8-persona test matrix (`config/personas.json`), prompt injection defense, document isolation, and size limits.
9. **Observability & Provenance:** Traceability, source lineage, audit trails, and per-agent operational heatmap.
10. **Performance Evaluation:** 40 controlled runs across 6 configuration groups, token/cost estimation model, boxplots, and heatmap.
11. **Cloud Deployment:** Production `Dockerfile`, `render.yaml`, `docker-compose.yml`, and verified FastAPI endpoints (`/health`, `/analyze`).

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

### 3.2 Run Automated Tests (100% Offline)
```powershell
$env:PYTHONPATH="src"
.\.venv\Scripts\pytest.exe -v
```
*Result: 31 passed in ~4.0s.*

### 3.3 Run Code Linting & Formatting
```powershell
.\.venv\Scripts\ruff.exe check src tests
```

---

## 4. Running the 40-Run Empirical Evaluation

To reproduce the 40 controlled evaluation runs and regenerate the boxplots and heatmap:
```powershell
$env:PYTHONPATH="src"
.\.venv\Scripts\python.exe scripts/run_academic_evaluation.py
```

### Evaluation Summary Table (Real 40-Run Data)
| Configuration | Runs | Completion Rate | Schema Validity | Mean Latency (ms) | Mean Tool Calls | Mean Cost (USD) |
|---|---:|---:|---:|---:|---:|---:|
| **single_agent** | 6 | 100.0% | 100.0% | 2.22 ± 0.57 | 1.0 | $0.000000 |
| **multi_agent** | 5 | 100.0% | 100.0% | 8.15 ± 0.24 | 1.0 | $0.000000 |
| **stockshield_parallel** | 8 | 50.0% | 100.0% | 11.97 ± 11.81 | 1.0 | $0.000000 |
| **stockshield_hierarchical** | 8 | 50.0% | 100.0% | 12.04 ± 11.82 | 1.0 | $0.000000 |
| **stockshield_sequential** | 8 | 50.0% | 100.0% | 13.39 ± 13.11 | 1.0 | $0.000000 |
| **no_callbacks (ablation)** | 5 | 100.0% | 100.0% | 12.65 ± 2.83 | 2.0 | $0.000000 |

*Note: In the StockShield groups, the 50% non-completed runs reflect adversarial prompt injection and malformed inputs correctly intercepted and blocked by the perimeter Guardrails.*

---

## 5. Running the FastAPI Application

Start the local server:
```powershell
$env:PYTHONPATH="src"
.\.venv\Scripts\uvicorn.exe stockshield.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Endpoints:
- **Liveness Probe:** `GET http://localhost:8000/health`
- **A2A AgentCard Discovery:** `GET http://localhost:8000/.well-known/agent.json`
- **Analysis Execution:** `POST http://localhost:8000/analyze`
  ```json
  {
    "ticker": "TCS.NS",
    "user_prompt": "Run full technical momentum and risk review.",
    "lookback_days": 200,
    "workflow_mode": "sequential"
  }
  ```

---

## 6. Cloud Deployment

### 6.1 Local Docker Container Verification
```powershell
docker-compose up --build
curl http://localhost:8000/health
```

### 6.2 Render Deployment
1. Connect repository to [Render](https://render.com).
2. Select **New Web Service** -> Use `render.yaml`.
3. Set plan to **Free Tier**. Healthcheck path is `/health`.

---

## 7. Academic Documentation Matrix
- **[PROJECT_PLAN.md](file:///d:/StockShield3/PROJECT_PLAN.md)**: 11 criteria tracking and milestone roadmap.
- **[DECISIONS.md](file:///d:/StockShield3/DECISIONS.md)**: Architectural Decision Records (ADRs).
- **[docs/COVERAGE_MATRIX.md](file:///d:/StockShield3/docs/COVERAGE_MATRIX.md)**: Comprehensive requirement-to-code mapping.
- **[docs/PROGRESS_REPORT.md](file:///d:/StockShield3/docs/PROGRESS_REPORT.md)**: Planned vs. actual progress report.
- **[docs/EVALUATION_METHOD.md](file:///d:/StockShield3/docs/EVALUATION_METHOD.md)**: Methodology, run design, and formulas.
- **[docs/VIVA_NOTES.md](file:///d:/StockShield3/docs/VIVA_NOTES.md)**: Oral examination defense notes.
