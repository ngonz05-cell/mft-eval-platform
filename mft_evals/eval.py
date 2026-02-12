"""
MFT Eval - Core Eval Definition

Based on the MFT reference doc principle: "Evals are your PRD"
Every eval must define:
- What capability it measures
- How success is calculated
- What threshold is acceptable to ship
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

import yaml


class EvalStatus(Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


@dataclass
class EvalOwner:
    """Ownership information for an eval"""

    pm: str
    eng: str
    team: str = ""


@dataclass
class Threshold:
    """Threshold configuration for pass/fail determination"""

    baseline: Dict[str, float]
    target: Dict[str, float]
    blocking: bool = False  # If True, blocks deploy when below baseline


@dataclass
class AutomationConfig:
    """Automation settings for the eval"""

    schedule: Optional[str] = None  # Cron expression
    ci_integration: bool = False
    alert_on_regression: bool = False
    alert_channel: Optional[str] = None


@dataclass
class EvalConfig:
    """
    Complete eval configuration matching the MFT Eval Template.

    From the reference doc:
    "If you can't fill this out, pause and do that first."

    Required fields (Minimum Viable Eval):
    - name: What capability does this measure?
    - description: What problem is this eval validating?
    - dataset_source: Where do the test cases come from?
    - scoring_method: How is success calculated?
    - threshold: What score is acceptable to ship?
    - owner: Who maintains this eval?
    """

    # Identity
    name: str
    version: str = "1.0.0"
    description: str = ""

    # Ownership
    owner: Optional[EvalOwner] = None

    # Capability
    capability_what: str = ""  # Precise behavior being tested
    capability_why: str = ""  # Why this matters for users/business

    # Dataset
    dataset_source: str = ""  # hive://path, gsheet://url, or local path
    dataset_size: Optional[int] = None

    # Scoring
    primary_metric: str = "accuracy"
    metrics: List[Dict[str, Any]] = field(default_factory=list)

    # Thresholds
    thresholds: Optional[Threshold] = None

    # Automation
    automation: Optional[AutomationConfig] = None

    # Metadata
    tags: List[str] = field(default_factory=list)
    status: EvalStatus = EvalStatus.DRAFT
    created_at: Optional[datetime] = None

    # Launch tracking — links eval to code and feature flags
    gk_name: str = ""  # Gatekeeper feature flag name
    task_id: str = ""  # Phabricator task ID (e.g., T123456789)
    diff_ids: List[str] = field(
        default_factory=list
    )  # Associated diffs (e.g., D987654321)
    feature_name: str = ""  # Human-readable feature name for launch tracking

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "EvalConfig":
        """Load config from YAML file"""
        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)
        return cls._from_dict(data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvalConfig":
        """Create config from dictionary"""
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "EvalConfig":
        """Internal method to parse dict into EvalConfig"""
        owner_data = data.get("owner", {})
        owner = (
            EvalOwner(
                pm=owner_data.get("pm", ""),
                eng=owner_data.get("eng", ""),
                team=data.get("team", ""),
            )
            if owner_data
            else None
        )

        threshold_data = data.get("thresholds", {})
        thresholds = (
            Threshold(
                baseline=threshold_data.get("baseline", {}),
                target=threshold_data.get("target", {}),
                blocking=threshold_data.get("blocking", False),
            )
            if threshold_data
            else None
        )

        automation_data = data.get("automation", {})
        automation = (
            AutomationConfig(
                schedule=automation_data.get("schedule"),
                ci_integration=automation_data.get("ci_integration", False),
                alert_on_regression=automation_data.get("alert_on_regression", False),
                alert_channel=automation_data.get("alert_channel"),
            )
            if automation_data
            else None
        )

        scoring = data.get("scoring", {})

        return cls(
            name=data.get("name", ""),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            owner=owner,
            capability_what=data.get("capability", {}).get("what", ""),
            capability_why=data.get("capability", {}).get("why", ""),
            dataset_source=data.get("dataset", {}).get("source", ""),
            dataset_size=data.get("dataset", {}).get("size"),
            primary_metric=scoring.get("primary_metric", "accuracy"),
            metrics=scoring.get("metrics", []),
            thresholds=thresholds,
            automation=automation,
            tags=data.get("tags", []),
            status=EvalStatus(data.get("status", "draft")),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if data.get("created_at")
                else None
            ),
            gk_name=data.get("launch", {}).get("gk_name", data.get("gk_name", "")),
            task_id=data.get("launch", {}).get("task_id", data.get("task_id", "")),
            diff_ids=data.get("launch", {}).get("diff_ids", data.get("diff_ids", [])),
            feature_name=data.get("launch", {}).get(
                "feature_name", data.get("feature_name", "")
            ),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary"""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "team": self.owner.team if self.owner else "",
            "owner": {
                "pm": self.owner.pm if self.owner else "",
                "eng": self.owner.eng if self.owner else "",
            },
            "capability": {
                "what": self.capability_what,
                "why": self.capability_why,
            },
            "dataset": {
                "source": self.dataset_source,
                "size": self.dataset_size,
            },
            "scoring": {
                "primary_metric": self.primary_metric,
                "metrics": self.metrics,
            },
            "thresholds": {
                "baseline": self.thresholds.baseline if self.thresholds else {},
                "target": self.thresholds.target if self.thresholds else {},
                "blocking": self.thresholds.blocking if self.thresholds else False,
            },
            "automation": {
                "schedule": self.automation.schedule if self.automation else None,
                "ci_integration": (
                    self.automation.ci_integration if self.automation else False
                ),
                "alert_on_regression": (
                    self.automation.alert_on_regression if self.automation else False
                ),
                "alert_channel": (
                    self.automation.alert_channel if self.automation else None
                ),
            },
            "launch": {
                "gk_name": self.gk_name,
                "task_id": self.task_id,
                "diff_ids": self.diff_ids,
                "feature_name": self.feature_name,
            },
            "tags": self.tags,
            "status": self.status.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def to_yaml(self, path: str) -> None:
        """Save config to YAML file"""
        with open(path, "w") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)

    def validate(self) -> List[str]:
        """
        Validate the eval config against minimum requirements.

        From the reference doc - Minimum Viable Eval:
        - 50-100 examples (hand-labeled)
        - Clear pass/fail criteria
        - Simple scoring method
        - 80% pass rate threshold
        - Owner assigned
        """
        errors = []

        if not self.name:
            errors.append("Eval name is required")

        if not self.description:
            errors.append(
                "Description is required - what problem does this eval validate?"
            )

        if not self.dataset_source:
            errors.append("Dataset source is required")

        if not self.thresholds or not self.thresholds.baseline:
            errors.append(
                "Baseline thresholds are required - what score is acceptable to ship?"
            )

        if not self.owner or (not self.owner.pm and not self.owner.eng):
            errors.append("Owner (PM or Eng) is required")

        return errors


class Eval:
    """
    Main Eval class that encapsulates an evaluation definition and execution.

    Usage:
        # Define eval
        eval = Eval(
            name="payment_extraction",
            dataset=Dataset.from_csv("test_cases.csv"),
            scorers=[ExactMatchScorer(field="amount")],
            thresholds={"accuracy": 0.95}
        )

        # Run eval
        results = eval.run(model=my_model)

        # Check results
        if results.passed_baseline:
            print("Ready to ship!")
    """

    def __init__(
        self,
        name: str,
        dataset: "Dataset" = None,
        scorers: List["Scorer"] = None,
        thresholds: Dict[str, float] = None,
        model: Any = None,
        config: EvalConfig = None,
    ):
        self.name = name
        self.dataset = dataset
        self.scorers = scorers or []
        self.thresholds = thresholds or {}
        self.model = model
        self.config = config or EvalConfig(name=name)

    @classmethod
    def from_config(cls, config: EvalConfig, dataset: "Dataset" = None) -> "Eval":
        """Create Eval from config"""
        return cls(
            name=config.name,
            dataset=dataset,
            config=config,
        )

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "Eval":
        """Load eval from YAML config file"""
        config = EvalConfig.from_yaml(yaml_path)
        return cls.from_config(config)

    def run(self, model: Any = None) -> "EvalResults":
        """
        Run the evaluation.

        Args:
            model: The model/agent to evaluate (optional if pre-generated outputs)

        Returns:
            EvalResults with scores, pass/fail status, and details
        """
        from mft_evals.runner import EvalRunner

        runner = EvalRunner(self)
        return runner.run(model or self.model)

    def validate(self) -> List[str]:
        """Validate eval configuration"""
        errors = self.config.validate()

        if not self.dataset:
            errors.append("Dataset is required")

        if not self.scorers:
            errors.append("At least one scorer is required")

        return errors
