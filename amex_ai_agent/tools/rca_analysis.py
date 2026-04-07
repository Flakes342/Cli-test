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

    if raw_text and not payload:
        user_query = raw_text
    else:
        parts = [
            f"variable_id={variable_reference}" if variable_reference else "",
            f"alert_date={alert_date}" if alert_date else "",
            f"alert_type={alert_type}" if alert_type and alert_type != "unknown" else "",
            str(payload.get("analyst_notes", "") or ""),
        ]
        user_query = "; ".join(part for part in parts if part).strip()

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


def _compact_response(full_output: dict[str, object], *, include_sql_templates: bool) -> dict[str, object]:
    stage_rows = full_output.get("stage_diagnostics") if isinstance(full_output.get("stage_diagnostics"), list) else []
    flagged_stages = [item for item in stage_rows if isinstance(item, dict) and item.get("flagged")]

    hypotheses = full_output.get("hypotheses") if isinstance(full_output.get("hypotheses"), list) else []
    top_hypotheses = [
        {
            "hypothesis": str(item.get("hypothesis", "")),
            "confidence": item.get("confidence"),
        }
        for item in hypotheses[:3]
        if isinstance(item, dict)
    ]

    metadata = full_output.get("resolved_variable_metadata", {})
    minimal_metadata = {
        "variable_id": metadata.get("variable_id", ""),
        "variable_name": metadata.get("variable_name", ""),
        "description": metadata.get("description", ""),
        "source_table": metadata.get("source_table", ""),
        "segment": metadata.get("segment", ""),
        "model_family": metadata.get("model_family", ""),
    } if isinstance(metadata, dict) else {}

    input_context = full_output.get("input_context", {})
    minimal_context = {
        "raw_user_query": input_context.get("raw_user_query", ""),
        "resolved_variable_id": input_context.get("resolved_variable_id", ""),
        "resolved_variable_name": input_context.get("resolved_variable_name", ""),
        "alert_date": input_context.get("alert_date", ""),
        "alert_type": input_context.get("alert_type", "unknown"),
        "metric_view": input_context.get("metric_view", "unknown"),
        "parse_confidence": input_context.get("parse_confidence", 0.0),
    } if isinstance(input_context, dict) else {}

    metric_decomposition = full_output.get("metric_decomposition", {})
    include_decomp = False
    if isinstance(metric_decomposition, dict):
        for side in ("numerator", "denominator"):
            part = metric_decomposition.get(side)
            if isinstance(part, dict) and any(part.get(key) is not None for key in ("value", "baseline", "pct_change")):
                include_decomp = True
                break

    sql_execution = full_output.get("sql_execution", {})
    query_results = sql_execution.get("query_results", []) if isinstance(sql_execution, dict) else []
    summarized_results = []
    for item in query_results:
        if isinstance(item, dict):
            summarized_results.append(
                {
                    "name": item.get("name", ""),
                    "status": item.get("status", ""),
                    "row_count": item.get("row_count", 0),
                    "error": item.get("error", ""),
                }
            )

    compact = {
        "tool": full_output.get("tool", "rca_analysis"),
        "status": full_output.get("status", "success"),
        "input_context": minimal_context,
        "resolved_variable_metadata": minimal_metadata,
        "analysis_window": full_output.get("analysis_window", {}),
        "baseline_window": full_output.get("baseline_window", {}),
        "alert_summary": full_output.get("alert_summary", {}),
        "key_findings": {
            "flagged_stages": flagged_stages,
            "top_hypotheses": top_hypotheses,
        },
        "sql_execution": {
            "execute_sql": bool(sql_execution.get("execute_sql", False)) if isinstance(sql_execution, dict) else False,
            "execute_generated_sql": bool(sql_execution.get("execute_generated_sql", False)) if isinstance(sql_execution, dict) else False,
            "query_results": summarized_results,
        },
        "analyst_summary": full_output.get("analyst_summary", ""),
    }

    if include_decomp:
        compact["metric_decomposition"] = metric_decomposition

    if include_sql_templates:
        compact["analysis_sql"] = full_output.get("analysis_sql", {})
    return compact


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
    base_output = build_rca_output(
        context=context_obj,
        metadata=resolved_metadata,
        observations=observations,
        sample_rate=sample_rate,
        stage_sql=stage_sql,
        driver_sql=driver_sql,
    )

    custom_queries = _collect_custom_queries(payload)
    execute_sql = bool(payload.get("execute_sql", False) or custom_queries)
    execute_generated_sql = bool(payload.get("execute_generated_sql", False))
    executed_results: list[dict[str, object]] = []

    if execute_sql or execute_generated_sql:
        context.report_progress("Executing BigQuery SQL and gathering result rows...")
        query_batch = list(custom_queries)
        if execute_generated_sql:
            query_batch.extend(_collect_generated_queries(stage_sql, driver_sql))

        if query_batch:
            logger = context.logger or LOGGER
            executed_results = [result.to_dict() for result in run_bq_queries(query_batch, logger=logger)]
        else:
            executed_results = [{"name": "none", "status": "skipped", "row_count": 0, "rows": [], "duration_seconds": 0.0, "error": "No queries supplied."}]

    full_output = {
        "tool": "rca_analysis",
        "status": "success",
        "sql_execution": {
            "execute_sql": execute_sql,
            "execute_generated_sql": execute_generated_sql,
            "query_results": executed_results,
        },
        **base_output,
    }

    response_mode = str(payload.get("response_mode", "compact") or "compact").strip().lower()
    include_sql_templates = bool(payload.get("include_sql_templates", False))
    if response_mode == "full":
        if not include_sql_templates and "analysis_sql" in full_output:
            del full_output["analysis_sql"]
        stage_rows = full_output.get("stage_diagnostics")
        if isinstance(stage_rows, list) and stage_rows:
            if all(
                isinstance(item, dict)
                and item.get("current_count") is None
                and item.get("baseline_count") is None
                and item.get("pct_change") is None
                for item in stage_rows
            ):
                full_output["stage_diagnostics"] = []
        return full_output

    return _compact_response(full_output, include_sql_templates=include_sql_templates)
