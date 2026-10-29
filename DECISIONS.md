# StockShield 2.0 — Architecture Decision Records (ADR)

## ADR-001: Clean-Room Environment & Dependency Isolation
- **Context**: The academic evaluation requires strict adherence to allowed frameworks (Google ADK and CrewAI only) with zero pollution from LangChain, LangGraph, AutoGen, or other multi-agent frameworks.
- **Decision**: 
  - Created a dedicated Python 3.11 virtual environment at `D:\StockShield3\.venv`.
  - Installed official `google-adk` (v2.13.0) and `mcp` (v2.3.0) along with `fastapi`, `pydantic` (v2), `pandas`, `numpy`, `matplotlib`, and `crewai`.
  - Disallowed any transitive dependencies that bring alternative multi-agent frameworks.
- **Consequences**: Deterministic control over imports, reproducible builds on Windows 11 with 16 GB RAM without requiring GPU acceleration.

## ADR-002: Offline Deterministic Fixtures vs. Unreliable Live Data
- **Context**: Yahoo Finance and public market data APIs frequently rate-limit, alter schema structures, or suffer outages during live academic evaluations. Live dependence causes non-deterministic test failures.
- **Decision**:
  - Implemented deterministic historical price fixtures for `TCS.NS`, `INFY.NS`, and `RELIANCE.NS` covering 200+ trading days (to satisfy 200-SMA calculations).
  - Fixtures explicitly record `source="fixture"`, `price_adjustment="adjusted_close"`, `retrieval_date`, and schema signatures.
  - The system provides a unified provider interface with `DATA_PROVIDER_MODE=fixture` (default for offline testing) and `DATA_PROVIDER_MODE=live` (optional runtime provider).
- **Consequences**: 100% offline testability, zero flaky network dependencies in CI/eval, complete transparency in provenance.

## ADR-003: Blackboard Architecture with Strict Pydantic State & Field Provenance
- **Context**: Multi-agent systems fail when state is loosely typed or mutated haphazardly without attribution. Downstream agents (e.g., Risk) must consume upstream findings (e.g., Technical indicators) with guaranteed schema contracts.
- **Decision**:
  - Central `StockShieldBlackboard` model holds `run_id`, `trace_id`, `ticker`, `market_data`, `technical_findings`, `risk_findings`, `evidence_provenance`, `agent_statuses`, and `execution_events`.
  - Field statuses follow explicit states: `pending`, `available`, `unavailable`, `failed`.
  - Updates require `producer_agent`, `timestamp_utc`, and `provenance_id`.
  - Thread-safe updates guarded by `asyncio.Lock` to support parallel execution workflows.
- **Consequences**: Explicit state transitions, prevention of silent overwrites, full auditability.

## ADR-004: MCP (Model Context Protocol) Implementation
- **Context**: The system requires at least two genuine MCP tools callable through standard MCP client-server semantics.
- **Decision**:
  - **Tool 1 (`market_data_service`)**: Exposes historical OHLCV data retrieval with parameter validation, caching metadata, and data-quality scoring.
  - **Tool 2 (`financial_evidence_service`)**: Exposes bounded text extraction from financial documents and financial ratio calculations (Debt-to-Equity, Current Ratio, Operating Margin).
  - Both tools validate inputs via Pydantic before Blackboard ingestion.
- **Consequences**: Standardized tooling interface decoupled from specific agent frameworks.

## ADR-005: Dual-Framework Roles: Google ADK and CrewAI
- **Context**: Both Google ADK and CrewAI must participate in actual execution, not just token imports.
- **Decision**:
  - **Google ADK**: Powers the deterministic `TechnicalAgent`, hosting technical indicator algorithms (SMA, EMA, MACD, RSI, Bollinger Bands, ATR) and exposing A2A AgentCard.
  - **CrewAI**: Powers workflow orchestration, task delegation, and execution topologies (Sequential, Parallel, Hierarchical).
- **Consequences**: Clear separation of concerns without redundant or overlapping agent definitions.

## ADR-006: A2A Protocol Implementation
- **Context**: Inter-agent communication requires a genuine Agent-to-Agent (A2A) protocol exchange rather than in-memory function calls.
- **Decision**:
  - Google ADK Technical Agent exposes an A2A agent card (`/.well-known/agent.json`) and task execution endpoint (`/a2a/tasks`).
  - CrewAI orchestrator acts as the A2A client, discovering capabilities via the AgentCard, sending structured task payloads, validating responses via Pydantic, and committing findings to the Blackboard.
- **Consequences**: Demonstrable, standards-compliant inter-agent interoperability.

## ADR-007: Deterministic Stub LLM & Cost Modeling
- **Context**: Evaluation runs (~40 runs across 6 configurations) must be repeatable, zero-cost, and independent of external API quotas.
- **Decision**:
  - Implemented interchangeable model interface with a deterministic Stub LLM that generates consistent, reproducible risk narratives based strictly on Blackboard findings.
  - Token and Cost Estimator tracks input/output tokens using standard tokenizer heuristics and applies versioned Gemini 1.5 Flash pricing tables ($0.075/1M input, $0.30/1M output).
- **Consequences**: Fast, zero-cost test suite and evaluation benchmarks with accurate cost and latency projections.
