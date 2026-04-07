from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from amex_ai_agent.rca.alert_query_parser import parse_alert_query
from amex_ai_agent.rca.bq_executor import run_bq_queries
from amex_ai_agent.rca.variable_metadata_resolver import VariableMetadataResolver, metadata_to_dict
from amex_ai_agent.tools.base import ToolExecutionContext


LOGGER = logging.getLogger(__name__)


def _parse_argument(argument: str) -> tuple[dict[str, Any], str]:
    text = (argument or "").strip()
    if not text:
        return {}, ""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}, text
    return (payload if isinstance(payload, dict) else {}), text


def _resolve_catalog_path(context: ToolExecutionContext, payload: dict[str, Any]) -> str:
    explicit = str(payload.get("variable_metadata_path", "") or "").strip()
    if explicit:
        return explicit
    return str(context.defaults.get("variable_catalog_path", "") or "").strip()


def _resolve_variable(payload: dict[str, Any], raw_text: str, context: ToolExecutionContext) -> tuple[dict[str, object] | None, str]:
    ref = str(payload.get("variable_id") or payload.get("variable_name") or "").strip()
    parsed = parse_alert_query(str(payload.get("user_query") or raw_text or ref))
    reference = ref or parsed.variable_reference
    if not reference:
        return None, ""

    catalog_path = _resolve_catalog_path(context, payload)
    if not catalog_path:
        return None, reference
    path = Path(catalog_path)
    if not path.exists() or not path.is_file():
        return None, reference

    resolver = VariableMetadataResolver.from_csv(path)
    resolved, candidates = resolver.resolve(reference)
    if resolved is not None:
        return metadata_to_dict(resolved), reference
    if candidates:
        return {"ambiguous_candidates": [metadata_to_dict(item) for item in candidates[:10]]}, reference
    return None, reference


def _build_fallback_sql(*, table_name: str, start_date: str, end_date: str, metric_col: str, alert_type: str) -> str:
    direction_expr = "LAG(avg_metric) OVER (ORDER BY trans_dt)"
    return (
        "WITH daily AS ("
        f" SELECT trans_dt, COUNT(*) AS txn_cnt, AVG({metric_col}) AS avg_metric"
        f" FROM {table_name}"
        f" WHERE trans_dt BETWEEN '{start_date}' AND '{end_date}'"
        " GROUP BY trans_dt"
        ") "
        "SELECT trans_dt, txn_cnt, avg_metric, "
        f"avg_metric - {direction_expr} AS metric_delta "
        "FROM daily ORDER BY trans_dt"
    )


def run(argument: str, *, context: ToolExecutionContext) -> dict[str, Any]:
    context.report_progress("Parsing alert rationalization request...")
    payload, raw_text = _parse_argument(argument)

    parsed = parse_alert_query(str(payload.get("user_query") or raw_text or ""))
    resolved_variable, reference = _resolve_variable(payload, raw_text, context)

    if isinstance(resolved_variable, dict) and "ambiguous_candidates" in resolved_variable:
        return {
            "tool": "alert_rationalization",
            "status": "needs_user_input",
            "message": "Variable reference is ambiguous. Run variable_lookup or provide exact variable_id.",
            "variable_reference": reference,
            "candidate_variables": resolved_variable["ambiguous_candidates"],
            "workflow_hint": "Use variable_lookup first, then rerun alert_rationalization with exact variable_id.",
        }

    variable_id = str(payload.get("variable_id") or (resolved_variable or {}).get("variable_id") or reference).strip()
    sql_metric_name = str(payload.get("variable_name") or (resolved_variable or {}).get("variable_name") or variable_id).strip()
    alert_date = str(payload.get("alert_date") or parsed.alert_date or "")
    start_date = str(payload.get("start_date") or alert_date)
    end_date = str(payload.get("end_date") or alert_date)

    table_name = str(payload.get("alert_table") or (resolved_variable or {}).get("source_table") or "").strip()
    llm_sql = str(payload.get("sql_query") or payload.get("query") or "").strip()

    fallback_sql = ""
    if table_name and sql_metric_name:
        fallback_sql = _build_fallback_sql(
            table_name=table_name,
            start_date=start_date,
            end_date=end_date,
            metric_col=sql_metric_name,
            alert_type=str(payload.get("alert_type") or parsed.alert_type),
        )

    chosen_sql = llm_sql or fallback_sql

    execute_sql = bool(payload.get("execute_sql", False))
    query_results: list[dict[str, object]] = []
    if execute_sql and chosen_sql:
        context.report_progress("Running alert rationalization SQL...")
        query_results = [result.to_dict() for result in run_bq_queries([("alert_rationalization", chosen_sql)], logger=context.logger or LOGGER)]

    if not variable_id:
        return {
            "tool": "alert_rationalization",
            "status": "needs_user_input",
            "message": "Variable is required for alert rationalization.",
            "workflow_hint": "Run variable_lookup first to resolve the variable_id, then rerun alert_rationalization.",
            "parsed_alert_context": {
                "raw_user_query": parsed.raw_user_query,
                "alert_date": parsed.alert_date,
                "alert_type": parsed.alert_type,
                "metric_view": parsed.metric_view,
            },
        }

    return {
        "tool": "alert_rationalization",
        "status": "success",
        "input_context": {
            "raw_user_query": parsed.raw_user_query,
            "variable_id": variable_id,
            "sql_metric_name": sql_metric_name,
            "alert_date": alert_date,
            "alert_type": str(payload.get("alert_type") or parsed.alert_type),
            "metric_view": str(payload.get("metric_view") or parsed.metric_view),
        },
        "resolved_variable_metadata": resolved_variable or {},
        "analysis_window": {"start_date": start_date, "end_date": end_date},
        "sql_execution": {
            "execute_sql": execute_sql,
            "query_results": query_results,
        },
        "sql_query": chosen_sql,
        "sql_source": "llm_query" if llm_sql else "fallback_template",
        "workflow_hint": "For variable-specific alert rationalization, run variable_lookup first if variable_id is uncertain.",
    }
