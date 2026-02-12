"""
MFT Eval Platform - Eval Runner Service

Bridges the web UI → mft_evals engine. Responsibilities:
  1. Convert frontend evalConfig JSON → mft_evals.Eval + Dataset + Scorers
  2. Execute eval runs (sync for now, async workers later)
  3. Store results via storage.py
  4. Provide dry-run metric validation via LLM

This is the core orchestration layer between the API endpoints and the
evaluation framework.
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import httpx

from mft_evals.dataset import Dataset, TestCase
from mft_evals.eval import Eval, EvalConfig, EvalOwner, Threshold
from mft_evals.results import EvalResults
from mft_evals.runner import EvalRunner
from mft_evals.scorers import (
    BinaryPassFailScorer,
    CompositeScorer,
    ExactMatchScorer,
    F1Scorer,
    LLMJudgeScorer,
    NumericToleranceScorer,
    Scorer,
    ScorerResult,
    TokenF1Scorer,
)
from mft_evals import storage

logger = logging.getLogger(__name__)


# ─── Measurement Method → Scorer Mapping ─────────────────────────────────────

SCORER_MAP = {
    "exact_match_ratio": lambda m: ExactMatchScorer(
        name=m.get("field", "exact_match"),
        case_sensitive=False,
    ),
    "simple_pass_fail": lambda m: BinaryPassFailScorer(
        predicate=lambda actual: bool(actual and str(actual).strip()),
        name=m.get("field", "pass_fail"),
    ),
    "contains_check": lambda m: BinaryPassFailScorer(
        predicate=lambda actual: _contains_check(actual, m),
        name=m.get("field", "contains"),
    ),
    "numeric_tolerance": lambda m: NumericToleranceScorer(
        tolerance=m.get("tolerance", 0.01),
        name=m.get("field", "numeric"),
    ),
    "fuzzy_string_match": lambda m: TokenF1Scorer(
        name=m.get("field", "fuzzy_match"),
    ),
    "classification_f1": lambda m: F1Scorer(
        name=m.get("field", "classification_f1"),
    ),
    "field_f1": lambda m: F1Scorer(
        name=m.get("field", "field_f1"),
    ),
    "llm_judge": lambda m: LLMJudgeScorer(
        rubric=m.get("description", "Rate accuracy and quality 0.0-1.0"),
        name=m.get("field", "llm_judge"),
    ),
    "task_success_rate": lambda m: BinaryPassFailScorer(
        predicate=lambda actual: _task_success_check(actual),
        name=m.get("field", "task_success"),
    ),
    "tool_correctness": lambda m: ExactMatchScorer(
        name=m.get("field", "tool_correctness"),
        case_sensitive=False,
    ),
    "weighted_composite": lambda m: None,  # Handled separately
}


def _contains_check(actual: Any, metric_config: dict) -> bool:
    """Check if actual output contains expected keywords."""
    actual_str = str(actual).lower()
    keywords = metric_config.get("keywords", [])
    if not keywords:
        return bool(actual_str.strip())
    return all(kw.lower() in actual_str for kw in keywords)


def _task_success_check(actual: Any) -> bool:
    """Check if a task-oriented output indicates success."""
    actual_str = str(actual).lower()
    failure_indicators = ["error", "failed", "exception", "timeout", "could not"]
    return not any(ind in actual_str for ind in failure_indicators)


# ─── Config → Eval Objects ───────────────────────────────────────────────────


def build_scorers(metrics: List[Dict]) -> List[Scorer]:
    """Convert frontend metric configs to Scorer instances."""
    scorers = []
    for metric in metrics:
        measurement_ids = metric.get("measurement", [])
        if not measurement_ids:
            measurement_ids = ["exact_match_ratio"]

        primary_method = measurement_ids[0]
        factory = SCORER_MAP.get(primary_method)
        if factory:
            scorer = factory(metric)
            if scorer:
                scorers.append(scorer)

    if not scorers:
        scorers.append(ExactMatchScorer(name="default_accuracy"))

    return scorers


def build_dataset_from_config(eval_data: Dict) -> Optional[Dataset]:
    """Build a Dataset from stored eval config."""
    sample_data = eval_data.get("sample_data", [])
    if not sample_data:
        sample_json = eval_data.get("sample_data_json", "[]")
        if isinstance(sample_json, str):
            try:
                sample_data = json.loads(sample_json)
            except (json.JSONDecodeError, TypeError):
                sample_data = []

    if not sample_data:
        return None

    test_cases = []
    for i, item in enumerate(sample_data):
        if isinstance(item, dict):
            test_cases.append(TestCase(
                id=item.get("id", f"test_{i}"),
                input=item.get("input", item.get("query", "")),
                expected_output=item.get("expected_output", item.get("expected", "")),
                metadata={k: v for k, v in item.items()
                         if k not in ("id", "input", "query", "expected_output", "expected")},
            ))
        elif isinstance(item, str):
            test_cases.append(TestCase(
                id=f"test_{i}",
                input=item,
                expected_output="",
            ))

    return Dataset(
        test_cases=test_cases,
        name=eval_data.get("name", "eval_dataset"),
        source=eval_data.get("dataset_source", "ui"),
    )


def build_eval_from_config(eval_data: Dict) -> Eval:
    """Convert a stored eval record to an mft_evals.Eval object."""
    metrics = eval_data.get("metrics", [])
    if isinstance(metrics, str):
        metrics = json.loads(metrics)

    scorers = build_scorers(metrics)
    dataset = build_dataset_from_config(eval_data)

    baseline_thresholds = eval_data.get("baseline_thresholds", {})
    if isinstance(baseline_thresholds, str):
        baseline_thresholds = json.loads(baseline_thresholds)

    target_thresholds = eval_data.get("target_thresholds", {})
    if isinstance(target_thresholds, str):
        target_thresholds = json.loads(target_thresholds)

    config = EvalConfig(
        name=eval_data.get("name", ""),
        version=eval_data.get("version", "1.0.0"),
        description=eval_data.get("description", ""),
        owner=EvalOwner(
            pm=eval_data.get("owner_pm", ""),
            eng=eval_data.get("owner_eng", ""),
            team=eval_data.get("team", ""),
        ),
        dataset_source=eval_data.get("dataset_source", ""),
        thresholds=Threshold(
            baseline=baseline_thresholds,
            target=target_thresholds,
            blocking=bool(eval_data.get("blocking", False)),
        ),
        gk_name=eval_data.get("gk_name", ""),
        task_id=eval_data.get("task_id", ""),
    )

    return Eval(
        name=eval_data.get("name", ""),
        dataset=dataset,
        scorers=scorers,
        config=config,
    )


# ─── Model Caller ────────────────────────────────────────────────────────────


async def call_target_model(
    endpoint: str,
    input_text: str,
    auth_type: str = "none",
    api_key: str = "",
    request_format: str = "openai_chat",
    request_template: str = "",
    response_path: str = "choices[0].message.content",
) -> str:
    """
    Call the user's target model endpoint with a test input.
    Supports OpenAI-compatible, Anthropic, and raw JSON formats.
    """
    headers = {"content-type": "application/json"}
    if auth_type == "api_key" and api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    elif auth_type == "oauth":
        pass  # OAuth token would be handled separately

    if request_format == "openai_chat":
        payload = {
            "messages": [{"role": "user", "content": input_text}],
            "max_tokens": 1024,
        }
    elif request_format == "anthropic":
        headers["anthropic-version"] = "2023-06-01"
        if api_key:
            headers["x-api-key"] = api_key
            del headers["Authorization"]
        payload = {
            "messages": [{"role": "user", "content": input_text}],
            "max_tokens": 1024,
        }
    elif request_format == "raw_json" and request_template:
        try:
            payload = json.loads(request_template.replace("{{input}}", input_text))
        except json.JSONDecodeError:
            payload = {"input": input_text}
    elif request_format == "text_in_text_out":
        payload = input_text
    else:
        payload = {"input": input_text}

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        logger.error(f"Model call failed: {e}")
        return f"ERROR: {e}"

    return _extract_response(data, response_path)


def _extract_response(data: Any, path: str) -> str:
    """Extract response text from model output using a dotpath like 'choices[0].message.content'."""
    try:
        import re
        parts = re.split(r'\.', path)
        current = data
        for part in parts:
            array_match = re.match(r'(\w+)\[(\d+)\]', part)
            if array_match:
                key, index = array_match.group(1), int(array_match.group(2))
                current = current[key][index]
            else:
                current = current[part]
        return str(current)
    except (KeyError, IndexError, TypeError):
        if isinstance(data, dict):
            for key in ("text", "content", "output", "result", "response"):
                if key in data:
                    return str(data[key])
            content = data.get("content", [])
            if isinstance(content, list) and content:
                return str(content[0].get("text", ""))
        return str(data)


# ─── Run Execution ───────────────────────────────────────────────────────────


async def execute_eval_run(eval_id: str, trigger: str = "manual") -> Dict[str, Any]:
    """
    Execute an eval run end-to-end:
      1. Load eval config from DB
      2. Build Eval + Dataset + Scorers
      3. If model endpoint configured, call model for each test input
      4. Score outputs
      5. Store results
      6. Return results dict
    """
    eval_data = storage.get_eval(eval_id)
    if not eval_data:
        raise ValueError(f"Eval not found: {eval_id}")

    run_record = storage.create_run(eval_id, trigger)
    run_id = run_record["id"]
    start_time = time.time()

    try:
        eval_obj = build_eval_from_config(eval_data)

        if not eval_obj.dataset or len(eval_obj.dataset) == 0:
            raise ValueError("No test data available. Add sample data or connect a dataset source.")

        model_endpoint = eval_data.get("model_endpoint", "")

        if model_endpoint:
            generate_fn = _make_async_generate_fn(
                endpoint=model_endpoint,
                auth_type=eval_data.get("model_auth_type", "none"),
                api_key=eval_data.get("model_api_key", ""),
                request_format=eval_data.get("model_request_format", "openai_chat"),
                request_template=eval_data.get("model_request_template", ""),
                response_path=eval_data.get("model_response_path", "choices[0].message.content"),
            )
            # Run model calls for each test case
            for tc in eval_obj.dataset:
                if not tc.metadata.get("actual_output"):
                    actual = await call_target_model(
                        endpoint=model_endpoint,
                        input_text=str(tc.input),
                        auth_type=eval_data.get("model_auth_type", "none"),
                        api_key=eval_data.get("model_api_key", ""),
                        request_format=eval_data.get("model_request_format", "openai_chat"),
                        request_template=eval_data.get("model_request_template", ""),
                        response_path=eval_data.get("model_response_path", "choices[0].message.content"),
                    )
                    tc.metadata["actual_output"] = actual

        # Run the evaluation engine
        runner = EvalRunner(eval_obj)
        results = runner.run(trigger=trigger)

        duration_ms = int((time.time() - start_time) * 1000)

        failures_dicts = [
            {
                "test_case_id": f.test_case_id,
                "input": f.input,
                "expected": f.expected,
                "actual": f.actual,
                "scores": f.scores,
                "rationale": f.rationale,
            }
            for f in results.failures
        ]

        completed = storage.complete_run(
            run_id=run_id,
            primary_score=results.primary_score,
            pass_rate=results.pass_rate,
            metrics=results.metrics,
            num_examples=results.num_examples,
            num_passed=results.num_passed,
            num_failed=len(results.failures),
            passed_baseline=results.passed_baseline,
            passed_target=results.passed_target,
            detailed_results=results.detailed_results,
            failures=failures_dicts,
            duration_ms=duration_ms,
            baseline_thresholds=results.baseline_thresholds,
            target_thresholds=results.target_thresholds,
        )

        return completed

    except Exception as e:
        logger.error(f"Eval run {run_id} failed: {e}", exc_info=True)
        storage.fail_run(run_id, str(e))
        raise


def _make_async_generate_fn(
    endpoint: str,
    auth_type: str,
    api_key: str,
    request_format: str,
    request_template: str,
    response_path: str,
) -> Callable:
    """Create a sync generate function for the EvalRunner."""
    async def _generate(input_text: str) -> str:
        return await call_target_model(
            endpoint=endpoint,
            input_text=input_text,
            auth_type=auth_type,
            api_key=api_key,
            request_format=request_format,
            request_template=request_template,
            response_path=response_path,
        )
    return _generate


# ─── Dry-Run / Metric Validation ─────────────────────────────────────────────


async def validate_metrics_against_data(
    metrics: List[Dict],
    sample_data: List[Dict],
    description: str,
) -> Dict[str, Any]:
    """
    Run sample data against proposed metrics using the platform's LLM to assess
    whether the metrics and thresholds are realistic.

    Returns analysis with suggested adjustments.
    """
    from api.config import SYSTEM_PROMPT, MAX_TOKENS
    from api.llm import _call_llm

    metrics_summary = "\n".join([
        f"- {m['field']}: {m.get('description', '')} "
        f"(method: {m.get('measurement', ['?'])[0]}, "
        f"baseline: {m.get('baseline', '?')}%, target: {m.get('target', '?')}%)"
        for m in metrics
    ])

    data_preview = json.dumps(sample_data[:5], indent=2, default=str)

    prompt = f"""You are an eval metrics validation expert. Analyze whether the proposed metrics
and thresholds are realistic given the sample data.

## Eval Description
{description}

## Proposed Metrics
{metrics_summary}

## Sample Data (first 5 examples)
{data_preview}

## Your Task
For each metric, assess:
1. Is the measurement method appropriate for this data format?
2. Are the baseline/target thresholds realistic?
3. Would this metric actually catch quality regressions?

Respond with ONLY valid JSON:
{{
  "overall_assessment": "good|needs_adjustment|problematic",
  "message": "2-3 sentence summary of your findings for the user",
  "metric_feedback": [
    {{
      "field": "metric name",
      "status": "good|adjust|problematic",
      "suggestion": "specific recommendation",
      "suggested_baseline": 80,
      "suggested_target": 95
    }}
  ]
}}"""

    system = "You are an expert eval designer validating metric configurations against real data."
    messages = [{"role": "user", "content": prompt}]

    try:
        raw = await _call_llm(system, messages)
        from api.llm import _parse_json_response
        return _parse_json_response(raw)
    except Exception as e:
        logger.error(f"Metric validation failed: {e}")
        return {
            "overall_assessment": "error",
            "message": f"Could not validate metrics: {str(e)}",
            "metric_feedback": [],
        }
