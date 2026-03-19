import logging
import time
from typing import Optional

from google.api_core.exceptions import NotFound, GoogleAPICallError
from google.cloud.bigquery import Client, QueryJobConfig

logger = logging.getLogger(_name_)
client = Client()

# Poll interval for long-running queries
POLL_INTERVAL_SECONDS = 10

# Heartbeat interval: how often to log "still running" while waiting
LOG_EVERY_SECONDS = 120


def _ts() -> str:
    """
    Return a local timestamp string for consistent log messages.

    Returns
    -------
    str
        Current local time formatted as YYYY-MM-DD HH:mm:SS
    """
    return time.strftime("%Y-%m-%d %H:%M:%S")


def format_duration(seconds: float) -> str:
    """
    Convert a duration in seconds into a human-readable string.

    Parameters
    ----------
    seconds : float
        Duration in seconds.

    Returns
    -------
    str
        Human-readable duration like "1 hr, 2 mins, 3 secs".
    """
    seconds = max(0.0, float(seconds))
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    parts = []
    if hours:
        parts.append(f"{hours} hr{'' if hours == 1 else 's'}")
    if minutes or hours:
        parts.append(f"{minutes} min{'' if minutes == 1 else 's'}")
    parts.append(f"{secs} sec{'' if secs == 1 else 's'}")
    return ", ".join(parts)


def non_empty_table_exists(table_id: str) -> bool:
    """
    Return True if BigQuery table exists and has at least 1 row.

    This is used as a guardrail to prevent re-creating (and paying for)
    intermediate tables that already exist and are populated.

    Parameters
    ----------
    table_id : str
        Fully qualified table id in the form "project.dataset.table".

    Returns
    -------
    bool
        True if the table exists and contains >= 1 row, else False.

    Raises
    ------
    GoogleAPICallError
        If BigQuery API call fails for reasons other than NotFound.
    """
    logger.debug("[%s] Checking whether table exists and is non-empty: <%s>", _ts(), table_id)
    try:
        table = client.get_table(table_id)
        logger.debug(
            "[%s] Table <%s> exists. num_rows=%s",
            _ts(),
            table_id,
            getattr(table, "num_rows", None),
        )
        return (table.num_rows or 0) > 0
    except NotFound:
        logger.info("[%s] Table <%s> not found.", _ts(), table_id)
        return False
    except GoogleAPICallError as e:
        logger.exception("[%s] BigQuery API error while checking table <%s>: %s", _ts(), table_id, e)
        raise


def _get_row_count(table_id: str, where_clause: Optional[str] = None) -> int:
    """
    Count rows in a table (optionally with a WHERE clause).

    Parameters
    ----------
    table_id : str
        Fully qualified table id "project.dataset.table".
    where_clause : Optional[str]
        SQL predicate (without the WHERE keyword). Example: "col = 'x'".

    Returns
    -------
    int
        Row count.

    Raises
    ------
    GoogleAPICallError
        If query execution fails.
    """
    query = f"SELECT COUNT(*) AS row_count FROM {table_id}"
    if where_clause:
        query += f" WHERE {where_clause}"

    logger.debug("[%s] Row count query: %s", _ts(), query)
    try:
        return int(list(client.query(query).result())[0]["row_count"])
    except GoogleAPICallError as e:
        logger.exception("[%s] Failed to get row count for <%s>: %s", _ts(), table_id, e)
        raise


def _get_col_count(table_id: str) -> int:
    """
    Count columns in a table using INFORMATION_SCHEMA.

    Parameters
    ----------
    table_id : str
        Fully qualified table id "project.dataset.table".

    Returns
    -------
    int
        Column count.

    Raises
    ------
    GoogleAPICallError
        If query execution fails.
    ValueError
        If table_id is not in "project.dataset.table" form.
    """
    # table_id is expected to be: project.dataset.table
    project, dataset, table = table_id.split(".", 2)

    query = f"""
        SELECT COUNT(*) AS col_count
        FROM {project}.{dataset}.INFORMATION_SCHEMA.COLUMNS
        WHERE table_name = '{table}'
    """
    query = " ".join(query.split())  # compact for logging
    logger.debug("[%s] Column count query: %s", _ts(), query)

    try:
        return int(list(client.query(query).result())[0]["col_count"])
    except GoogleAPICallError as e:
        logger.exception("[%s] Failed to get column count for <%s>: %s", _ts(), table_id, e)
        raise


def create_table(query: str, table_id: str) -> None:
    """
    Create/overwrite a destination table from a query IF the table does not already exist with rows.

    Behavior:
    - If destination table exists AND has >= 1 row -> skip creation.
    - Else -> execute query into destination with WRITE_TRUNCATE.

    Progress:
    - Logs job start with job_id
    - Polls job status every POLL_INTERVAL_SECONDS
    - Logs a heartbeat every LOG_EVERY_SECONDS while still running
    - After completion logs row and column counts + total duration

    Parameters
    ----------
    query : str
        SQL query string that produces the destination table contents.
    table_id : str
        Destination table id in form "project.dataset.table".

    Raises
    ------
    GoogleAPICallError
        If BigQuery API call fails.
    Exception
        For unexpected errors (re-raised after logging).
    """
    if non_empty_table_exists(table_id):
        logger.info("[%s] Table <%s> already exists and is non-empty. Skipping creation.", _ts(), table_id)
        return

    logger.info("[%s] Creating table <%s>.", _ts(), table_id)
    start_time = time.time()

    job_config = QueryJobConfig(
        destination=table_id,
        write_disposition="WRITE_TRUNCATE",
    )

    try:
        query_job = client.query(query, job_config=job_config)
        logger.info("[%s] Started query job %s for destination <%s>.", _ts(), query_job.job_id, table_id)

        # Poll job status with periodic log heartbeat.
        elapsed_since_log = 0
        while not query_job.done():
            time.sleep(POLL_INTERVAL_SECONDS)
            elapsed_since_log += POLL_INTERVAL_SECONDS
            if elapsed_since_log >= LOG_EVERY_SECONDS:
                elapsed_since_log = 0
                logger.info("[%s] Query job %s still running...", _ts(), query_job.job_id)

        # Ensure exceptions are raised if the job failed.
        query_job.result()

        end_time = time.time()
        row_count = _get_row_count(table_id)
        col_count = _get_col_count(table_id)

        logger.info(
            "[%s] Created table <%s> with %s row%s and %s column%s; Time taken: %s.",
            _ts(),
            table_id,
            f"{row_count:,}",
            "" if row_count == 1 else "s",
            f"{col_count:,}",
            "" if col_count == 1 else "s",
            format_duration(end_time - start_time),
        )
    except GoogleAPICallError as e:
        logger.exception("[%s] BigQuery API error while creating table <%s>: %s", _ts(), table_id, e)
        raise
    except Exception as e:
        logger.exception("[%s] Unexpected error while creating table <%s>: %s", _ts(), table_id, e)
        raise


def delete_table(table_id: str) -> None:
    """
    Delete a table if it exists (safe no-op if the table is missing).

    Parameters
    ----------
    table_id : str
        Fully qualified table id "project.dataset.table".

    Raises
    ------
    GoogleAPICallError
        If BigQuery API call fails.
    """
    logger.info("[%s] Deleting table <%s> (if it exists).", _ts(), table_id)
    try:
        client.delete_table(table_id)  # NotFound handled below
        logger.info("[%s] Deleted table <%s>.", _ts(), table_id)
    except NotFound:
        logger.info("[%s] Table <%s> does not exist. Skipping deletion.", _ts(), table_id)
    except GoogleAPICallError as e:
        logger.exception("[%s] BigQuery API error while deleting table <%s>: %s", _ts(), table_id, e)
        raise


def fetch_data(
    table_id: str,
    filter_condition: str,
    max_row_count: int = 100_000,
    sort_column: str = "date_time",
):
    """
    Fetch data from a BigQuery table with a filter condition into a pandas DataFrame.

    If row count exceeds max_row_count:
    - fetch only the latest max_row_count rows by sort_column (DESC),
    - then return them in ascending order (ASC) for convenient analysis.

    Parameters
    ----------
    table_id : str
        Fully qualified table id "project.dataset.table".
    filter_condition : str
        SQL predicate (without WHERE). Example: "cm15 = '123' AND trans_dt >= '2025-01-01'".
    max_row_count : int, default=100_000
        Maximum rows to fetch. If exceeded, only the most recent rows are returned.
    sort_column : str, default="date_time"
        Column used to order rows when limiting.

    Returns
    -------
    pandas.DataFrame
        DataFrame of fetched rows.

    Raises
    ------
    GoogleAPICallError
        If BigQuery query execution fails.
    """
    logger.info("[%s] Fetching data from <%s> for condition <%s>.", _ts(), table_id, filter_condition)

    row_count = _get_row_count(table_id, where_clause=filter_condition)
    logger.info(
        "[%s] Table <%s> with condition <%s> has %s row%s.",
        _ts(),
        table_id,
        filter_condition,
        f"{row_count:,}",
        "" if row_count == 1 else "s",
    )

    if row_count > max_row_count:
        logger.info(
            "[%s] Row count exceeds %s. Fetching only last %s rows ordered by <%s>.",
            _ts(),
            f"{max_row_count:,}",
            f"{max_row_count:,}",
            sort_column,
        )
        fetch_query = f"""
            SELECT *
            FROM (
                SELECT *
                FROM {table_id}
                WHERE {filter_condition}
                ORDER BY {sort_column} DESC
                LIMIT {max_row_count}
            )
            ORDER BY {sort_column} ASC
        """
    else:
        logger.info("[%s] Fetching all rows ordered by <%s>.", _ts(), sort_column)
        fetch_query = f"""
            SELECT *
            FROM {table_id}
            WHERE {filter_condition}
            ORDER BY {sort_column} ASC
        """

    fetch_query = fetch_query.strip()
    logger.debug("[%s] Fetch query: %s", _ts(), " ".join(fetch_query.split()))

    try:
        df = client.query(fetch_query).to_dataframe()
        logger.info("[%s] Fetch complete for <%s>. Returned %s rows.", _ts(), table_id, f"{len(df):,}")
        return df
    except GoogleAPICallError as e:
        logger.exception("[%s] BigQuery API error while fetching from <%s>: %s", _ts(), table_id, e)
        raise