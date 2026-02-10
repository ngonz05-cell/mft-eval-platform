"""
MFT Eval Platform - EP Launch Tracker Integration

Records eval launches in Meta's EP Launch Tracker, the canonical system
for tracking what shipped, when, and by whom.

How this fits in the flow:
  1. Engineer creates eval (logged to Scuba as eval_created)
  2. Eval runs in CI/scheduled (logged to Scuba as eval_run_completed)
  3. Eval passes baseline → team decides to ship the feature
  4. Engineer records the launch via EP Launch Tracker (this module)
  5. Launch metadata flows to `dim_all_exp_decisions` Hive table

EP Launch Tracker URL: bunnylol eplaunch
Launch Dashboard: internalfb.com/intern/experiments/?hub_tab=launch_dashboard

This module provides:
  - LaunchRecord: structured data for a launch post
  - LaunchTracker: client to create/update launch posts
  - Auto-populate launch fields from eval results + GK config
"""

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class LaunchRecord:
    """
    Structured launch record for EP Launch Tracker.

    This maps to the fields in the Launch Post form at bunnylol eplaunch.
    """

    # Feature identity
    feature_name: str = ""
    description: str = ""
    team: str = ""
    owner: str = ""

    # Eval association
    eval_name: str = ""
    eval_version: str = ""
    eval_primary_score: float = 0.0
    eval_passed_baseline: bool = False
    eval_passed_target: bool = False

    # Code association
    gk_name: str = ""
    task_id: str = ""
    diff_ids: List[str] = field(default_factory=list)

    # Experiment association (if A/B tested)
    qe_universe: str = ""
    experiment_id: str = ""
    holdout_gk: str = ""

    # Launch details
    launch_date: str = ""
    rollout_percentage: int = 100
    launch_decision: str = "ship"  # ship, no_ship, needs_more_data

    # Metrics evidence
    metrics_summary: Dict[str, float] = field(default_factory=dict)
    baseline_thresholds: Dict[str, float] = field(default_factory=dict)
    target_thresholds: Dict[str, float] = field(default_factory=dict)

    # Backtest / holdout
    backtest_id: str = ""
    holdout_id: str = ""

    # Tags
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_eval_results(
        cls,
        results,
        feature_name: str = "",
        gk_name: str = "",
        task_id: str = "",
        diff_ids: List[str] = None,
        team: str = "",
        owner: str = "",
    ) -> "LaunchRecord":
        """
        Create a LaunchRecord from EvalResults.

        Usage:
            results = runner.run(model=my_model)
            launch = LaunchRecord.from_eval_results(
                results,
                feature_name="Payment Extraction AI",
                gk_name="mft_payment_extraction_v2",
                task_id="T123456789",
            )
            tracker.record_launch(launch)
        """
        return cls(
            feature_name=feature_name or results.eval_name,
            description=f"Launch of {results.eval_name} v{results.eval_version} "
            f"with primary score {results.primary_score:.4f}",
            team=team,
            owner=owner or os.environ.get("USER", "unknown"),
            eval_name=results.eval_name,
            eval_version=results.eval_version,
            eval_primary_score=results.primary_score,
            eval_passed_baseline=results.passed_baseline,
            eval_passed_target=results.passed_target,
            gk_name=gk_name,
            task_id=task_id,
            diff_ids=diff_ids or [],
            launch_date=datetime.now().strftime("%Y-%m-%d"),
            launch_decision="ship" if results.passed_baseline else "no_ship",
            metrics_summary=results.metrics,
            baseline_thresholds=results.baseline_thresholds,
            target_thresholds=results.target_thresholds,
        )


class LaunchTracker:
    """
    Client for recording launches to EP Launch Tracker.

    In production (Meta infra), this calls the EP Launch Tracker API.
    In local dev, launch records are saved to ~/.mft_evals/launches.jsonl

    Usage:
        tracker = LaunchTracker()

        # Record from eval results
        results = runner.run(model=my_model)
        tracker.record_from_results(
            results,
            feature_name="Payment Extraction AI",
            gk_name="mft_payment_extraction_v2",
            task_id="T123456789",
        )

        # Or record a manual launch
        tracker.record_launch(LaunchRecord(
            feature_name="My Feature",
            gk_name="my_gk",
            ...
        ))
    """

    def __init__(self, creator: str = None):
        self.creator = creator or os.environ.get("USER", "unknown")
        self._ep_client = None
        self._scuba_logger = None
        self._init_backend()

    def _init_backend(self):
        """Initialize EP Launch Tracker client (production) or local fallback."""
        try:
            from ep_launch_tracker.client import EPLaunchClient

            self._ep_client = EPLaunchClient()
            logger.info("EP Launch Tracker client initialized")
        except ImportError:
            self._ep_client = None
            self._local_log_path = (
                __import__("pathlib").Path.home() / ".mft_evals" / "launches.jsonl"
            )
            self._local_log_path.parent.mkdir(parents=True, exist_ok=True)
            logger.info(
                f"EP client unavailable, logging launches to: {self._local_log_path}"
            )

        try:
            from mft_evals.integrations.scuba import ScubaLogger

            self._scuba_logger = ScubaLogger()
        except Exception:
            self._scuba_logger = None

    def record_launch(self, launch: LaunchRecord) -> str:
        """
        Record a launch in EP Launch Tracker.

        Returns:
            Launch post URL (production) or local file path (development)
        """
        launch_dict = launch.to_dict()
        launch_dict["recorded_at"] = datetime.now().isoformat()
        launch_dict["recorded_by"] = self.creator

        if self._ep_client:
            return self._record_to_ep(launch_dict)
        else:
            return self._record_to_local(launch_dict)

    def _record_to_ep(self, launch_dict: Dict[str, Any]) -> str:
        """Record to EP Launch Tracker in production."""
        response = self._ep_client.create_launch_post(
            feature_name=launch_dict["feature_name"],
            description=launch_dict["description"],
            team=launch_dict["team"],
            gk_name=launch_dict["gk_name"],
            task_id=launch_dict["task_id"],
            metrics=launch_dict["metrics_summary"],
            launch_decision=launch_dict["launch_decision"],
        )
        launch_url = response.get("url", "")
        logger.info(f"Launch recorded in EP: {launch_url}")
        return launch_url

    def _record_to_local(self, launch_dict: Dict[str, Any]) -> str:
        """Record to local file for development."""
        with open(self._local_log_path, "a") as f:
            f.write(json.dumps(launch_dict, default=str) + "\n")

        # Also log to Scuba as eval_launched event
        if self._scuba_logger:
            self._scuba_logger._log_event(
                __import__(
                    "mft_evals.integrations.scuba", fromlist=["MFTEvalScubaEvent"]
                ).MFTEvalScubaEvent(
                    event_type="eval_launched",
                    eval_name=launch_dict.get("eval_name", ""),
                    eval_version=launch_dict.get("eval_version", ""),
                    primary_score=launch_dict.get("eval_primary_score", 0.0),
                    passed_baseline=int(launch_dict.get("eval_passed_baseline", False)),
                    passed_target=int(launch_dict.get("eval_passed_target", False)),
                    gk_name=launch_dict.get("gk_name", ""),
                    task_id=launch_dict.get("task_id", ""),
                    creator=self.creator,
                    metrics_json=json.dumps(launch_dict.get("metrics_summary", {})),
                )
            )

        logger.info(f"Launch recorded locally: {self._local_log_path}")
        return str(self._local_log_path)

    def record_from_results(
        self,
        results,
        feature_name: str = "",
        gk_name: str = "",
        task_id: str = "",
        diff_ids: List[str] = None,
        team: str = "",
    ) -> str:
        """
        Convenience method: record a launch directly from EvalResults.

        Usage:
            results = runner.run(model=my_model)
            url = tracker.record_from_results(
                results,
                feature_name="Payment Extraction AI",
                gk_name="mft_payment_extraction_v2",
                task_id="T123456789",
            )
            print(f"Launch recorded: {url}")
        """
        launch = LaunchRecord.from_eval_results(
            results,
            feature_name=feature_name,
            gk_name=gk_name,
            task_id=task_id,
            diff_ids=diff_ids,
            team=team,
            owner=self.creator,
        )
        return self.record_launch(launch)

    def get_local_launches(self, eval_name: str = None) -> List[Dict]:
        """Read launches from local log (development only)."""
        if self._ep_client:
            raise RuntimeError(
                "Use EP Launch Dashboard for production queries: "
                "internalfb.com/intern/experiments/?hub_tab=launch_dashboard"
            )

        launches = []
        if not self._local_log_path.exists():
            return launches

        with open(self._local_log_path, "r") as f:
            for line in f:
                record = json.loads(line.strip())
                if eval_name and record.get("eval_name") != eval_name:
                    continue
                launches.append(record)

        return launches

    @staticmethod
    def get_launch_dashboard_url() -> str:
        """Return the URL for the EP Launch Dashboard."""
        return "https://www.internalfb.com/intern/experiments/?hub_tab=launch_dashboard"

    @staticmethod
    def get_launch_tool_url() -> str:
        """Return the URL for creating a new launch post."""
        return "https://www.internalfb.com/intern/experiments/launch/"
