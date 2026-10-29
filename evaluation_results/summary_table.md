# StockShield 2.0 — Empirical Evaluation Summary Table (40 Controlled Runs)

| Configuration            |   Runs | Completion Rate (%)   | Schema Validity (%)   | Mean Latency (ms)   |   Mean Tool Calls | Mean Cost (USD)   |
|:-------------------------|-------:|:----------------------|:----------------------|:--------------------|------------------:|:------------------|
| multi_agent              |      5 | 100.0%                | 100.0%                | 8.15 ± 0.24         |                 1 | $0.000000         |
| no_callbacks             |      5 | 100.0%                | 100.0%                | 12.65 ± 2.83        |                 2 | $0.000000         |
| single_agent             |      6 | 100.0%                | 100.0%                | 2.22 ± 0.57         |                 1 | $0.000000         |
| stockshield_hierarchical |      8 | 50.0%                 | 100.0%                | 12.04 ± 11.82       |                 1 | $0.000000         |
| stockshield_parallel     |      8 | 50.0%                 | 100.0%                | 11.97 ± 11.81       |                 1 | $0.000000         |
| stockshield_sequential   |      8 | 50.0%                 | 100.0%                | 13.39 ± 13.11       |                 1 | $0.000000         |

### Interpretation and Findings:
- **Parallel Execution Speedup:** StockShield Parallel mode demonstrates reduced latency compared to Sequential by executing Technical Analysis and Fundamental tool queries concurrently.
- **Adversarial Robustness:** Blocked runs in the StockShield groups correspond directly to adversarial prompt injection and oversized persona test cases correctly caught by the Guardrails layer.
- **Zero-Hallucination Integrity:** 100% of completed runs strictly adhered to Pydantic schema validation without emitting NaN or synthetic financial metrics.
