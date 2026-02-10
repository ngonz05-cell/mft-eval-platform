"""
MFT Eval Platform - Scuba Integration

Scuba table schema definition and logging client for tracking all eval
lifecycle events: creation, runs, scoring, and regressions.

Scuba Table: mft_eval_events

To register this table:
  1. Go to: https://www.internalfb.com/intern/scuba/new_table/
  2. Table name: mft_eval_events
  3. Copy the schema from SCUBA_TABLE_SCHEMA below
  4. Set retention: 90 days (with Hive persistence for long-term)

For local development, events are logged to a JSON file.
"""

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─── Scuba Table Schema Definition ───────────────────────────────────────────
# This is the schema to register at internalfb.com/intern/scuba/new_table/

SCUBA_TABLE_NAME = "mft_eval_events"

SCUBA_TABLE_SCHEMA = {
    "table_name": SCUBA_TABLE_NAME,
    "description": "MFT Eval Platform lifecycle events — tracks eval creation, runs, and results",
    "columns": {
        # Event identity
        "event_type": {
            "type": "normal",
            "description": "Event type: eval_created, eval_run_started, eval_run_completed, eval_scored, eval_regression",
        },
        "event_id": {"type": "normal", "description": "Unique event ID (UUID)"},
        "event_timestamp": {
            "type": "integer",
            "description": "Unix timestamp of the event",
        },
        # Eval identity
        "eval_id": {
            "type": "normal",
            "description": "Unique eval identifier (name + version)",
        },
        "eval_name": {"type": "normal", "description": "Human-readable eval name"},
        "eval_version": {
            "type": "normal",
            "description": "Eval config version (semver)",
        },
        # Run identity
        "run_id": {"type": "normal", "description": "Unique run identifier"},
        "model_version": {
            "type": "normal",
            "description": "Model/agent version being evaluated",
        },
        "prompt_version": {
            "type": "normal",
            "description": "Prompt version if applicable",
        },
        # Ownership & association
        "creator": {
            "type": "normal",
            "description": "Unix name of the person who created/ran the eval",
        },
        "team": {"type": "normal", "description": "Team that owns this eval"},
        "gk_name": {
            "type": "normal",
            "description": "Associated Gatekeeper feature flag name",
        },
        "task_id": {
            "type": "normal",
            "description": "Associated Phabricator task ID (T-number)",
        },
        "diff_id": {"type": "normal", "description": "Associated diff ID (D-number)"},
        # Scores & metrics
        "primary_score": {
            "type": "double",
            "description": "Primary composite score (0.0 to 1.0)",
        },
        "pass_rate": {
            "type": "double",
            "description": "Percentage of test cases that passed",
        },
        "num_examples": {
            "type": "integer",
            "description": "Total number of test cases",
        },
        "num_passed": {
            "type": "integer",
            "description": "Number of test cases that passed",
        },
        "num_failed": {
            "type": "integer",
            "description": "Number of test cases that failed",
        },
        # Threshold results
        "passed_baseline": {
            "type": "integer",
            "description": "1 if passed baseline threshold, 0 otherwise",
        },
        "passed_target": {
            "type": "integer",
            "description": "1 if passed target threshold, 0 otherwise",
        },
        "is_blocking": {
            "type": "integer",
            "description": "1 if this eval blocks deploys, 0 otherwise",
        },
        # Per-metric scores (JSON-encoded for flexibility)
        "metrics_json": {
            "type": "normal",
            "description": "JSON-encoded map of metric_name -> score",
        },
        "baseline_thresholds_json": {
            "type": "normal",
            "description": "JSON-encoded baseline thresholds",
        },
        "target_thresholds_json": {
            "type": "normal",
            "description": "JSON-encoded target thresholds",
        },
        # Regression detection
        "regression_detected": {
            "type": "integer",
            "description": "1 if regression detected vs previous run",
        },
        "delta_primary_score": {
            "type": "double",
            "description": "Change in primary score vs previous run",
        },
        # Run metadata
        "duration_ms": {
            "type": "integer",
            "description": "Eval run duration in milliseconds",
        },
        "dataset_source": {
            "type": "normal",
            "description": "Dataset source (hive://, csv://, etc.)",
        },
        "dataset_size": {
            "type": "integer",
            "description": "Number of examples in the dataset",
        },
        "trigger": {
            "type": "normal",
            "description": "What triggered this run: manual, ci, scheduled, pre_deploy",
        },
        "environment": {
            "type": "normal",
            "description": "Execution environment: local, ci, production",
        },
        # Tags for filtering
        "tags_json": {"type": "normal", "description": "JSON-encoded list of tags"},
    },
}


# ─── Event Types ──────────────────────────────────────────────────────────────


class EvalEventType(str, Enum):
    EVAL_CREATED = "eval_created"
    EVAL_RUN_STARTED = "eval_run_started"
    EVAL_RUN_COMPLETED = "eval_run_completed"
    EVAL_SCORED = "eval_scored"
    EVAL_REGRESSION = "eval_regression"
    EVAL_LAUNCHED = "eval_launched"


# ─── Event Data Structure ─────────────────────────────────────────────────────


@dataclass
class MFTEvalScubaEvent:
    """A single Scuba event for the mft_eval_events table."""

    # Event identity
    event_type: str
    event_id: str = ""
    event_timestamp: int = 0

    # Eval identity
    eval_id: str = ""
    eval_name: str = ""
    eval_version: str = ""

    # Run identity
    run_id: str = ""
    model_version: str = ""
    prompt_version: str = ""

    # Ownership
    creator: str = ""
    team: str = ""
    gk_name: str = ""
    task_id: str = ""
    diff_id: str = ""

    # Scores
    primary_score: float = 0.0
    pass_rate: float = 0.0
    num_examples: int = 0
    num_passed: int = 0
    num_failed: int = 0

    # Thresholds
    passed_baseline: int = 0
    passed_target: int = 0
    is_blocking: int = 0

    # Detailed metrics (JSON-encoded)
    metrics_json: str = "{}"
    baseline_thresholds_json: str = "{}"
    target_thresholds_json: str = "{}"

    # Regression
    regression_detected: int = 0
    delta_primary_score: float = 0.0

    # Run metadata
    duration_ms: int = 0
    dataset_source: str = ""
    dataset_size: int = 0
    trigger: str = "manual"
    environment: str = "local"

    # Tags
    tags_json: str = "[]"

    def __post_init__(self):
        if not self.event_id:
            import uuid

            self.event_id = str(uuid.uuid4())[:12]
        if not self.event_timestamp:
            self.event_timestamp = int(time.time())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ─── Scuba Logger ─────────────────────────────────────────────────────────────


class ScubaLogger:
    """
    Logs MFT eval events to Scuba (production) or local JSON (development).

    Usage:
        scuba = ScubaLogger()

        # Log eval creation
        scuba.log_eval_created(eval_config)

        # Log eval run completion
        scuba.log_eval_run_completed(eval_results)

    In production (Meta infra), events go to the mft_eval_events Scuba table.
    In local dev, events are appended to ~/.mft_evals/events.jsonl
    """

    def __init__(
        self,
        table_name: str = SCUBA_TABLE_NAME,
        environment: str = None,
        creator: str = None,
    ):
        self.table_name = table_name
        self.environment = environment or os.environ.get("MFT_EVAL_ENV", "local")
        self.creator = creator or os.environ.get("USER", "unknown")
        self._scuba_client = None
        self._init_backend()

    def _init_backend(self):
        """Initialize Scuba client (production) or local file (development)."""
        try:
            from libfb.py.scubadata import ScubaData

            self._scuba_client = ScubaData(self.table_name)
            logger.info(f"Scuba client initialized for table: {self.table_name}")
        except ImportError:
            self._scuba_client = None
            self._local_log_path = Path.home() / ".mft_evals" / "events.jsonl"
            self._local_log_path.parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"Scuba unavailable, logging to: {self._local_log_path}")

    def _log_event(self, event: MFTEvalScubaEvent):
        """Send event to Scuba or local log file."""
        event_dict = event.to_dict()

        if self._scuba_client:
            self._log_to_scuba(event_dict)
        else:
            self._log_to_local(event_dict)

        logger.debug(
            f"Logged event: {event.event_type} | {event.eval_name} | {event.run_id}"
        )

    def _log_to_scuba(self, event_dict: Dict[str, Any]):
        """Log event to Scuba in production."""
        from libfb.py.scubadata import Sample

        sample = Sample()
        for key, value in event_dict.items():
            if isinstance(value, str):
                sample.addNormalValue(key, value)
            elif isinstance(value, int):
                sample.addIntValue(key, value)
            elif isinstance(value, float):
                sample.addFloatValue(key, value)

        self._scuba_client.addSample(sample)
        self._scuba_client.flush()

    def _log_to_local(self, event_dict: Dict[str, Any]):
        """Log event to local JSONL file for development."""
        with open(self._local_log_path, "a") as f:
            f.write(json.dumps(event_dict, default=str) + "\n")

    # ─── High-Level Logging Methods ───────────────────────────────────────

    def log_eval_created(
        self,
        eval_name: str,
        eval_version: str = "1.0.0",
        team: str = "",
        gk_name: str = "",
        task_id: str = "",
        tags: List[str] = None,
        dataset_source: str = "",
        dataset_size: int = 0,
        is_blocking: bool = False,
    ):
        """Log that a new eval was created or registered."""
        self._log_event(
            MFTEvalScubaEvent(
                event_type=EvalEventType.EVAL_CREATED.value,
                eval_id=f"{eval_name}@{eval_version}",
                eval_name=eval_name,
                eval_version=eval_version,
                creator=self.creator,
                team=team,
                gk_name=gk_name,
                task_id=task_id,
                dataset_source=dataset_source,
                dataset_size=dataset_size,
                is_blocking=int(is_blocking),
                tags_json=json.dumps(tags or []),
                environment=self.environment,
            )
        )

    def log_eval_run_started(
        self,
        eval_name: str,
        run_id: str,
        model_version: str = "",
        trigger: str = "manual",
        eval_version: str = "1.0.0",
        gk_name: str = "",
        task_id: str = "",
    ):
        """Log that an eval run has started."""
        self._log_event(
            MFTEvalScubaEvent(
                event_type=EvalEventType.EVAL_RUN_STARTED.value,
                eval_id=f"{eval_name}@{eval_version}",
                eval_name=eval_name,
                eval_version=eval_version,
                run_id=run_id,
                model_version=model_version,
                trigger=trigger,
                creator=self.creator,
                gk_name=gk_name,
                task_id=task_id,
                environment=self.environment,
            )
        )

    def log_eval_run_completed(
        self,
        eval_name: str,
        run_id: str,
        eval_version: str = "1.0.0",
        model_version: str = "",
        primary_score: float = 0.0,
        pass_rate: float = 0.0,
        num_examples: int = 0,
        num_passed: int = 0,
        num_failed: int = 0,
        passed_baseline: bool = False,
        passed_target: bool = False,
        is_blocking: bool = False,
        metrics: Dict[str, float] = None,
        baseline_thresholds: Dict[str, float] = None,
        target_thresholds: Dict[str, float] = None,
        duration_ms: int = 0,
        dataset_source: str = "",
        dataset_size: int = 0,
        trigger: str = "manual",
        gk_name: str = "",
        task_id: str = "",
        diff_id: str = "",
        tags: List[str] = None,
    ):
        """Log that an eval run completed with results."""
        self._log_event(
            MFTEvalScubaEvent(
                event_type=EvalEventType.EVAL_RUN_COMPLETED.value,
                eval_id=f"{eval_name}@{eval_version}",
                eval_name=eval_name,
                eval_version=eval_version,
                run_id=run_id,
                model_version=model_version,
                primary_score=primary_score,
                pass_rate=pass_rate,
                num_examples=num_examples,
                num_passed=num_passed,
                num_failed=num_failed,
                passed_baseline=int(passed_baseline),
                passed_target=int(passed_target),
                is_blocking=int(is_blocking),
                metrics_json=json.dumps(metrics or {}),
                baseline_thresholds_json=json.dumps(baseline_thresholds or {}),
                target_thresholds_json=json.dumps(target_thresholds or {}),
                duration_ms=duration_ms,
                dataset_source=dataset_source,
                dataset_size=dataset_size,
                trigger=trigger,
                creator=self.creator,
                gk_name=gk_name,
                task_id=task_id,
                diff_id=diff_id,
                tags_json=json.dumps(tags or []),
                environment=self.environment,
            )
        )

    def log_eval_regression(
        self,
        eval_name: str,
        run_id: str,
        eval_version: str = "1.0.0",
        primary_score: float = 0.0,
        delta_primary_score: float = 0.0,
        metrics: Dict[str, float] = None,
        gk_name: str = "",
        task_id: str = "",
    ):
        """Log that a regression was detected."""
        self._log_event(
            MFTEvalScubaEvent(
                event_type=EvalEventType.EVAL_REGRESSION.value,
                eval_id=f"{eval_name}@{eval_version}",
                eval_name=eval_name,
                eval_version=eval_version,
                run_id=run_id,
                primary_score=primary_score,
                delta_primary_score=delta_primary_score,
                regression_detected=1,
                metrics_json=json.dumps(metrics or {}),
                creator=self.creator,
                gk_name=gk_name,
                task_id=task_id,
                environment=self.environment,
            )
        )

    # ─── Convenience: Log from EvalResults ────────────────────────────────

    def log_from_results(
        self,
        results,
        trigger: str = "manual",
        gk_name: str = "",
        task_id: str = "",
        diff_id: str = "",
    ):
        """
        Log a complete eval run from an EvalResults object.

        Args:
            results: EvalResults from runner.run()
            trigger: What triggered this run (manual, ci, scheduled, pre_deploy)
            gk_name: Associated GK feature flag
            task_id: Associated Phabricator task
            diff_id: Associated diff
        """
        duration_ms = 0
        if hasattr(results, "timestamp"):
            duration_ms = int(
                (datetime.now() - results.timestamp).total_seconds() * 1000
            )

        self.log_eval_run_completed(
            eval_name=results.eval_name,
            run_id=results.run_id,
            eval_version=results.eval_version,
            model_version=results.model_version,
            primary_score=results.primary_score,
            pass_rate=results.pass_rate,
            num_examples=results.num_examples,
            num_passed=results.num_passed,
            num_failed=results.num_examples - results.num_passed,
            passed_baseline=results.passed_baseline,
            passed_target=results.passed_target,
            metrics=results.metrics,
            baseline_thresholds=results.baseline_thresholds,
            target_thresholds=results.target_thresholds,
            duration_ms=duration_ms,
            trigger=trigger,
            gk_name=gk_name,
            task_id=task_id,
            diff_id=diff_id,
        )

        if results.regression_detected:
            self.log_eval_regression(
                eval_name=results.eval_name,
                run_id=results.run_id,
                eval_version=results.eval_version,
                primary_score=results.primary_score,
                delta_primary_score=results.delta_vs_previous.get("primary_score", 0.0),
                metrics=results.metrics,
                gk_name=gk_name,
                task_id=task_id,
            )

    # ─── Query helpers (for local dev) ────────────────────────────────────

    def get_local_events(
        self, eval_name: str = None, event_type: str = None
    ) -> List[Dict]:
        """Read events from local log (development only)."""
        if self._scuba_client:
            raise RuntimeError(
                "Use Scuba UI for production queries: bunnylol scuba mft_eval_events"
            )

        events = []
        if not self._local_log_path.exists():
            return events

        with open(self._local_log_path, "r") as f:
            for line in f:
                event = json.loads(line.strip())
                if eval_name and event.get("eval_name") != eval_name:
                    continue
                if event_type and event.get("event_type") != event_type:
                    continue
                events.append(event)

        return events
