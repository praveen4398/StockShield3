# StockShield 2.0 — Academic Project Plan & Criteria Tracker

## Overview
- **Project**: StockShield 2.0 — Agentic Stock Analysis and Risk Intelligence
- **Deadline**: 3 Days to Phase 2 Academic Evaluation
- **Primary Objective**: Deliver a production-grade, demonstrable vertical slice with honest, empirical evidence across all 11 mandatory criteria.

---

## The 11 Mandatory Academic Criteria

| # | Criterion | Required Capabilities | Current Status | Verification Evidence |
|---|---|---|---|---|
| 1 | **Blackboard Architecture** | Typed Pydantic state (`StockShieldBlackboard`), field update provenance, status transitions (`pending`, `available`, `unavailable`, `failed`), concurrent safety, downstream consumption proof. | `Demonstrated` | `tests/test_blackboard.py` (3 passed) |
| 2 | **MCP Integration** | Genuine MCP protocol client/server with 2 callable tools: (1) Market Data adapter, (2) Financial Evidence & Ratio Calculator over real `ClientSession` stdio transport. | `Demonstrated` | `tests/test_mcp_tools.py` (6 passed) |
| 3 | **Structured Outputs** | Pydantic-validated findings schemas, strict types, comprehensive JSON and Markdown executive reports. | `Demonstrated` | `tests/test_workflow_vertical_slice.py` (3 passed) |
| 4 | **Architecture Evaluation** | Sequential, Parallel, and Hierarchical workflow execution modes; empirical latency/completion comparison. | `Demonstrated` | 40-run empirical matrix & `latency_boxplot.png` |
| 5 | **Monitoring & Callbacks** | Lifecycle callback manager tracking runs, agents, tools, A2A exchanges, state updates, durations, errors. | `Demonstrated` | `evaluation_results/logs/` JSONL audit trail |
| 6 | **A2A Protocol** | Genuine A2A protocol communication based on official `a2a-sdk`: Google ADK Technical Agent publishes Protobuf AgentCard at `/.well-known/agent-card.json`; CrewAI uses `A2ACardResolver`. | `Demonstrated` | `tests/test_a2a_protocol.py` (4 passed) |
| 7 | **Both Frameworks** | True execution participation: Google ADK (`Runner.run_async`) and CrewAI (`Crew.kickoff`). | `Demonstrated` | Logged in callbacks & `tests/test_workflow_vertical_slice.py` |
| 8 | **Security Guardrails** | Persona testing (`neutral_analyst`, `rude_customer`, `prompt_injection_user`, etc.), ticker/date whitelisting, document isolation, deterministic risk constraints. | `Demonstrated` | `tests/test_guardrails.py` (6 passed) |
| 9 | **Observability & Provenance** | End-to-end trace IDs, JSONL/SQLite audit trail, per-agent latency/failure/tool metrics, source data lineage. | `Demonstrated` | `agent_metric_heatmap.png` & provenance trails |
| 10 | **Performance Evaluation** | 40 controlled runs, token/cost estimation model, boxplots for latency, per-agent execution heatmap, Welch's t-test. | `Demonstrated` | `summary_table.md`, `runs.jsonl`, `runs.csv`, and boxplots |
| 11 | **Cloud Deployment** | Working deployed FastAPI service on Cloud Run / Render with `/health`, `/analyze`, verified live requests. | `Demonstrated` | `Dockerfile`, `render.yaml`, `docker-compose.yml`, local container test ready |

---

## Status Legend
- `Planned`: Scoped and mapped to architecture.
- `In Progress`: Implementation underway or pending live cloud verification.
- `Implemented`: Working implementation in source repository.
- `Tested`: Covered by verified automated pytest test suite.
- `Demonstrated`: Live execution evidence captured with end-to-end validation.
- `Partial`: Incomplete due to technical blocker (documented transparently).
