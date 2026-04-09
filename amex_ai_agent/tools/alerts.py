from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from amex_ai_agent.rca.alert_query_parser import parse_alert_query
from amex_ai_agent.rca.bq_executor import run_bq_query
from amex_ai_agent.rca.variable_metadata_resolver import VariableMetadataResolver, metadata_to_dict
from amex_ai_agent.tools.base import ToolExecutionContext


LOGGER = logging.getLogger(__name__)
TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "cdit_alert_rationalization"


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


def _sanitize_identifier(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "", (value or "").strip())


def _normalize_table_reference(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    # Catalog values may already contain backticks (for project-only or full path quoting).
    # Templates quote the whole table identifier, so keep a plain dotted path here.
    return raw.replace("`", "")


def _sanitize_table_segment(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", (value or "").strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned:
        return "alert"
    if cleaned[0].isdigit():
        cleaned = f"t_{cleaned}"
    return cleaned


def _normalize_dataset_id(value: str, *, project_id: str) -> str:
    raw = (value or "").strip().replace("`", "")
    if not raw:
        return ""

    # Handle fully-qualified forms passed by mistake:
    # - project.dataset
    # - project:dataset
    # - project.dataset.table (take dataset token)
    normalized = raw.replace(":", ".")
    parts = [part for part in normalized.split(".") if part]
    if len(parts) >= 2 and parts[0] == project_id:
        return parts[1]
    if len(parts) == 1:
        return parts[0]
    return raw


def _template_query_names(variable_type: str, default_value: str) -> list[str]:
    normalized = (variable_type or "").strip().lower()
    is_categorical = normalized.startswith("cat")
    if is_categorical:
        return ["00_cat_var_dist", "01_cat_var_stats", "02_cat_top_cm", "02_cat_top_se"]

    has_default = bool(str(default_value or "").strip())
    stats_file = "01_num_var_stats_w_default" if has_default else "01_num_var_stats_wo_default"
    return ["00_num_var_dist", stats_file, "02_num_top_cm", "02_num_top_se"]


def _build_queries(
    *,
    variable_name: str,
    variable_table: str,
    alert_date: str,
    variable_type: str,
    default_value: str,
    alerted_value: str,
) -> list[tuple[str, str]]:
    chosen_templates = _template_query_names(variable_type, default_value)
    safe_var = _sanitize_identifier(variable_name)
    if not safe_var:
        return []

    replacement_map = {
        "var": safe_var,
        "var_table": _normalize_table_reference(variable_table),
        "alert_dt": alert_date,
        "default_value": str(default_value or "0"),
        "alerted_value": str(alerted_value or "").strip(),
    }

    rendered_queries: list[tuple[str, str]] = []
    for template_name in chosen_templates:
        template_path = TEMPLATE_DIR / f"{template_name}.txt"
        if not template_path.exists() or not template_path.is_file():
            continue

        sql_template = template_path.read_text(encoding="utf-8").strip()
        try:
            rendered = sql_template.format(**replacement_map)
        except KeyError:
            continue
        rendered_queries.append((template_name, rendered))

    return rendered_queries


def _build_summary(
    *,
    variable_id: str,
    variable_name: str,
    variable_type: str,
    alert_date: str,
    executed_results: list[dict[str, object]],
) -> tuple[str, bool]:
    if not executed_results:
        return (
            "Default alert-rationalization SQL templates were generated but not executed. "
            "Run with execute_sql=true to produce data-backed findings.",
            True,
        )

    failures = [result for result in executed_results if result.get("status") != "success"]
    if failures:
        failed_names = ", ".join(str(item.get("name")) for item in failures)
        return (
            f"Executed {len(executed_results)} queries for {variable_id}/{variable_name} ({variable_type}) around {alert_date}, "
            f"but some failed ({failed_names}).",
            True,
        )

    total_rows = sum(int(result.get("row_count") or 0) for result in executed_results)
    if total_rows == 0:
        return (
            f"Executed {len(executed_results)} queries for {variable_id}/{variable_name} ({variable_type}) around {alert_date}, "
            "but no rows were returned. Additional scoped SQL is needed.",
            True,
        )

    largest_result = max(executed_results, key=lambda item: int(item.get("row_count") or 0))
    largest_name = str(largest_result.get("name") or "query")
    largest_rows = int(largest_result.get("row_count") or 0)
    needs_followup = total_rows < 20
    summary = (
        f"Executed {len(executed_results)} default queries for {variable_id}/{variable_name} ({variable_type}) around {alert_date}. "
        f"Returned {total_rows} rows total; the most populated output was {largest_name} with {largest_rows} rows."
    )
    return summary, needs_followup


def _build_followup_prompt(
    *,
    variable_id: str,
    variable_name: str,
    variable_type: str,
    alert_date: str,
    query_results: list[dict[str, object]],
) -> str:
    compact_result_view = [
        {
            "name": result.get("name"),
            "status": result.get("status"),
            "row_count": result.get("row_count"),
            "sample_rows": (result.get("rows") or [])[:3],
        }
        for result in query_results
    ]
    return (
        "Write 2-4 additional BigQuery SQL queries for deeper alert RCA. "
        f"Variable ID: {variable_id}; variable name: {variable_name}; variable type: {variable_type}; alert date: {alert_date}. "
        "Base queries have already been run. Focus on explaining root drivers by merchant/entity/time and isolate what changed on/near the alert date. "
        f"Current results snapshot: {json.dumps(compact_result_view, default=str)}"
    )


def _build_destination_tables(
    *,
    query_names: list[str],
    variable_id: str,
    alert_date: str,
    context: ToolExecutionContext,
    payload: dict[str, Any],
) -> dict[str, str]:
    project_id = str(
        payload.get("project_id")
        or context.defaults.get("project_id")
        or context.defaults.get("default_project_id")
        or ""
    ).strip()
    dataset_id = str(
        payload.get("dataset_id")
        or context.defaults.get("dataset_id")
        or context.defaults.get("default_dataset_id")
        or ""
    ).strip()
    dataset_id = _normalize_dataset_id(dataset_id, project_id=project_id)
    folder_nm = str(
        payload.get("folder_nm")
        or context.defaults.get("folder_nm")
        or context.defaults.get("default_folder_nm")
        or "alert_rationalization"
    ).strip()
    if not project_id or not dataset_id:
        return {}

    safe_var = _sanitize_table_segment(variable_id)
    safe_date = _sanitize_table_segment(alert_date.replace("-", ""))
    safe_prefix = _sanitize_table_segment(folder_nm)
    destinations: dict[str, str] = {}
    for query_name in query_names:
        safe_query = _sanitize_table_segment(query_name)
        table_name = f"{safe_prefix}_alert_{safe_var}_{safe_date}_{safe_query}"
        destinations[query_name] = f"{project_id}.{dataset_id}.{table_name}"
    return destinations


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
    variable_name = str(payload.get("variable_name") or (resolved_variable or {}).get("variable_name") or variable_id).strip()
    variable_type = str(payload.get("variable_type") or (resolved_variable or {}).get("variable_type") or "Numerical").strip()
    default_value = str(payload.get("default_value") or (resolved_variable or {}).get("default_value") or "").strip()
    alerted_value = str(payload.get("alerted_value") or "").strip()
    alert_date = str(payload.get("alert_date") or parsed.alert_date or "")

    variable_table = str(payload.get("alert_table") or (resolved_variable or {}).get("source_table") or "").strip()

    if not variable_id:
        return {
            "tool": "alert_rationalization",
            "status": "needs_user_input",
            "message": "Variable is required for alert rationalization.",
            "workflow_hint": "Run variable_lookup first to resolve the variable_id, then rerun alert_rationalization.",
        }

    if not _sanitize_identifier(variable_name):
        return {
            "tool": "alert_rationalization",
            "status": "needs_user_input",
            "message": "Variable name is empty/invalid for SQL template rendering.",
            "workflow_hint": "Provide a valid variable_name or ensure Full Name exists in catalog.",
            "input_context": {"variable_id": variable_id, "variable_name": variable_name},
        }

    if not variable_table:
        return {
            "tool": "alert_rationalization",
            "status": "needs_user_input",
            "message": "Variable table is required to build default alert-rationalization SQL.",
            "workflow_hint": "Ensure variable metadata CSV contains the Table column or pass alert_table explicitly.",
            "input_context": {"variable_id": variable_id, "variable_name": variable_name},
        }

    if not alert_date:
        return {
            "tool": "alert_rationalization",
            "status": "needs_user_input",
            "message": "alert_date is required for default alert-rationalization SQL templates.",
            "input_context": {"variable_id": variable_id, "variable_name": variable_name},
        }

    default_queries = _build_queries(
        variable_name=variable_name,
        variable_table=variable_table,
        alert_date=alert_date,
        variable_type=variable_type,
        default_value=default_value,
        alerted_value=alerted_value,
    )

    if not default_queries:
        return {
            "tool": "alert_rationalization",
            "status": "error",
            "message": "Unable to build default query set for the variable.",
            "input_context": {
                "variable_id": variable_id,
                "variable_name": variable_name,
                "variable_type": variable_type,
                "variable_table": variable_table,
            },
        }

    execute_sql = bool(payload.get("execute_sql", False))
    query_results: list[dict[str, object]] = []
    destination_tables = _build_destination_tables(
        query_names=[name for name, _ in default_queries],
        variable_id=variable_id,
        alert_date=alert_date,
        context=context,
        payload=payload,
    )
    if execute_sql:
        if not destination_tables:
            return {
                "tool": "alert_rationalization",
                "status": "needs_user_input",
                "message": "project_id and dataset_id are required to persist alert query outputs as BigQuery tables.",
                "workflow_hint": "Provide project_id/dataset_id (or set default_project_id/default_dataset_id in config) and rerun.",
                "input_context": {
                    "variable_id": variable_id,
                    "alert_date": alert_date,
                },
            }
        context.report_progress("Running default alert-rationalization SQL query set...")
        total = len(default_queries)
        for index, (name, sql) in enumerate(default_queries, start=1):
            context.report_progress(f"Running query {index}/{total}: {name}")
            result = run_bq_query(
                sql,
                name=name,
                logger=context.logger or LOGGER,
                destination_table=destination_tables.get(name, ""),
            )
            query_results.append(result.to_dict())
        context.report_progress("Default alert-rationalization SQL query set finished.")

    summary, needs_llm_followup = _build_summary(
        variable_id=variable_id,
        variable_name=variable_name,
        variable_type=variable_type,
        alert_date=alert_date,
        executed_results=query_results,
    )

    return {
        "tool": "alert_rationalization",
        "status": "success",
        "input_context": {
            "raw_user_query": parsed.raw_user_query,
            "variable_id": variable_id,
            "variable_name": variable_name,
            "variable_type": variable_type,
            "default_value": default_value,
            "alerted_value": alerted_value,
            "alert_date": alert_date,
            "metric_view": str(payload.get("metric_view") or parsed.metric_view),
            "alert_type": str(payload.get("alert_type") or parsed.alert_type),
        },
        "resolved_variable_metadata": resolved_variable or {},
        "sql_execution": {
            "execute_sql": execute_sql,
            "persist_query_tables": bool(destination_tables),
            "destination_tables": destination_tables,
            "query_set": [
                {"name": name, "sql": sql}
                for name, sql in default_queries
            ],
            "query_results": query_results,
        },
        "summary": summary,
        "needs_llm_followup": needs_llm_followup,
        "llm_followup_prompt": _build_followup_prompt(
            variable_id=variable_id,
            variable_name=variable_name,
            variable_type=variable_type,
            alert_date=alert_date,
            query_results=query_results,
        ) if needs_llm_followup else "",
    }
