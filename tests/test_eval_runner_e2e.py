#!/usr/bin/env python3
"""
End-to-end test for the MFT Eval Runner.

Tests the full flow:
  1. Create an eval via the API with sample data and metrics
  2. Run the eval (using pre-populated expected/actual outputs)
  3. Verify results (scores, pass rate, failures)
  4. Query run results via API

Zero external dependencies — uses only stdlib.

Usage:
  python3 tests/test_eval_runner_e2e.py
"""

import json
import sys
import time
import urllib.request
import urllib.error

API_BASE = "http://localhost:8000"

# ─── Sample eval config mimicking what the frontend sends ─────────────────────

SAMPLE_EVAL_CONFIG = {
    "evalName": "payment_extraction_e2e_test",
    "name": "payment_extraction_e2e_test",
    "version": "1.0.0",
    "description": "End-to-end test: extract payment amount from transaction descriptions.",
    "refinedPrompt": (
        "Evaluate an AI system that extracts the payment amount "
        "from unstructured transaction descriptions. "
        "Correct output is the numeric amount as a string."
    ),
    "team": "Payments Platform",
    "ownerPm": "nategonzalez",
    "ownerEng": "nategonzalez",

    "metrics": [
        {
            "field": "Amount Accuracy",
            "measurement": ["exact_match_ratio"],
            "description": "Exact match on extracted payment amount",
            "baseline": 75,
            "target": 95,
            "rationale": "Payment amounts must be precisely correct.",
        },
    ],

    # 10 test cases — 8 correct, 2 wrong
    "sampleData": [
        {"id": "txn_001", "input": "Payment of $150.00 USD to Acme Corp", "expected_output": "150.00", "actual_output": "150.00"},
        {"id": "txn_002", "input": "Sent €200.50 EUR to Berlin Tech GmbH", "expected_output": "200.50", "actual_output": "200.50"},
        {"id": "txn_003", "input": "Wire transfer $1,234.56 to Johnson & Assoc", "expected_output": "1234.56", "actual_output": "1234.56"},
        {"id": "txn_004", "input": "Refund of ¥5000 JPY from Tokyo Electronics", "expected_output": "5000", "actual_output": "5000"},
        {"id": "txn_005", "input": "Payment $75.99 USD to Netflix subscription", "expected_output": "75.99", "actual_output": "75.99"},
        {"id": "txn_006", "input": "Invoice payment £450.00 GBP to London Services", "expected_output": "450.00", "actual_output": "450.00"},
        {"id": "txn_007", "input": "Transfer $89.50 to Mike's Auto Shop", "expected_output": "89.50", "actual_output": "89.50"},
        {"id": "txn_008", "input": "Payment of $320.00 to Dr. Smith Medical", "expected_output": "320.00", "actual_output": "320.00"},
        {"id": "txn_009", "input": "Charge of $42.10 USD at Whole Foods Market", "expected_output": "42.10", "actual_output": "42.00"},
        {"id": "txn_010", "input": "Payment R$550.00 BRL to São Paulo Imports", "expected_output": "550.00", "actual_output": "55.00"},
    ],

    "modelEndpoint": "",
    "modelAuthType": "none",
    "modelRequestFormat": "openai_chat",
    "modelResponsePath": "choices[0].message.content",
    "datasetSource": "manual",
    "datasetSize": 10,
    "schedule": "manual",
    "alertOnRegression": False,
    "blocking": False,
}


def api_request(method, path, body=None):
    """Make an HTTP request to the API. Returns parsed JSON."""
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8")), resp.status
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8") if e.fp else ""
        return {"error": body_text, "status": e.code}, e.code


def p(text):
    print(text)


def main():
    p("\n" + "=" * 60)
    p("  MFT Eval Runner — End-to-End Test")
    p("=" * 60)

    # ── 1: Health check ───────────────────────────────────────────
    p("\n  [1] Checking API health...")
    data, status = api_request("GET", "/api/health")
    if status != 200:
        p(f"  ❌ API not available (status {status})")
        p("  Make sure backend is running: python3 -m uvicorn api.server:app --port 8000")
        return 1
    p(f"      ✅ Status: {data['status']} | Provider: {data['provider']} | Model: {data['model']}")

    # ── 2: Create eval ────────────────────────────────────────────
    p("\n  [2] Creating eval via POST /api/evals...")
    data, status = api_request("POST", "/api/evals", {"eval_config": SAMPLE_EVAL_CONFIG})
    if status != 200:
        p(f"  ❌ Create failed (status {status}): {data}")
        return 1

    eval_record = data["eval"]
    eval_id = eval_record["id"]
    p(f"      ✅ Eval ID: {eval_id}")
    p(f"      Name: {eval_record.get('name', '')}")

    # ── 3: Verify stored ──────────────────────────────────────────
    p("\n  [3] Verifying eval stored via GET /api/evals/{id}...")
    data, status = api_request("GET", f"/api/evals/{eval_id}")
    if status != 200:
        p(f"  ❌ Fetch failed (status {status})")
        return 1
    fetched = data["eval"]
    p(f"      ✅ Stored name: {fetched.get('name', '')} | Status: {fetched.get('status', '')}")

    # ── 4: List evals ─────────────────────────────────────────────
    p("\n  [4] Listing evals via GET /api/evals...")
    data, status = api_request("GET", "/api/evals")
    p(f"      ✅ Total evals: {data.get('count', '?')}")

    # ── 5: Run the eval ───────────────────────────────────────────
    p("\n  [5] Running eval via POST /api/evals/{id}/run...")
    p("      ⏳ Executing... (scoring 10 test cases)")

    start = time.time()
    data, status = api_request("POST", f"/api/evals/{eval_id}/run", {"trigger": "e2e_test"})
    duration = time.time() - start

    if status != 200:
        p(f"  ❌ Run failed (status {status}): {json.dumps(data, indent=2)[:500]}")
        return 1

    run = data["run"]
    run_id = run["id"]

    p(f"      ✅ Run ID: {run_id}")
    p(f"      Status: {run.get('status', '')}")
    p(f"      Primary Score: {run.get('primary_score', 0):.1%}")
    p(f"      Pass Rate: {run.get('pass_rate', 0):.1%}")
    p(f"      Passed: {run.get('num_passed', 0)}/{run.get('num_examples', 0)}")
    p(f"      Failed: {run.get('num_failed', 0)}")
    p(f"      Duration (API round trip): {duration:.2f}s")
    p(f"      Duration (engine): {run.get('duration_ms', 0)}ms")
    p(f"      Passed Baseline: {run.get('passed_baseline', False)}")

    # ── 6: Get detailed results ───────────────────────────────────
    p("\n  [6] Fetching results via GET /api/runs/{id}/results...")
    data, status = api_request("GET", f"/api/runs/{run_id}/results")
    if status != 200:
        p(f"  ❌ Results fetch failed (status {status})")
        return 1

    metrics = data.get("metrics", {})
    if isinstance(metrics, str):
        metrics = json.loads(metrics)

    p("      Metrics:")
    for name, score in metrics.items():
        emoji = "✅" if score >= 0.85 else "🔶" if score >= 0.70 else "❌"
        p(f"        {emoji} {name}: {score:.1%}")

    failures = data.get("failures", [])
    if isinstance(failures, str):
        failures = json.loads(failures)

    if failures:
        p("      Failures:")
        for f in failures[:5]:
            p(f"        ❌ {f.get('test_case_id', '?')}: expected '{f.get('expected', '')}', got '{f.get('actual', '')}'")

    # ── 7: List runs ──────────────────────────────────────────────
    p("\n  [7] Listing runs via GET /api/evals/{id}/runs...")
    data, status = api_request("GET", f"/api/evals/{eval_id}/runs")
    p(f"      ✅ Total runs: {data.get('count', '?')}")

    # ── 8: Cleanup ────────────────────────────────────────────────
    p("\n  [8] Cleaning up via DELETE /api/evals/{id}...")
    data, status = api_request("DELETE", f"/api/evals/{eval_id}")
    p(f"      🗑️  Deleted: {eval_id}")

    # ── Summary ───────────────────────────────────────────────────
    p("\n" + "=" * 60)
    p("  TEST RESULTS SUMMARY")
    p("=" * 60)

    actual_pass_rate = run.get("pass_rate", 0)
    checks = [
        ("Eval created successfully", eval_id is not None),
        ("Eval stored & fetched correctly", fetched.get("name") == "payment_extraction_e2e_test"),
        ("Run completed", run.get("status") == "completed"),
        ("10 examples scored", run.get("num_examples") == 10),
        ("8 passed, 2 failed", run.get("num_passed") == 8 and run.get("num_failed") == 2),
        ("Pass rate is 80%", 0.79 <= actual_pass_rate <= 0.81),
        ("Baseline check correct", run.get("passed_baseline") in (True, 1)),
        ("Cleanup succeeded", status == 200),
    ]

    all_passed = True
    for label, passed in checks:
        emoji = "✅" if passed else "❌"
        p(f"  {emoji} {label}")
        if not passed:
            all_passed = False

    p("")
    if all_passed:
        p("  🎉 ALL CHECKS PASSED — Eval runner is working end-to-end!")
    else:
        p("  ⚠️  Some checks failed — review output above.")

    p("")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
