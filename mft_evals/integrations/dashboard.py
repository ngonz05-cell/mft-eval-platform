"""
MFT Eval Platform - Unidash Dashboard Configuration

Pre-built Scuba queries and Unidash dashboard configuration for tracking
all MFT evals. These queries can be:

  1. Pasted directly into Scuba UI (bunnylol scuba mft_eval_events)
  2. Exported from Scuba → Unidash as widgets
  3. Used in Daiquery for more complex joins

Dashboard setup:
  1. Go to: bunnylol unidash → Create New Dashboard
  2. Name: "MFT Eval Platform - All Evals"
  3. Add widgets using the queries below (Scuba data source)
  4. Publish and share the URL

Alternatively, use the DashboardBuilder class to generate the config programmatically.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ─── Scuba Queries for Dashboard Widgets ──────────────────────────────────────

SCUBA_QUERIES = {
    # ── Widget 1: Eval Registry (all evals ever created) ──────────────
    "eval_registry": {
        "title": "📋 Eval Registry — All Evals Created",
        "description": "Master list of all evals registered in the platform",
        "table": "mft_eval_events",
        "query": {
            "filterBy": {"event_type": ["eval_created"]},
            "columns": [
                "eval_name",
                "eval_version",
                "creator",
                "team",
                "gk_name",
                "task_id",
                "dataset_source",
                "dataset_size",
                "is_blocking",
                "tags_json",
                "event_timestamp",
            ],
            "orderBy": "event_timestamp DESC",
        },
        "visualization": "table",
    },
    # ── Widget 2: Evals Created Over Time ─────────────────────────────
    "evals_created_over_time": {
        "title": "📈 Evals Created Over Time",
        "description": "Adoption curve — how many evals are being created per week",
        "table": "mft_eval_events",
        "query": {
            "filterBy": {"event_type": ["eval_created"]},
            "aggregateBy": "count",
            "groupBy": "time:week",
        },
        "visualization": "line_chart",
    },
    # ── Widget 3: Eval Run Pass Rate ──────────────────────────────────
    "eval_pass_rate": {
        "title": "✅ Eval Pass Rate by Eval",
        "description": "Percentage of runs that pass baseline threshold, grouped by eval",
        "table": "mft_eval_events",
        "query": {
            "filterBy": {"event_type": ["eval_run_completed"]},
            "aggregateBy": "avg(passed_baseline)",
            "groupBy": "eval_name",
            "orderBy": "avg(passed_baseline) ASC",
        },
        "visualization": "bar_chart",
    },
    # ── Widget 4: Primary Score Trends ────────────────────────────────
    "score_trends": {
        "title": "📊 Primary Score Trends Over Time",
        "description": "Primary score over time for each eval — watch for regressions",
        "table": "mft_eval_events",
        "query": {
            "filterBy": {"event_type": ["eval_run_completed"]},
            "columns": ["primary_score"],
            "aggregateBy": "avg(primary_score)",
            "groupBy": ["eval_name", "time:day"],
        },
        "visualization": "line_chart",
    },
    # ── Widget 5: Recent Runs ─────────────────────────────────────────
    "recent_runs": {
        "title": "🕐 Recent Eval Runs",
        "description": "Last 50 eval runs with scores and pass/fail status",
        "table": "mft_eval_events",
        "query": {
            "filterBy": {"event_type": ["eval_run_completed"]},
            "columns": [
                "eval_name",
                "run_id",
                "model_version",
                "primary_score",
                "pass_rate",
                "passed_baseline",
                "passed_target",
                "num_examples",
                "num_passed",
                "num_failed",
                "duration_ms",
                "trigger",
                "creator",
                "gk_name",
                "event_timestamp",
            ],
            "orderBy": "event_timestamp DESC",
            "limit": 50,
        },
        "visualization": "table",
    },
    # ── Widget 6: Regressions ─────────────────────────────────────────
    "regressions": {
        "title": "🚨 Regressions Detected",
        "description": "Eval runs where a regression was detected",
        "table": "mft_eval_events",
        "query": {
            "filterBy": {"event_type": ["eval_regression"]},
            "columns": [
                "eval_name",
                "run_id",
                "primary_score",
                "delta_primary_score",
                "gk_name",
                "task_id",
                "creator",
                "event_timestamp",
            ],
            "orderBy": "event_timestamp DESC",
        },
        "visualization": "table",
    },
    # ── Widget 7: Runs by Trigger Type ────────────────────────────────
    "runs_by_trigger": {
        "title": "⚙️ Runs by Trigger Type",
        "description": "Breakdown of eval runs by trigger: manual, CI, scheduled, pre-deploy",
        "table": "mft_eval_events",
        "query": {
            "filterBy": {"event_type": ["eval_run_completed"]},
            "aggregateBy": "count",
            "groupBy": "trigger",
        },
        "visualization": "pie_chart",
    },
    # ── Widget 8: Blocking Evals Status ───────────────────────────────
    "blocking_evals_status": {
        "title": "🛑 Blocking Evals — Current Status",
        "description": "Evals that block deploys and their latest pass/fail status",
        "table": "mft_eval_events",
        "query": {
            "filterBy": {
                "event_type": ["eval_run_completed"],
                "is_blocking": [1],
            },
            "columns": [
                "eval_name",
                "primary_score",
                "passed_baseline",
                "gk_name",
                "event_timestamp",
            ],
            "aggregateBy": "latest",
            "groupBy": "eval_name",
        },
        "visualization": "table",
    },
    # ── Widget 9: Team Leaderboard ────────────────────────────────────
    "team_leaderboard": {
        "title": "🏆 Team Leaderboard — Evals Created",
        "description": "Number of evals created per team",
        "table": "mft_eval_events",
        "query": {
            "filterBy": {"event_type": ["eval_created"]},
            "aggregateBy": "count",
            "groupBy": "team",
            "orderBy": "count DESC",
        },
        "visualization": "bar_chart",
    },
    # ── Widget 10: Average Run Duration ───────────────────────────────
    "avg_run_duration": {
        "title": "⏱️ Average Run Duration by Eval",
        "description": "Average eval run duration in milliseconds",
        "table": "mft_eval_events",
        "query": {
            "filterBy": {"event_type": ["eval_run_completed"]},
            "aggregateBy": "avg(duration_ms)",
            "groupBy": "eval_name",
            "orderBy": "avg(duration_ms) DESC",
        },
        "visualization": "bar_chart",
    },
}


# ─── ODS Counters (for real-time alerting) ────────────────────────────────────

ODS_COUNTERS = {
    "description": "ODS counters to register for real-time monitoring and alerting",
    "entity": "mft_eval_platform",
    "counters": {
        "eval_created": "Bumped when a new eval is created",
        "eval_run_started": "Bumped when an eval run starts",
        "eval_run_completed": "Bumped when an eval run completes",
        "eval_run_passed": "Bumped when an eval run passes baseline",
        "eval_run_failed": "Bumped when an eval run fails baseline",
        "eval_regression_detected": "Bumped when a regression is detected",
        "eval_run_duration_ms": "Records eval run duration for latency tracking",
    },
    "alerts": [
        {
            "name": "MFT Eval Regression Detected",
            "counter": "eval_regression_detected",
            "condition": "value > 0 for 5 minutes",
            "severity": "warning",
            "oncall": "#mft-ai-alerts",
        },
        {
            "name": "MFT Eval Run Failures Spike",
            "counter": "eval_run_failed",
            "condition": "rate > 5 per hour",
            "severity": "critical",
            "oncall": "#mft-ai-alerts",
        },
    ],
}


# ─── Dashboard Builder ────────────────────────────────────────────────────────


@dataclass
class UnidashWidget:
    """A single widget on the Unidash dashboard."""

    title: str
    query_key: str
    width: str = "half"  # "full" or "half"
    height: str = "medium"  # "small", "medium", "large"


@dataclass
class DashboardConfig:
    """
    Unidash dashboard configuration for MFT Eval Platform.

    To create the dashboard:
      1. Go to bunnylol unidash → Create New Dashboard
      2. Name: "MFT Eval Platform"
      3. For each widget below:
         a. Go to bunnylol scuba mft_eval_events
         b. Build the query using the params in SCUBA_QUERIES[widget.query_key]
         c. Click Export → to Unidash → select this dashboard
      4. Arrange widgets and Publish
    """

    name: str = "MFT Eval Platform — All Evals"
    description: str = (
        "Central dashboard tracking all MFT eval creation, runs, scores, and regressions"
    )
    owner: str = ""
    layout: List[List[UnidashWidget]] = field(default_factory=list)

    @classmethod
    def default(cls) -> "DashboardConfig":
        """Create the default dashboard layout."""
        return cls(
            layout=[
                # Row 1: Overview
                [
                    UnidashWidget(
                        "Evals Created Over Time",
                        "evals_created_over_time",
                        width="half",
                    ),
                    UnidashWidget(
                        "Runs by Trigger Type", "runs_by_trigger", width="half"
                    ),
                ],
                # Row 2: Scores
                [
                    UnidashWidget(
                        "Primary Score Trends",
                        "score_trends",
                        width="full",
                        height="large",
                    ),
                ],
                # Row 3: Pass/Fail
                [
                    UnidashWidget("Eval Pass Rate", "eval_pass_rate", width="half"),
                    UnidashWidget(
                        "Blocking Evals Status", "blocking_evals_status", width="half"
                    ),
                ],
                # Row 4: Tables
                [
                    UnidashWidget(
                        "Recent Eval Runs", "recent_runs", width="full", height="large"
                    ),
                ],
                # Row 5: Regressions & Health
                [
                    UnidashWidget("Regressions Detected", "regressions", width="half"),
                    UnidashWidget("Avg Run Duration", "avg_run_duration", width="half"),
                ],
                # Row 6: Registry & Teams
                [
                    UnidashWidget(
                        "Eval Registry", "eval_registry", width="half", height="large"
                    ),
                    UnidashWidget("Team Leaderboard", "team_leaderboard", width="half"),
                ],
            ]
        )

    def get_setup_instructions(self) -> str:
        """Generate step-by-step setup instructions."""
        lines = [
            "=" * 60,
            "MFT EVAL PLATFORM — UNIDASH DASHBOARD SETUP",
            "=" * 60,
            "",
            "1. CREATE DASHBOARD",
            "   → Go to: bunnylol unidash",
            "   → Click 'Create New Dashboard'",
            f"   → Name: '{self.name}'",
            f"   → Description: '{self.description}'",
            "",
            "2. ADD WIDGETS (for each widget below):",
            "",
        ]

        widget_num = 1
        for row in self.layout:
            for widget in row:
                query = SCUBA_QUERIES.get(widget.query_key, {})
                lines.extend(
                    [
                        f"   Widget {widget_num}: {widget.title}",
                        f"   → Open: bunnylol scuba mft_eval_events",
                        f"   → Filter: event_type = {query.get('query', {}).get('filterBy', {}).get('event_type', ['*'])}",
                        f"   → Visualization: {query.get('visualization', 'table')}",
                        f"   → Export → to Unidash → select this dashboard",
                        "",
                    ]
                )
                widget_num += 1

        lines.extend(
            [
                "3. ARRANGE & PUBLISH",
                "   → Drag widgets into the layout described above",
                "   → Click 'Publish' to make visible to the team",
                "",
                "4. SET UP ODS ALERTS",
                "   → Create ODS entity: 'mft_eval_platform'",
                "   → Register counters from ODS_COUNTERS config",
                "   → Set up alerts for regression detection",
                "",
                "=" * 60,
            ]
        )

        return "\n".join(lines)
