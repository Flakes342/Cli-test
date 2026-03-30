from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from amex_ai_agent.rca.alert_context_normalizer import normalize_alert_context
from amex_ai_agent.rca.alert_query_parser import ParsedAlertRequest, parse_alert_query
from amex_ai_agent.rca.analysis import build_rca_output
from amex_ai_agent.rca.alert_context import VariableMetadata
from amex_ai_agent.rca.bq_executor import run_bq_queries
from amex_ai_agent.rca.sql_templates import render_driver_sql, render_stage_funnel_sql
from amex_ai_agent.rca.variable_metadata_resolver import VariableMetadataResolver, metadata_to_dict
from amex_ai_agent.tools.base import ToolExecutionContext


LOGGER = logging.getLogger(__name__)

DEFAULT_SAMPLE_RATE = 0.025
DRIVER_DIMENSIONS = ("mcc", "country", "model_id", "lift_path")


def _parse_argument(argument: str) -> tuple[dict[str, Any], str]:
    text = (argument or "").strip()
    if not text:
        return {}, ""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}, text
    return (payload if isinstance(payload, dict) else {}), text


def _resolve_metadata_path(context: ToolExecutionContext, payload: dict[str, Any]) -> str:
    explicit = str(payload.get("variable_metadata_path", "") or "").strip()
    if explicit:
        return explicit
    return str(context.defaults.get("variable_catalog_path", "") or "").strip()


def _load_resolver(metadata_path: str) -> tuple[VariableMetadataResolver | None, str | None]:
    if not metadata_path:
        return None, "variable_catalog_path is not configured for RCA metadata resolution."
    path = Path(metadata_path)
    if not path.exists() or not path.is_file():
        return None, f"Variable metadata file not found at {path}."
    return VariableMetadataResolver.from_csv(path), None


def _parsed_from_payload(payload: dict[str, Any], raw_text: str) -> ParsedAlertRequest:
    if payload.get("user_query"):
        return parse_alert_query(str(payload.get("user_query", "")))

    variable_reference = str(payload.get("variable_id") or payload.get("variable_name") or "").strip()
    alert_date = str(payload.get("alert_date", "")).strip()
    alert_type = str(payload.get("alert_type", "unknown")).strip() or "unknown"
    metric_view = str(payload.get("metric_view", "unknown")).strip() or "unknown"

    user_query = str(payload.get("analyst_notes") or raw_text or variable_reference)
    parsed = parse_alert_query(user_query)
    return ParsedAlertRequest(
        raw_user_query=user_query,
        variable_reference=variable_reference or parsed.variable_reference,
        alert_date=alert_date or parsed.alert_date,
        alert_type=alert_type if alert_type != "unknown" else parsed.alert_type,
        metric_view=metric_view if metric_view != "unknown" else parsed.metric_view,
        model_hint=str(payload.get("model_metadata", "") or parsed.model_hint),
        segment_hint=str(payload.get("segmentation_filters", "") or parsed.segment_hint),
        market_hint=str(payload.get("market_filters", "") or parsed.market_hint),
        analyst_notes=str(payload.get("analyst_notes", "") or user_query),
        confidence=parsed.confidence,
    )


def _resolve_variable_metadata(
    resolver: VariableMetadataResolver,
    parsed: ParsedAlertRequest,
    payload: dict[str, Any],
) -> tuple[VariableMetadata | None, list[dict[str, object]]]:
    reference = str(payload.get("variable_id") or payload.get("variable_name") or parsed.variable_reference).strip()
    if not reference:
        return None, []

    resolved, candidates = resolver.resolve(reference)
    if resolved is not None:
        return resolved, [metadata_to_dict(item) for item in candidates]
    return None, [metadata_to_dict(item) for item in candidates]


def _collect_custom_queries(payload: dict[str, Any]) -> list[tuple[str, str]]:
    queries: list[tuple[str, str]] = []
    single_query = str(payload.get("query", "") or "").strip()
    if single_query:
        queries.append(("adhoc_query", single_query))

    extra_queries = payload.get("queries")
    if isinstance(extra_queries, list):
        for idx, item in enumerate(extra_queries):
            if not isinstance(item, dict):
                continue
            sql = str(item.get("sql", "") or "").strip()
            if not sql:
                continue
            name = str(item.get("name", f"query_{idx+1}") or f"query_{idx+1}").strip()
            queries.append((name, sql))
    return queries


def _collect_generated_queries(stage_sql: str, driver_sql: dict[str, str]) -> list[tuple[str, str]]:
    queries: list[tuple[str, str]] = [("stage_funnel", stage_sql)]
    for key, sql in driver_sql.items():
        queries.append((f"driver_{key}", sql))
    return queries


def run(argument: str, *, context: ToolExecutionContext) -> dict[str, Any]:
    context.report_progress("Parsing RCA input...")
    payload, raw_text = _parse_argument(argument)

    parsed = _parsed_from_payload(payload, raw_text)

    metadata_path = _resolve_metadata_path(context, payload)
    resolver, error = _load_resolver(metadata_path)
    if error:
        return {
            "tool": "rca_analysis",
            "status": "not_ready",
            "message": error,
            "example_argument": {
                "user_query": "RDMC3048 got a lower-limit alert on 2026-03-22",
                "sample_rate_override": 0.025,
                "execute_sql": False,
            },
        }

    context.report_progress("Resolving variable metadata from catalog...")
    resolved_metadata, candidates = _resolve_variable_metadata(resolver, parsed, payload)
    if resolved_metadata is None:
        if candidates:
            return {
                "tool": "rca_analysis",
                "status": "needs_user_input",
                "message": "Variable reference is ambiguous. Please specify variable_id.",
                "candidate_variables": candidates[:10],
                "parsed_alert_context": {
                    "raw_user_query": parsed.raw_user_query,
                    "variable_reference": parsed.variable_reference,
                    "alert_date": parsed.alert_date,
                    "alert_type": parsed.alert_type,
                    "metric_view": parsed.metric_view,
                    "confidence": parsed.confidence,
                },
            }
        return {
            "tool": "rca_analysis",
            "status": "not_found",
            "message": "Unable to resolve variable from metadata sheet.",
            "parsed_alert_context": {
                "raw_user_query": parsed.raw_user_query,
                "variable_reference": parsed.variable_reference,
                "alert_date": parsed.alert_date,
                "alert_type": parsed.alert_type,
                "metric_view": parsed.metric_view,
                "confidence": parsed.confidence,
            },
        }

    context.report_progress("Normalizing alert context and windows...")
    context_obj = normalize_alert_context(
        parsed,
        resolved_variable_id=resolved_metadata.variable_id,
        resolved_variable_name=resolved_metadata.variable_name or resolved_metadata.variable_id,
        alert_date=str(payload.get("alert_date", "") or parsed.alert_date),
        start_date=str(payload.get("start_date", "") or "") or None,
        end_date=str(payload.get("end_date", "") or "") or None,
        baseline_start_date=str(payload.get("baseline_start_date", "") or "") or None,
        baseline_end_date=str(payload.get("baseline_end_date", "") or "") or None,
    )

    sample_rate = payload.get("sample_rate_override", DEFAULT_SAMPLE_RATE)
    try:
        sample_rate = float(sample_rate)
    except (TypeError, ValueError):
        sample_rate = DEFAULT_SAMPLE_RATE

    stage_sql = render_stage_funnel_sql(start_date=context_obj.start_date, end_date=context_obj.end_date, sample_rate=sample_rate)
    driver_sql = {
        dim: render_driver_sql(start_date=context_obj.start_date, end_date=context_obj.end_date, dimension=dim)
        for dim in DRIVER_DIMENSIONS
    }

    observations = payload.get("observations") if isinstance(payload.get("observations"), dict) else {}

    context.report_progress("Building first-pass RCA findings...")
    output = build_rca_output(
        context=context_obj,
        metadata=resolved_metadata,
        observations=observations,
        sample_rate=sample_rate,
        stage_sql=stage_sql,
        driver_sql=driver_sql,
    )

    execute_sql = bool(payload.get("execute_sql", False))
    execute_generated_sql = bool(payload.get("execute_generated_sql", False))
    executed_results: list[dict[str, object]] = []

    if execute_sql or execute_generated_sql:
        context.report_progress("Executing BigQuery SQL and gathering result rows...")
        query_batch = _collect_custom_queries(payload)
        if execute_generated_sql:
            query_batch.extend(_collect_generated_queries(stage_sql, driver_sql))

        if query_batch:
            logger = context.logger or LOGGER
            executed_results = [result.to_dict() for result in run_bq_queries(query_batch, logger=logger)]
        else:
            executed_results = [{"name": "none", "status": "skipped", "row_count": 0, "rows": [], "duration_seconds": 0.0, "error": "No queries supplied."}]

    return {
        "tool": "rca_analysis",
        "status": "success",
        "sql_execution": {
            "execute_sql": execute_sql,
            "execute_generated_sql": execute_generated_sql,
            "query_results": executed_results,
        },
        **output,
    }
