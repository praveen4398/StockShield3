# StockShield 2.0 — Empirical Evaluation Summary Table (40 Controlled Runs)

| Configuration            |   Runs |   Completed |   Expected Blocks |   Unexpected Fails | Completion Rate (%)   | Schema Validity (%)   | Mean Latency (ms) [Completed]   |   Distinct MCP Tools [Completed] | Mean Cost (USD)   |
|:-------------------------|-------:|------------:|------------------:|-------------------:|:----------------------|:----------------------|:--------------------------------|---------------------------------:|:------------------|
| no_callbacks             |      4 |           4 |                 0 |                  0 | 100.0%                | 100.0%                | 1261.53 ± 275.06                |                                2 | $0.000000         |
| stockshield_hierarchical |     12 |          12 |                 0 |                  0 | 100.0%                | 100.0%                | 1282.31 ± 400.08                |                                2 | $0.000000         |
| stockshield_parallel     |     12 |          12 |                 0 |                  0 | 100.0%                | 100.0%                | 1114.38 ± 338.24                |                                2 | $0.000000         |
| stockshield_sequential   |     12 |          12 |                 0 |                  0 | 100.0%                | 100.0%                | 1125.23 ± 342.54                |                                2 | $0.000000         |

### Statistical Rigor & Hypothesis Testing:
- **Sequential vs. Parallel Latency:** Welch's t-test (t=0.08, df=22.0) indicates that the latency difference between Sequential (1125.2ms) and Parallel (1114.4ms) is evaluated under alpha=0.05. Parallel execution schedules concurrent tasks via asyncio.gather while sequential executes in lockstep.
- **Tool-Call Reconciled Analysis:** Completed StockShield runs invoke exactly 2 distinct MCP tools (`get_historical_market_data` and `compute_financial_ratios`). Blocked runs invoke 0 tools because execution terminates at perimeter guardrails. In v1, averaging across blocked runs created the artifact of 1.0 tool calls.
- **Outcome Classification:** All 40 runs are categorized into `completed` (40 runs), `expected_guardrail_block` (0 runs), and `unexpected_failure` (0 runs). Zero unexpected crashes occurred.
- **Multi-Agent Specialization:** Integrates Google ADK Quantitative Analyst, News & Sentiment Agent, Multi-Model Forecasting (ARIMA/ExpSmoothing/LightGBM), Deterministic Risk Engine (Gates 1-7), Scenario Simulation (Gate 8 with 1,000-path Monte Carlo GBM), CrewAI Lead Orchestrator, and Gemini LLM-as-a-Judge.
