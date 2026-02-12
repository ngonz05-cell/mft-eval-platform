"""
MFT Eval Platform - Production Log Ingestion Worker

Background worker that periodically samples production logs and
converts them into eval test cases. Enables continuous evaluation
against real production traffic.

The worker:
  1. Checks all evals with prod_log_enabled=True
  2. For each, fetches recent logs via the configured LogSource
  3. Converts logs to TestCase format
  4. Optionally triggers an eval run with the fresh data
  5. Stores results and emits Scuba events

Run modes:
  - One-shot: python -m mft_evals.integrations.log_worker --once
  - Daemon:   python -m mft_evals.integrations.log_worker --interval 3600
  - API-triggered: Called from POST /api/evals/{id}/ingest endpoint

In local dev, this reads from mock JSONL files under ~/.mft_evals/mock_logs/
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from mft_evals import storage
from mft_evals.integrations.log_sources import config_from_eval_data, create_log_source
from mft_evals.integrations.scuba import ScubaLogger

logger = logging.getLogger(__name__)


class IngestionResult:
    """Result of a single ingestion cycle for one eval."""

    def __init__(self, eval_id: str, eval_name: str):
        self.eval_id = eval_id
        self.eval_name = eval_name
        self.status = "pending"
        self.records_fetched = 0
        self.test_cases_created = 0
        self.eval_run_triggered = False
        self.eval_run_id = ""
        self.error = ""
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.completed_at = ""
        self.duration_ms = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "eval_id": self.eval_id,
            "eval_name": self.eval_name,
            "status": self.status,
            "records_fetched": self.records_fetched,
            "test_cases_created": self.test_cases_created,
            "eval_run_triggered": self.eval_run_triggered,
            "eval_run_id": self.eval_run_id,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
        }


class LogIngestionWorker:
    """
    Background worker for continuous production log ingestion.

    Usage:
        worker = LogIngestionWorker(auto_run=True)

        # One-shot ingestion for all enabled evals
        results = await worker.ingest_all()

        # Ingest for a specific eval
        result = await worker.ingest_eval("eval-id-123")

        # Run as daemon
        await worker.run_daemon(interval_seconds=3600)
    """

    def __init__(
        self,
        auto_run: bool = False,
        max_rows_per_eval: int = 500,
        scuba_logger: ScubaLogger = None,
    ):
        self.auto_run = auto_run
        self.max_rows_per_eval = max_rows_per_eval
        self.scuba_logger = scuba_logger or ScubaLogger()
        self._running = False

    async def ingest_eval(
        self,
        eval_id: str,
        trigger_run: bool = None,
        max_rows: int = None,
    ) -> IngestionResult:
        """
        Ingest production logs for a single eval.

        Steps:
          1. Load eval config from storage
          2. Build LogSource from config
          3. Fetch recent production logs
          4. Convert to TestCase format
          5. Update eval's sample_data with fresh production data
          6. Optionally trigger an eval run

        Args:
            eval_id: The eval to ingest for
            trigger_run: Whether to trigger an eval run after ingestion.
                        Defaults to self.auto_run
            max_rows: Override max rows to fetch

        Returns:
            IngestionResult with details of the ingestion
        """
        eval_data = storage.get_eval(eval_id)
        if not eval_data:
            result = IngestionResult(eval_id, "unknown")
            result.status = "error"
            result.error = f"Eval not found: {eval_id}"
            return result

        result = IngestionResult(eval_id, eval_data.get("name", ""))
        start = time.time()

        try:
            log_config = config_from_eval_data(eval_data)
            if not log_config:
                result.status = "skipped"
                result.error = "Production logging not enabled for this eval"
                return result

            source = create_log_source(log_config)

            conn_test = await source.test_connection()
            if not conn_test["connected"]:
                result.status = "error"
                result.error = f"Connection failed: {conn_test['message']}"
                return result

            limit = max_rows or self.max_rows_per_eval
            test_cases = await source.sample(max_rows=limit)
            result.records_fetched = len(test_cases)

            if not test_cases:
                result.status = "completed"
                result.test_cases_created = 0
                logger.info(f"No new records for eval {eval_id}")
                return result

            prod_data = [
                {
                    "id": tc.id,
                    "input": tc.input,
                    "expected_output": tc.expected_output,
                    "actual_output": tc.metadata.get("actual_output", ""),
                    "source": "production",
                    "fetched_at": tc.metadata.get("fetched_at", ""),
                    **{
                        k: v
                        for k, v in tc.metadata.items()
                        if k not in ("actual_output", "source", "fetched_at")
                    },
                }
                for tc in test_cases
            ]

            existing_data = eval_data.get("sample_data", [])
            if isinstance(existing_data, str):
                try:
                    existing_data = json.loads(existing_data)
                except (json.JSONDecodeError, TypeError):
                    existing_data = []

            manual_data = [d for d in existing_data if d.get("source") != "production"]
            combined = manual_data + prod_data

            storage.update_eval(
                eval_id,
                {
                    "sample_data_json": json.dumps(combined),
                    "dataset_size": len(combined),
                },
            )

            result.test_cases_created = len(prod_data)
            result.status = "completed"

            should_run = trigger_run if trigger_run is not None else self.auto_run
            if should_run:
                try:
                    from mft_evals.eval_service import execute_eval_run

                    run_result = await execute_eval_run(
                        eval_id, trigger="log_ingestion"
                    )
                    result.eval_run_triggered = True
                    result.eval_run_id = run_result.get("id", "")
                    logger.info(
                        f"Auto-run completed for eval {eval_id}: "
                        f"score={run_result.get('primary_score', 0):.4f}"
                    )
                except Exception as run_err:
                    logger.error(f"Auto-run failed for eval {eval_id}: {run_err}")
                    result.eval_run_triggered = True
                    result.error = f"Ingestion succeeded but auto-run failed: {run_err}"

        except Exception as e:
            result.status = "error"
            result.error = str(e)
            logger.error(f"Ingestion failed for eval {eval_id}: {e}", exc_info=True)

        finally:
            result.duration_ms = int((time.time() - start) * 1000)
            result.completed_at = datetime.now(timezone.utc).isoformat()

        return result

    async def ingest_all(
        self,
        trigger_runs: bool = None,
    ) -> List[IngestionResult]:
        """
        Ingest production logs for all evals with prod_log_enabled=True.

        Returns:
            List of IngestionResult for each eval processed
        """
        all_evals = storage.list_evals(limit=500)
        enabled_evals = [
            e for e in all_evals if e.get("prodLogEnabled") or e.get("prod_log_enabled")
        ]

        if not enabled_evals:
            logger.info("No evals with production logging enabled")
            return []

        logger.info(f"Starting ingestion for {len(enabled_evals)} evals")
        results = []

        for eval_data in enabled_evals:
            result = await self.ingest_eval(
                eval_data["id"],
                trigger_run=trigger_runs,
            )
            results.append(result)
            logger.info(
                f"  [{result.status}] {result.eval_name}: "
                f"fetched={result.records_fetched}, created={result.test_cases_created}"
            )

        succeeded = sum(1 for r in results if r.status == "completed")
        failed = sum(1 for r in results if r.status == "error")
        logger.info(
            f"Ingestion complete: {succeeded} succeeded, {failed} failed, "
            f"{len(results) - succeeded - failed} skipped"
        )

        return results

    async def run_daemon(self, interval_seconds: int = 3600):
        """
        Run as a background daemon that ingests on a schedule.

        Args:
            interval_seconds: How often to run ingestion (default: hourly)
        """
        self._running = True
        logger.info(f"Log ingestion daemon started (interval: {interval_seconds}s)")

        while self._running:
            try:
                results = await self.ingest_all(trigger_runs=self.auto_run)
                summary = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "evals_processed": len(results),
                    "succeeded": sum(1 for r in results if r.status == "completed"),
                    "failed": sum(1 for r in results if r.status == "error"),
                    "total_records": sum(r.records_fetched for r in results),
                }
                logger.info(f"Daemon cycle complete: {json.dumps(summary)}")
            except Exception as e:
                logger.error(f"Daemon cycle failed: {e}", exc_info=True)

            await asyncio.sleep(interval_seconds)

    def stop(self):
        """Stop the daemon loop."""
        self._running = False
        logger.info("Log ingestion daemon stopping")


# ─── CLI Entry Point ──────────────────────────────────────────────────────────


async def _main():
    import argparse

    parser = argparse.ArgumentParser(
        description="MFT Eval - Production Log Ingestion Worker"
    )
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--eval-id", type=str, help="Ingest for a specific eval ID")
    parser.add_argument(
        "--interval", type=int, default=3600, help="Daemon interval in seconds"
    )
    parser.add_argument(
        "--auto-run", action="store_true", help="Auto-trigger eval runs after ingestion"
    )
    parser.add_argument(
        "--max-rows", type=int, default=500, help="Max rows to fetch per eval"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    storage.init_db()
    worker = LogIngestionWorker(auto_run=args.auto_run, max_rows_per_eval=args.max_rows)

    if args.eval_id:
        result = await worker.ingest_eval(args.eval_id, trigger_run=args.auto_run)
        print(json.dumps(result.to_dict(), indent=2))
    elif args.once:
        results = await worker.ingest_all(trigger_runs=args.auto_run)
        for r in results:
            status_icon = {"completed": "✅", "error": "❌", "skipped": "⏭️"}.get(
                r.status, "❓"
            )
            print(
                f"  {status_icon} {r.eval_name}: {r.records_fetched} records, {r.test_cases_created} test cases"
            )
    else:
        await worker.run_daemon(interval_seconds=args.interval)


if __name__ == "__main__":
    asyncio.run(_main())
