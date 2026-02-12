"""
MFT Eval Platform - Production Log Source Connectors

Abstract base and concrete implementations for pulling production logs
from various Meta infrastructure sources. These connectors enable the
"CONNECT" phase in the UI — where users point their eval at a real
production data source.

Supported sources:
  - ScubaLogSource: Pull from Scuba tables (e.g. transaction logs, inference logs)
  - HiveLogSource: Pull from Hive/Presto tables (batch data)
  - CustomApiLogSource: Pull from arbitrary REST/GraphQL endpoints

Each connector normalizes raw production data into TestCase objects
that the eval runner can score.

Local development: All connectors have a mock/file-based fallback
so the full pipeline works without Meta infra access.
"""

import asyncio
import json
import logging
import os
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from mft_evals.dataset import TestCase

logger = logging.getLogger(__name__)


# ─── Base Log Source ──────────────────────────────────────────────────────────


@dataclass
class LogSourceConfig:
    """Configuration for a production log source connector."""

    source_type: str = ""
    table_or_endpoint: str = ""
    input_column: str = "input"
    output_column: str = "output"
    expected_column: str = ""
    timestamp_column: str = "timestamp"
    id_column: str = "id"
    sample_rate: int = 10
    lookback_hours: int = 24
    max_rows: int = 1000
    filters: Dict[str, Any] = field(default_factory=dict)
    auth_type: str = "none"
    credentials: Dict[str, str] = field(default_factory=dict)


class LogSource(ABC):
    """
    Abstract base class for production log source connectors.

    All log sources must implement:
      - fetch_raw_logs(): Pull raw log records from the source
      - test_connection(): Verify the source is reachable
      - get_schema(): Return available columns/fields

    The base class provides:
      - to_test_cases(): Convert raw logs → TestCase objects
      - sample(): Fetch + convert in one call
    """

    def __init__(self, config: LogSourceConfig):
        self.config = config

    @abstractmethod
    async def fetch_raw_logs(
        self,
        lookback_hours: int = None,
        max_rows: int = None,
        filters: Dict[str, Any] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch raw log records from the production source."""

    @abstractmethod
    async def test_connection(self) -> Dict[str, Any]:
        """
        Test connectivity to the log source.

        Returns:
            Dict with keys: connected (bool), message (str), sample_row (dict|None)
        """

    @abstractmethod
    async def get_schema(self) -> List[Dict[str, str]]:
        """
        Get the schema of available columns/fields.

        Returns:
            List of dicts with keys: name, type, description
        """

    def to_test_cases(
        self,
        raw_logs: List[Dict[str, Any]],
        transform_fn: Callable = None,
    ) -> List[TestCase]:
        """
        Convert raw log records to TestCase objects for the eval runner.

        Args:
            raw_logs: Raw records from fetch_raw_logs()
            transform_fn: Optional function to transform each record before conversion

        Returns:
            List of TestCase objects ready for scoring
        """
        test_cases = []
        for i, record in enumerate(raw_logs):
            if transform_fn:
                record = transform_fn(record)

            tc_id = str(record.get(self.config.id_column, f"prod_{i}"))
            input_val = record.get(self.config.input_column, "")
            output_val = record.get(self.config.output_column, "")
            expected_val = (
                record.get(self.config.expected_column, "")
                if self.config.expected_column
                else ""
            )

            metadata = {
                k: v
                for k, v in record.items()
                if k
                not in (
                    self.config.id_column,
                    self.config.input_column,
                    self.config.output_column,
                    self.config.expected_column,
                )
            }
            metadata["actual_output"] = output_val
            metadata["source"] = "production"
            metadata["source_type"] = self.config.source_type
            metadata["fetched_at"] = datetime.now(timezone.utc).isoformat()

            test_cases.append(
                TestCase(
                    id=tc_id,
                    input=str(input_val),
                    expected_output=(
                        str(expected_val) if expected_val else str(output_val)
                    ),
                    metadata=metadata,
                )
            )

        return test_cases

    async def sample(
        self,
        lookback_hours: int = None,
        max_rows: int = None,
        transform_fn: Callable = None,
    ) -> List[TestCase]:
        """Fetch raw logs and convert to TestCase objects in one call."""
        raw = await self.fetch_raw_logs(
            lookback_hours=lookback_hours, max_rows=max_rows
        )
        return self.to_test_cases(raw, transform_fn=transform_fn)


# ─── Scuba Log Source ─────────────────────────────────────────────────────────


class ScubaLogSource(LogSource):
    """
    Pull production logs from a Scuba table.

    Scuba is Meta's real-time analytics store — ideal for:
      - Inference request/response logs
      - Transaction processing logs
      - User interaction events

    Example config:
        config = LogSourceConfig(
            source_type="scuba",
            table_or_endpoint="mft_payment_inference_logs",
            input_column="request_text",
            output_column="model_response",
            expected_column="",  # Often not available in prod logs
            timestamp_column="event_time",
            sample_rate=10,
            lookback_hours=24,
        )
        source = ScubaLogSource(config)
        test_cases = await source.sample(max_rows=100)

    In local dev, reads from ~/.mft_evals/mock_logs/<table_name>.jsonl
    """

    def __init__(self, config: LogSourceConfig):
        super().__init__(config)
        self._scuba_client = None
        self._mock_path = (
            Path.home()
            / ".mft_evals"
            / "mock_logs"
            / f"{config.table_or_endpoint}.jsonl"
        )
        self._init_client()

    def _init_client(self):
        try:
            from libfb.py.scubadata import ScubaData

            self._scuba_client = ScubaData(self.config.table_or_endpoint)
            logger.info(f"Scuba client connected to: {self.config.table_or_endpoint}")
        except ImportError:
            self._scuba_client = None
            logger.info(f"Scuba unavailable, using mock data: {self._mock_path}")

    async def fetch_raw_logs(
        self,
        lookback_hours: int = None,
        max_rows: int = None,
        filters: Dict[str, Any] = None,
    ) -> List[Dict[str, Any]]:
        lookback = lookback_hours or self.config.lookback_hours
        limit = max_rows or self.config.max_rows

        if self._scuba_client:
            return await asyncio.to_thread(
                self._fetch_from_scuba_sync, lookback, limit, filters
            )
        else:
            return self._fetch_from_mock(limit)

    def _fetch_from_scuba_sync(
        self, lookback_hours: int, limit: int, filters: Dict = None
    ) -> List[Dict[str, Any]]:
        """Query Scuba for recent logs (blocking — called via asyncio.to_thread)."""
        from libfb.py.scubadata import Query

        query = Query(self.config.table_or_endpoint)
        query.set_time_range(lookback_hours * 3600)
        query.set_limit(limit)

        if self.config.sample_rate and self.config.sample_rate < 100:
            query.set_sample_rate(self.config.sample_rate)

        merged_filters = {**self.config.filters, **(filters or {})}
        for col, val in merged_filters.items():
            if isinstance(val, list):
                query.add_constraint(col, "IN", val)
            else:
                query.add_constraint(col, "=", val)

        results = query.execute()
        return [dict(row) for row in results]

    def _fetch_from_mock(self, limit: int) -> List[Dict[str, Any]]:
        """Read from local mock JSONL file."""
        records = []
        if not self._mock_path.exists():
            logger.warning(f"No mock data at {self._mock_path}")
            return records

        with open(self._mock_path, "r") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
                    if len(records) >= limit:
                        break

        logger.info(f"Loaded {len(records)} mock records from {self._mock_path}")
        return records

    async def test_connection(self) -> Dict[str, Any]:
        if self._scuba_client:
            try:
                rows = await asyncio.to_thread(self._fetch_from_scuba_sync, 1, 1)
                return {
                    "connected": True,
                    "message": f"Connected to Scuba table: {self.config.table_or_endpoint}",
                    "sample_row": rows[0] if rows else None,
                }
            except Exception as e:
                return {
                    "connected": False,
                    "message": f"Scuba connection failed: {e}",
                    "sample_row": None,
                }
        else:
            exists = self._mock_path.exists()
            sample_row = None
            if exists:
                rows = self._fetch_from_mock(1)
                sample_row = rows[0] if rows else None
            return {
                "connected": exists,
                "message": (
                    f"Mock data found at {self._mock_path}"
                    if exists
                    else f"No mock data at {self._mock_path}. Create a .jsonl file to test."
                ),
                "sample_row": sample_row,
            }

    def _get_schema_sync(self) -> List[Dict[str, str]]:
        """Fetch schema from Scuba (blocking — called via asyncio.to_thread)."""
        from libfb.py.scubadata import get_table_schema

        schema = get_table_schema(self.config.table_or_endpoint)
        return [
            {
                "name": col["name"],
                "type": col["type"],
                "description": col.get("description", ""),
            }
            for col in schema
        ]

    async def get_schema(self) -> List[Dict[str, str]]:
        if self._scuba_client:
            try:
                return await asyncio.to_thread(self._get_schema_sync)
            except Exception as e:
                logger.warning(f"Schema fetch failed: {e}")
                return []
        else:
            rows = self._fetch_from_mock(1)
            if rows:
                return [
                    {"name": k, "type": type(v).__name__, "description": ""}
                    for k, v in rows[0].items()
                ]
            return []


# ─── Hive Log Source ──────────────────────────────────────────────────────────


class HiveLogSource(LogSource):
    """
    Pull production logs from a Hive/Presto table via Daiquery or direct Presto.

    Hive is ideal for:
      - Large batch datasets (daily transaction summaries)
      - Historical data with partitioned storage
      - Joining across multiple data sources

    Example config:
        config = LogSourceConfig(
            source_type="hive",
            table_or_endpoint="mft_data.payment_transactions",
            input_column="request_body",
            output_column="response_body",
            timestamp_column="ds",
            lookback_hours=168,  # 7 days
            max_rows=5000,
            filters={"status": "completed"},
        )
        source = HiveLogSource(config)
        test_cases = await source.sample()

    In local dev, reads from ~/.mft_evals/mock_logs/<table_name>.csv or .jsonl
    """

    def __init__(self, config: LogSourceConfig):
        super().__init__(config)
        self._presto_client = None
        table_safe = config.table_or_endpoint.replace(".", "_").replace("/", "_")
        self._mock_path = (
            Path.home() / ".mft_evals" / "mock_logs" / f"{table_safe}.jsonl"
        )
        self._init_client()

    def _init_client(self):
        try:
            from pyhive import presto

            self._presto_client = presto.connect(
                host=os.environ.get("PRESTO_HOST", "presto.intern.facebook.com"),
                port=int(os.environ.get("PRESTO_PORT", "8080")),
                username=os.environ.get("USER", "unknown"),
            )
            logger.info(
                f"Presto client connected for table: {self.config.table_or_endpoint}"
            )
        except ImportError:
            self._presto_client = None
            logger.info(f"Presto unavailable, using mock data: {self._mock_path}")

    async def fetch_raw_logs(
        self,
        lookback_hours: int = None,
        max_rows: int = None,
        filters: Dict[str, Any] = None,
    ) -> List[Dict[str, Any]]:
        lookback = lookback_hours or self.config.lookback_hours
        limit = max_rows or self.config.max_rows

        if self._presto_client:
            return await asyncio.to_thread(
                self._fetch_from_presto_sync, lookback, limit, filters
            )
        else:
            return self._fetch_from_mock(limit)

    @staticmethod
    def _validate_sql_identifier(name: str) -> str:
        """Validate and sanitize a SQL identifier (table/column name) to prevent injection."""
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_.]*$", name):
            raise ValueError(f"Invalid SQL identifier: {name!r}")
        return name

    @staticmethod
    def _escape_sql_value(val: str) -> str:
        """Escape a string value for safe SQL interpolation."""
        return str(val).replace("'", "''")

    def _fetch_from_presto_sync(
        self, lookback_hours: int, limit: int, filters: Dict = None
    ) -> List[Dict[str, Any]]:
        """Execute Presto query for recent logs (blocking — called via asyncio.to_thread)."""
        ts_col = self._validate_sql_identifier(self.config.timestamp_column)
        table = self._validate_sql_identifier(self.config.table_or_endpoint)

        if ts_col == "ds":
            lookback_date = (
                datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
            ).strftime("%Y-%m-%d")
            where_clause = f"WHERE ds >= '{lookback_date}'"
        else:
            lookback_ts = int(time.time()) - (lookback_hours * 3600)
            where_clause = f"WHERE {ts_col} >= {lookback_ts}"

        merged_filters = {**self.config.filters, **(filters or {})}
        for col, val in merged_filters.items():
            safe_col = self._validate_sql_identifier(col)
            if isinstance(val, list):
                vals_str = ", ".join(f"'{self._escape_sql_value(v)}'" for v in val)
                where_clause += f" AND {safe_col} IN ({vals_str})"
            else:
                where_clause += f" AND {safe_col} = '{self._escape_sql_value(val)}'"

        query = f"SELECT * FROM {table} {where_clause} LIMIT {int(limit)}"
        logger.info(f"Presto query: {query}")

        cursor = self._presto_client.cursor()
        cursor.execute(query)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]

    def _fetch_from_mock(self, limit: int) -> List[Dict[str, Any]]:
        """Read from local mock file (JSONL or CSV)."""
        records = []

        if self._mock_path.exists():
            with open(self._mock_path, "r") as f:
                for line in f:
                    if line.strip():
                        records.append(json.loads(line))
                        if len(records) >= limit:
                            break
        else:
            csv_path = self._mock_path.with_suffix(".csv")
            if csv_path.exists():
                import csv

                with open(csv_path, "r") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        records.append(dict(row))
                        if len(records) >= limit:
                            break
            else:
                logger.warning(f"No mock data at {self._mock_path} or {csv_path}")

        logger.info(f"Loaded {len(records)} mock records from {self._mock_path}")
        return records

    async def test_connection(self) -> Dict[str, Any]:
        if self._presto_client:
            try:
                rows = await asyncio.to_thread(self._fetch_from_presto_sync, 1, 1)
                return {
                    "connected": True,
                    "message": f"Connected to Hive table: {self.config.table_or_endpoint}",
                    "sample_row": rows[0] if rows else None,
                }
            except Exception as e:
                return {
                    "connected": False,
                    "message": f"Presto connection failed: {e}",
                    "sample_row": None,
                }
        else:
            exists = (
                self._mock_path.exists() or self._mock_path.with_suffix(".csv").exists()
            )
            sample_row = None
            if exists:
                rows = self._fetch_from_mock(1)
                sample_row = rows[0] if rows else None
            return {
                "connected": exists,
                "message": (
                    f"Mock data available for {self.config.table_or_endpoint}"
                    if exists
                    else f"No mock data. Create {self._mock_path} or .csv to test."
                ),
                "sample_row": sample_row,
            }

    def _get_schema_sync(self) -> List[Dict[str, str]]:
        """Fetch schema from Presto (blocking — called via asyncio.to_thread)."""
        table = self._validate_sql_identifier(self.config.table_or_endpoint)
        cursor = self._presto_client.cursor()
        cursor.execute(f"DESCRIBE {table}")
        return [
            {
                "name": row[0],
                "type": row[1],
                "description": row[2] if len(row) > 2 else "",
            }
            for row in cursor.fetchall()
        ]

    async def get_schema(self) -> List[Dict[str, str]]:
        if self._presto_client:
            try:
                return await asyncio.to_thread(self._get_schema_sync)
            except Exception as e:
                logger.warning(f"Schema fetch failed: {e}")
                return []
        else:
            rows = self._fetch_from_mock(1)
            if rows:
                return [
                    {"name": k, "type": type(v).__name__, "description": ""}
                    for k, v in rows[0].items()
                ]
            return []


# ─── Custom API Log Source ────────────────────────────────────────────────────


class CustomApiLogSource(LogSource):
    """
    Pull production logs from a custom REST or GraphQL API endpoint.

    For teams that expose their own logging APIs or have custom
    data pipelines that don't go through Scuba/Hive.

    Example config:
        config = LogSourceConfig(
            source_type="custom_api",
            table_or_endpoint="https://my-service.intern.facebook.com/api/logs",
            input_column="user_query",
            output_column="bot_response",
            auth_type="api_key",
            credentials={"api_key": "sk-..."},
            max_rows=500,
            filters={"status": "success", "product": "payments"},
        )
        source = CustomApiLogSource(config)
        test_cases = await source.sample()

    Supports:
      - REST GET/POST with JSON response
      - Bearer token or API key auth
      - Response JSONPath for nested data extraction
      - Pagination via cursor/offset params
    """

    def __init__(
        self,
        config: LogSourceConfig,
        response_data_path: str = "data",
        pagination_cursor_path: str = "",
        method: str = "GET",
    ):
        super().__init__(config)
        self.response_data_path = response_data_path
        self.pagination_cursor_path = pagination_cursor_path
        self.method = method.upper()
        self._mock_path = Path.home() / ".mft_evals" / "mock_logs" / "custom_api.jsonl"

    async def fetch_raw_logs(
        self,
        lookback_hours: int = None,
        max_rows: int = None,
        filters: Dict[str, Any] = None,
    ) -> List[Dict[str, Any]]:
        limit = max_rows or self.config.max_rows
        endpoint = self.config.table_or_endpoint

        if not endpoint or endpoint.startswith("mock://"):
            return self._fetch_from_mock(limit)

        try:
            import httpx
        except ImportError:
            logger.warning("httpx not available, falling back to mock data")
            return self._fetch_from_mock(limit)

        return await self._fetch_from_api(endpoint, limit, filters)

    async def _fetch_from_api(
        self, endpoint: str, limit: int, filters: Dict = None
    ) -> List[Dict[str, Any]]:
        """Fetch from the custom API endpoint."""
        import httpx

        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        if self.config.auth_type == "api_key":
            api_key = self.config.credentials.get("api_key", "")
            headers["Authorization"] = f"Bearer {api_key}"
        elif self.config.auth_type == "header":
            header_name = self.config.credentials.get("header_name", "X-API-Key")
            header_value = self.config.credentials.get("header_value", "")
            headers[header_name] = header_value

        params = {**self.config.filters, **(filters or {})}
        params["limit"] = limit

        all_records = []
        cursor = None

        async with httpx.AsyncClient(timeout=30) as client:
            while len(all_records) < limit:
                if cursor:
                    params["cursor"] = cursor

                if self.method == "POST":
                    response = await client.post(endpoint, json=params, headers=headers)
                else:
                    response = await client.get(
                        endpoint, params=params, headers=headers
                    )

                response.raise_for_status()
                data = response.json()

                records = self._extract_data(data)
                all_records.extend(records)

                if self.pagination_cursor_path and records:
                    cursor = self._extract_field(data, self.pagination_cursor_path)
                    if not cursor:
                        break
                else:
                    break

        return all_records[:limit]

    def _extract_data(self, data: Any) -> List[Dict]:
        """Extract the data array from the API response using response_data_path."""
        if not self.response_data_path:
            if isinstance(data, list):
                return data
            return [data]

        current = data
        for part in self.response_data_path.split("."):
            if isinstance(current, dict):
                current = current.get(part, [])
            else:
                return []

        if isinstance(current, list):
            return current
        return [current]

    def _extract_field(self, data: Any, path: str) -> Any:
        """Extract a single field from nested data using dot notation."""
        current = data
        for part in path.split("."):
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current

    def _fetch_from_mock(self, limit: int) -> List[Dict[str, Any]]:
        """Read from local mock JSONL file."""
        records = []
        if not self._mock_path.exists():
            logger.warning(f"No mock data at {self._mock_path}")
            return records

        with open(self._mock_path, "r") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
                    if len(records) >= limit:
                        break

        logger.info(f"Loaded {len(records)} mock API records from {self._mock_path}")
        return records

    async def test_connection(self) -> Dict[str, Any]:
        endpoint = self.config.table_or_endpoint
        if not endpoint or endpoint.startswith("mock://"):
            exists = self._mock_path.exists()
            return {
                "connected": exists,
                "message": f"Mock mode {'active' if exists else 'no data available'}",
                "sample_row": self._fetch_from_mock(1)[0] if exists else None,
            }

        try:
            import httpx

            async with httpx.AsyncClient(timeout=10) as client:
                headers = {"Accept": "application/json"}
                if self.config.auth_type == "api_key":
                    headers["Authorization"] = (
                        f"Bearer {self.config.credentials.get('api_key', '')}"
                    )
                response = await client.get(
                    endpoint, headers=headers, params={"limit": 1}
                )
                response.raise_for_status()
                data = response.json()
                records = self._extract_data(data)
                return {
                    "connected": True,
                    "message": f"Connected to API: {endpoint}",
                    "sample_row": records[0] if records else None,
                }
        except Exception as e:
            return {
                "connected": False,
                "message": f"API connection failed: {e}",
                "sample_row": None,
            }

    async def get_schema(self) -> List[Dict[str, str]]:
        try:
            rows = await self.fetch_raw_logs(max_rows=1)
            if rows:
                return [
                    {"name": k, "type": type(v).__name__, "description": ""}
                    for k, v in rows[0].items()
                ]
        except Exception:
            pass
        return []


# ─── Factory ──────────────────────────────────────────────────────────────────


def create_log_source(config: LogSourceConfig) -> LogSource:
    """
    Factory function to create the appropriate LogSource from config.

    Usage:
        config = LogSourceConfig(source_type="scuba", table_or_endpoint="my_table", ...)
        source = create_log_source(config)
        test_cases = await source.sample(max_rows=100)
    """
    source_map = {
        "scuba": ScubaLogSource,
        "hive": HiveLogSource,
        "presto": HiveLogSource,
        "custom_api": CustomApiLogSource,
        "api": CustomApiLogSource,
    }

    source_class = source_map.get(config.source_type.lower())
    if not source_class:
        raise ValueError(
            f"Unknown log source type: {config.source_type}. "
            f"Supported: {list(source_map.keys())}"
        )

    return source_class(config)


def config_from_eval_data(eval_data: Dict[str, Any]) -> Optional[LogSourceConfig]:
    """
    Build a LogSourceConfig from a stored eval record.

    Maps the prod_log_* fields in the evals table to a LogSourceConfig.
    Returns None if production logging is not enabled.
    """
    if not eval_data.get("prodLogEnabled") and not eval_data.get("prod_log_enabled"):
        return None

    config_json = eval_data.get("config", {})
    if isinstance(config_json, str):
        try:
            config_json = json.loads(config_json)
        except (json.JSONDecodeError, TypeError):
            config_json = {}

    return LogSourceConfig(
        source_type=eval_data.get(
            "prod_log_source", eval_data.get("prodLogSource", "")
        ),
        table_or_endpoint=eval_data.get(
            "prod_log_table", eval_data.get("prodLogTable", "")
        ),
        input_column=eval_data.get(
            "prod_log_input_column", eval_data.get("prodLogInputColumn", "input")
        ),
        output_column=eval_data.get(
            "prod_log_output_column", eval_data.get("prodLogOutputColumn", "output")
        ),
        expected_column=config_json.get("prodLogExpectedColumn", ""),
        timestamp_column=eval_data.get(
            "prod_log_timestamp_column",
            eval_data.get("prodLogTimestampColumn", "timestamp"),
        ),
        id_column=config_json.get("prodLogIdColumn", "id"),
        sample_rate=eval_data.get(
            "prod_log_sample_rate", eval_data.get("prodLogSampleRate", 10)
        ),
        lookback_hours=int(config_json.get("prodLogLookbackHours", 24)),
        max_rows=int(config_json.get("prodLogMaxRows", 1000)),
        filters=config_json.get("prodLogFilters", {}),
    )
