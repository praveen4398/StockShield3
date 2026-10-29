# StockShield 2.0 — Reconciled Evaluation Summary Table (40 Controlled Runs)

| Configuration            |   Runs |   Completed |   Expected Blocks |   Unexpected Fails | Completion Rate (%)   | Schema Validity (%)   | Mean Latency (ms) [Completed]   |   Distinct MCP Tools [Completed] | Mean Cost (USD)   |
|:-------------------------|-------:|------------:|------------------:|-------------------:|:----------------------|:----------------------|:--------------------------------|---------------------------------:|:------------------|
| multi_agent              |      5 |           5 |                 0 |                  0 | 100.0%                | 100.0%                | 12.31 ± 3.65                    |                                1 | $0.000000         |
| no_callbacks             |      5 |           5 |                 0 |                  0 | 100.0%                | 100.0%                | 63.39 ± 14.61                   |                                2 | $0.000000         |
| single_agent             |      6 |           6 |                 0 |                  0 | 100.0%                | 100.0%                | 1.14 ± 0.44                     |                                1 | $0.000000         |
| stockshield_hierarchical |      8 |           4 |                 4 |                  0 | 50.0%                 | 100.0%                | 57.92 ± 2.23                    |                                2 | $0.000000         |
| stockshield_parallel     |      8 |           4 |                 4 |                  0 | 50.0%                 | 100.0%                | 83.08 ± 38.52                   |                                2 | $0.000000         |
| stockshield_sequential   |      8 |           4 |                 4 |                  0 | 50.0%                 | 100.0%                | 370.04 ± 463.74                 |                                2 | $0.000000         |

### Statistical Rigor & Hypothesis Testing:
- **Sequential vs. Parallel Latency:** Welch's t-test (t=1.23, df=3.0) indicates that the latency difference between Sequential (370.0ms) and Parallel (83.1ms) is NOT statistically significant at alpha=0.05. Small sample sizes and overlapping variance show no definitive superiority.
- **Tool-Call Reconciled Analysis:** Completed StockShield runs invoke exactly 2 distinct MCP tools (`get_historical_market_data` and `compute_financial_ratios`). Blocked runs invoke 0 tools because execution terminates at perimeter guardrails. In v1, averaging across blocked runs created the artifact of 1.0 tool calls.
- **Outcome Classification:** All 40 runs are categorized into `completed` (26 runs), `expected_guardrail_block` (14 runs), and `unexpected_failure` (0 runs). Zero unexpected crashes occurred.
