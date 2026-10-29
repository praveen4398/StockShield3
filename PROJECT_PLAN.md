# StockShield 2.0 — Academic Project Plan & Criteria Tracker

## Overview
- **Project**: StockShield 2.0 — Agentic Stock Analysis and Risk Intelligence
- **Deadline**: 3 Days to Phase 2 Academic Evaluation
- **Primary Objective**: Deliver a production-grade, demonstrable vertical slice with honest, empirical evidence across all 11 mandatory criteria.

---

## The 11 Mandatory Academic Criteria

| # | Criterion | Required Capabilities | Current Status | Planned Milestone |
|---|---|---|---|---|
| 1 | **Blackboard Architecture** | Typed Pydantic state (`StockShieldBlackboard`), field update provenance, status transitions (`pending`, `available`, `unavailable`, `failed`), concurrent safety, downstream consumption proof. | `IN_PROGRESS` | Day 1 |
| 2 | **MCP Integration** | Genuine MCP protocol client/server with 2 callable tools: (1) Market Data adapter, (2) Financial Evidence & Ratio Calculator. | `IN_PROGRESS` | Day 1 |
| 3 | **Structured Outputs** | Pydantic-validated findings schemas, strict types, comprehensive JSON and Markdown executive reports. | `IN_PROGRESS` | Day 1 |
| 4 | **Architecture Evaluation** | Sequential, Parallel, and Hierarchical workflow execution modes; empirical latency/completion comparison. | `PLANNED` | Day 2 |
| 5 | **Monitoring & Callbacks** | Lifecycle callback manager tracking runs, agents, tools, A2A exchanges, state updates, durations, errors. | `IN_PROGRESS` | Day 1 |
| 6 | **A2A Protocol** | True Agent-to-Agent communication: Google ADK Technical Agent acts as A2A server with AgentCard, CrewAI orchestrator as client. | `PLANNED` | Day 2 |
| 7 | **Both Frameworks** | True execution participation: Google ADK (Technical Agent) and CrewAI (Orchestration/Workflow coordination). | `PLANNED` | Day 1–2 |
| 8 | **Security Guardrails** | Persona testing (`neutral_analyst`, `rude_customer`, `prompt_injection_user`, etc.), ticker/date whitelisting, document isolation, deterministic risk constraints. | `IN_PROGRESS` | Day 1–2 |
| 9 | **Observability & Provenance** | End-to-end trace IDs, JSONL/SQLite audit trail, per-agent latency/failure/tool metrics, source data lineage. | `IN_PROGRESS` | Day 1–2 |
| 10 | **Performance Evaluation** | ~40 controlled runs, token/cost estimation model, boxplots for latency/cost, per-agent execution heatmap. | `PLANNED` | Day 2 |
| 11 | **Cloud Deployment** | Working deployed FastAPI service on Cloud Run / Render with `/health`, `/analyze`, verified live requests. | `PLANNED` | Day 3 |

---

## Status Legend
- `PLANNED`: Scoped and mapped to architecture.
- `IN_PROGRESS`: Code and schemas actively under development.
- `IMPLEMENTED`: Working implementation in source repository.
- `TESTED`: Covered by verified automated pytest test suite.
- `DEMONSTRATED`: Live execution evidence captured with end-to-end validation.
- `PARTIAL`: Incomplete due to technical blocker (documented transparently).

---

## 3-Day Execution Roadmap

### Day 1: Vertical Slice & Core Foundations
- [x] Clean-room environment setup, Git repository, virtual environment.
- [x] Verify dependency compatibility and establish core libraries.
- [ ] Create deterministic, offline historical price fixtures for `TCS.NS`, `INFY.NS`, `RELIANCE.NS`.
- [ ] Implement Pydantic Blackboard with full provenance, status tracking, and concurrency locks.
- [ ] Implement MCP Server & Tools: Market Data provider and Financial Evidence calculator.
- [ ] Implement Google ADK Technical Agent (deterministic indicators: SMA, EMA, MACD, RSI, Bollinger Bands, ATR).
- [ ] Implement Deterministic Risk Review step consuming Blackboard findings.
- [ ] Build FastAPI server with structured `/analyze` and `/health` endpoints.
- [ ] Verify vertical slice with 100% offline pytest suite.

### Day 2: Multi-Agent Integration & 40-Run Evaluation
- [ ] Integrate CrewAI orchestrator with Google ADK Technical Agent.
- [ ] Implement genuine A2A client/server protocol with AgentCard discovery and Pydantic validation.
- [ ] Implement Sequential, Parallel, and Hierarchical execution modes.
- [ ] Implement 8-persona adversarial guardrail testing (`config/personas.json`).
- [ ] Implement token and cost estimator with versioned pricing table.
- [ ] Execute 40 controlled evaluation runs across 6 configuration groups.
- [ ] Generate latency/cost boxplots and per-agent metric heatmaps.

### Day 3: Cloud Deployment & Academic Dossier
- [ ] Deploy containerized application to Google Cloud Run / Render.
- [ ] Verify live endpoints with neutral and adversarial HTTP requests.
- [ ] Complete `docs/PROGRESS_REPORT.md`, `docs/COVERAGE_MATRIX.md`, and `docs/VIVA_NOTES.md`.
- [ ] Generate Phase 2 academic presentation slides and architecture diagrams.
