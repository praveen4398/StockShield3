"""Persistent Experiment Result Storage for StockShield 2.0.

Provides durable SQLite storage, incremental stage updates, JSON snapshot archival,
and academic CSV exports for empirical evaluations, pilot runs, and institutional benchmarks.
"""

import csv
import json
import logging
import os
import re
import sqlite3
import subprocess
import threading
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("stockshield.evaluation.storage")

CURRENT_SCHEMA_VERSION = 1
DEFAULT_DB_PATH = "evaluation_results/experiments.db"
DEFAULT_SNAPSHOT_DIR = "evaluation_results/snapshots"
DEFAULT_EXPORT_DIR = "evaluation_results"


class RunStatus(str, Enum):
    """Categorical states for an empirical experiment or analysis run."""

    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


# Sensitive key pattern for redacting secrets before serialization
SECRET_PATTERN = re.compile(r"api_key|token|secret|password|credential|gemini_api_key", re.IGNORECASE)


def redact_secrets(data: Any) -> Any:
    """Recursively scrub any sensitive credentials or secrets."""
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            if SECRET_PATTERN.search(str(k)):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = redact_secrets(v)
        return sanitized
    elif isinstance(data, list):
        return [redact_secrets(item) for item in data]
    return data


def safe_json_dumps(obj: Any) -> str:
    """Safely serialize an object to JSON string with secret redaction and default fallback."""
    clean_obj = redact_secrets(obj)
    try:
        return json.dumps(clean_obj, default=str)
    except Exception:
        return json.dumps({"serialization_error": "Object could not be serialized"}, default=str)


def get_git_commit_hash() -> Optional[str]:
    """Retrieve current Git commit SHA-1 if available."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return None


class ExperimentStorage:
    """Canonical SQLite-backed persistence engine for StockShield 2.0 runs.

    Features:
    - Write-Ahead Logging (WAL) and thread-safe connection pooling for concurrency.
    - Zero data loss: immediate run registration and incremental per-stage updates.
    - Preserves partial stage achievements upon agent or judge failure.
    - Full-fidelity JSON snapshots on filesystem and canonical SQLite column.
    - 4 standardized academic CSV exports: runs_summary, judge_scores, performance_metrics, forecast_metrics.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        snapshot_dir: Optional[str] = None,
        export_dir: Optional[str] = None,
    ):
        raw_db_path = db_path or os.getenv("STOCKSHIELD_EVAL_DB", DEFAULT_DB_PATH)
        self.db_path = Path(raw_db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        raw_snap_dir = snapshot_dir or os.getenv("STOCKSHIELD_SNAPSHOT_DIR", DEFAULT_SNAPSHOT_DIR)
        self.snapshot_dir = Path(raw_snap_dir).resolve()
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

        raw_exp_dir = export_dir or os.getenv("STOCKSHIELD_EXPORT_DIR", DEFAULT_EXPORT_DIR)
        self.export_dir = Path(raw_exp_dir).resolve()
        self.export_dir.mkdir(parents=True, exist_ok=True)

        self._lock = threading.RLock()
        self._initialize_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Create and configure a SQLite connection with WAL and foreign keys."""
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=15.0,
            check_same_thread=False,
            isolation_level=None,  # Autocommit mode; transactions handled explicitly
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA busy_timeout = 10000;")
        return conn

    def _initialize_database(self):
        """Create tables, indexes, and record schema version if not existing."""
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("BEGIN IMMEDIATE;")

                # 1. Schema Version Table
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_version (
                        version INTEGER PRIMARY KEY,
                        applied_at_utc TEXT NOT NULL,
                        description TEXT
                    );
                    """
                )

                # 2. Canonical Runs Table
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS runs (
                        run_id TEXT PRIMARY KEY,
                        experiment_id TEXT NOT NULL,
                        ticker TEXT NOT NULL,
                        workflow_mode TEXT NOT NULL,
                        status TEXT NOT NULL,
                        started_at_utc TEXT NOT NULL,
                        completed_at_utc TEXT,
                        total_duration_ms REAL,
                        app_version TEXT,
                        git_commit TEXT,
                        config_json TEXT,
                        error_message TEXT,
                        snapshot_path TEXT,
                        snapshot_json TEXT,
                        created_at_utc TEXT NOT NULL,
                        updated_at_utc TEXT NOT NULL
                    );
                    """
                )

                # 3. Market Data Stage Table
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS stage_market_data (
                        run_id TEXT PRIMARY KEY,
                        status TEXT,
                        provider TEXT,
                        source TEXT,
                        bar_count INTEGER,
                        data_quality TEXT,
                        is_stale INTEGER,
                        freshness_age_days INTEGER,
                        start_date TEXT,
                        end_date TEXT,
                        warnings_json TEXT,
                        raw_json TEXT,
                        FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
                    );
                    """
                )

                # 4. Technical Analysis Stage Table
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS stage_technical (
                        run_id TEXT PRIMARY KEY,
                        status TEXT,
                        signal TEXT,
                        confidence REAL,
                        indicators_json TEXT,
                        summary TEXT,
                        raw_json TEXT,
                        FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
                    );
                    """
                )

                # 5. News & Sentiment Stage Table
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS stage_news_sentiment (
                        run_id TEXT PRIMARY KEY,
                        status TEXT,
                        source TEXT,
                        overall_sentiment TEXT,
                        sentiment_score REAL,
                        total_articles INTEGER,
                        positive_count INTEGER,
                        neutral_count INTEGER,
                        negative_count INTEGER,
                        event_categories_json TEXT,
                        articles_json TEXT,
                        warnings_json TEXT,
                        raw_json TEXT,
                        FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
                    );
                    """
                )

                # 6. Forecasting Stage Table
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS stage_forecasting (
                        run_id TEXT PRIMARY KEY,
                        status TEXT,
                        selected_model TEXT,
                        selection_reason TEXT,
                        directional_accuracy REAL,
                        forecast_label TEXT,
                        is_stale_data INTEGER,
                        models_evaluated_json TEXT,
                        predictions_json TEXT,
                        warnings_json TEXT,
                        raw_json TEXT,
                        FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
                    );
                    """
                )

                # 7. Risk Analysis Stage Table
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS stage_risk (
                        run_id TEXT PRIMARY KEY,
                        status TEXT,
                        composite_score REAL,
                        risk_level TEXT,
                        recommendation TEXT,
                        gate_scores_json TEXT,
                        warnings_json TEXT,
                        reasons_json TEXT,
                        raw_json TEXT,
                        FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
                    );
                    """
                )

                # 8. Scenario Simulation Stage Table
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS stage_scenario_simulation (
                        run_id TEXT PRIMARY KEY,
                        status TEXT,
                        total_scenarios INTEGER,
                        worst_case_name TEXT,
                        worst_case_price_drop_pct REAL,
                        scenarios_flipping_recommendation INTEGER,
                        scenarios_material_risk_increase INTEGER,
                        monte_carlo_runs INTEGER,
                        cvar_95_pct REAL,
                        loss_probability REAL,
                        max_drawdown_pct REAL,
                        scenarios_json TEXT,
                        raw_json TEXT,
                        FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
                    );
                    """
                )

                # 9. Gemini Judge Evaluation Stage Table
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS stage_judge (
                        run_id TEXT PRIMARY KEY,
                        status TEXT,
                        configured_model TEXT,
                        actual_model TEXT,
                        fallback_triggered INTEGER,
                        overall_score REAL,
                        verdict TEXT,
                        factual_grounding REAL,
                        completeness REAL,
                        cross_agent_consistency REAL,
                        forecasting_assessment REAL,
                        risk_reasoning REAL,
                        financial_safety REAL,
                        dimensions_json TEXT,
                        evaluation_summary TEXT,
                        critical_findings_json TEXT,
                        warnings_json TEXT,
                        strengths_json TEXT,
                        limitations_json TEXT,
                        input_tokens INTEGER,
                        output_tokens INTEGER,
                        total_tokens INTEGER,
                        latency_ms REAL,
                        estimated_cost_usd REAL,
                        cost_status TEXT,
                        attempt_history_json TEXT,
                        error_message TEXT,
                        raw_json TEXT,
                        FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
                    );
                    """
                )

                # 10. Performance & Execution Events Table
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS stage_performance (
                        run_id TEXT PRIMARY KEY,
                        total_duration_ms REAL,
                        agent_durations_json TEXT,
                        events_count INTEGER,
                        error_count INTEGER,
                        execution_events_json TEXT,
                        raw_json TEXT,
                        FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
                    );
                    """
                )

                # Indexes for query acceleration
                conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_experiment_id ON runs(experiment_id);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_ticker ON runs(ticker);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_started_at ON runs(started_at_utc);")

                # Insert initial schema version if empty
                cur = conn.execute("SELECT version FROM schema_version WHERE version = ?;", (CURRENT_SCHEMA_VERSION,))
                if cur.fetchone() is None:
                    now_utc = datetime.now(timezone.utc).isoformat()
                    conn.execute(
                        "INSERT INTO schema_version (version, applied_at_utc, description) VALUES (?, ?, ?);",
                        (CURRENT_SCHEMA_VERSION, now_utc, "StockShield 2.0 Canonical Experiment Database Schema"),
                    )

                conn.execute("COMMIT;")
            except Exception as e:
                conn.execute("ROLLBACK;")
                logger.error("Failed to initialize database: %s", e)
                raise
            finally:
                conn.close()

    # -----------------------------------------------------------------------
    # Lifecycle Operations
    # -----------------------------------------------------------------------
    def create_run(
        self,
        run_id: str,
        experiment_id: str,
        ticker: str,
        workflow_mode: str,
        config: Optional[Dict[str, Any]] = None,
        started_at_utc: Optional[str] = None,
    ) -> str:
        """Create a new run record with status RUNNING.

        Raises ValueError if run_id already exists to strictly prevent accidental overwrites.
        """
        now_utc = started_at_utc or datetime.now(timezone.utc).isoformat()
        git_sha = get_git_commit_hash()
        app_ver = "2.0.0"
        try:
            from stockshield import __version__

            app_ver = __version__
        except Exception:
            pass

        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("BEGIN IMMEDIATE;")
                # Check for existing run_id
                cur = conn.execute("SELECT run_id FROM runs WHERE run_id = ?;", (run_id,))
                if cur.fetchone() is not None:
                    raise ValueError(f"Run ID '{run_id}' already exists in database. Overwrites are strictly prohibited.")

                conn.execute(
                    """
                    INSERT INTO runs (
                        run_id, experiment_id, ticker, workflow_mode, status,
                        started_at_utc, app_version, git_commit, config_json,
                        created_at_utc, updated_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        run_id,
                        experiment_id,
                        ticker,
                        workflow_mode,
                        RunStatus.RUNNING.value,
                        now_utc,
                        app_ver,
                        git_sha,
                        safe_json_dumps(config or {}),
                        now_utc,
                        now_utc,
                    ),
                )
                conn.execute("COMMIT;")
                return run_id
            except Exception:
                conn.execute("ROLLBACK;")
                raise
            finally:
                conn.close()

    def record_stage_market_data(self, run_id: str, market_data_obj: Any):
        """Persist market data stage results incrementally."""
        now_utc = datetime.now(timezone.utc).isoformat()
        bars = getattr(market_data_obj, "bars", []) or []
        start_dt = bars[0].get("timestamp") if bars and isinstance(bars[0], dict) else None
        end_dt = bars[-1].get("timestamp") if bars and isinstance(bars[-1], dict) else None

        status_val = getattr(market_data_obj, "status", None)
        status_str = status_val.value if hasattr(status_val, "value") else str(status_val or "")

        data_quality = getattr(market_data_obj, "data_quality_status", None) or getattr(
            market_data_obj, "data_quality", None
        )
        is_stale_val = 1 if getattr(market_data_obj, "is_stale", False) else 0

        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("BEGIN IMMEDIATE;")
                conn.execute(
                    """
                    INSERT OR REPLACE INTO stage_market_data (
                        run_id, status, provider, source, bar_count,
                        data_quality, is_stale, freshness_age_days,
                        start_date, end_date, warnings_json, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        run_id,
                        status_str,
                        getattr(market_data_obj, "source", "unknown"),
                        getattr(market_data_obj, "source", "unknown"),
                        getattr(market_data_obj, "bar_count", len(bars)),
                        str(data_quality) if data_quality else None,
                        is_stale_val,
                        getattr(market_data_obj, "freshness_age_days", None),
                        str(start_dt) if start_dt else None,
                        str(end_dt) if end_dt else None,
                        safe_json_dumps(getattr(market_data_obj, "warnings", [])),
                        safe_json_dumps(
                            market_data_obj.model_dump()
                            if hasattr(market_data_obj, "model_dump")
                            else market_data_obj
                        ),
                    ),
                )
                conn.execute("UPDATE runs SET updated_at_utc = ? WHERE run_id = ?;", (now_utc, run_id))
                conn.execute("COMMIT;")
            except Exception as e:
                conn.execute("ROLLBACK;")
                logger.error("Error recording market data stage for %s: %s", run_id, e)
            finally:
                conn.close()

    def record_stage_technical(self, run_id: str, technical_obj: Any):
        """Persist technical analysis stage results incrementally."""
        now_utc = datetime.now(timezone.utc).isoformat()
        status_val = getattr(technical_obj, "status", None)
        status_str = status_val.value if hasattr(status_val, "value") else str(status_val or "")

        indicators = getattr(technical_obj, "indicators", {})
        if hasattr(indicators, "model_dump"):
            ind_dict = indicators.model_dump()
        elif isinstance(indicators, dict):
            ind_dict = indicators
        else:
            ind_dict = {}

        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("BEGIN IMMEDIATE;")
                conn.execute(
                    """
                    INSERT OR REPLACE INTO stage_technical (
                        run_id, status, signal, confidence,
                        indicators_json, summary, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        run_id,
                        status_str,
                        getattr(technical_obj, "signal", None),
                        getattr(technical_obj, "signal_confidence", None),
                        safe_json_dumps(ind_dict),
                        getattr(technical_obj, "summary", None),
                        safe_json_dumps(
                            technical_obj.model_dump() if hasattr(technical_obj, "model_dump") else technical_obj
                        ),
                    ),
                )
                conn.execute("UPDATE runs SET updated_at_utc = ? WHERE run_id = ?;", (now_utc, run_id))
                conn.execute("COMMIT;")
            except Exception as e:
                conn.execute("ROLLBACK;")
                logger.error("Error recording technical stage for %s: %s", run_id, e)
            finally:
                conn.close()

    def record_stage_news_sentiment(self, run_id: str, news_obj: Any):
        """Persist news and sentiment stage results incrementally."""
        now_utc = datetime.now(timezone.utc).isoformat()
        status_val = getattr(news_obj, "status", None)
        status_str = status_val.value if hasattr(status_val, "value") else str(status_val or "")

        articles = getattr(news_obj, "articles", []) or []
        art_list = [a.model_dump() if hasattr(a, "model_dump") else a for a in articles]

        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("BEGIN IMMEDIATE;")
                conn.execute(
                    """
                    INSERT OR REPLACE INTO stage_news_sentiment (
                        run_id, status, source, overall_sentiment, sentiment_score,
                        total_articles, positive_count, neutral_count, negative_count,
                        event_categories_json, articles_json, warnings_json, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        run_id,
                        status_str,
                        getattr(news_obj, "source", None),
                        getattr(news_obj, "overall_sentiment", None),
                        getattr(news_obj, "sentiment_score", None),
                        getattr(news_obj, "total_articles", len(art_list)),
                        getattr(news_obj, "positive_count", 0),
                        getattr(news_obj, "neutral_count", 0),
                        getattr(news_obj, "negative_count", 0),
                        safe_json_dumps(getattr(news_obj, "positive_events", []) + getattr(news_obj, "negative_events", [])),
                        safe_json_dumps(art_list),
                        safe_json_dumps(getattr(news_obj, "risk_observations", [])),
                        safe_json_dumps(news_obj.model_dump() if hasattr(news_obj, "model_dump") else news_obj),
                    ),
                )
                conn.execute("UPDATE runs SET updated_at_utc = ? WHERE run_id = ?;", (now_utc, run_id))
                conn.execute("COMMIT;")
            except Exception as e:
                conn.execute("ROLLBACK;")
                logger.error("Error recording news sentiment stage for %s: %s", run_id, e)
            finally:
                conn.close()

    def record_stage_forecasting(self, run_id: str, forecast_obj: Any):
        """Persist statistical and ML forecasting models and projections."""
        now_utc = datetime.now(timezone.utc).isoformat()
        status_val = getattr(forecast_obj, "status", None)
        status_str = status_val.value if hasattr(status_val, "value") else str(status_val or "")

        models = getattr(forecast_obj, "models", []) or []
        models_data = []
        for m in models:
            m_dict = {
                "model_name": getattr(m, "model_name", None),
                "status": getattr(m, "status", None),
                "rmse": getattr(getattr(m, "validation_metrics", None), "rmse", None),
                "mae": getattr(getattr(m, "validation_metrics", None), "mae", None),
                "directional_accuracy": getattr(getattr(m, "validation_metrics", None), "directional_accuracy", None),
            }
            models_data.append(m_dict)

        best_m = getattr(forecast_obj, "best_model", None)
        selected_model_name = getattr(best_m, "model_name", None) if best_m else getattr(forecast_obj, "selected_model_name", None)
        dir_acc = getattr(getattr(best_m, "validation_metrics", None), "directional_accuracy", None) if best_m else None

        forecasts = getattr(best_m, "forecasts", []) if best_m else getattr(forecast_obj, "selected_forecasts", [])
        pred_list = [f.model_dump() if hasattr(f, "model_dump") else f for f in (forecasts or [])]

        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("BEGIN IMMEDIATE;")
                conn.execute(
                    """
                    INSERT OR REPLACE INTO stage_forecasting (
                        run_id, status, selected_model, selection_reason,
                        directional_accuracy, forecast_label, is_stale_data,
                        models_evaluated_json, predictions_json, warnings_json, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        run_id,
                        status_str,
                        selected_model_name,
                        getattr(forecast_obj, "selection_reason", None),
                        dir_acc,
                        getattr(forecast_obj, "forecast_label", None),
                        1 if getattr(forecast_obj, "is_stale_data", False) else 0,
                        safe_json_dumps(models_data),
                        safe_json_dumps(pred_list),
                        safe_json_dumps(getattr(forecast_obj, "warnings", [])),
                        safe_json_dumps(forecast_obj.model_dump() if hasattr(forecast_obj, "model_dump") else forecast_obj),
                    ),
                )
                conn.execute("UPDATE runs SET updated_at_utc = ? WHERE run_id = ?;", (now_utc, run_id))
                conn.execute("COMMIT;")
            except Exception as e:
                conn.execute("ROLLBACK;")
                logger.error("Error recording forecasting stage for %s: %s", run_id, e)
            finally:
                conn.close()

    def record_stage_risk(self, run_id: str, risk_obj: Any):
        """Persist deterministic institutional risk evaluation results."""
        now_utc = datetime.now(timezone.utc).isoformat()
        status_val = getattr(risk_obj, "status", None)
        status_str = status_val.value if hasattr(status_val, "value") else str(status_val or "")

        checks = getattr(risk_obj, "checks", []) or []
        check_list = [c.model_dump() if hasattr(c, "model_dump") else c for c in checks]

        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("BEGIN IMMEDIATE;")
                conn.execute(
                    """
                    INSERT OR REPLACE INTO stage_risk (
                        run_id, status, composite_score, risk_level,
                        recommendation, gate_scores_json, warnings_json,
                        reasons_json, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        run_id,
                        status_str,
                        getattr(risk_obj, "composite_risk_score", None),
                        getattr(risk_obj, "overall_risk_level", None),
                        getattr(risk_obj, "recommendation", None),
                        safe_json_dumps(check_list),
                        safe_json_dumps(getattr(risk_obj, "warnings", [])),
                        safe_json_dumps(getattr(risk_obj, "reasons", [])),
                        safe_json_dumps(risk_obj.model_dump() if hasattr(risk_obj, "model_dump") else risk_obj),
                    ),
                )
                conn.execute("UPDATE runs SET updated_at_utc = ? WHERE run_id = ?;", (now_utc, run_id))
                conn.execute("COMMIT;")
            except Exception as e:
                conn.execute("ROLLBACK;")
                logger.error("Error recording risk stage for %s: %s", run_id, e)
            finally:
                conn.close()

    def record_stage_scenario_simulation(self, run_id: str, sim_obj: Any):
        """Persist scenario simulation, stress testing, and Monte Carlo results."""
        now_utc = datetime.now(timezone.utc).isoformat()
        status_val = getattr(sim_obj, "status", None)
        status_str = status_val.value if hasattr(status_val, "value") else str(status_val or "")

        worst_case = getattr(sim_obj, "worst_case_scenario", None)
        worst_name = getattr(worst_case, "scenario_name", None) if worst_case else None
        worst_drop = getattr(getattr(worst_case, "simulated", None), "percentage_price_change", None) if worst_case else None

        mc = getattr(sim_obj, "monte_carlo_result", None) or getattr(sim_obj, "monte_carlo", None)
        mc_runs = getattr(mc, "num_simulations", None) or getattr(mc, "paths_simulated", None) if mc else None
        cvar = getattr(mc, "probability_severe_loss_pct", None) or getattr(mc, "cvar_95_pct", None) if mc else None
        prob_loss = getattr(mc, "probability_loss_pct", None) or getattr(mc, "loss_probability", None) if mc else None
        max_dd = getattr(mc, "max_drawdown_pct", None) if mc else None

        flip_recs = getattr(sim_obj, "scenarios_changing_recommendation", None)
        flip_count = len(flip_recs) if isinstance(flip_recs, list) else (flip_recs if isinstance(flip_recs, int) else None)
        mat_risk = getattr(sim_obj, "scenarios_material_risk_increase", None)
        mat_count = len(mat_risk) if isinstance(mat_risk, list) else (mat_risk if isinstance(mat_risk, int) else None)

        scenarios = getattr(sim_obj, "scenarios", []) or []
        scen_list = [s.model_dump() if hasattr(s, "model_dump") else s for s in scenarios[:10]]

        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("BEGIN IMMEDIATE;")
                conn.execute(
                    """
                    INSERT OR REPLACE INTO stage_scenario_simulation (
                        run_id, status, total_scenarios, worst_case_name,
                        worst_case_price_drop_pct, scenarios_flipping_recommendation,
                        scenarios_material_risk_increase, monte_carlo_runs,
                        cvar_95_pct, loss_probability, max_drawdown_pct,
                        scenarios_json, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        run_id,
                        status_str,
                        getattr(sim_obj, "total_scenarios_evaluated", len(scenarios)),
                        worst_name,
                        worst_drop,
                        flip_count,
                        mat_count,
                        mc_runs,
                        cvar,
                        prob_loss,
                        max_dd,
                        safe_json_dumps(scen_list),
                        safe_json_dumps(sim_obj.model_dump() if hasattr(sim_obj, "model_dump") else sim_obj),
                    ),
                )
                conn.execute("UPDATE runs SET updated_at_utc = ? WHERE run_id = ?;", (now_utc, run_id))
                conn.execute("COMMIT;")
            except Exception as e:
                conn.execute("ROLLBACK;")
                logger.error("Error recording scenario simulation stage for %s: %s", run_id, e)
            finally:
                conn.close()

    def record_stage_judge(self, run_id: str, judge_obj: Any):
        """Persist Gemini LLM-as-a-Judge evaluations and individual rubric dimensions."""
        now_utc = datetime.now(timezone.utc).isoformat()
        status_str = getattr(judge_obj, "status", "pending")

        dims = getattr(judge_obj, "dimensions", {}) or {}
        dim_scores: Dict[str, Optional[float]] = {}
        for d_name in [
            "factual_grounding",
            "completeness",
            "cross_agent_consistency",
            "forecasting_assessment",
            "risk_reasoning",
            "financial_safety",
        ]:
            dim_val = dims.get(d_name)
            dim_scores[d_name] = getattr(dim_val, "score", None) if dim_val else None

        dims_serialized = {
            k: (v.model_dump() if hasattr(v, "model_dump") else v) for k, v in dims.items()
        }

        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("BEGIN IMMEDIATE;")
                conn.execute(
                    """
                    INSERT OR REPLACE INTO stage_judge (
                        run_id, status, configured_model, actual_model,
                        fallback_triggered, overall_score, verdict,
                        factual_grounding, completeness, cross_agent_consistency,
                        forecasting_assessment, risk_reasoning, financial_safety,
                        dimensions_json, evaluation_summary, critical_findings_json,
                        warnings_json, strengths_json, limitations_json,
                        input_tokens, output_tokens, total_tokens, latency_ms,
                        estimated_cost_usd, cost_status, attempt_history_json,
                        error_message, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        run_id,
                        status_str,
                        getattr(judge_obj, "configured_model", None),
                        getattr(judge_obj, "actual_model", None),
                        1 if getattr(judge_obj, "fallback_triggered", False) else 0,
                        getattr(judge_obj, "overall_score", None),
                        getattr(judge_obj, "verdict", None),
                        dim_scores.get("factual_grounding"),
                        dim_scores.get("completeness"),
                        dim_scores.get("cross_agent_consistency"),
                        dim_scores.get("forecasting_assessment"),
                        dim_scores.get("risk_reasoning"),
                        dim_scores.get("financial_safety"),
                        safe_json_dumps(dims_serialized),
                        getattr(judge_obj, "evaluation_summary", ""),
                        safe_json_dumps(getattr(judge_obj, "critical_findings", [])),
                        safe_json_dumps(getattr(judge_obj, "warnings", [])),
                        safe_json_dumps(getattr(judge_obj, "strengths", [])),
                        safe_json_dumps(getattr(judge_obj, "limitations", [])),
                        getattr(judge_obj, "input_tokens", None),
                        getattr(judge_obj, "output_tokens", None),
                        getattr(judge_obj, "total_tokens", None),
                        getattr(judge_obj, "latency_ms", None),
                        getattr(judge_obj, "estimated_cost_usd", None),
                        getattr(judge_obj, "cost_status", "unavailable"),
                        safe_json_dumps(getattr(judge_obj, "attempt_history", [])),
                        getattr(judge_obj, "error_message", None),
                        safe_json_dumps(judge_obj.model_dump() if hasattr(judge_obj, "model_dump") else judge_obj),
                    ),
                )
                conn.execute("UPDATE runs SET updated_at_utc = ? WHERE run_id = ?;", (now_utc, run_id))
                conn.execute("COMMIT;")
            except Exception as e:
                conn.execute("ROLLBACK;")
                logger.error("Error recording judge stage for %s: %s", run_id, e)
            finally:
                conn.close()

    def record_stage_performance(
        self,
        run_id: str,
        total_duration_ms: float,
        agent_durations: Dict[str, float],
        execution_events: List[Dict[str, Any]],
        error_count: int = 0,
    ):
        """Persist pipeline timing and agent execution trace events."""
        now_utc = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("BEGIN IMMEDIATE;")
                conn.execute(
                    """
                    INSERT OR REPLACE INTO stage_performance (
                        run_id, total_duration_ms, agent_durations_json,
                        events_count, error_count, execution_events_json, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        run_id,
                        total_duration_ms,
                        safe_json_dumps(agent_durations),
                        len(execution_events),
                        error_count,
                        safe_json_dumps(execution_events),
                        safe_json_dumps({"total_duration_ms": total_duration_ms, "agent_durations": agent_durations}),
                    ),
                )
                conn.execute("UPDATE runs SET updated_at_utc = ? WHERE run_id = ?;", (now_utc, run_id))
                conn.execute("COMMIT;")
            except Exception as e:
                conn.execute("ROLLBACK;")
                logger.error("Error recording performance stage for %s: %s", run_id, e)
            finally:
                conn.close()

    def record_state(
        self,
        run_id: str,
        state: Any,
        status: RunStatus = RunStatus.COMPLETED,
        duration_ms: Optional[float] = None,
        final_response: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ):
        """Populate all constituent stage tables from a BlackboardState snapshot atomically."""
        if hasattr(state, "market_data"):
            self.record_stage_market_data(run_id, state.market_data)
        if hasattr(state, "technical_findings"):
            self.record_stage_technical(run_id, state.technical_findings)
        if hasattr(state, "news_sentiment"):
            self.record_stage_news_sentiment(run_id, state.news_sentiment)
        if hasattr(state, "forecasting"):
            self.record_stage_forecasting(run_id, state.forecasting)
        if hasattr(state, "risk_findings"):
            self.record_stage_risk(run_id, state.risk_findings)
        if hasattr(state, "scenario_simulation"):
            self.record_stage_scenario_simulation(run_id, state.scenario_simulation)
        if hasattr(state, "judge_evaluation"):
            self.record_stage_judge(run_id, state.judge_evaluation)

        # Performance metrics
        events = getattr(state, "execution_events", []) or []
        durations: Dict[str, float] = {}
        for ev in events:
            comp = ev.get("component")
            dur = None
            if isinstance(ev.get("details"), dict):
                dur = ev["details"].get("duration_ms")
            if dur is None:
                dur = ev.get("duration_ms")
            if comp and dur is not None and comp not in durations:
                durations[comp] = dur
        if hasattr(state, "judge_evaluation") and getattr(state.judge_evaluation, "latency_ms", None):
            durations.setdefault("gemini_llm_judge", state.judge_evaluation.latency_ms)

        val_errors = getattr(state, "validation_errors", []) or []
        tot_dur = duration_ms if duration_ms is not None else 0.0
        self.record_stage_performance(
            run_id=run_id,
            total_duration_ms=tot_dur,
            agent_durations=durations,
            execution_events=events,
            error_count=len(val_errors),
        )

        snap_obj = final_response
        if snap_obj is None and state is not None:
            snap_obj = state.model_dump() if hasattr(state, "model_dump") else state

        if status == RunStatus.COMPLETED:
            self.complete_run(run_id=run_id, duration_ms=duration_ms, snapshot_data=snap_obj)
        elif status in (RunStatus.FAILED, RunStatus.PARTIAL):
            self.fail_run(
                run_id=run_id,
                error_message=error_message or (val_errors[0] if val_errors else "Execution failed"),
                duration_ms=duration_ms,
                snapshot_data=snap_obj,
                is_partial=(status == RunStatus.PARTIAL),
            )

    def complete_run(
        self,
        run_id: str,
        duration_ms: Optional[float] = None,
        snapshot_data: Optional[Dict[str, Any]] = None,
    ):
        """Mark run as COMPLETED, record completion time, and save JSON snapshot."""
        now_utc = datetime.now(timezone.utc).isoformat()
        snapshot_path_str = None
        snapshot_json_str = None

        if snapshot_data is not None:
            snapshot_json_str = safe_json_dumps(snapshot_data)
            snap_file = self.snapshot_dir / f"{run_id}.json"
            try:
                snap_file.write_text(snapshot_json_str, encoding="utf-8")
                snapshot_path_str = str(snap_file)
            except Exception as e:
                logger.error("Failed to write snapshot file %s: %s", snap_file, e)

        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("BEGIN IMMEDIATE;")
                conn.execute(
                    """
                    UPDATE runs SET
                        status = ?,
                        completed_at_utc = ?,
                        total_duration_ms = COALESCE(?, total_duration_ms),
                        snapshot_path = COALESCE(?, snapshot_path),
                        snapshot_json = COALESCE(?, snapshot_json),
                        updated_at_utc = ?
                    WHERE run_id = ?;
                    """,
                    (
                        RunStatus.COMPLETED.value,
                        now_utc,
                        duration_ms,
                        snapshot_path_str,
                        snapshot_json_str,
                        now_utc,
                        run_id,
                    ),
                )
                conn.execute("COMMIT;")
            except Exception as e:
                conn.execute("ROLLBACK;")
                logger.error("Failed to complete run %s: %s", run_id, e)
                raise
            finally:
                conn.close()

    def fail_run(
        self,
        run_id: str,
        error_message: str,
        duration_ms: Optional[float] = None,
        snapshot_data: Optional[Dict[str, Any]] = None,
        is_partial: bool = False,
    ):
        """Record run failure or partial status without erasing completed stage findings."""
        now_utc = datetime.now(timezone.utc).isoformat()
        target_status = RunStatus.PARTIAL.value if is_partial else RunStatus.FAILED.value
        snapshot_path_str = None
        snapshot_json_str = None

        if snapshot_data is not None:
            snapshot_json_str = safe_json_dumps(snapshot_data)
            snap_file = self.snapshot_dir / f"{run_id}.json"
            try:
                snap_file.write_text(snapshot_json_str, encoding="utf-8")
                snapshot_path_str = str(snap_file)
            except Exception as e:
                logger.error("Failed to write snapshot file for failed run %s: %s", snap_file, e)

        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("BEGIN IMMEDIATE;")
                conn.execute(
                    """
                    UPDATE runs SET
                        status = ?,
                        completed_at_utc = ?,
                        total_duration_ms = COALESCE(?, total_duration_ms),
                        error_message = ?,
                        snapshot_path = COALESCE(?, snapshot_path),
                        snapshot_json = COALESCE(?, snapshot_json),
                        updated_at_utc = ?
                    WHERE run_id = ?;
                    """,
                    (
                        target_status,
                        now_utc,
                        duration_ms,
                        str(error_message),
                        snapshot_path_str,
                        snapshot_json_str,
                        now_utc,
                        run_id,
                    ),
                )
                conn.execute("COMMIT;")
            except Exception as e:
                conn.execute("ROLLBACK;")
                logger.error("Failed to record failure for run %s: %s", run_id, e)
            finally:
                conn.close()

    def attach_final_response(self, run_id: str, final_response_dict: Dict[str, Any]):
        """Attach final API JSON response and write snapshot file."""
        now_utc = datetime.now(timezone.utc).isoformat()
        snapshot_json_str = safe_json_dumps(final_response_dict)
        snap_file = self.snapshot_dir / f"{run_id}.json"
        try:
            snap_file.write_text(snapshot_json_str, encoding="utf-8")
            snap_path_str = str(snap_file)
        except Exception as e:
            logger.error("Failed writing snapshot for %s: %s", run_id, e)
            snap_path_str = None

        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("BEGIN IMMEDIATE;")
                conn.execute(
                    """
                    UPDATE runs SET
                        snapshot_path = COALESCE(?, snapshot_path),
                        snapshot_json = ?,
                        updated_at_utc = ?
                    WHERE run_id = ?;
                    """,
                    (snap_path_str, snapshot_json_str, now_utc, run_id),
                )
                conn.execute("COMMIT;")
            except Exception as e:
                conn.execute("ROLLBACK;")
                logger.error("Error attaching final response snapshot for %s: %s", run_id, e)
            finally:
                conn.close()

    # -----------------------------------------------------------------------
    # Retrieval Methods
    # -----------------------------------------------------------------------
    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve complete run record with all joined stage tables."""
        conn = self._get_connection()
        try:
            cur = conn.execute("SELECT * FROM runs WHERE run_id = ?;", (run_id,))
            run_row = cur.fetchone()
            if run_row is None:
                return None

            result = dict(run_row)
            if result.get("config_json"):
                result["config"] = json.loads(result["config_json"])

            # Query each stage table
            stage_tables = [
                ("market_data", "stage_market_data"),
                ("technical", "stage_technical"),
                ("news_sentiment", "stage_news_sentiment"),
                ("forecasting", "stage_forecasting"),
                ("risk", "stage_risk"),
                ("scenario_simulation", "stage_scenario_simulation"),
                ("judge", "stage_judge"),
                ("performance", "stage_performance"),
            ]
            for stage_key, tbl_name in stage_tables:
                scur = conn.execute(f"SELECT * FROM {tbl_name} WHERE run_id = ?;", (run_id,))
                srow = scur.fetchone()
                if srow:
                    s_dict = dict(srow)
                    # Parse inner json columns
                    for col in srow.keys():
                        if col.endswith("_json") and s_dict[col]:
                            try:
                                s_dict[col[:-5]] = json.loads(s_dict[col])
                            except Exception:
                                pass
                    result[stage_key] = s_dict
                else:
                    result[stage_key] = None

            return result
        finally:
            conn.close()

    def list_runs(
        self,
        ticker: Optional[str] = None,
        status: Optional[str] = None,
        experiment_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List runs with optional filtering by ticker, status, and experiment_id."""
        conn = self._get_connection()
        try:
            query = "SELECT * FROM runs WHERE 1=1"
            params: List[Any] = []
            if ticker:
                query += " AND ticker = ?"
                params.append(ticker)
            if status:
                query += " AND status = ?"
                params.append(status.upper())
            if experiment_id:
                query += " AND experiment_id = ?"
                params.append(experiment_id)

            query += " ORDER BY started_at_utc DESC LIMIT ? OFFSET ?;"
            params.extend([limit, offset])

            cur = conn.execute(query, params)
            rows = cur.fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_experiment_summary(self, experiment_id: Optional[str] = None) -> Dict[str, Any]:
        """Aggregate statistical summary across stored runs."""
        conn = self._get_connection()
        try:
            where_clause = "WHERE experiment_id = ?" if experiment_id else ""
            params = (experiment_id,) if experiment_id else ()

            # Count by status
            cur = conn.execute(
                f"SELECT status, COUNT(*) as cnt FROM runs {where_clause} GROUP BY status;",
                params,
            )
            status_counts = {r["status"]: r["cnt"] for r in cur.fetchall()}

            # Mean latency for completed runs
            cur = conn.execute(
                f"""
                SELECT
                    AVG(total_duration_ms) as avg_duration,
                    MIN(total_duration_ms) as min_duration,
                    MAX(total_duration_ms) as max_duration,
                    COUNT(*) as total_completed
                FROM runs
                {where_clause} {'AND' if where_clause else 'WHERE'} status = 'COMPLETED';
                """,
                params,
            )
            lat_stats = dict(cur.fetchone() or {})

            # Judge score statistics
            judge_query = f"""
                SELECT
                    AVG(j.overall_score) as avg_judge_score,
                    MIN(j.overall_score) as min_judge_score,
                    MAX(j.overall_score) as max_judge_score,
                    COUNT(j.overall_score) as evaluated_count
                FROM stage_judge j
                JOIN runs r ON j.run_id = r.run_id
                {where_clause} {'AND' if where_clause else 'WHERE'} j.overall_score IS NOT NULL;
            """
            cur = conn.execute(judge_query, params)
            judge_stats = dict(cur.fetchone() or {})

            # Model distribution
            model_query = f"""
                SELECT f.selected_model, COUNT(*) as cnt
                FROM stage_forecasting f
                JOIN runs r ON f.run_id = r.run_id
                {where_clause} {'AND' if where_clause else 'WHERE'} f.selected_model IS NOT NULL
                GROUP BY f.selected_model;
            """
            cur = conn.execute(model_query, params)
            model_dist = {r["selected_model"]: r["cnt"] for r in cur.fetchall()}

            return {
                "experiment_id": experiment_id or "all_experiments",
                "total_runs": sum(status_counts.values()),
                "status_counts": status_counts,
                "latency_ms": lat_stats,
                "judge_metrics": judge_stats,
                "forecasting_distribution": model_dist,
            }
        finally:
            conn.close()

    # -----------------------------------------------------------------------
    # CSV Export Operations
    # -----------------------------------------------------------------------
    def export_csv(
        self,
        export_dir: Optional[str] = None,
        experiment_id: Optional[str] = None,
    ) -> Dict[str, Path]:
        """Export the 4 canonical academic CSV files:
        1. runs_summary.csv
        2. judge_scores.csv
        3. performance_metrics.csv
        4. forecast_metrics.csv
        """
        out_dir = Path(export_dir).resolve() if export_dir else self.export_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        conn = self._get_connection()
        try:
            where_clause = "WHERE r.experiment_id = ?" if experiment_id else ""
            params = (experiment_id,) if experiment_id else ()

            # -------------------------------------------------------------
            # 1. runs_summary.csv
            # -------------------------------------------------------------
            runs_summary_path = out_dir / "runs_summary.csv"
            query1 = f"""
                SELECT
                    r.run_id,
                    r.experiment_id,
                    r.ticker,
                    r.workflow_mode,
                    r.status,
                    r.started_at_utc,
                    r.completed_at_utc,
                    ROUND(r.total_duration_ms, 2) AS total_duration_ms,
                    rk.composite_score AS composite_risk_score,
                    rk.risk_level,
                    rk.recommendation,
                    f.selected_model AS forecast_best_model,
                    f.directional_accuracy,
                    j.overall_score AS judge_score,
                    j.verdict AS judge_verdict,
                    j.actual_model AS judge_actual_model,
                    j.total_tokens,
                    j.estimated_cost_usd,
                    j.cost_status,
                    r.error_message
                FROM runs r
                LEFT JOIN stage_risk rk ON r.run_id = rk.run_id
                LEFT JOIN stage_forecasting f ON r.run_id = f.run_id
                LEFT JOIN stage_judge j ON r.run_id = j.run_id
                {where_clause}
                ORDER BY r.started_at_utc ASC;
            """
            cur1 = conn.execute(query1, params)
            rows1 = cur1.fetchall()
            headers1 = [d[0] for d in cur1.description]

            with open(runs_summary_path, "w", newline="", encoding="utf-8") as f1:
                writer = csv.DictWriter(f1, fieldnames=headers1)
                writer.writeheader()
                for r in rows1:
                    row_dict = {k: ("" if r[k] is None else r[k]) for k in headers1}
                    writer.writerow(row_dict)

            # -------------------------------------------------------------
            # 2. judge_scores.csv
            # -------------------------------------------------------------
            judge_scores_path = out_dir / "judge_scores.csv"
            query2 = f"""
                SELECT
                    r.run_id,
                    r.experiment_id,
                    r.ticker,
                    r.status AS run_status,
                    COALESCE(j.status, 'unrecorded') AS judge_status,
                    j.configured_model,
                    j.actual_model,
                    j.fallback_triggered,
                    j.overall_score,
                    j.verdict,
                    j.factual_grounding,
                    j.completeness,
                    j.cross_agent_consistency,
                    j.forecasting_assessment,
                    j.risk_reasoning,
                    j.financial_safety,
                    j.input_tokens,
                    j.output_tokens,
                    j.total_tokens,
                    ROUND(j.latency_ms, 2) AS latency_ms,
                    j.estimated_cost_usd,
                    j.cost_status,
                    r.error_message
                FROM runs r
                LEFT JOIN stage_judge j ON r.run_id = j.run_id
                {where_clause}
                ORDER BY r.started_at_utc ASC;
            """
            cur2 = conn.execute(query2, params)
            rows2 = cur2.fetchall()
            headers2 = [d[0] for d in cur2.description]

            with open(judge_scores_path, "w", newline="", encoding="utf-8") as f2:
                writer = csv.DictWriter(f2, fieldnames=headers2)
                writer.writeheader()
                for r in rows2:
                    row_dict = {k: ("" if r[k] is None else r[k]) for k in headers2}
                    writer.writerow(row_dict)

            # -------------------------------------------------------------
            # 3. performance_metrics.csv
            # -------------------------------------------------------------
            perf_path = out_dir / "performance_metrics.csv"
            perf_rows = []
            headers3 = [
                "run_id",
                "experiment_id",
                "ticker",
                "workflow_mode",
                "status",
                "total_duration_ms",
                "mcp_market_duration_ms",
                "adk_technical_duration_ms",
                "news_sentiment_duration_ms",
                "forecasting_duration_ms",
                "risk_engine_duration_ms",
                "scenario_simulation_duration_ms",
                "crewai_orchestrator_duration_ms",
                "gemini_judge_duration_ms",
                "events_count",
                "error_count",
                "error_message",
            ]

            query3 = f"""
                SELECT
                    r.run_id,
                    r.experiment_id,
                    r.ticker,
                    r.workflow_mode,
                    r.status,
                    ROUND(r.total_duration_ms, 2) AS total_duration_ms,
                    p.agent_durations_json,
                    p.events_count,
                    p.error_count,
                    r.error_message
                FROM runs r
                LEFT JOIN stage_performance p ON r.run_id = p.run_id
                {where_clause}
                ORDER BY r.started_at_utc ASC;
            """
            cur3 = conn.execute(query3, params)
            for r in cur3.fetchall():
                durations_dict = {}
                if r["agent_durations_json"]:
                    try:
                        durations_dict = json.loads(r["agent_durations_json"])
                    except Exception:
                        pass

                row_dict = {
                    "run_id": r["run_id"],
                    "experiment_id": r["experiment_id"],
                    "ticker": r["ticker"],
                    "workflow_mode": r["workflow_mode"],
                    "status": r["status"],
                    "total_duration_ms": r["total_duration_ms"] if r["total_duration_ms"] is not None else "",
                    "mcp_market_duration_ms": durations_dict.get("mcp_market_data", "") or durations_dict.get("mcp_market", ""),
                    "adk_technical_duration_ms": (
                        durations_dict.get("GoogleADKTechnicalAgent", "")
                        or durations_dict.get("google_adk_technical_agent", "")
                        or durations_dict.get("technical_agent", "")
                    ),
                    "news_sentiment_duration_ms": (
                        durations_dict.get("news_sentiment_agent", "")
                        or durations_dict.get("NewsSentimentAgent", "")
                    ),
                    "forecasting_duration_ms": (
                        durations_dict.get("forecasting_agent", "")
                        or durations_dict.get("ForecastingAgent", "")
                    ),
                    "risk_engine_duration_ms": (
                        durations_dict.get("risk_engine", "")
                        or durations_dict.get("DeterministicRiskEngine", "")
                    ),
                    "scenario_simulation_duration_ms": (
                        durations_dict.get("scenario_simulation_agent", "")
                        or durations_dict.get("ScenarioSimulationAgent", "")
                    ),
                    "crewai_orchestrator_duration_ms": (
                        durations_dict.get("crewai_orchestrator", "")
                        or durations_dict.get("CrewAgent", "")
                    ),
                    "gemini_judge_duration_ms": (
                        durations_dict.get("gemini_llm_judge", "")
                        or durations_dict.get("JudgeEvaluationService", "")
                    ),
                    "events_count": r["events_count"] if r["events_count"] is not None else "",
                    "error_count": r["error_count"] if r["error_count"] is not None else "",
                    "error_message": r["error_message"] or "",
                }
                perf_rows.append(row_dict)

            with open(perf_path, "w", newline="", encoding="utf-8") as f3:
                writer = csv.DictWriter(f3, fieldnames=headers3)
                writer.writeheader()
                for pr in perf_rows:
                    writer.writerow(pr)

            # -------------------------------------------------------------
            # 4. forecast_metrics.csv
            # -------------------------------------------------------------
            forecast_path = out_dir / "forecast_metrics.csv"
            forecast_rows = []
            headers4 = [
                "run_id",
                "experiment_id",
                "ticker",
                "status",
                "selected_model",
                "directional_accuracy",
                "arima_rmse",
                "arima_mae",
                "arima_directional_accuracy",
                "exp_smoothing_rmse",
                "exp_smoothing_mae",
                "exp_smoothing_directional_accuracy",
                "lightgbm_rmse",
                "lightgbm_mae",
                "lightgbm_directional_accuracy",
                "predictions_count",
                "forecast_label",
                "error_message",
            ]

            query4 = f"""
                SELECT
                    r.run_id,
                    r.experiment_id,
                    r.ticker,
                    r.status,
                    f.selected_model,
                    f.directional_accuracy,
                    f.models_evaluated_json,
                    f.predictions_json,
                    f.forecast_label,
                    r.error_message
                FROM runs r
                LEFT JOIN stage_forecasting f ON r.run_id = f.run_id
                {where_clause}
                ORDER BY r.started_at_utc ASC;
            """
            cur4 = conn.execute(query4, params)
            for r in cur4.fetchall():
                models_list = []
                if r["models_evaluated_json"]:
                    try:
                        models_list = json.loads(r["models_evaluated_json"])
                    except Exception:
                        pass

                model_by_name = {m.get("model_name", ""): m for m in models_list}
                arima_m = model_by_name.get("ARIMA", {}) or model_by_name.get("ARIMAForecaster", {})
                exp_m = model_by_name.get("ExponentialSmoothing", {}) or model_by_name.get("ExpSmoothingForecaster", {})
                lgbm_m = model_by_name.get("LightGBM", {}) or model_by_name.get("LightGBMForecaster", {})

                preds_list = []
                if r["predictions_json"]:
                    try:
                        preds_list = json.loads(r["predictions_json"])
                    except Exception:
                        pass

                row_dict = {
                    "run_id": r["run_id"],
                    "experiment_id": r["experiment_id"],
                    "ticker": r["ticker"],
                    "status": r["status"],
                    "selected_model": r["selected_model"] or "",
                    "directional_accuracy": r["directional_accuracy"] if r["directional_accuracy"] is not None else "",
                    "arima_rmse": arima_m.get("rmse", ""),
                    "arima_mae": arima_m.get("mae", ""),
                    "arima_directional_accuracy": arima_m.get("directional_accuracy", ""),
                    "exp_smoothing_rmse": exp_m.get("rmse", ""),
                    "exp_smoothing_mae": exp_m.get("mae", ""),
                    "exp_smoothing_directional_accuracy": exp_m.get("directional_accuracy", ""),
                    "lightgbm_rmse": lgbm_m.get("rmse", ""),
                    "lightgbm_mae": lgbm_m.get("mae", ""),
                    "lightgbm_directional_accuracy": lgbm_m.get("directional_accuracy", ""),
                    "predictions_count": len(preds_list) if preds_list else "",
                    "forecast_label": r["forecast_label"] or "",
                    "error_message": r["error_message"] or "",
                }
                forecast_rows.append(row_dict)

            with open(forecast_path, "w", newline="", encoding="utf-8") as f4:
                writer = csv.DictWriter(f4, fieldnames=headers4)
                writer.writeheader()
                for fr in forecast_rows:
                    writer.writerow(fr)

            return {
                "runs_summary": runs_summary_path,
                "judge_scores": judge_scores_path,
                "performance_metrics": perf_path,
                "forecast_metrics": forecast_path,
            }
        finally:
            conn.close()

    def export_snapshot(self, run_id: str) -> Optional[Path]:
        """Ensure snapshot file is written for run_id and return its Path."""
        snap_file = self.snapshot_dir / f"{run_id}.json"
        if snap_file.exists():
            return snap_file

        conn = self._get_connection()
        try:
            cur = conn.execute("SELECT snapshot_json FROM runs WHERE run_id = ?;", (run_id,))
            row = cur.fetchone()
            if row and row["snapshot_json"]:
                snap_file.write_text(row["snapshot_json"], encoding="utf-8")
                return snap_file

            # Reconstruct from stage tables if snapshot_json was not serialized
            run_data = self.get_run(run_id)
            if run_data:
                snap_json = safe_json_dumps(run_data)
                snap_file.write_text(snap_json, encoding="utf-8")
                conn.execute(
                    "UPDATE runs SET snapshot_json = ?, snapshot_path = ? WHERE run_id = ?;",
                    (snap_json, str(snap_file), run_id),
                )
                return snap_file
            return None
        finally:
            conn.close()
