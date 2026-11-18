# StockShield 2.0 — Saved Results

This folder stores JSON analysis results from the StockShield 2.0 frontend.

## File Naming Convention
`{TICKER}_{TIMESTAMP}.json`

Example: `TCS_2024-01-15T10-30-00.json`

## Structure
Each saved JSON file contains the full analysis response from the `/analyze` API endpoint including:
- `run_id` — Unique analysis run identifier
- `ticker` — NSE stock symbol (e.g., TCS.NS)
- `technical_findings` — Indicators, signals, confidence
- `news_and_sentiment` — Articles, sentiment scores, events
- `risk_findings` — Risk score, recommendation, warnings
- `forecasting` — Model results, price forecasts, confidence intervals
- `scenario_simulation` — Stress test results, Monte Carlo data
- `judge_evaluation` — Gemini LLM evaluation scores
- `final_report` — Executive summary and full markdown report

## Usage
Results are automatically saved when you run an analysis from the Dashboard.
You can view, reload, or download them from the **Saved Results** page.

> Note: Results are also stored in browser `localStorage` for quick access.
