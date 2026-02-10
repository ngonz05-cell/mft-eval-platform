"""
MFT Eval - Runner

From the reference doc:
"If it's not automated, it's not an eval."

A real eval:
- Runs in CI or on a schedule
- Compares current output to a baseline
- Produces a metric you can chart
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
import uuid
import logging

from mft_evals.eval import Eval, EvalConfig
from mft_evals.dataset import Dataset, TestCase
from mft_evals.scorers import Scorer, ScorerResult
from mft_evals.results import EvalResults, FailureCase

logger = logging.getLogger(__name__)


class EvalRunner:
    """
    Runs evaluations and produces results.

    Usage:
        eval = Eval(
            name="payment_extraction",
            dataset=Dataset.from_csv("test_cases.csv"),
            scorers=[ExactMatchScorer(field="amount")],
            thresholds={"accuracy": 0.95}
        )

        runner = EvalRunner(eval)
        results = runner.run(model=my_model)
    """

    def __init__(self, eval: Eval):
        self.eval = eval

    def run(
        self,
        model: Any = None,
        generate_fn: Callable[[Any], Any] = None,
    ) -> EvalResults:
        """
        Run the evaluation.

        Args:
            model: Model/agent to evaluate
            generate_fn: Optional function to generate outputs from inputs
                        If not provided, dataset must have pre-generated outputs

        Returns:
            EvalResults with complete evaluation results
        """
        run_id = str(uuid.uuid4())[:8]
        start_time = datetime.now()

        logger.info(f"Starting eval run {run_id} for {self.eval.name}")

        if not self.eval.dataset:
            raise ValueError("Dataset is required to run evaluation")

        if not self.eval.scorers:
            raise ValueError("At least one scorer is required")

        # Process each test case
        detailed_results = []
        failures = []
        per_scorer_scores = {s.name: [] for s in self.eval.scorers}

        for test_case in self.eval.dataset:
            # Get actual output
            if generate_fn:
                actual = generate_fn(test_case.input)
            elif model and hasattr(model, '__call__'):
                actual = model(test_case.input)
            elif model and hasattr(model, 'generate'):
                actual = model.generate(test_case.input)
            else:
                # Assume actual output is in metadata
                actual = test_case.metadata.get("actual_output", test_case.metadata.get("actual", ""))

            # Score with each scorer
            case_scores = {}
            case_passed = True
            rationales = []

            for scorer in self.eval.scorers:
                result = scorer.score(
                    expected=test_case.expected_output,
                    actual=actual,
                    input=test_case.input,
                    test_case=test_case,
                )

                case_scores[scorer.name] = result.score
                per_scorer_scores[scorer.name].append(result.score)
                rationales.append(f"{scorer.name}: {result.rationale}")

                if not result.passed:
                    case_passed = False

            # Record detailed result
            detailed_results.append({
                "test_case_id": test_case.id,
                "input": test_case.input,
                "expected": test_case.expected_output,
                "actual": actual,
                "scores": case_scores,
                "passed": case_passed,
            })

            # Record failure if applicable
            if not case_passed:
                failures.append(FailureCase(
                    test_case_id=test_case.id,
                    input=test_case.input,
                    expected=test_case.expected_output,
                    actual=actual,
                    scores=case_scores,
                    rationale="; ".join(rationales),
                    metadata=test_case.metadata,
                ))

        # Aggregate metrics
        metrics = {}
        for scorer_name, scores in per_scorer_scores.items():
            if scores:
                metrics[scorer_name] = sum(scores) / len(scores)
            else:
                metrics[scorer_name] = 0.0

        # Calculate primary score (weighted average if composite, else average)
        if metrics:
            primary_score = sum(metrics.values()) / len(metrics)
        else:
            primary_score = 0.0

        # Get thresholds
        baseline_thresholds = {}
        target_thresholds = {}

        if self.eval.config and self.eval.config.thresholds:
            baseline_thresholds = self.eval.config.thresholds.baseline
            target_thresholds = self.eval.config.thresholds.target
        elif self.eval.thresholds:
            baseline_thresholds = self.eval.thresholds

        # Check thresholds
        passed_baseline = True
        passed_target = True

        for metric, threshold in baseline_thresholds.items():
            if metrics.get(metric, 0.0) < threshold:
                passed_baseline = False

        for metric, threshold in target_thresholds.items():
            if metrics.get(metric, 0.0) < threshold:
                passed_target = False

        # If no specific metric thresholds, use primary score
        if not baseline_thresholds and primary_score < 0.8:  # Default 80% baseline
            passed_baseline = False

        num_passed = len(detailed_results) - len(failures)

        results = EvalResults(
            eval_name=self.eval.name,
            eval_version=self.eval.config.version if self.eval.config else "1.0.0",
            run_id=run_id,
            timestamp=start_time,
            model_version=getattr(model, 'version', '') if model else '',
            metrics=metrics,
            primary_score=primary_score,
            passed_baseline=passed_baseline,
            passed_target=passed_target,
            baseline_thresholds=baseline_thresholds,
            target_thresholds=target_thresholds,
            num_examples=len(detailed_results),
            num_passed=num_passed,
            failures=failures,
            detailed_results=detailed_results,
        )

        logger.info(f"Eval run {run_id} completed: {results.pass_rate:.1%} pass rate")

        return results


class SimpleEvalRunner:
    """
    Minimal eval runner for quick testing.
    Matches the "Minimum Viable Eval" from the reference doc.

    Usage:
        runner = SimpleEvalRunner(
            test_cases=[
                {"input": "What's 2+2?", "expected": "4"},
                {"input": "What's 3+3?", "expected": "6"},
            ],
            scorer=ExactMatchScorer()
        )

        results = runner.run(model_fn=lambda x: my_model(x))
    """

    def __init__(
        self,
        test_cases: List[Dict[str, Any]],
        scorer: Scorer,
        name: str = "simple_eval",
    ):
        self.test_cases = test_cases
        self.scorer = scorer
        self.name = name

    def run(self, model_fn: Callable[[str], str]) -> Dict[str, Any]:
        """
        Run the evaluation with a simple model function.

        Args:
            model_fn: Function that takes input and returns output

        Returns:
            Simple results dict with score and pass rate
        """
        scores = []
        failures = []

        for i, tc in enumerate(self.test_cases):
            input_text = tc.get("input", "")
            expected = tc.get("expected", "")

            try:
                actual = model_fn(input_text)
            except Exception as e:
                actual = f"ERROR: {e}"

            result = self.scorer.score(expected, actual, input=input_text)
            scores.append(result.score)

            if not result.passed:
                failures.append({
                    "id": f"test_{i}",
                    "input": input_text,
                    "expected": expected,
                    "actual": actual,
                    "score": result.score,
                })

        avg_score = sum(scores) / len(scores) if scores else 0.0
        pass_rate = sum(1 for s in scores if s >= 0.5) / len(scores) if scores else 0.0

        return {
            "name": self.name,
            "score": avg_score,
            "pass_rate": pass_rate,
            "num_tests": len(self.test_cases),
            "num_passed": int(pass_rate * len(self.test_cases)),
            "passed_80_threshold": pass_rate >= 0.8,  # Default MVE threshold
            "failures": failures[:10],  # Top 10 failures
        }
