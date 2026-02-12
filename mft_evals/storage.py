"""
MFT Eval Platform - SQLite Storage Layer

Persists eval configurations and run results to a local SQLite database.
This enables:
  - Listing all created evals ("My Evals" dashboard)
  - Querying historical run results with filtering
  - Tracking score trends over time
  - Comparing runs for regression detection

Database location: ~/.mft_evals/evals.db (configurable via MFT_EVALS_DB_PATH)
"""

import json
import logging
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path.home() / ".mft_evals" / "evals.db"


def get_db_path() -> str:
    path = os.environ.get("MFT_EVALS_DB_PATH", str(DEFAULT_DB_PATH))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def get_connection():
    """Context manager for SQLite connections with WAL mode for concurrent reads."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create tables if they don't exist."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS evals (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                version TEXT NOT NULL DEFAULT '1.0.0',
                description TEXT DEFAULT '',
                refined_prompt TEXT DEFAULT '',
                team TEXT DEFAULT '',
                owner_pm TEXT DEFAULT '',
                owner_eng TEXT DEFAULT '',
                status TEXT DEFAULT 'draft',

                -- Scoring config
                primary_metric TEXT DEFAULT 'accuracy',
                metrics_json TEXT DEFAULT '[]',
                baseline_thresholds_json TEXT DEFAULT '{}',
                target_thresholds_json TEXT DEFAULT '{}',

                -- Dataset config
                dataset_source TEXT DEFAULT '',
                dataset_url TEXT DEFAULT '',
                dataset_size INTEGER DEFAULT 0,
                sample_data_json TEXT DEFAULT '[]',

                -- Model connection
                model_endpoint TEXT DEFAULT '',
                model_auth_type TEXT DEFAULT 'none',
                model_request_format TEXT DEFAULT 'openai_chat',
                model_response_path TEXT DEFAULT 'choices[0].message.content',
                model_request_template TEXT DEFAULT '',

                -- Production monitoring
                prod_log_enabled INTEGER DEFAULT 0,
                prod_log_source TEXT DEFAULT '',
                prod_log_table TEXT DEFAULT '',
                prod_log_input_column TEXT DEFAULT '',
                prod_log_output_column TEXT DEFAULT '',
                prod_log_timestamp_column TEXT DEFAULT '',
                prod_log_sample_rate INTEGER DEFAULT 10,

                -- Automation
                schedule TEXT DEFAULT '',
                ci_integration INTEGER DEFAULT 0,
                alert_on_regression INTEGER DEFAULT 0,
                alert_channel TEXT DEFAULT '',
                blocking INTEGER DEFAULT 0,

                -- Launch tracking
                gk_name TEXT DEFAULT '',
                task_id TEXT DEFAULT '',
                feature_name TEXT DEFAULT '',
                tags_json TEXT DEFAULT '[]',

                -- Full config blob (for fields not explicitly columned)
                config_json TEXT DEFAULT '{}',

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS eval_runs (
                id TEXT PRIMARY KEY,
                eval_id TEXT NOT NULL,
                eval_version TEXT DEFAULT '1.0.0',
                status TEXT DEFAULT 'pending',

                -- What was evaluated
                model_version TEXT DEFAULT '',
                trigger TEXT DEFAULT 'manual',

                -- Scores
                primary_score REAL DEFAULT 0.0,
                pass_rate REAL DEFAULT 0.0,
                metrics_json TEXT DEFAULT '{}',

                -- Counts
                num_examples INTEGER DEFAULT 0,
                num_passed INTEGER DEFAULT 0,
                num_failed INTEGER DEFAULT 0,

                -- Thresholds
                passed_baseline INTEGER DEFAULT 0,
                passed_target INTEGER DEFAULT 0,
                baseline_thresholds_json TEXT DEFAULT '{}',
                target_thresholds_json TEXT DEFAULT '{}',

                -- Detailed results (JSON array of per-example results)
                detailed_results_json TEXT DEFAULT '[]',
                failures_json TEXT DEFAULT '[]',

                -- Timing
                duration_ms INTEGER DEFAULT 0,
                started_at TEXT,
                completed_at TEXT,

                -- Error info (if run failed)
                error_message TEXT DEFAULT '',

                created_at TEXT NOT NULL,

                FOREIGN KEY (eval_id) REFERENCES evals(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_eval_runs_eval_id ON eval_runs(eval_id);
            CREATE INDEX IF NOT EXISTS idx_eval_runs_status ON eval_runs(status);
            CREATE INDEX IF NOT EXISTS idx_evals_status ON evals(status);
            CREATE INDEX IF NOT EXISTS idx_evals_team ON evals(team);
        """)
    logger.info(f"Database initialized at {get_db_path()}")


# ─── Eval CRUD ────────────────────────────────────────────────────────────────


def create_eval(config: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new eval from the frontend evalConfig object."""
    eval_id = config.get("id") or str(uuid.uuid4())[:12]
    now = datetime.utcnow().isoformat()

    metrics = config.get("metrics", [])
    baseline_thresholds = {}
    target_thresholds = {}
    for m in metrics:
        field_name = m.get("field", "")
        if field_name:
            baseline_thresholds[field_name] = m.get("baseline", 80) / 100.0
            target_thresholds[field_name] = m.get("target", 95) / 100.0

    with get_connection() as conn:
        conn.execute("""
            INSERT INTO evals (
                id, name, version, description, refined_prompt, team,
                owner_pm, owner_eng, status, primary_metric,
                metrics_json, baseline_thresholds_json, target_thresholds_json,
                dataset_source, dataset_url, dataset_size, sample_data_json,
                model_endpoint, model_auth_type, model_request_format,
                model_response_path, model_request_template,
                prod_log_enabled, prod_log_source, prod_log_table,
                prod_log_input_column, prod_log_output_column,
                prod_log_timestamp_column, prod_log_sample_rate,
                schedule, ci_integration, alert_on_regression,
                alert_channel, blocking,
                gk_name, task_id, feature_name, tags_json,
                config_json, created_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?,
                ?, ?, ?,
                ?, ?,
                ?, ?,
                ?, ?, ?,
                ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?
            )
        """, (
            eval_id,
            config.get("evalName", config.get("name", "")),
            config.get("version", "1.0.0"),
            config.get("description", ""),
            config.get("refinedPrompt", ""),
            config.get("team", ""),
            config.get("ownerPm", ""),
            config.get("ownerEng", ""),
            "draft",
            config.get("primaryMetric", "accuracy"),
            json.dumps(metrics),
            json.dumps(baseline_thresholds),
            json.dumps(target_thresholds),
            config.get("datasetSource", ""),
            config.get("datasetUrl", ""),
            config.get("datasetSize", 0),
            json.dumps(config.get("sampleData", [])),
            config.get("modelEndpoint", ""),
            config.get("modelAuthType", "none"),
            config.get("modelRequestFormat", "openai_chat"),
            config.get("modelResponsePath", "choices[0].message.content"),
            config.get("modelRequestTemplate", ""),
            1 if config.get("prodLogEnabled") else 0,
            config.get("prodLogSource", ""),
            config.get("prodLogTable", ""),
            config.get("prodLogInputColumn", ""),
            config.get("prodLogOutputColumn", ""),
            config.get("prodLogTimestampColumn", ""),
            config.get("prodLogSampleRate", 10),
            config.get("schedule", ""),
            1 if config.get("ciIntegration") else 0,
            1 if config.get("alertOnRegression") else 0,
            config.get("alertChannel", ""),
            1 if config.get("blocking") else 0,
            config.get("gkName", ""),
            config.get("taskId", ""),
            config.get("featureName", ""),
            json.dumps(config.get("tags", [])),
            json.dumps(config),
            now,
            now,
        ))

    return get_eval(eval_id)


def get_eval(eval_id: str) -> Optional[Dict[str, Any]]:
    """Get a single eval by ID."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM evals WHERE id = ?", (eval_id,)).fetchone()
    if not row:
        return None
    return _row_to_eval_dict(row)


def list_evals(
    team: str = None,
    status: str = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """List evals with optional filtering."""
    query = "SELECT * FROM evals WHERE 1=1"
    params = []

    if team:
        query += " AND team = ?"
        params.append(team)
    if status:
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_eval_dict(r) for r in rows]


def update_eval(eval_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update an eval's configuration."""
    now = datetime.utcnow().isoformat()

    allowed_columns = {
        "name", "version", "description", "refined_prompt", "team",
        "owner_pm", "owner_eng", "status", "primary_metric",
        "model_endpoint", "model_auth_type", "model_request_format",
        "model_response_path", "model_request_template",
        "dataset_source", "dataset_url", "dataset_size",
        "schedule", "alert_channel", "gk_name", "task_id", "feature_name",
    }

    set_clauses = ["updated_at = ?"]
    params = [now]

    for key, value in updates.items():
        col = _camel_to_snake(key)
        if col in allowed_columns:
            set_clauses.append(f"{col} = ?")
            params.append(value)

    if "metrics" in updates:
        set_clauses.append("metrics_json = ?")
        params.append(json.dumps(updates["metrics"]))

    params.append(eval_id)

    with get_connection() as conn:
        conn.execute(
            f"UPDATE evals SET {', '.join(set_clauses)} WHERE id = ?",
            params,
        )

    return get_eval(eval_id)


def delete_eval(eval_id: str) -> bool:
    """Delete an eval and its runs."""
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM evals WHERE id = ?", (eval_id,))
    return cursor.rowcount > 0


# ─── Run CRUD ─────────────────────────────────────────────────────────────────


def create_run(eval_id: str, trigger: str = "manual") -> Dict[str, Any]:
    """Create a new pending run for an eval."""
    run_id = str(uuid.uuid4())[:12]
    now = datetime.utcnow().isoformat()

    with get_connection() as conn:
        conn.execute("""
            INSERT INTO eval_runs (id, eval_id, status, trigger, created_at, started_at)
            VALUES (?, ?, 'running', ?, ?, ?)
        """, (run_id, eval_id, trigger, now, now))

    return get_run(run_id)


def complete_run(
    run_id: str,
    primary_score: float,
    pass_rate: float,
    metrics: Dict[str, float],
    num_examples: int,
    num_passed: int,
    num_failed: int,
    passed_baseline: bool,
    passed_target: bool,
    detailed_results: List[Dict],
    failures: List[Dict],
    duration_ms: int,
    baseline_thresholds: Dict[str, float] = None,
    target_thresholds: Dict[str, float] = None,
    model_version: str = "",
) -> Dict[str, Any]:
    """Mark a run as completed with results."""
    now = datetime.utcnow().isoformat()

    with get_connection() as conn:
        conn.execute("""
            UPDATE eval_runs SET
                status = 'completed',
                primary_score = ?,
                pass_rate = ?,
                metrics_json = ?,
                num_examples = ?,
                num_passed = ?,
                num_failed = ?,
                passed_baseline = ?,
                passed_target = ?,
                baseline_thresholds_json = ?,
                target_thresholds_json = ?,
                detailed_results_json = ?,
                failures_json = ?,
                duration_ms = ?,
                model_version = ?,
                completed_at = ?
            WHERE id = ?
        """, (
            primary_score,
            pass_rate,
            json.dumps(metrics),
            num_examples,
            num_passed,
            num_failed,
            1 if passed_baseline else 0,
            1 if passed_target else 0,
            json.dumps(baseline_thresholds or {}),
            json.dumps(target_thresholds or {}),
            json.dumps(detailed_results),
            json.dumps(failures),
            duration_ms,
            model_version,
            now,
            run_id,
        ))

    return get_run(run_id)


def fail_run(run_id: str, error_message: str) -> Dict[str, Any]:
    """Mark a run as failed with an error message."""
    now = datetime.utcnow().isoformat()

    with get_connection() as conn:
        conn.execute("""
            UPDATE eval_runs SET
                status = 'failed',
                error_message = ?,
                completed_at = ?
            WHERE id = ?
        """, (error_message, now, run_id))

    return get_run(run_id)


def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    """Get a single run by ID."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM eval_runs WHERE id = ?", (run_id,)).fetchone()
    if not row:
        return None
    return _row_to_run_dict(row)


def list_runs(
    eval_id: str,
    status: str = None,
    limit: int = 20,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """List runs for an eval."""
    query = "SELECT * FROM eval_runs WHERE eval_id = ?"
    params = [eval_id]

    if status:
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_run_dict(r) for r in rows]


def get_latest_run(eval_id: str) -> Optional[Dict[str, Any]]:
    """Get the most recent completed run for an eval."""
    with get_connection() as conn:
        row = conn.execute("""
            SELECT * FROM eval_runs
            WHERE eval_id = ? AND status = 'completed'
            ORDER BY completed_at DESC LIMIT 1
        """, (eval_id,)).fetchone()
    if not row:
        return None
    return _row_to_run_dict(row)


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _row_to_eval_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert a SQLite Row to a frontend-friendly dict."""
    d = dict(row)
    for key in ("metrics_json", "baseline_thresholds_json", "target_thresholds_json",
                "sample_data_json", "tags_json", "config_json"):
        if key in d and d[key]:
            try:
                d[key.replace("_json", "")] = json.loads(d[key])
            except (json.JSONDecodeError, TypeError):
                d[key.replace("_json", "")] = d[key]
    d["prodLogEnabled"] = bool(d.get("prod_log_enabled", 0))
    d["ciIntegration"] = bool(d.get("ci_integration", 0))
    d["alertOnRegression"] = bool(d.get("alert_on_regression", 0))
    d["blocking"] = bool(d.get("blocking", 0))
    return d


def _row_to_run_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert a SQLite Row to a frontend-friendly dict."""
    d = dict(row)
    for key in ("metrics_json", "baseline_thresholds_json", "target_thresholds_json",
                "detailed_results_json", "failures_json"):
        if key in d and d[key]:
            try:
                d[key.replace("_json", "")] = json.loads(d[key])
            except (json.JSONDecodeError, TypeError):
                d[key.replace("_json", "")] = d[key]
    d["passedBaseline"] = bool(d.get("passed_baseline", 0))
    d["passedTarget"] = bool(d.get("passed_target", 0))
    return d


def _camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    import re
    s1 = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
