"""
MFT Eval - Results

From the reference doc:
"Evals are not one-and-done."

Best practices:
- Track eval scores over time
- Annotate major changes (model swap, prompt change, tool addition)
- Watch for regressions, plateaus, and tradeoffs between metrics
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import json


@dataclass
class FailureCase:
    """A single failure case from the evaluation"""
    test_case_id: str
    input: Any
    expected: Any
    actual: Any
    scores: Dict[str, float]
    rationale: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_case_id": self.test_case_id,
            "input": self.input,
            "expected": self.expected,
            "actual": self.actual,
            "scores": self.scores,
            "rationale": self.rationale,
            **self.metadata
        }


@dataclass
class EvalResults:
    """
    Complete results from an evaluation run.

    Contains:
    - Overall metrics and scores
    - Pass/fail status against thresholds
    - Detailed results per test case
    - Failure analysis
    """

    # Identity
    eval_name: str
    eval_version: str
    run_id: str
    timestamp: datetime = field(default_factory=datetime.now)

    # What was evaluated
    model_version: str = ""
    prompt_version: str = ""
    config_hash: str = ""

    # Scores
    metrics: Dict[str, float] = field(default_factory=dict)
    primary_score: float = 0.0

    # Thresholds
    passed_baseline: bool = False
    passed_target: bool = False
    baseline_thresholds: Dict[str, float] = field(default_factory=dict)
    target_thresholds: Dict[str, float] = field(default_factory=dict)

    # Details
    num_examples: int = 0
    num_passed: int = 0
    failures: List[FailureCase] = field(default_factory=list)

    # Per-test-case results
    detailed_results: List[Dict[str, Any]] = field(default_factory=list)

    # Comparison
    delta_vs_previous: Dict[str, float] = field(default_factory=dict)
    regression_detected: bool = False

    @property
    def pass_rate(self) -> float:
        """Percentage of test cases that passed"""
        if self.num_examples == 0:
            return 0.0
        return self.num_passed / self.num_examples

    @property
    def failure_rate(self) -> float:
        """Percentage of test cases that failed"""
        return 1.0 - self.pass_rate

    def summary(self) -> str:
        """Human-readable summary of results"""
        status = "✅ PASSED" if self.passed_baseline else "❌ FAILED"

        lines = [
            f"\n{'='*60}",
            f"EVAL RESULTS: {self.eval_name} v{self.eval_version}",
            f"{'='*60}",
            f"Status: {status}",
            f"",
            f"Primary Score: {self.primary_score:.4f}",
            f"Pass Rate: {self.pass_rate:.1%} ({self.num_passed}/{self.num_examples})",
            f"",
            f"Metrics:",
        ]

        for metric, value in self.metrics.items():
            baseline = self.baseline_thresholds.get(metric, None)
            target = self.target_thresholds.get(metric, None)

            status_emoji = ""
            if baseline is not None:
                if value >= baseline:
                    status_emoji = "✅" if (target is None or value >= target) else "🔶"
                else:
                    status_emoji = "❌"

            line = f"  {status_emoji} {metric}: {value:.4f}"
            if baseline is not None:
                line += f" (baseline: {baseline:.4f})"
            if target is not None:
                line += f" (target: {target:.4f})"
            lines.append(line)

        if self.failures:
            lines.extend([
                f"",
                f"Top Failures ({min(5, len(self.failures))} of {len(self.failures)}):",
            ])
            for failure in self.failures[:5]:
                lines.append(f"  - {failure.test_case_id}: {failure.rationale[:60]}...")

        lines.append(f"{'='*60}\n")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "eval_name": self.eval_name,
            "eval_version": self.eval_version,
            "run_id": self.run_id,
            "timestamp": self.timestamp.isoformat(),
            "model_version": self.model_version,
            "prompt_version": self.prompt_version,
            "config_hash": self.config_hash,
            "metrics": self.metrics,
            "primary_score": self.primary_score,
            "passed_baseline": self.passed_baseline,
            "passed_target": self.passed_target,
            "baseline_thresholds": self.baseline_thresholds,
            "target_thresholds": self.target_thresholds,
            "num_examples": self.num_examples,
            "num_passed": self.num_passed,
            "pass_rate": self.pass_rate,
            "failures": [f.to_dict() for f in self.failures],
            "delta_vs_previous": self.delta_vs_previous,
            "regression_detected": self.regression_detected,
        }

    def to_json(self, path: str) -> None:
        """Save results to JSON file"""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, default=str)

    @classmethod
    def from_json(cls, path: str) -> "EvalResults":
        """Load results from JSON file"""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return cls(
            eval_name=data["eval_name"],
            eval_version=data["eval_version"],
            run_id=data["run_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            model_version=data.get("model_version", ""),
            prompt_version=data.get("prompt_version", ""),
            config_hash=data.get("config_hash", ""),
            metrics=data.get("metrics", {}),
            primary_score=data.get("primary_score", 0.0),
            passed_baseline=data.get("passed_baseline", False),
            passed_target=data.get("passed_target", False),
            baseline_thresholds=data.get("baseline_thresholds", {}),
            target_thresholds=data.get("target_thresholds", {}),
            num_examples=data.get("num_examples", 0),
            num_passed=data.get("num_passed", 0),
            failures=[FailureCase(**f) for f in data.get("failures", [])],
            delta_vs_previous=data.get("delta_vs_previous", {}),
            regression_detected=data.get("regression_detected", False),
        )

    def get_failures(self, min_severity: str = "all") -> List[FailureCase]:
        """Get failures filtered by severity"""
        # For now, return all failures
        # Can be extended to filter by severity level
        return self.failures

    def compare(self, other: "EvalResults") -> Dict[str, float]:
        """Compare with another results set"""
        deltas = {}

        for metric in self.metrics:
            if metric in other.metrics:
                deltas[metric] = self.metrics[metric] - other.metrics[metric]

        deltas["primary_score"] = self.primary_score - other.primary_score
        deltas["pass_rate"] = self.pass_rate - other.pass_rate

        return deltas
