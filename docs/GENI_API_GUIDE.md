# StockShield 2.0 — GENI API Architecture & Integration Guide

**GENI = StockShield AI Analysis Assistant**

GENI is an institutional conversational explanation layer for StockShield 2.0. It allows users to ask natural language questions about a completed multi-agent stock analysis run without re-executing the workflow pipeline or modifying baseline results.

---

## 1. Architectural Overview

```
                                  [ Completed Analysis ]
                                             │
               ┌─────────────────────────────┴────────────────────────────┐
               ▼                                                          ▼
    SQLite (data/experiments.db)                          Snapshots (snapshots/<run_id>.json)
               │                                                          │
               └─────────────────────────────┬────────────────────────────┘
                                             ▼
                                [ GeniContextBuilder ]
                       (Extracts Sections A–F + Agent Conflicts)
                                             │
      User Request                           ▼
 [ POST /geni/chat ] ─────────► [ GeniService / Router ]
                                             │
                    ┌────────────────────────┴────────────────────────┐
                    ▼                                                 ▼
        [ GeniConversationManager ]                             [ GeniClient ]
           (data/geni_chat.db)                                (Google GenAI SDK)
          • WAL Mode Concurrency                             • Primary: gemini-3.8-flash
          • Run-Locked Validation                            • Transient Fallback
          • Multi-turn History (last 10)                     • Immediate 429 Abort
                    │                                                 │
                    └────────────────────────┬────────────────────────┘
                                             ▼
                                   [ GeniChatResponse ]
```

### Core Design Principles
1. **Strict Post-Hoc Explainer:** GENI operates exclusively on completed analyses (`status == "COMPLETED"`). It never triggers analysis agents or rewrites Blackboard state.
2. **Deterministic Source of Truth:** Stored analysis records in `ExperimentStorage` and immutable snapshots in `evaluation_results/snapshots/{run_id}.json` serve as the sole factual authority.
3. **Multi-Agent Signal Synthesis:** When specialized agents produce differing outputs (e.g., ADK Technical Agent is `BULLISH` while Risk Engine enforces `APPROVED_WITH_CAUTION` due to historical drawdowns or tail hazards), GENI explains the distinct mathematical lenses of each agent without overriding either.
4. **Isolated Conversation Persistence:** Conversation state is maintained in a dedicated SQLite database (`data/geni_chat.db`) configured with Write-Ahead Logging (WAL) and busy timeouts, ensuring zero risk of locking or modifying `data/experiments.db`.
5. **Run-Locked Threading:** Every `conversation_id` is permanently locked to its target `run_id`. Attempting to switch stocks or ask about a different run using an existing conversation ID is strictly rejected (`HTTP 400`).

---

## 2. API Endpoints

### 2.1 Ask GENI a Question: `POST /geni/chat`

#### Request Schema (`GeniChatRequest`)

| Field | Type | Required | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `run_id` | string | **Yes** | Target completed analysis run ID (alphanumeric `^run_[a-zA-Z0-9_\-]+$`) | `"run_3be6e1bfc274"` |
| `message` | string | **Yes** | Question or directive (1–4000 characters, no `<script>` tags) | `"Why is this stock marked as moderate risk?"` |
| `conversation_id` | string | Optional | Existing conversation thread ID (`^conv_[a-zA-Z0-9_\-]+$`). Omit or pass `null` to begin a new thread. | `"conv_89a1f2b3c4d5"` |

#### Request Example (New Conversation)
```json
{
  "run_id": "run_3be6e1bfc274",
  "message": "Why is this stock classified as moderate risk despite a bullish technical signal?",
  "conversation_id": null
}
```

#### Request Example (Follow-up Turn)
```json
{
  "run_id": "run_3be6e1bfc274",
  "message": "Which specific risk factor contributed most to the caution recommendation?",
  "conversation_id": "conv_89a1f2b3c4d5"
}
```

---

#### Response Schema (`GeniChatResponse`)

| Field | Type | Description |
| :--- | :--- | :--- |
| `run_id` | string | Target analysis run identifier |
| `conversation_id` | string | Persistent conversation thread identifier (reuse for subsequent turns) |
| `assistant_name` | string | Fixed identity (`"GENI"`) |
| `response` | string | Grounded natural language explanation |
| `status` | string | `"success"`, `"rate_limited"`, `"not_configured"`, or `"failed"` |
| `sources_used` | list[string] | Analysis domains referenced (e.g., `["technical_analysis", "risk_assessment"]`) |
| `model_used` | string / null | Actual Gemini model used to generate reply |
| `error` | string / null | Error message if status is non-success |
| `created_at_utc` | string | ISO 8601 generation timestamp |

#### Response Example
```json
{
  "run_id": "run_3be6e1bfc274",
  "conversation_id": "conv_89a1f2b3c4d5",
  "assistant_name": "GENI",
  "response": "HDFC Bank (HDFCBANK.NS) is classified as MODERATE risk (Composite Risk Score: 0.142) with an 'APPROVED_WITH_CAUTION' recommendation due to two specific governance flags:\n\n1. **Historical Drawdown Exposure:** The asset experienced a past historical drawdown of 28.63%, which triggers cautionary risk buffers under institutional short-term mandates.\n2. **Gate 8 Tail Hazard:** In the scenario stress tests, a 'Severe Market Crash' (-15% price drop, +100% volatility, negative sentiment) severely escalates the simulated risk score to 0.698, flipping the recommendation to 'REJECTED_HIGH_RISK'.\n\nWhile the Google ADK Technical Agent identifies strong BULLISH momentum (80% confidence, RSI 74.79, MACD positive), the Risk Engine acts as a conservative safety governor to ensure downside tail exposures are not ignored.",
  "status": "success",
  "sources_used": [
    "technical_analysis",
    "risk_assessment",
    "scenario_simulation"
  ],
  "model_used": "gemini-3.8-flash",
  "error": null,
  "created_at_utc": "2026-11-17T12:20:00.000000+00:00"
}
```

---

### 2.2 Retrieve Conversation Messages: `GET /geni/conversations/{conversation_id}/messages`

Returns the chronological turn history for a conversation thread.

#### Response Example
```json
[
  {
    "message_id": "msg_01a2b3c4d5e6",
    "conversation_id": "conv_89a1f2b3c4d5",
    "role": "user",
    "content": "Why is this stock classified as moderate risk?",
    "sources_used": ["risk_assessment"],
    "created_at_utc": "2026-11-17T12:20:00.000000+00:00"
  },
  {
    "message_id": "msg_02f3e4d5c6b7",
    "conversation_id": "conv_89a1f2b3c4d5",
    "role": "assistant",
    "content": "The stock is classified as MODERATE risk because...",
    "sources_used": ["risk_assessment", "scenario_simulation"],
    "created_at_utc": "2026-11-17T12:20:02.000000+00:00"
  }
]
```

---

### 2.3 List Conversations for Run: `GET /geni/conversations/run/{run_id}`

Lists all conversation threads initialized for a specific analysis run.

#### Response Example
```json
[
  {
    "conversation_id": "conv_89a1f2b3c4d5",
    "run_id": "run_3be6e1bfc274",
    "ticker": "HDFCBANK.NS",
    "created_at_utc": "2026-11-17T12:20:00+00:00",
    "updated_at_utc": "2026-11-17T12:21:15+00:00",
    "message_count": 4
  }
]
```

---

## 3. Error Handling & Status Codes

| HTTP Status | Error Type | Condition |
| :--- | :--- | :--- |
| **`400 Bad Request`** | `ConversationRunMismatchError` | Supplied `conversation_id` belongs to a different `run_id` than requested. |
| **`400 Bad Request`** | `AnalysisNotReadyError` | Target `run_id` is still `PENDING` or `RUNNING`. |
| **`400 Bad Request`** | `AnalysisFailedError` | Target `run_id` terminated with `FAILED` status. |
| **`404 Not Found`** | `RunNotFoundError` | Target `run_id` does not exist in SQLite or snapshot storage. |
| **`404 Not Found`** | `ConversationNotFoundError` | Supplied `conversation_id` does not exist. |
| **`422 Unprocessable`** | `ValueError` | Path traversal sequence in ID (`..`, `/`), empty message, or malicious script tag. |
| **`200 OK`** (with `status: "rate_limited"`) | Rate Limit Graceful Handshake | Gemini API daily quota exhausted (HTTP 429). The system informs the user gracefully without crashing. |

---

## 4. Environment Configuration

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | *(None)* | Google AI Studio API key used for Gemini calls. |
| `GENI_MODEL` | `gemini-3.8-flash` | Primary Gemini model for GENI explanations. |
| `GENI_TIMEOUT_SECONDS` | `30` | Request timeout per attempt. |
| `STOCKSHIELD_GENI_DB` | `data/geni_chat.db` | Dedicated SQLite database path for conversation threads. |

---

## 5. Verification & Testing

Run the automated GENI test suite:

```powershell
.venv\Scripts\pytest.exe tests/test_geni.py -v
```

All 23 test cases run fully mocked against the Google GenAI SDK, consuming 0 live API tokens.
