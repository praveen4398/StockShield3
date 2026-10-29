# StockShield 2.0 — Empirical Evaluation Methodology

## 1. Experimental Design & Objectives
The evaluation evaluates the trade-offs in multi-agent orchestration across four dimensions:
1. **Computational Latency:** End-to-end execution wall-clock time in milliseconds.
2. **Schema & Provenance Completeness:** Verification of Pydantic data contract enforcement and field-level producer attribution.
3. **Adversarial Resilience:** Defensive efficacy against prompt injections, toxic wording, malformed inputs, and resource exhaustion.
4. **Token Usage & Economic Projections:** Accurate cost projections based on versioned commercial LLM pricing models.

---

## 2. The 6 Experimental Configuration Groups (40 Runs)

| Group | Configuration | Workflow Mode | Runs | Evaluation Target |
|---|---|---|---:|---|
| **Group 1** | `stockshield_sequential` | Sequential | 8 | Full orchestration pipeline with serial task execution. |
| **Group 2** | `stockshield_parallel` | Parallel | 8 | Concurrent execution of Technical and Fundamental tasks. |
| **Group 3** | `stockshield_hierarchical`| Hierarchical | 8 | Supervisor orchestrator delegating sub-tasks conditionally. |
| **Group 4** | `single_agent` | Monolithic | 6 | Baseline monolithic execution without blackboard modularity. |
| **Group 5** | `multi_agent` | Cooperative | 5 | Multi-agent collaboration without extended callback logging. |
| **Group 6** | `no_callbacks` | Ablation | 5 | Full StockShield workflow with event persistence disabled. |
| **Total** | | | **40** | Controlled, balanced empirical evaluation. |

---

## 3. Stock Universe & Persona Rotation
- **Equities:** `TCS.NS`, `INFY.NS`, `RELIANCE.NS` (NSE Indian Equities).
- **Historical Fixtures:** Verified 228 daily trading bars per asset, adjusted close basis, retrieved from institutional test fixtures.
- **Personas Tested:**
  - `neutral_analyst`: Standard valid institutional request.
  - `rude_customer`: Aggressive tone without exploits (tests false-positive behavior).
  - `prompt_injection_user`: Adversarial system prompt overrides and jailbreaks.
  - `malformed_input`: Schema and parameter corruption.

---

## 4. Token & Cost Estimation Formula
- **Input Token Rate:** $0.075 per 1,000,000 tokens (Gemini 1.5 Flash Rate Table v2025.1).
- **Output Token Rate:** $0.300 per 1,000,000 tokens.
- **Formula:**
  $$\text{Cost} = \left(\frac{\text{Tokens}_{\text{in}}}{10^6} \times 0.075\right) + \left(\frac{\text{Tokens}_{\text{out}}}{10^6} \times 0.300\right)$$
- **Stub Policy:** Because deterministic stub adapters incur no live API charges, the reported API expenditure is $0.000000, while projected commercial costs are retained in logs for academic evaluation.
