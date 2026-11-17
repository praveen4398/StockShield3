# StockShield 2.0 — Agentic Stock Analysis and Risk Intelligence

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![Google ADK](https://img.shields.io/badge/Google_ADK-2.13.0-4285F4.svg)](https://pypi.org/project/google-adk/)
[![CrewAI](https://img.shields.io/badge/CrewAI-1.15.33-FF4B4B.svg)](https://crewai.com)
[![MCP](https://img.shields.io/badge/MCP-1.30.0-8A2BE2.svg)](https://modelcontextprotocol.io)
[![A2A Protocol](https://img.shields.io/badge/A2A_SDK-1.3.0-orange.svg)](https://pypi.org/project/a2a-sdk/)
[![Tests](https://img.shields.io/badge/Tests-Passing-success.svg)]()
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

> **Academic Research Prototype & Institutional Intelligence Engine:** A clean-room, multi-agent financial intelligence and deterministic risk governance system for Indian equities (NSE/BSE). StockShield 2.0 unifies **Google Agent Development Kit (ADK)**, **CrewAI**, **Model Context Protocol (MCP)**, **Agent-to-Agent (A2A)** protocol, and a **Blackboard Architecture** to deliver deterministic risk ratings, quantitative forward forecasting, sentiment intelligence, macro stress testing, independent LLM-as-a-Judge evaluations, and conversational analysis via **GENI**.

---

## 1. System Overview & Problem Statement

Retail equity screening tools frequently rely on siloed, lagging technical indicators (such as simple moving average crossovers or static RSI thresholds) without holistic risk governance, multi-model forward uncertainty bounds, media sentiment corroboration, or scenario stress testing. Conversely, unconstrained Large Language Model (LLM) financial assistants suffer from hallucinations, inconsistent numerical deductions, and inability to maintain audit provenance.

**StockShield 2.0 solves this by decoupling algorithmic computation from narrative synthesis:**
1. **Deterministic Safety:** Core indicators, maximum historical drawdowns, volatility bands, and risk gates are calculated using deterministic mathematics and strict rule boundaries.
2. **Multi-Agent Consensus:** Specialized agents observe distinct dimensions of market reality (momentum, fundamentals, news, forward trajectories, and tail shocks).
3. **Grounded Explanations (GENI):** Conversational explanations are strictly grounded in canonical persisted analysis snapshots, preventing retroactive hallucination or altered scores.
4. **Post-Hoc Evaluation (Gemini Judge):** Independent LLM-as-a-Judge audits analysis outputs across 5 institutional dimensions with automated scoring and error categorization.

---

## 2. Core Architecture & Multi-Agent Workflow

```
+---------------------------------------------------------------------------------------------------+
|                                     StockShield 2.0 Architecture                                  |
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
|   [ User / HTTP Request ]                                                                         |
|             │                                                                                     |
|             ▼                                                                                     |
|   +───────────────────+                                                                           |
|   | Guardrails Engine |  <--- 8-Persona Security Matrix (Prompt Injection, Toxicity, Input Bounds)|
|   +───────────────────+                                                                           |
|             │                                                                                     |
|             ▼                                                                                     |
|   +===========================================================================================+   |
|   ||                           CANONICAL BLACKBOARD (Thread-Safe)                            ||   |
|   ||  • Market Data State (OHLCV)               • Google ADK Technical Findings State        ||   |
|   ||  • Financial News & Media Sentiment State  • Quantitative Forward Forecasting State     ||   |
|   ||  • Deterministic Risk Governance State     • Scenario Stress Testing & Monte Carlo State||   |
|   ||  • Immutable Provenance & Event Trail      • Execution Timings & Token Accounting       ||   |
|   +===========================================================================================+   |
|             ▲                        ▲                       ▲                      ▲             |
|             │                        │                       │                      │             |
|   +───────────────────+    +───────────────────+   +───────────────────+  +───────────────────+   |
|   | FastMCP Tools     |    | Google ADK Agent  |   | Quantitative      |  | News & Sentiment  |   |
|   | • get_market_data |    | • SMA/EMA/MACD    |   | Forecasting Agent |  | Agent             |   |
|   | • compute_ratios  |    | • Wilder RSI/ATR  |   | • ARIMA (Auto)    |  | • RSS / NewsFeed  |   |
|   | • search_document |    | • Bollinger Bands |   | • Exp. Smoothing  |  | • Polarity Score  |   |
|   +───────────────────+    +───────────────────+   | • LightGBM ML     |  | • Governance Alert|   |
|             │                        │             | • Holdout Accuracy|  +───────────────────+   |
|             └───────[ A2A Protocol ]─┘             +───────────────────+            │             |
|                  (AgentCard /tasks)                          │                      │             |
|                                                              ▼                      ▼             |
|                                                    +──────────────────────────────────────────+   |
|                                                    | Deterministic Risk Intelligence Engine   |   |
|                                                    | • Gates 1–7: Base-Case Arithmetic Mean   |   |
|                                                    | • Recommendation Caution Governance Rule |   |
|                                                    +──────────────────────────────────────────+   |
|                                                                      │                            |
|                                                                      ▼                            |
|                                                    +──────────────────────────────────────────+   |
|                                                    | Scenario Simulation Agent                |   |
|                                                    | • 6 Macro Shocks + Custom Scenarios      |   |
|                                                    | • 1,000-Path Monte Carlo Simulation      |   |
|                                                    | • Gate 8: Post-Hoc Tail Hazard Assessment|   |
|                                                    +──────────────────────────────────────────+   |
|                                                                      │                            |
|                                                                      ▼                            |
|                                                    +──────────────────────────────────────────+   |
|                                                    | Multi-Agent Synthesis & Final Report     |   |
|                                                    +──────────────────────────────────────────+   |
|                                                                      │                            |
|                    ┌─────────────────────────────────────────────────┴──────────────────┐         |
|                    ▼                                                                    ▼         |
|   +──────────────────────────────────+                               +────────────────────────+   |
|   | Gemini LLM-as-a-Judge Evaluator  |                               | ExperimentStorage      |   |
|   | • 5 Academic Quality Dimensions  |                               | • SQLite (data/*.db)   |   |
|   | • Independent Post-Hoc Audit     |                               | • JSON Snapshots       |   |
|   +──────────────────────────────────+                               +────────────────────────+   |
|                                                                                  │                |
|                                                                                  ▼                |
|                                                              +────────────────────────────────+   |
|                                                              | GENI AI Analysis Assistant     |   |
|                                                              | • Grounded Conversational Q&A  |   |
|                                                              | • Strict Causal Explanations   |   |
|                                                              | • Multi-Turn SQLite Threads    |   |
|                                                              +────────────────────────────────+   |
+---------------------------------------------------------------------------------------------------+
```

---

## 3. Implemented Components & Agent Roles

| Component | Class / Module | Primary Responsibility |
|---|---|---|
| **Blackboard State** | `StockShieldBlackboard` | Centralized, thread-safe asyncio state holding domain models, field-level provenance, and audit logs. |
| **Google ADK Agent** | `GoogleADKTechnicalAgent` | Computes Wilder RSI-14, MACD (12, 26, 9), SMA (20, 50, 200), Bollinger Bands, and ATR-14. Acts as an A2A server. |
| **Deterministic Risk Engine** | `RiskEngine` | Evaluates 7 base-case gates (arithmetic average) and assigns institutional recommendations (`APPROVED`, `APPROVED_WITH_CAUTION`, `REJECTED_HIGH_RISK`). |
| **Forecasting Agent** | `QuantitativeForecastingAgent` | Evaluates candidate statistical models (ARIMA, Exponential Smoothing, LightGBM) on holdouts, calculates directional consensus and multi-model divergence. |
| **News & Sentiment Agent** | `NewsAndSentimentAgent` | Analyzes financial articles, extracts corporate governance flags (SEBI, RBI, probes, court cases), and computes composite polarity. |
| **Scenario Simulation Agent** | `ScenarioSimulationAgent` | Stresses positions across 6 deterministic macro shocks + user custom scenarios, plus 1,000-path stochastic Monte Carlo price distributions. Evaluates Gate 8 tail hazard. |
| **Gemini Judge** | `GeminiJudgeEvaluator` | Independent post-hoc audit examining Technical Accuracy, Risk Governance, Narrative Consistency, Formatting, and Actionability. |
| **GENI Assistant** | `GeniService` | Conversational explanation assistant for completed analyses. Uses dynamic context building and SQLite thread persistence. |
| **MCP Server & Client** | `FastMCP` / `MCPToolProvider` | Exposes standard financial tools (`get_historical_market_data`, `compute_financial_ratios`, `search_financial_document`) over stdio transport. |
| **A2A Protocol** | `a2a-sdk` v1.3.0 | Exposes official Protobuf AgentCard discovery at `/.well-known/agent-card.json` and task handling at `/a2a/tasks`. |

---

## 4. Technology Stack

- **Runtime & Language:** Python 3.11+
- **API Framework:** FastAPI 0.115+, Uvicorn (ASGI)
- **Data Validation & Schemas:** Pydantic v2.10+
- **Quantitative Mathematics:** NumPy, Pandas, SciPy, Statsmodels, LightGBM, Scikit-learn
- **Multi-Agent Orchestration:** Google ADK 2.13.0, CrewAI 1.15.33
- **Protocol Standards:** Model Context Protocol (MCP) 1.30.0, Agent-to-Agent SDK (a2a-sdk) 1.3.0
- **LLM Integration:** Google GenAI SDK (`google-genai` 2.34.0) with `truststore` Windows SSL integration
- **Market Data Provider:** Yahoo Finance (`yfinance` 1.7.0) with offline fallback JSON fixtures
- **Testing & Code Quality:** Pytest, Pytest-Asyncio, Ruff

---

## 5. Repository Directory Layout

```
StockShield3/
├── config/
│   └── personas.json                   # 8-persona adversarial test matrix for guardrails
├── data/
│   ├── fixtures/                       # Deterministic offline market data fixtures
│   │   ├── INFY.NS.json
│   │   ├── RELIANCE.NS.json
│   │   ├── TCS.NS.json
│   │   └── news/                       # Verified news fixtures for offline testability
│   └── reports/                        # Corporate annual report fixtures (FY24)
├── docs/
│   ├── COVERAGE_MATRIX.md              # Requirements and validation coverage
│   ├── EVALUATION_METHOD.md            # Academic evaluation methodology
│   ├── GENI_API_GUIDE.md               # Detailed GENI architecture and integration guide
│   ├── PROGRESS_REPORT.md              # Milestones and operational reports
│   ├── RESULTS_VALIDATION.md           # Statistical recalculations and hypothesis tests
│   └── VIVA_NOTES.md                   # Architecture defense reference
├── evaluation_results/
│   ├── final_40_run_academic_evaluation_final.md # Complete 40-run empirical report
│   ├── agent_metric_heatmap.png        # Operational latency heatmap
│   ├── latency_boxplot.png             # End-to-end latency boxplot by topology
│   ├── runtime_topology_boxplot.png    # Runtime latency boxplot
│   ├── runs.csv                        # Canonical 40-run benchmark metrics
│   ├── performance_metrics.csv         # Per-run execution timings
│   ├── forecast_metrics.csv            # Multi-model forecasting accuracy metrics
│   ├── judge_scores.csv                # Gemini Judge evaluation scores
│   └── snapshots/                      # Persisted JSON blackboard snapshots
├── scripts/
│   ├── generate_fixtures.py            # Utility to refresh offline data fixtures
│   ├── run_academic_evaluation.py      # Reproducibility script for 40-run matrix
│   ├── run_horizon_trial.py            # Comparative Short/Mid/Long-Term horizon trial
│   └── validate_results_empirically.py # Statistical hypothesis validation (Welch's t-test)
├── src/
│   └── stockshield/
│       ├── a2a/                        # A2A protocol implementation (server, client, models)
│       ├── agents/                     # Specialized agent implementations
│       ├── api/                        # FastAPI main application and route handlers
│       ├── blackboard/                 # Thread-safe canonical Blackboard state
│       ├── evaluation/                 # ExperimentStorage SQLite engine and benchmark runners
│       ├── forecasting/                # ARIMA, Exponential Smoothing, LightGBM models
│       ├── geni/                       # GENI Assistant (router, service, context, conversation)
│       ├── guardrails/                 # 8-persona input sanitizer and size defense
│       ├── judge/                      # Gemini LLM-as-a-Judge post-hoc audit engine
│       ├── llm/                        # Deterministic stubs, cost estimators, and adapters
│       ├── mcp/                        # FastMCP financial calculator and tools
│       ├── news/                       # Media sentiment analyzer and scraper
│       ├── observability/              # Structured logging and lifecycle callbacks
│       ├── orchestration/              # Sequential, Parallel, and Hierarchical workflows
│       ├── risk/                       # Deterministic Risk Intelligence Engine (Gates 1–8)
│       ├── simulation/                 # Macro shock stress testing and Monte Carlo
│       └── static/                     # Embedded interactive dashboard (HTML5/JS)
├── tests/                              # Comprehensive Pytest test suites (30+ test modules)
├── .env.example                        # Safe environment variable template
├── .gitignore                          # Production Git ignore rules
├── Dockerfile                          # Production container specification
├── docker-compose.yml                  # Multi-service container orchestration
├── pyproject.toml                      # Build metadata and dependencies
└── requirements.txt                    # Pinned production dependencies
```

---

## 6. Installation & Setup Guide

### 6.1 Prerequisites
- **Operating System:** Windows 10/11, macOS, or Linux (Ubuntu 22.04+ recommended)
- **Python Version:** Python **3.11.x** (3.11.7 recommended). *Python 3.12+ is not currently recommended due to binary wheel requirements in statsmodels and lightgbm.*
- **Git:** Git 2.30+

### 6.2 Setup on Windows (PowerShell)

```powershell
# 1. Clone repository
git clone https://github.com/praveen4398/StockShield3.git
cd StockShield3

# 2. Create Python 3.11 virtual environment
python -m venv .venv

# 3. Activate virtual environment
.\.venv\Scripts\Activate.ps1

# 4. Upgrade pip and install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# 5. Configure environment variables
Copy-Item .env.example .env
```

### 6.3 Setup on Linux / macOS (Bash)

```bash
# 1. Clone repository
git clone https://github.com/praveen4398/StockShield3.git
cd StockShield3

# 2. Create Python 3.11 virtual environment
python3.11 -m venv .venv

# 3. Activate virtual environment
source .venv/bin/activate

# 4. Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 5. Configure environment variables
cp .env.example .env
```

### 6.4 Environment Variables (`.env`)

StockShield 2.0 is designed for **zero-cost offline testability** by default:

```ini
# Application Settings
ENVIRONMENT=development
APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=INFO

# Provider Mode:
# - "fixture": 100% offline using local fixtures (TCS.NS, INFY.NS, RELIANCE.NS)
# - "live": Real-time market data retrieval via Yahoo Finance
# - "auto": Fixture if available, otherwise Yahoo Finance
DATA_PROVIDER_MODE=auto
YFINANCE_CACHE_TTL_SECONDS=3600

# LLM Mode:
# - "stub": Deterministic zero-cost stub (default, zero API keys needed)
# - "gemini": Live Google Gemini API calls for Judge and GENI
LLM_PROVIDER=stub
GEMINI_API_KEY=your_gemini_api_key_here
LLM_MODEL_NAME=gemini-3.8-flash

# Gemini LLM-as-a-Judge Evaluation Configuration
GEMINI_JUDGE_MODEL=gemini-3.8-flash
LLM_JUDGE_ENABLED=false
LLM_JUDGE_TIMEOUT_SECONDS=30

# GENI Conversational Assistant Configuration
GENI_MODEL=gemini-3.8-flash
GENI_TIMEOUT_SECONDS=30
STOCKSHIELD_GENI_DB=data/geni_chat.db
```

### Feature Dependencies on `GEMINI_API_KEY`:

| Feature / Endpoint | Works WITHOUT `GEMINI_API_KEY`? | Mode & Behavior |
|---|:---:|---|
| **Multi-Agent Analysis (`POST /analyze`)** | **YES** (100% Offline) | Uses `DeterministicStubLLM` with deterministic algorithms for technical momentum, 8-gate risk, forecasting, and news sentiment. Returns complete structured findings, executive summary, and markdown report with zero API costs. |
| **Scenario Stress Testing (`POST /simulate`)** | **YES** (100% Offline) | Macro price shocks, volatility shifts, and Monte Carlo stochastic simulations run purely on local NumPy/SciPy math. |
| **Run History & Evaluation (`GET /evaluations/*`)** | **YES** (100% Offline) | Reads local SQLite databases, exports academic CSVs, and retrieves canonical JSON snapshots. |
| **A2A Protocol (`/.well-known/agent-card.json`)** | **YES** (100% Offline) | Protobuf AgentCard discovery and local technical analysis tasks execute locally. |
| **GENI Conversational Assistant (`POST /geni/chat`)** | **Requires API Key** | Calls Google's Gemini API (`gemini-3.8-flash` via `google-genai` SDK) to generate grounded multi-turn explanations. If key is missing or quota is exhausted, gracefully returns a structured fallback error response (`status: "rate_limited"` or `"error"`). |
| **Gemini LLM-as-a-Judge (`enable_judge: true`)** | **Requires API Key** | Performs post-hoc 6-dimension evaluation of reports. If unconfigured or key is absent, Section 8 records `status: "not_configured"` without affecting analysis findings. |

---

## 7. Running the Backend Server

Start the FastAPI application with Uvicorn:

```powershell
# Windows PowerShell
$env:PYTHONPATH="src"
uvicorn stockshield.api.main:app --host 0.0.0.0 --port 8000 --reload
```

```bash
# Linux / macOS
export PYTHONPATH="src"
uvicorn stockshield.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Server Verification URLs:
- **Interactive Swagger Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc Interactive Documentation:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **API Health & Readiness Probe:** [http://localhost:8000/health](http://localhost:8000/health)
- **Built-in HTML Dashboard:** [http://localhost:8000/dashboard](http://localhost:8000/dashboard) (or [http://localhost:8000/](http://localhost:8000/))
- **A2A AgentCard Discovery:** [http://localhost:8000/.well-known/agent-card.json](http://localhost:8000/.well-known/agent-card.json)

---

## 8. FRONTEND DEVELOPER HANDOVER GUIDE

This section provides all specifications required for a frontend developer to connect an independent frontend (e.g., React, Vue, Next.js, or mobile client) to this backend.

### 8.1 Base URL & CORS Configuration
- **Base URL:** `http://localhost:8000` (Local Development)
- **CORS Policy:** Fully permissive for development. Configured with:
  - `allow_origins=["*"]`
  - `allow_credentials=True`
  - `allow_methods=["*"]`
  - `allow_headers=["*"]`
  Frontend applications running on `http://localhost:3000`, `http://localhost:5173`, etc., can make direct asynchronous API requests without encountering CORS rejections.

---

### 8.2 End-to-End Frontend Flow

```
[ Frontend Client ]
        │
        ├─ 1. POST /analyze (ticker, options)
        │     └──> Receives complete analysis JSON with "run_id"
        │
        ├─ 2. Render Analysis UI (Cards: Technical, Risk, Forecast, News, Scenarios)
        │
        ├─ 3. POST /geni/chat (run_id, message)
        │     └──> Receives grounded answer + "conversation_id"
        │
        ├─ 4. Follow-up: POST /geni/chat (run_id, conversation_id, message)
        │     └──> Receives contextual follow-up answer in same thread
        │
        └─ 5. Reload Page / Switch Run: GET /geni/conversations/run/{run_id}
              └──> Retrieves existing conversation threads for that run
```

---

### 8.3 Core API Endpoints & Request/Response Contracts

#### Endpoint 1: Execute Full Analysis (`POST /analyze`)
Runs the complete multi-agent pipeline and returns the canonical structured findings.

- **URL:** `POST /analyze`
- **Headers:** `Content-Type: application/json`
- **Request Payload:**
```json
{
  "ticker": "HDFCBANK.NS",
  "user_prompt": "Conduct institutional technical momentum and deterministic risk intelligence review.",
  "workflow_mode": "sequential",
  "time_horizon": "short_term",
  "forecast_horizon": "1_month",
  "lookback_days": 200,
  "risk_profile": "moderate",
  "provider_mode": "auto",
  "enable_judge": false,
  "custom_scenarios": []
}
```
*Parameter Options:*
- `ticker`: Any NSE equity ticker (e.g., `TCS.NS`, `INFY.NS`, `HDFCBANK.NS`, `SBIN.NS`, `RELIANCE.NS`, `ITC.NS`).
- `workflow_mode`: `"sequential"`, `"parallel"`, or `"hierarchical"`.
- `time_horizon`: `"short_term"` (1–30d), `"mid_term"` (1–6m), or `"long_term"` (1–2+ yrs).
- `forecast_horizon`: `"1_month"`, `"3_months"`, `"6_months"`, `"1_year"`, `"2_years"`.
- `provider_mode`: `"auto"` (fixture if available, else Yahoo Finance), `"fixture"` (offline only), `"live"` (force Yahoo Finance).

- **Response Payload (Extract):**
```json
{
  "run_id": "run_3be6e1bfc274",
  "trace_id": "trace_357ac26691704e5e",
  "workflow_status": "completed",
  "ticker": "HDFCBANK.NS",
  "time_horizon": "short_term",
  "forecast_horizon": "1_month",
  "market_data": {
    "status": "available",
    "source": "yahoo_finance",
    "bar_count": 200,
    "data_quality": "valid",
    "is_stale": false,
    "freshness_age_days": 0
  },
  "technical_findings": {
    "status": "available",
    "signal": "BULLISH",
    "confidence": 0.8,
    "indicators": {
      "sma_20": 739.92,
      "sma_50": 725.14,
      "sma_200": 774.66,
      "rsi_14": 74.79,
      "macd_line": 27.86,
      "macd_signal": 17.25,
      "macd_hist": 10.62,
      "bb_upper": 843.92,
      "bb_middle": 739.92,
      "bb_lower": 635.92,
      "atr_14": 16.62
    },
    "summary": "Strong bullish momentum above 20-day SMA."
  },
  "risk_findings": {
    "status": "available",
    "risk_level": "MODERATE",
    "composite_score": 0.142,
    "recommendation": "APPROVED_WITH_CAUTION",
    "warnings": [
      "Asset experienced historical drawdown of 28.63%.",
      "Low validation directional accuracy (30.0%): ARIMA trend direction carries elevated uncertainty.",
      "Gate 8 Tail Hazard: Severe market stress (Severe Market Crash) escalates simulated risk to REJECTED_HIGH_RISK."
    ],
    "reasons": [
      "Evaluated under institutional [SHORT TERM] risk mandate.",
      "Passes institutional safety criteria with noted cautionary flags."
    ]
  },
  "forecasting": {
    "status": "available",
    "best_model": "ARIMA",
    "model_divergence_pct": 0.0,
    "directional_consensus": "NEUTRAL",
    "models_evaluated": [
      {
        "model_name": "ARIMA",
        "rmse": 16.71,
        "mae": 13.93,
        "directional_accuracy": 30.0
      }
    ],
    "forecasts": [
      {
        "step": 1,
        "target_date": "2026-11-17",
        "predicted_price": 814.95,
        "pct_change": 0.0,
        "conf_lower": 782.2,
        "conf_upper": 847.7
      }
    ]
  },
  "scenario_simulation": {
    "status": "available",
    "total_scenarios": 23,
    "worst_case_scenario": {
      "name": "Severe Market Crash",
      "risk_score": 0.698,
      "recommendation": "REJECTED_HIGH_RISK"
    },
    "scenarios_flipping_recommendation": ["Severe Market Crash"]
  },
  "final_report": {
    "executive_summary": "Institutional risk assessment summary...",
    "markdown_report": "# Comprehensive StockShield Report..."
  }
}
```
> **Frontend Integration Note:** Always save `response.run_id` in your UI state (e.g., Redux, Pinia, or local state). It is required to bind subsequent GENI chat interactions to this specific analysis.

---

#### Endpoint 2: Conversational AI Assistant (`POST /geni/chat`)
Allows users to ask natural language questions grounded in a completed analysis run.

- **URL:** `POST /geni/chat`
- **Headers:** `Content-Type: application/json`
- **Request Payload (New Thread):**
```json
{
  "run_id": "run_3be6e1bfc274",
  "message": "Why is this stock classified as moderate risk despite bullish momentum?"
}
```
- **Response Payload:**
```json
{
  "run_id": "run_3be6e1bfc274",
  "conversation_id": "conv_9f2a41d8e0",
  "assistant_name": "GENI",
  "response": "HDFC Bank (HDFCBANK.NS) is classified as MODERATE risk (Composite Risk Score: 0.142) with an institutional recommendation of 'APPROVED_WITH_CAUTION'. While Google ADK technical analysis confirms BULLISH momentum (80% confidence, RSI 74.79), the Risk Engine elevated the recommendation strictly due to two base-case governance warnings: (1) an observed historical peak-to-trough drawdown of 28.63% (> 20% threshold), and (2) low directional validation accuracy (30.0%) from the ARIMA model. The Severe Market Crash stress test indicates tail risk (flipping simulated risk to REJECTED_HIGH_RISK), but did not calculate the original recommendation.",
  "status": "success",
  "sources_used": [
    "overall_analysis",
    "technical_analysis",
    "risk_assessment",
    "forecasting",
    "scenario_simulation"
  ]
}
```

- **Request Payload (Follow-up Question in Same Thread):**
To maintain multi-turn conversational context, pass the returned `conversation_id`:
```json
{
  "run_id": "run_3be6e1bfc274",
  "conversation_id": "conv_9f2a41d8e0",
  "message": "Which risk factor contributed the most to this score?"
}
```

---

#### Endpoint 3: Fetch Conversation Message History (`GET /geni/conversations/{conversation_id}/messages`)
Retrieves chronological message history to render a chat timeline in the UI.

- **URL:** `GET /geni/conversations/conv_9f2a41d8e0/messages`
- **Response Payload:**
```json
[
  {
    "message_id": "msg_001",
    "conversation_id": "conv_9f2a41d8e0",
    "role": "user",
    "content": "Why is this stock classified as moderate risk despite bullish momentum?",
    "sources_used": [],
    "created_at_utc": "2026-11-17T12:00:00Z",
    "metadata": {}
  },
  {
    "message_id": "msg_002",
    "conversation_id": "conv_9f2a41d8e0",
    "role": "assistant",
    "content": "HDFC Bank (HDFCBANK.NS) is classified as MODERATE risk...",
    "sources_used": ["technical_analysis", "risk_assessment"],
    "created_at_utc": "2026-11-17T12:00:02Z",
    "metadata": {}
  }
]
```

---

#### Endpoint 4: List Conversations for a Run (`GET /geni/conversations/run/{run_id}`)
Retrieves all conversation threads associated with a specific analysis run.

- **URL:** `GET /geni/conversations/run/run_3be6e1bfc274`
- **Response Payload:**
```json
[
  {
    "conversation_id": "conv_9f2a41d8e0",
    "run_id": "run_3be6e1bfc274",
    "ticker": "HDFCBANK.NS",
    "created_at_utc": "2026-11-17T12:00:00Z",
    "updated_at_utc": "2026-11-17T12:02:15Z",
    "message_count": 4
  }
]
```

---

#### Endpoint 5: Scenario Simulation & Stress Testing (`POST /simulate`)
Executes standalone or custom macro stress tests and Monte Carlo paths.

- **URL:** `POST /simulate`
- **Request Payload:**
```json
{
  "ticker": "INFY.NS",
  "user_prompt": "Run scenario simulation and sensitivity analysis.",
  "workflow_mode": "sequential",
  "lookback_days": 200,
  "include_monte_carlo": true,
  "monte_carlo_simulations": 1000,
  "monte_carlo_horizon_days": 20
}
```

---

#### Endpoint 6: Run History & Stored Snapshots (`GET /evaluations/...`)
Allows frontends to list historical analysis runs, retrieve full run metadata, or load raw JSON snapshots.

- **List Past Runs:** `GET /evaluations/runs?ticker=TCS.NS&status=completed&limit=20`
- **Get Full Run Details:** `GET /evaluations/runs/{run_id}`
- **Get Raw JSON Snapshot:** `GET /evaluations/snapshots/{run_id}`
- **Get Statistical Summary:** `GET /evaluations/summary`

---

### 8.4 API Error Handling & Status Codes

The backend returns standard RFC 7807 formatted error responses:
```json
{
  "detail": "Error description message"
}
```

| HTTP Status | Meaning | Typical Scenario | Frontend Handling |
|---|---|---|---|
| **`400 Bad Request`** | Context / State Mismatch | `conversation_id` was created for Run A, but passed with Run B; or analysis is still pending. | Show a banner warning user that the chat thread is tied to a different analysis run. |
| **`404 Not Found`** | Resource Missing | Invalid `run_id` or nonexistent `conversation_id`. | Prompt user to execute an analysis first. |
| **`422 Unprocessable Entity`** | Pydantic Validation Error | Missing required fields, invalid parameter types, or malicious script tags (`<script>`). | Display field validation errors under form inputs. |
| **`500 Internal Server Error`** | Server Pipeline Failure | Unexpected pipeline or network exception. | Show generic error toast with suggestion to retry. |

---

## 9. Running Tests & Code Quality

### 9.1 Run Full Test Suite
```powershell
$env:PYTHONPATH="src"
.\.venv\Scripts\pytest.exe -v
```
All unit, integration, conversation, and security suites execute with 100% offline mocks, consuming zero API quota.

### 9.2 Run Code Linting & Style Checks
```powershell
.\.venv\Scripts\ruff.exe check src tests
```

---

## 10. Academic Evaluation & Empirical Results

The multi-agent system underwent rigorous academic benchmarking across **40 controlled runs** evaluating three architectural topologies (Sequential, Parallel, Hierarchical) and two LLM integration modes (Deterministic Stubs vs. Live Gemini Evaluation):

| Execution Topology | Mean Latency | Error Rate | Welch's t-test vs. Sequential | Status |
|---|---|---|---|---|
| **Sequential** | ~11.85 s | 0.0% | Baseline | Verified |
| **Parallel** | ~7.42 s | 0.0% | $p < 0.001$ (Statistically significant acceleration) | Verified |
| **Hierarchical** | ~15.20 s | 0.0% | Additional governance verification layer | Verified |

- **Operational Heatmap:** Lineage tracking records zero data-quality dropouts across historical trading sessions.
- **Independent Judge Audit:** Gemini LLM-as-a-Judge awarded a composite quality rating of **8.92 / 10.0** across 5 audited dimensions.
- Full details and charts are available in [`evaluation_results/final_40_run_academic_evaluation_final.md`](evaluation_results/final_40_run_academic_evaluation_final.md).

---

## 11. Known Limitations & Technical Constraints

1. **Market Data Source:** Live data retrieved via Yahoo Finance (`yfinance`) reflects exchange-reported data with typical 15-minute dissemination delays during market hours. It does not provide sub-second institutional order book feeds.
2. **Predictive Uncertainty:** Statistical forecasts (ARIMA, Exponential Smoothing, LightGBM) evaluate historical pattern persistence across chronological holdouts. Market regime shifts, geopolitical catalysts, and sudden macroeconomic shocks cannot be predicted with mathematical certainty.
3. **Hypothetical Stress Testing:** Scenario simulations (e.g., Severe Market Crash, Currency Devaluation) and Monte Carlo quantiles (P5, P50, P95) represent simulated stress exposures and do not guarantee capital outcomes.
4. **LLM Separation:** The Gemini Judge (which performs post-hoc academic evaluations) is completely separate from GENI (which provides conversational explanations). Neither agent can retroactively alter calculated risk scores or recommendations.

---

## 12. Regulatory & Financial Disclaimer

> **IMPORTANT DISCLAIMER:** StockShield 2.0 is an academic research prototype and educational software system designed for algorithmic multi-agent experimentation. It does **NOT** constitute professional investment advice, financial planning, credit rating, portfolio management, or a solicitation to buy or sell equities, derivatives, or securities. All risk scores, technical signals, quantitative forecasts, and scenario outcomes are purely hypothetical model outputs. The developers and contributors accept zero liability for any capital losses or investment decisions made based on this software.
