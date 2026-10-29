# StockShield 2.0 — Academic Viva Voce & Technical Defense Notes

## Key Examination Questions & Defensible Answers

### Q1: Why did you choose a Blackboard architecture instead of simple message-passing or pipeline chains?
**Answer:**
A pipeline chain couples each agent directly to its predecessor, creating brittle dependencies and making parallel execution or state auditing complex. A Pydantic-validated Blackboard acts as a single, canonical, thread-safe source of truth. It decouples data producers (e.g. MCP tools, Google ADK) from data consumers (e.g. Deterministic Risk Engine). Furthermore, every field update on our Blackboard records immutable provenance metadata (producer ID, timestamp, source, prior status), which provides complete auditable lineage essential for financial compliance.

---

### Q2: How do you prove that genuine A2A communication occurred rather than an in-memory function call?
**Answer:**
Our system implements a true protocol separation:
1. The Google ADK Technical Agent runs as an independent A2A service that advertises its capabilities via a standard AgentCard endpoint at `/.well-known/agent.json`.
2. The CrewAI orchestrator acts as an A2A client, discovers the AgentCard over HTTP/REST, verifies capability compatibility (e.g. `sma_20_50_200`, `rsi_14_wilder`), and dispatches an `A2ATaskRequest` with a unique task ID to `/a2a/tasks`.
3. The response is validated using Pydantic (`A2ATaskResponse`) and written to the Blackboard with provenance attributing the finding to `GoogleADKTechnicalAgent (via A2A)`.
This protocol exchange is demonstrated and tested in `tests/test_a2a_protocol.py`.

---

### Q3: What is the architectural role of Google ADK vs. CrewAI?
**Answer:**
- **Google ADK (`google-adk` v2.13.0):** Hosts the specialist quantitative agent (`TechnicalAgent`), encapsulating institutional technical indicator algorithms (SMA, EMA, MACD, RSI, Bollinger Bands, ATR) and serving the A2A capability card.
- **CrewAI (`crewai` v1.15.33):** Acts as the high-level workflow coordinator, managing orchestration patterns (Sequential, Parallel, Hierarchical) and client-side task dispatching.

---

### Q4: Why use MCP (Model Context Protocol)? What are your two tools?
**Answer:**
MCP establishes an open, standardized interface for tool exposure that is agent-agnostic.
1. **Tool 1 (`get_historical_market_data`):** Provides validated OHLCV time-series data with lookback bounds, caching metadata, and data quality checks.
2. **Tool 2 (`compute_financial_ratios` & `search_financial_document`):** Computes institutional balance sheet solvency ratios (Debt-to-Equity, Current Ratio, Operating Margin, ROE) and extracts bounded document snippets with verified page references from official annual reports.

---

### Q5: How do your security guardrails handle prompt injections vs. abusive customers?
**Answer:**
Our `GuardrailsEngine` implements a multi-layer defense:
- **Prompt Injections (`prompt_injection_user`):** Pattern matchers detect jailbreaks (e.g. "Ignore previous instructions", "DAN", "System override"), completely blocking the execution and flagging `PROMPT_INJECTION_ATTEMPT`.
- **Rude Customers (`rude_customer`):** As per real-world institutional standards, abrasive language is flagged (`LOW_TOXICITY_FLAG`) for auditing, but the financial request is **not blocked** because it carries no security exploit.
- **Resource Exhaustion (`oversized_request`):** Enforces strict upper bounds on prompt lengths (≤ 1000 chars) and lookback windows (≤ 500 days).

---

### Q6: Why did you use deterministic fixtures instead of live Yahoo Finance during evaluation?
**Answer:**
Live web APIs frequently rate-limit, alter data schemas, or experience outages, introducing non-deterministic failures into academic benchmarks. By implementing deterministic historical price fixtures for `TCS.NS`, `INFY.NS`, and `RELIANCE.NS` (228 trading bars each), we guarantee 100% offline reproducibility, zero flaky test runs, and transparent provenance attribution (`source="fixture"`).
