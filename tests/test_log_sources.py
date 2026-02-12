#!/usr/bin/env python3
"""
Integration tests for MFT Eval Platform — Production Log Sources.

Tests the full log source pipeline using mock/file-based fallbacks:
  - ScubaLogSource (JSONL mock)
  - HiveLogSource (JSONL and CSV mock)
  - CustomApiLogSource (JSONL mock)
  - Factory function (create_log_source)
  - Config mapping (config_from_eval_data)
  - SQL injection defenses (_validate_sql_identifier, _escape_sql_value)
  - LogSourceConfig dataclass defaults
  - to_test_cases() normalization
  - LogIngestionWorker (ingest_eval, ingest_all)

Zero external dependencies — uses only stdlib unittest + the mft_evals package.

Usage:
    python3 -m unittest tests.test_log_sources -v
    python3 tests/test_log_sources.py
"""

import asyncio
import csv
import importlib.util
import json
import os
import shutil

# Ensure project root is importable
# Ensure project root is importable
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

_project_root = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _project_root)

# Bypass mft_evals/__init__.py (it imports eval.py which needs pyyaml)
# by pre-registering a minimal mft_evals package and loading only
# the submodules we need (dataset, integrations.log_sources) directly.
_mft_pkg = types.ModuleType("mft_evals")
_mft_pkg.__path__ = [os.path.join(_project_root, "mft_evals")]
_mft_pkg.__package__ = "mft_evals"
sys.modules.setdefault("mft_evals", _mft_pkg)

# Load mft_evals.dataset (only stdlib deps)
_dataset_spec = importlib.util.spec_from_file_location(
    "mft_evals.dataset",
    os.path.join(_project_root, "mft_evals", "dataset.py"),
    submodule_search_locations=[],
)
_dataset_mod = importlib.util.module_from_spec(_dataset_spec)
sys.modules["mft_evals.dataset"] = _dataset_mod
_dataset_spec.loader.exec_module(_dataset_mod)

# Ensure integrations sub-package is registered
_integ_pkg = types.ModuleType("mft_evals.integrations")
_integ_pkg.__path__ = [os.path.join(_project_root, "mft_evals", "integrations")]
_integ_pkg.__package__ = "mft_evals.integrations"
sys.modules.setdefault("mft_evals.integrations", _integ_pkg)

# Load log_sources
_ls_spec = importlib.util.spec_from_file_location(
    "mft_evals.integrations.log_sources",
    os.path.join(_project_root, "mft_evals", "integrations", "log_sources.py"),
    submodule_search_locations=[],
)
_ls_mod = importlib.util.module_from_spec(_ls_spec)
sys.modules["mft_evals.integrations.log_sources"] = _ls_mod
_ls_spec.loader.exec_module(_ls_mod)

CustomApiLogSource = _ls_mod.CustomApiLogSource
HiveLogSource = _ls_mod.HiveLogSource
LogSource = _ls_mod.LogSource
LogSourceConfig = _ls_mod.LogSourceConfig
ScubaLogSource = _ls_mod.ScubaLogSource
config_from_eval_data = _ls_mod.config_from_eval_data
create_log_source = _ls_mod.create_log_source

# Check if full mft_evals package is importable (needs yaml, httpx, etc.)
try:
    import yaml  # noqa: F401

    HAS_FULL_PACKAGE = True
except ImportError:
    HAS_FULL_PACKAGE = False


def run_async(coro):
    """Helper to run async coroutines in sync test methods."""
    return asyncio.get_event_loop().run_until_complete(coro)


class TestLogSourceConfig(unittest.TestCase):
    """Tests for LogSourceConfig dataclass defaults and construction."""

    def test_defaults(self):
        config = LogSourceConfig()
        self.assertEqual(config.source_type, "")
        self.assertEqual(config.table_or_endpoint, "")
        self.assertEqual(config.input_column, "input")
        self.assertEqual(config.output_column, "output")
        self.assertEqual(config.expected_column, "")
        self.assertEqual(config.timestamp_column, "timestamp")
        self.assertEqual(config.id_column, "id")
        self.assertEqual(config.sample_rate, 10)
        self.assertEqual(config.lookback_hours, 24)
        self.assertEqual(config.max_rows, 1000)
        self.assertEqual(config.filters, {})
        self.assertEqual(config.auth_type, "none")
        self.assertEqual(config.credentials, {})

    def test_custom_values(self):
        config = LogSourceConfig(
            source_type="scuba",
            table_or_endpoint="my_table",
            input_column="request_text",
            output_column="model_response",
            sample_rate=5,
            lookback_hours=48,
            max_rows=500,
            filters={"status": "success"},
        )
        self.assertEqual(config.source_type, "scuba")
        self.assertEqual(config.table_or_endpoint, "my_table")
        self.assertEqual(config.input_column, "request_text")
        self.assertEqual(config.max_rows, 500)
        self.assertEqual(config.filters, {"status": "success"})

    def test_mutable_defaults_are_independent(self):
        """Verify each instance gets its own dict for mutable fields."""
        c1 = LogSourceConfig()
        c2 = LogSourceConfig()
        c1.filters["key"] = "val"
        self.assertNotIn("key", c2.filters)


# ─── ScubaLogSource Tests ─────────────────────────────────────────────────────


class TestScubaLogSource(unittest.TestCase):
    """Integration tests for ScubaLogSource using mock JSONL files."""

    @classmethod
    def setUpClass(cls):
        """Create temp mock data directory with a known JSONL file."""
        cls.temp_dir = tempfile.mkdtemp()
        cls.mock_dir = Path(cls.temp_dir) / ".mft_evals" / "mock_logs"
        cls.mock_dir.mkdir(parents=True)

        cls.mock_records = [
            {
                "id": "s001",
                "input": "Pay $100 to Acme",
                "output": "100.00",
                "timestamp": 1700000000,
                "status": "ok",
            },
            {
                "id": "s002",
                "input": "Send €50 to Berlin",
                "output": "50.00",
                "timestamp": 1700000060,
                "status": "ok",
            },
            {
                "id": "s003",
                "input": "Refund $25",
                "output": "25.00",
                "timestamp": 1700000120,
                "status": "ok",
            },
        ]
        cls.mock_file = cls.mock_dir / "test_scuba_table.jsonl"
        with open(cls.mock_file, "w") as f:
            for rec in cls.mock_records:
                f.write(json.dumps(rec) + "\n")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir)

    def _make_source(self, table="test_scuba_table", **overrides):
        config = LogSourceConfig(
            source_type="scuba", table_or_endpoint=table, **overrides
        )
        source = ScubaLogSource(config)
        source._mock_path = self.mock_dir / f"{table}.jsonl"
        return source

    def test_fetch_raw_logs_returns_all_records(self):
        source = self._make_source()
        logs = run_async(source.fetch_raw_logs(max_rows=100))
        self.assertEqual(len(logs), 3)
        self.assertEqual(logs[0]["id"], "s001")
        self.assertEqual(logs[2]["output"], "25.00")

    def test_fetch_raw_logs_respects_max_rows(self):
        source = self._make_source()
        logs = run_async(source.fetch_raw_logs(max_rows=2))
        self.assertEqual(len(logs), 2)

    def test_fetch_raw_logs_empty_file(self):
        empty_file = self.mock_dir / "empty_table.jsonl"
        empty_file.touch()
        source = self._make_source(table="empty_table")
        logs = run_async(source.fetch_raw_logs())
        self.assertEqual(len(logs), 0)

    def test_fetch_raw_logs_missing_file(self):
        source = self._make_source(table="nonexistent_table")
        logs = run_async(source.fetch_raw_logs())
        self.assertEqual(len(logs), 0)

    def test_to_test_cases_conversion(self):
        source = self._make_source()
        logs = run_async(source.fetch_raw_logs())
        test_cases = source.to_test_cases(logs)

        self.assertEqual(len(test_cases), 3)

        tc = test_cases[0]
        self.assertEqual(tc.id, "s001")
        self.assertEqual(tc.input, "Pay $100 to Acme")
        self.assertEqual(tc.expected_output, "100.00")
        self.assertEqual(tc.metadata["actual_output"], "100.00")
        self.assertEqual(tc.metadata["source"], "production")
        self.assertEqual(tc.metadata["source_type"], "scuba")
        self.assertIn("fetched_at", tc.metadata)

    def test_to_test_cases_custom_columns(self):
        source = self._make_source(
            input_column="input",
            output_column="output",
            id_column="id",
        )
        logs = run_async(source.fetch_raw_logs())
        test_cases = source.to_test_cases(logs)
        self.assertEqual(test_cases[0].id, "s001")
        self.assertEqual(test_cases[0].input, "Pay $100 to Acme")

    def test_to_test_cases_with_transform(self):
        source = self._make_source()
        logs = run_async(source.fetch_raw_logs())

        def uppercase_input(record):
            record = dict(record)
            record["input"] = record["input"].upper()
            return record

        test_cases = source.to_test_cases(logs, transform_fn=uppercase_input)
        self.assertEqual(test_cases[0].input, "PAY $100 TO ACME")

    def test_sample_convenience_method(self):
        source = self._make_source()
        test_cases = run_async(source.sample(max_rows=2))
        self.assertEqual(len(test_cases), 2)
        self.assertEqual(test_cases[0].id, "s001")

    def test_test_connection_with_mock_data(self):
        source = self._make_source()
        result = run_async(source.test_connection())
        self.assertTrue(result["connected"])
        self.assertIn("Mock data found", result["message"])
        self.assertIsNotNone(result["sample_row"])
        self.assertEqual(result["sample_row"]["id"], "s001")

    def test_test_connection_missing_data(self):
        source = self._make_source(table="nonexistent_xyz")
        result = run_async(source.test_connection())
        self.assertFalse(result["connected"])
        self.assertIn("No mock data", result["message"])
        self.assertIsNone(result["sample_row"])

    def test_get_schema_from_mock(self):
        source = self._make_source()
        schema = run_async(source.get_schema())
        self.assertGreater(len(schema), 0)
        names = [col["name"] for col in schema]
        self.assertIn("id", names)
        self.assertIn("input", names)
        self.assertIn("output", names)

    def test_get_schema_empty_source(self):
        source = self._make_source(table="nonexistent_xyz")
        schema = run_async(source.get_schema())
        self.assertEqual(schema, [])


# ─── HiveLogSource Tests ─────────────────────────────────────────────────────


class TestHiveLogSource(unittest.TestCase):
    """Integration tests for HiveLogSource using mock JSONL and CSV files."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.mock_dir = Path(cls.temp_dir) / ".mft_evals" / "mock_logs"
        cls.mock_dir.mkdir(parents=True)

        # JSONL mock
        cls.jsonl_records = [
            {
                "id": "h001",
                "request_body": "Check balance",
                "response_body": "$1234.56",
                "ds": "2024-01-15",
                "status": "ok",
            },
            {
                "id": "h002",
                "request_body": "Transfer $100",
                "response_body": "Done",
                "ds": "2024-01-15",
                "status": "ok",
            },
            {
                "id": "h003",
                "request_body": "Close account",
                "response_body": "ERROR: pending txns",
                "ds": "2024-01-14",
                "status": "failed",
            },
        ]
        cls.jsonl_file = cls.mock_dir / "mft_data_hive_test.jsonl"
        with open(cls.jsonl_file, "w") as f:
            for rec in cls.jsonl_records:
                f.write(json.dumps(rec) + "\n")

        # CSV mock (different table name to test CSV fallback)
        cls.csv_file = cls.mock_dir / "mft_data_csv_test.csv"
        with open(cls.csv_file, "w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["id", "request_body", "response_body", "ds", "status"]
            )
            writer.writeheader()
            writer.writerow(
                {
                    "id": "c001",
                    "request_body": "Pay $99",
                    "response_body": "99.00",
                    "ds": "2024-01-15",
                    "status": "ok",
                }
            )
            writer.writerow(
                {
                    "id": "c002",
                    "request_body": "Refund $25",
                    "response_body": "25.00",
                    "ds": "2024-01-14",
                    "status": "ok",
                }
            )

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir)

    def _make_source(self, table="mft_data.hive_test", mock_file=None, **overrides):
        config = LogSourceConfig(
            source_type="hive",
            table_or_endpoint=table,
            input_column="request_body",
            output_column="response_body",
            timestamp_column="ds",
            **overrides,
        )
        source = HiveLogSource(config)
        table_safe = table.replace(".", "_").replace("/", "_")
        source._mock_path = mock_file or (self.mock_dir / f"{table_safe}.jsonl")
        return source

    def test_fetch_jsonl(self):
        source = self._make_source()
        logs = run_async(source.fetch_raw_logs(max_rows=100))
        self.assertEqual(len(logs), 3)
        self.assertEqual(logs[0]["id"], "h001")

    def test_fetch_jsonl_max_rows(self):
        source = self._make_source()
        logs = run_async(source.fetch_raw_logs(max_rows=1))
        self.assertEqual(len(logs), 1)

    def test_fetch_csv_fallback(self):
        """When JSONL doesn't exist, falls back to CSV."""
        source = self._make_source(table="mft_data.csv_test")
        logs = run_async(source.fetch_raw_logs(max_rows=100))
        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[0]["id"], "c001")

    def test_fetch_missing_both(self):
        source = self._make_source(table="mft_data.nonexistent")
        logs = run_async(source.fetch_raw_logs())
        self.assertEqual(len(logs), 0)

    def test_to_test_cases_from_jsonl(self):
        source = self._make_source()
        logs = run_async(source.fetch_raw_logs())
        test_cases = source.to_test_cases(logs)

        self.assertEqual(len(test_cases), 3)
        self.assertEqual(test_cases[0].id, "h001")
        self.assertEqual(test_cases[0].input, "Check balance")
        self.assertEqual(test_cases[0].expected_output, "$1234.56")
        self.assertEqual(test_cases[0].metadata["actual_output"], "$1234.56")
        self.assertIn("ds", test_cases[0].metadata)

    def test_test_connection_jsonl_exists(self):
        source = self._make_source()
        result = run_async(source.test_connection())
        self.assertTrue(result["connected"])
        self.assertIn("Mock data available", result["message"])
        self.assertIsNotNone(result["sample_row"])

    def test_test_connection_csv_exists(self):
        source = self._make_source(table="mft_data.csv_test")
        result = run_async(source.test_connection())
        self.assertTrue(result["connected"])

    def test_test_connection_missing(self):
        source = self._make_source(table="mft_data.gone")
        result = run_async(source.test_connection())
        self.assertFalse(result["connected"])
        self.assertIn("No mock data", result["message"])

    def test_get_schema_from_jsonl(self):
        source = self._make_source()
        schema = run_async(source.get_schema())
        names = [col["name"] for col in schema]
        self.assertIn("id", names)
        self.assertIn("request_body", names)
        self.assertIn("response_body", names)


# ─── HiveLogSource SQL Injection Defense Tests ────────────────────────────────


class TestHiveLogSourceSQLDefense(unittest.TestCase):
    """Tests for SQL injection prevention in HiveLogSource."""

    def test_validate_sql_identifier_valid(self):
        valid_names = [
            "my_table",
            "mft_data.payment_transactions",
            "schema.table_name",
            "ds",
            "_private",
            "CamelCase123",
        ]
        for name in valid_names:
            result = HiveLogSource._validate_sql_identifier(name)
            self.assertEqual(result, name, f"Should accept: {name!r}")

    def test_validate_sql_identifier_rejects_injection(self):
        malicious_names = [
            "table; DROP TABLE users--",
            "table' OR '1'='1",
            'table"; DELETE FROM evals--',
            "tab\nle",
            "",
            "123_starts_with_digit",
            "has spaces",
            "has;semicolon",
            "has(parens)",
        ]
        for name in malicious_names:
            with self.assertRaises(ValueError, msg=f"Should reject: {name!r}"):
                HiveLogSource._validate_sql_identifier(name)

    def test_escape_sql_value_escapes_quotes(self):
        self.assertEqual(
            HiveLogSource._escape_sql_value("it's a test"),
            "it''s a test",
        )
        self.assertEqual(
            HiveLogSource._escape_sql_value("normal"),
            "normal",
        )
        self.assertEqual(
            HiveLogSource._escape_sql_value("'; DROP TABLE--"),
            "''; DROP TABLE--",
        )

    def test_escape_sql_value_handles_non_strings(self):
        self.assertEqual(HiveLogSource._escape_sql_value(42), "42")
        self.assertEqual(HiveLogSource._escape_sql_value(None), "None")


# ─── CustomApiLogSource Tests ─────────────────────────────────────────────────


class TestCustomApiLogSource(unittest.TestCase):
    """Integration tests for CustomApiLogSource using mock JSONL files."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.mock_dir = Path(cls.temp_dir) / ".mft_evals" / "mock_logs"
        cls.mock_dir.mkdir(parents=True)

        cls.mock_records = [
            {
                "id": "a001",
                "user_query": "Order status #123",
                "bot_response": "In transit",
                "channel": "web",
            },
            {
                "id": "a002",
                "user_query": "Cancel subscription",
                "bot_response": "Cancelled",
                "channel": "mobile",
            },
            {
                "id": "a003",
                "user_query": "Reset password",
                "bot_response": "Go to Settings",
                "channel": "web",
            },
        ]
        cls.mock_file = cls.mock_dir / "custom_api.jsonl"
        with open(cls.mock_file, "w") as f:
            for rec in cls.mock_records:
                f.write(json.dumps(rec) + "\n")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir)

    def _make_source(self, endpoint="mock://test", **overrides):
        config = LogSourceConfig(
            source_type="custom_api",
            table_or_endpoint=endpoint,
            input_column="user_query",
            output_column="bot_response",
            **overrides,
        )
        source = CustomApiLogSource(config)
        source._mock_path = self.mock_dir / "custom_api.jsonl"
        return source

    def test_fetch_from_mock(self):
        source = self._make_source()
        logs = run_async(source.fetch_raw_logs(max_rows=100))
        self.assertEqual(len(logs), 3)
        self.assertEqual(logs[0]["id"], "a001")

    def test_fetch_max_rows(self):
        source = self._make_source()
        logs = run_async(source.fetch_raw_logs(max_rows=1))
        self.assertEqual(len(logs), 1)

    def test_fetch_empty_endpoint_uses_mock(self):
        source = self._make_source(endpoint="")
        logs = run_async(source.fetch_raw_logs())
        self.assertEqual(len(logs), 3)

    def test_to_test_cases(self):
        source = self._make_source()
        logs = run_async(source.fetch_raw_logs())
        test_cases = source.to_test_cases(logs)

        self.assertEqual(len(test_cases), 3)
        self.assertEqual(test_cases[0].id, "a001")
        self.assertEqual(test_cases[0].input, "Order status #123")
        self.assertEqual(test_cases[0].expected_output, "In transit")
        self.assertEqual(test_cases[0].metadata["actual_output"], "In transit")
        self.assertIn("channel", test_cases[0].metadata)

    def test_sample_method(self):
        source = self._make_source()
        test_cases = run_async(source.sample(max_rows=2))
        self.assertEqual(len(test_cases), 2)

    def test_test_connection_mock_mode(self):
        source = self._make_source()
        result = run_async(source.test_connection())
        self.assertTrue(result["connected"])
        self.assertIn("Mock mode", result["message"])

    def test_test_connection_missing_mock(self):
        source = self._make_source()
        source._mock_path = Path("/nonexistent/path/mock.jsonl")
        result = run_async(source.test_connection())
        self.assertFalse(result["connected"])

    def test_get_schema(self):
        source = self._make_source()
        schema = run_async(source.get_schema())
        names = [col["name"] for col in schema]
        self.assertIn("id", names)
        self.assertIn("user_query", names)
        self.assertIn("bot_response", names)

    def test_extract_data_list_response(self):
        source = self._make_source()
        source.response_data_path = ""
        data = [{"a": 1}, {"b": 2}]
        self.assertEqual(source._extract_data(data), [{"a": 1}, {"b": 2}])

    def test_extract_data_nested_path(self):
        source = self._make_source()
        source.response_data_path = "results.items"
        data = {"results": {"items": [{"x": 1}, {"x": 2}]}}
        self.assertEqual(source._extract_data(data), [{"x": 1}, {"x": 2}])

    def test_extract_data_single_object(self):
        source = self._make_source()
        source.response_data_path = "result"
        data = {"result": {"x": 42}}
        self.assertEqual(source._extract_data(data), [{"x": 42}])

    def test_extract_data_missing_path(self):
        source = self._make_source()
        source.response_data_path = "nonexistent.path"
        data = {"other": "stuff"}
        self.assertEqual(source._extract_data(data), [])

    def test_extract_field(self):
        source = self._make_source()
        data = {"pagination": {"next_cursor": "abc123"}}
        self.assertEqual(
            source._extract_field(data, "pagination.next_cursor"), "abc123"
        )
        self.assertIsNone(source._extract_field(data, "missing.path"))


# ─── Factory Tests ────────────────────────────────────────────────────────────


class TestCreateLogSource(unittest.TestCase):
    """Tests for the create_log_source factory function."""

    def test_creates_scuba_source(self):
        config = LogSourceConfig(source_type="scuba", table_or_endpoint="test_table")
        source = create_log_source(config)
        self.assertIsInstance(source, ScubaLogSource)

    def test_creates_hive_source(self):
        config = LogSourceConfig(source_type="hive", table_or_endpoint="db.table")
        source = create_log_source(config)
        self.assertIsInstance(source, HiveLogSource)

    def test_creates_presto_as_hive(self):
        config = LogSourceConfig(source_type="presto", table_or_endpoint="db.table")
        source = create_log_source(config)
        self.assertIsInstance(source, HiveLogSource)

    def test_creates_custom_api_source(self):
        config = LogSourceConfig(
            source_type="custom_api", table_or_endpoint="https://api.example.com"
        )
        source = create_log_source(config)
        self.assertIsInstance(source, CustomApiLogSource)

    def test_api_alias(self):
        config = LogSourceConfig(
            source_type="api", table_or_endpoint="https://api.example.com"
        )
        source = create_log_source(config)
        self.assertIsInstance(source, CustomApiLogSource)

    def test_case_insensitive(self):
        config = LogSourceConfig(source_type="SCUBA", table_or_endpoint="test")
        source = create_log_source(config)
        self.assertIsInstance(source, ScubaLogSource)

    def test_unknown_type_raises(self):
        config = LogSourceConfig(source_type="bigquery", table_or_endpoint="test")
        with self.assertRaises(ValueError) as ctx:
            create_log_source(config)
        self.assertIn("bigquery", str(ctx.exception))
        self.assertIn("Supported", str(ctx.exception))


# ─── config_from_eval_data Tests ──────────────────────────────────────────────


class TestConfigFromEvalData(unittest.TestCase):
    """Tests for config_from_eval_data mapping function."""

    def test_returns_none_when_not_enabled(self):
        eval_data = {"prodLogEnabled": False, "prod_log_enabled": 0}
        self.assertIsNone(config_from_eval_data(eval_data))

    def test_returns_none_when_fields_missing(self):
        eval_data = {"name": "test eval"}
        self.assertIsNone(config_from_eval_data(eval_data))

    def test_maps_camel_case_fields(self):
        eval_data = {
            "prodLogEnabled": True,
            "prodLogSource": "scuba",
            "prodLogTable": "my_scuba_table",
            "prodLogInputColumn": "request_text",
            "prodLogOutputColumn": "response_text",
            "prodLogTimestampColumn": "event_time",
            "prodLogSampleRate": 5,
        }
        config = config_from_eval_data(eval_data)
        self.assertIsNotNone(config)
        self.assertEqual(config.source_type, "scuba")
        self.assertEqual(config.table_or_endpoint, "my_scuba_table")
        self.assertEqual(config.input_column, "request_text")
        self.assertEqual(config.output_column, "response_text")
        self.assertEqual(config.timestamp_column, "event_time")
        self.assertEqual(config.sample_rate, 5)

    def test_maps_snake_case_fields(self):
        eval_data = {
            "prod_log_enabled": 1,
            "prod_log_source": "hive",
            "prod_log_table": "db.transactions",
            "prod_log_input_column": "query",
            "prod_log_output_column": "answer",
            "prod_log_timestamp_column": "ds",
            "prod_log_sample_rate": 20,
        }
        config = config_from_eval_data(eval_data)
        self.assertIsNotNone(config)
        self.assertEqual(config.source_type, "hive")
        self.assertEqual(config.table_or_endpoint, "db.transactions")
        self.assertEqual(config.input_column, "query")

    def test_maps_extended_fields_from_config_json(self):
        eval_data = {
            "prodLogEnabled": True,
            "prodLogSource": "scuba",
            "prodLogTable": "table",
            "config": json.dumps(
                {
                    "prodLogExpectedColumn": "gold_label",
                    "prodLogIdColumn": "request_id",
                    "prodLogLookbackHours": 48,
                    "prodLogMaxRows": 2000,
                    "prodLogFilters": {"environment": "production"},
                }
            ),
        }
        config = config_from_eval_data(eval_data)
        self.assertIsNotNone(config)
        self.assertEqual(config.expected_column, "gold_label")
        self.assertEqual(config.id_column, "request_id")
        self.assertEqual(config.lookback_hours, 48)
        self.assertEqual(config.max_rows, 2000)
        self.assertEqual(config.filters, {"environment": "production"})

    def test_defaults_when_config_json_missing(self):
        eval_data = {
            "prodLogEnabled": True,
            "prodLogSource": "scuba",
            "prodLogTable": "table",
        }
        config = config_from_eval_data(eval_data)
        self.assertEqual(config.expected_column, "")
        self.assertEqual(config.id_column, "id")
        self.assertEqual(config.lookback_hours, 24)
        self.assertEqual(config.max_rows, 1000)
        self.assertEqual(config.filters, {})

    def test_handles_malformed_config_json(self):
        eval_data = {
            "prodLogEnabled": True,
            "prodLogSource": "scuba",
            "prodLogTable": "table",
            "config": "not valid json {{{",
        }
        config = config_from_eval_data(eval_data)
        self.assertIsNotNone(config)
        self.assertEqual(config.lookback_hours, 24)


# ─── to_test_cases Edge Cases ─────────────────────────────────────────────────


class TestToTestCasesEdgeCases(unittest.TestCase):
    """Tests for edge cases in LogSource.to_test_cases()."""

    def _make_source(self, **overrides):
        config = LogSourceConfig(
            source_type="scuba", table_or_endpoint="t", **overrides
        )
        source = ScubaLogSource(config)
        return source

    def test_empty_logs(self):
        source = self._make_source()
        result = source.to_test_cases([])
        self.assertEqual(result, [])

    def test_missing_columns_use_defaults(self):
        source = self._make_source()
        logs = [{"some_other_field": "value"}]
        test_cases = source.to_test_cases(logs)
        self.assertEqual(len(test_cases), 1)
        tc = test_cases[0]
        self.assertEqual(tc.id, "prod_0")
        self.assertEqual(tc.input, "")
        self.assertEqual(tc.expected_output, "")

    def test_expected_column_used_when_configured(self):
        source = self._make_source(expected_column="gold_label")
        logs = [{"input": "q", "output": "a", "gold_label": "correct_answer"}]
        test_cases = source.to_test_cases(logs)
        self.assertEqual(test_cases[0].expected_output, "correct_answer")

    def test_expected_output_falls_back_to_output_when_no_expected_column(self):
        source = self._make_source()
        logs = [{"input": "q", "output": "model_says_this"}]
        test_cases = source.to_test_cases(logs)
        self.assertEqual(test_cases[0].expected_output, "model_says_this")

    def test_metadata_excludes_mapped_columns(self):
        source = self._make_source(
            id_column="id", input_column="input", output_column="output"
        )
        logs = [{"id": "1", "input": "q", "output": "a", "extra": "metadata_val"}]
        test_cases = source.to_test_cases(logs)
        self.assertIn("extra", test_cases[0].metadata)
        self.assertNotIn("id", test_cases[0].metadata)
        self.assertNotIn("input", test_cases[0].metadata)

    def test_non_string_values_are_stringified(self):
        source = self._make_source()
        logs = [{"input": 42, "output": 3.14}]
        test_cases = source.to_test_cases(logs)
        self.assertEqual(test_cases[0].input, "42")
        self.assertEqual(test_cases[0].expected_output, "3.14")


# ─── LogIngestionWorker Tests ─────────────────────────────────────────────────


@unittest.skipUnless(HAS_FULL_PACKAGE, "Requires pyyaml and full mft_evals package")
class TestLogIngestionWorker(unittest.TestCase):
    """Integration tests for LogIngestionWorker."""

    @classmethod
    def setUpClass(cls):
        """Set up a temporary DB and mock data."""
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_evals.db")
        cls.mock_dir = Path(cls.temp_dir) / ".mft_evals" / "mock_logs"
        cls.mock_dir.mkdir(parents=True)

        # Write mock log data
        mock_records = [
            {
                "id": "w001",
                "input": "Test input 1",
                "output": "Output 1",
                "timestamp": 1700000000,
            },
            {
                "id": "w002",
                "input": "Test input 2",
                "output": "Output 2",
                "timestamp": 1700000060,
            },
        ]
        cls.mock_log_file = cls.mock_dir / "worker_test_table.jsonl"
        with open(cls.mock_log_file, "w") as f:
            for rec in mock_records:
                f.write(json.dumps(rec) + "\n")

        # Point storage at temp DB
        os.environ["MFT_EVALS_DB_PATH"] = cls.db_path

        from mft_evals import storage

        storage.init_db()

    @classmethod
    def tearDownClass(cls):
        os.environ.pop("MFT_EVALS_DB_PATH", None)
        shutil.rmtree(cls.temp_dir)

    def test_ingest_eval_not_found(self):
        from mft_evals.integrations.log_worker import LogIngestionWorker

        worker = LogIngestionWorker()
        result = run_async(worker.ingest_eval("nonexistent-id"))
        self.assertEqual(result.status, "error")
        self.assertIn("Eval not found", result.error)

    def test_ingest_eval_not_enabled(self):
        from mft_evals import storage
        from mft_evals.integrations.log_worker import LogIngestionWorker

        eval_record = storage.create_eval(
            {
                "evalName": "worker_test_no_log",
                "name": "worker_test_no_log",
                "team": "test",
                "metrics": [],
                "prodLogEnabled": False,
            }
        )
        worker = LogIngestionWorker()
        result = run_async(worker.ingest_eval(eval_record["id"]))
        self.assertEqual(result.status, "skipped")
        self.assertIn("not enabled", result.error)

        storage.delete_eval(eval_record["id"])

    def test_ingest_eval_with_mock_data(self):
        from mft_evals import storage
        from mft_evals.integrations.log_worker import LogIngestionWorker

        eval_record = storage.create_eval(
            {
                "evalName": "worker_test_with_log",
                "name": "worker_test_with_log",
                "team": "test",
                "metrics": [],
                "prodLogEnabled": True,
                "prodLogSource": "scuba",
                "prodLogTable": "worker_test_table",
                "prodLogInputColumn": "input",
                "prodLogOutputColumn": "output",
            }
        )

        worker = LogIngestionWorker()

        # Patch the ScubaLogSource mock path to our temp dir
        original_init = ScubaLogSource.__init__

        def patched_init(self_src, config):
            original_init(self_src, config)
            self_src._mock_path = (
                self.__class__.mock_dir / f"{config.table_or_endpoint}.jsonl"
            )

        test_instance = self

        def patched_init_bound(self_src, config):
            original_init(self_src, config)
            self_src._mock_path = (
                test_instance.mock_dir / f"{config.table_or_endpoint}.jsonl"
            )

        with patch.object(ScubaLogSource, "__init__", patched_init_bound):
            result = run_async(worker.ingest_eval(eval_record["id"]))

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.records_fetched, 2)
        self.assertEqual(result.test_cases_created, 2)
        self.assertGreater(result.duration_ms, 0)
        self.assertNotEqual(result.completed_at, "")

        # Verify data was persisted
        updated_eval = storage.get_eval(eval_record["id"])
        sample_data = updated_eval.get("sample_data", [])
        if isinstance(sample_data, str):
            sample_data = json.loads(sample_data)
        self.assertEqual(len(sample_data), 2)
        self.assertEqual(sample_data[0]["source"], "production")

        storage.delete_eval(eval_record["id"])

    def test_ingest_all_skips_disabled(self):
        from mft_evals import storage
        from mft_evals.integrations.log_worker import LogIngestionWorker

        eval_record = storage.create_eval(
            {
                "evalName": "worker_all_disabled",
                "name": "worker_all_disabled",
                "team": "test",
                "metrics": [],
                "prodLogEnabled": False,
            }
        )

        worker = LogIngestionWorker()
        results = run_async(worker.ingest_all())
        # Should return empty since no evals have prod logging enabled
        # (the one we created has it disabled)
        enabled_count = sum(1 for r in results if r.eval_name == "worker_all_disabled")
        self.assertEqual(enabled_count, 0)

        storage.delete_eval(eval_record["id"])

    def test_ingestion_result_to_dict(self):
        from mft_evals.integrations.log_worker import IngestionResult

        result = IngestionResult("eval-123", "Test Eval")
        result.status = "completed"
        result.records_fetched = 10
        result.test_cases_created = 10
        d = result.to_dict()
        self.assertEqual(d["eval_id"], "eval-123")
        self.assertEqual(d["eval_name"], "Test Eval")
        self.assertEqual(d["status"], "completed")
        self.assertEqual(d["records_fetched"], 10)
        self.assertIn("started_at", d)
        self.assertIn("duration_ms", d)

    def test_ingestion_preserves_manual_data(self):
        """Verify that ingestion keeps manually-added test data and only replaces production data."""
        from mft_evals import storage
        from mft_evals.integrations.log_worker import LogIngestionWorker

        manual_data = [
            {
                "id": "manual_1",
                "input": "Manual test",
                "expected_output": "Expected",
                "source": "manual",
            },
            {
                "id": "prod_old",
                "input": "Old prod",
                "expected_output": "Old",
                "source": "production",
            },
        ]

        eval_record = storage.create_eval(
            {
                "evalName": "worker_preserve_manual",
                "name": "worker_preserve_manual",
                "team": "test",
                "metrics": [],
                "sampleData": manual_data,
                "prodLogEnabled": True,
                "prodLogSource": "scuba",
                "prodLogTable": "worker_test_table",
                "prodLogInputColumn": "input",
                "prodLogOutputColumn": "output",
            }
        )

        test_instance = self
        original_init = ScubaLogSource.__init__

        def patched_init_bound(self_src, config):
            original_init(self_src, config)
            self_src._mock_path = (
                test_instance.mock_dir / f"{config.table_or_endpoint}.jsonl"
            )

        worker = LogIngestionWorker()
        with patch.object(ScubaLogSource, "__init__", patched_init_bound):
            result = run_async(worker.ingest_eval(eval_record["id"]))

        self.assertEqual(result.status, "completed")

        updated_eval = storage.get_eval(eval_record["id"])
        sample_data = updated_eval.get("sample_data", [])
        if isinstance(sample_data, str):
            sample_data = json.loads(sample_data)

        manual_items = [d for d in sample_data if d.get("source") == "manual"]
        prod_items = [d for d in sample_data if d.get("source") == "production"]

        self.assertEqual(len(manual_items), 1, "Manual data should be preserved")
        self.assertEqual(manual_items[0]["id"], "manual_1")
        self.assertEqual(len(prod_items), 2, "Should have fresh production data")
        # Old production data should be gone (replaced by new)
        old_prod = [d for d in prod_items if d.get("id") == "prod_old"]
        self.assertEqual(len(old_prod), 0, "Old production data should be replaced")

        storage.delete_eval(eval_record["id"])


# ─── Cross-Source: Verify TestCase Contract ───────────────────────────────────


class TestTestCaseContract(unittest.TestCase):
    """Verify all log sources produce TestCase objects with the same contract."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.mock_dir = Path(cls.temp_dir) / ".mft_evals" / "mock_logs"
        cls.mock_dir.mkdir(parents=True)

        record = {"id": "x1", "input": "query", "output": "answer", "ts": 1700000000}
        for name in ("scuba_contract", "hive_contract", "custom_api"):
            path = cls.mock_dir / f"{name}.jsonl"
            with open(path, "w") as f:
                f.write(json.dumps(record) + "\n")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir)

    def _test_source_contract(self, source):
        """Shared assertions for any log source's TestCase output."""
        test_cases = run_async(source.sample(max_rows=10))
        self.assertGreater(len(test_cases), 0)
        tc = test_cases[0]

        self.assertIsInstance(tc.id, str)
        self.assertTrue(len(tc.id) > 0)
        self.assertIsInstance(tc.input, str)
        self.assertIsInstance(tc.expected_output, str)
        self.assertIsInstance(tc.metadata, dict)
        self.assertIn("actual_output", tc.metadata)
        self.assertIn("source", tc.metadata)
        self.assertEqual(tc.metadata["source"], "production")
        self.assertIn("source_type", tc.metadata)
        self.assertIn("fetched_at", tc.metadata)

    def test_scuba_source_contract(self):
        config = LogSourceConfig(
            source_type="scuba", table_or_endpoint="scuba_contract"
        )
        source = ScubaLogSource(config)
        source._mock_path = self.mock_dir / "scuba_contract.jsonl"
        self._test_source_contract(source)
        self.assertEqual(
            run_async(source.sample(max_rows=1))[0].metadata["source_type"],
            "scuba",
        )

    def test_hive_source_contract(self):
        config = LogSourceConfig(source_type="hive", table_or_endpoint="hive.contract")
        source = HiveLogSource(config)
        source._mock_path = self.mock_dir / "hive_contract.jsonl"
        self._test_source_contract(source)
        self.assertEqual(
            run_async(source.sample(max_rows=1))[0].metadata["source_type"],
            "hive",
        )

    def test_api_source_contract(self):
        config = LogSourceConfig(
            source_type="custom_api", table_or_endpoint="mock://test"
        )
        source = CustomApiLogSource(config)
        source._mock_path = self.mock_dir / "custom_api.jsonl"
        self._test_source_contract(source)
        self.assertEqual(
            run_async(source.sample(max_rows=1))[0].metadata["source_type"],
            "custom_api",
        )


# ─── Main ─────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    unittest.main(verbosity=2)
