from __future__ import annotations

import json
import logging
import subprocess
import time
from dataclasses import dataclass


LOGGER = logging.getLogger(__name__)
POLL_INTERVAL_SECONDS = 2
LOG_EVERY_SECONDS = 20


@dataclass(frozen=True)
class QueryExecutionResult:
    name: str
    status: str
    row_count: int
    rows: list[dict[str, object]]
    duration_seconds: float
    error: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "status": self.status,
            "row_count": self.row_count,
            "rows": self.rows,
            "duration_seconds": round(self.duration_seconds, 3),
            "error": self.error,
        }


def run_bq_query(sql: str, *, name: str = "query", logger: logging.Logger | None = None) -> QueryExecutionResult:
    run_logger = logger or LOGGER
    query = (sql or "").strip()
    if not query:
        return QueryExecutionResult(name=name, status="invalid_input", row_count=0, rows=[], duration_seconds=0.0, error="Empty SQL query.")

    run_logger.info("Starting bq query execution. name=%s", name)
    start_time = time.time()
    last_log = start_time

    process = subprocess.Popen(
        ["bq", "query", "--nouse_legacy_sql", "--format=json", query],
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
        )

    rows = _safe_rows(stdout)
    run_logger.info("bq query completed. name=%s row_count=%d duration=%.2fs", name, len(rows), duration)
    return QueryExecutionResult(
        name=name,
        status="success",
        row_count=len(rows),
        rows=rows,
        duration_seconds=duration,
    )


def run_bq_queries(queries: list[tuple[str, str]], *, logger: logging.Logger | None = None) -> list[QueryExecutionResult]:
    results: list[QueryExecutionResult] = []
    for name, sql in queries:
        results.append(run_bq_query(sql, name=name, logger=logger))
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
