from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass

try:
    from google.api_core.exceptions import GoogleAPICallError
    from google.cloud.bigquery import Client, QueryJobConfig
except Exception:  # noqa: BLE001
    Client = None  # type: ignore[assignment]
    QueryJobConfig = None  # type: ignore[assignment]
    GoogleAPICallError = Exception  # type: ignore[assignment]


LOGGER = logging.getLogger(__name__)
POLL_INTERVAL_SECONDS = 2
LOG_EVERY_SECONDS = 20
USE_BQ_CLIENT_FOR_DEST_TABLES = os.getenv("SALLY_USE_BQ_CLIENT_FOR_DEST_TABLES", "1").strip() != "0"


@dataclass(frozen=True)
class QueryExecutionResult:
    name: str
    status: str
    row_count: int
    rows: list[dict[str, object]]
    duration_seconds: float
    error: str = ""
    destination_table: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "status": self.status,
            "row_count": self.row_count,
            "rows": self.rows,
            "duration_seconds": round(self.duration_seconds, 3),
            "error": self.error,
            "destination_table": self.destination_table,
        }


def run_bq_query(
    sql: str,
    *,
    name: str = "query",
    logger: logging.Logger | None = None,
    destination_table: str = "",
) -> QueryExecutionResult:
    run_logger = logger or LOGGER
    query = (sql or "").strip()
    if not query:
        return QueryExecutionResult(
            name=name,
            status="invalid_input",
            row_count=0,
            rows=[],
            duration_seconds=0.0,
            error="Empty SQL query.",
            destination_table=destination_table,
        )

    if destination_table and USE_BQ_CLIENT_FOR_DEST_TABLES and Client is not None and QueryJobConfig is not None:
        return _run_bq_query_with_client(query, name=name, logger=run_logger, destination_table=destination_table)

    run_logger.info("Starting bq query execution. name=%s", name)
    start_time = time.time()
    last_log = start_time

    args = ["bq", "query", "--nouse_legacy_sql", "--format=json"]
    if destination_table:
        args.extend([f"--destination_table={destination_table}", "--replace=true"])
    args.append(query)

    process = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    while process.poll() is None:
        now = time.time()
        if now - last_log >= LOG_EVERY_SECONDS:
            run_logger.info("Query still running. name=%s elapsed=%.1fs", name, now - start_time)
            last_log = now
        time.sleep(POLL_INTERVAL_SECONDS)

    stdout, stderr = process.communicate()
    duration = time.time() - start_time

    if process.returncode != 0:
        message = (stderr or stdout or "Unknown bq query error").strip()
        run_logger.error("bq query failed. name=%s error=%s", name, message)
        return QueryExecutionResult(
            name=name,
            status="error",
            row_count=0,
            rows=[],
            duration_seconds=duration,
            error=message,
            destination_table=destination_table,
        )

    rows = _safe_rows(stdout)
    run_logger.info("bq query completed. name=%s row_count=%d duration=%.2fs", name, len(rows), duration)
    return QueryExecutionResult(
        name=name,
        status="success",
        row_count=len(rows),
        rows=rows,
        duration_seconds=duration,
        destination_table=destination_table,
    )


def _run_bq_query_with_client(
    sql: str,
    *,
    name: str,
    logger: logging.Logger,
    destination_table: str,
) -> QueryExecutionResult:
    logger.info("Starting BigQuery client query execution. name=%s destination=%s", name, destination_table)
    start_time = time.time()
    last_log = start_time

    try:
        client = Client()
        job_config = QueryJobConfig(
            destination=destination_table,
            write_disposition="WRITE_TRUNCATE",
        )
        query_job = client.query(sql, job_config=job_config)

        while not query_job.done():
            now = time.time()
            if now - last_log >= LOG_EVERY_SECONDS:
                logger.info("Query still running. name=%s elapsed=%.1fs", name, now - start_time)
                last_log = now
            time.sleep(POLL_INTERVAL_SECONDS)

        query_job.result()
        duration = time.time() - start_time

        table = client.get_table(destination_table)
        row_count = int(getattr(table, "num_rows", 0) or 0)
        preview_sql = f"SELECT * FROM `{destination_table}` LIMIT 50"
        preview_rows = [dict(row.items()) for row in client.query(preview_sql).result()]

        logger.info(
            "BigQuery client query completed. name=%s destination=%s row_count=%d duration=%.2fs",
            name,
            destination_table,
            row_count,
            duration,
        )
        return QueryExecutionResult(
            name=name,
            status="success",
            row_count=row_count,
            rows=preview_rows,
            duration_seconds=duration,
            destination_table=destination_table,
        )
    except GoogleAPICallError as exc:
        duration = time.time() - start_time
        message = str(exc).strip() or "BigQuery API call failed."
        logger.error("BigQuery client query failed. name=%s error=%s", name, message)
        return QueryExecutionResult(
            name=name,
            status="error",
            row_count=0,
            rows=[],
            duration_seconds=duration,
            error=message,
            destination_table=destination_table,
        )
    except Exception as exc:  # noqa: BLE001
        duration = time.time() - start_time
        message = str(exc).strip() or "Unexpected BigQuery execution error."
        logger.error("Unexpected BigQuery client failure. name=%s error=%s", name, message)
        return QueryExecutionResult(
            name=name,
            status="error",
            row_count=0,
            rows=[],
            duration_seconds=duration,
            error=message,
            destination_table=destination_table,
        )


def run_bq_queries(
    queries: list[tuple[str, str]],
    *,
    logger: logging.Logger | None = None,
    destinations: dict[str, str] | None = None,
) -> list[QueryExecutionResult]:
    results: list[QueryExecutionResult] = []
    destination_map = destinations or {}
    for name, sql in queries:
        results.append(
            run_bq_query(
                sql,
                name=name,
                logger=logger,
                destination_table=destination_map.get(name, ""),
            )
        )
    return results


def _safe_rows(stdout: str) -> list[dict[str, object]]:
    text = (stdout or "").strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return [{"raw_output": text}]

    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        return [payload]
    return [{"raw_output": text}]
