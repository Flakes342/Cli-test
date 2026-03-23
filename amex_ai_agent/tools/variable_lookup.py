from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from amex_ai_agent.tools.base import ToolExecutionContext
from amex_ai_agent.variable_catalog import VariableCatalog


DEFAULT_LIMIT = 10


def _safe_json(argument: str) -> dict[str, Any]:
    text = (argument or "").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _serialize_record(record) -> dict[str, str]:
    return record.to_dict()


def _resolve_catalog(context: ToolExecutionContext) -> tuple[VariableCatalog | None, str | None]:
    catalog_path = str(context.defaults.get("variable_catalog_path", "") or "").strip()
    if not catalog_path:
        return None, "variable_catalog_path is not configured."

    path = Path(catalog_path)
    if not path.exists() or not path.is_file():
        return None, f"Variable catalog not found at {path}."

    return VariableCatalog.from_csv(path), None


def run(argument: str, *, context: ToolExecutionContext) -> dict[str, Any]:
    context.report_progress("Loading variable catalog...")
    payload = _safe_json(argument)
    catalog, error = _resolve_catalog(context)
    if error:
        return {
            "tool": "variable_lookup",
            "status": "not_ready",
            "message": error,
            "example_argument": {
                "code": "var_123",
                "query": "authorization amount",
                "model": "rnn",
                "domain": "authorization",
                "table": "feature_store",
                "limit": 5,
            },
        }

    code = str(payload.get("code", "") or "").strip()
    query = str(payload.get("query", "") or "").strip()
    model = str(payload.get("model", "") or "").strip() or None
    domain = str(payload.get("domain", "") or "").strip() or None
    table = str(payload.get("table", "") or "").strip() or None
    limit = payload.get("limit", DEFAULT_LIMIT)
    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        limit = DEFAULT_LIMIT

    if code:
        context.report_progress(f"Looking up exact variable code: {code}")
        record = catalog.exact_lookup(code)
        if record is None:
            return {
                "tool": "variable_lookup",
                "status": "not_found",
                "match_type": "exact",
                "code": code,
                "filters": {"model": model or "", "domain": domain or "", "table": table or ""},
                "message": f"No variable found for code '{code}'.",
            }
        return {
            "tool": "variable_lookup",
            "status": "success",
            "match_type": "exact",
            "record": _serialize_record(record),
        }

    filters = {"model": model, "domain": domain, "table": table}
    if query:
        context.report_progress(f"Searching variable catalog for: {query}")
        matches = catalog.search(query, model=model, domain=domain, table=table, limit=limit)
        if not matches:
            return {
                "tool": "variable_lookup",
                "status": "not_found",
                "match_type": "fuzzy",
                "query": query,
                "filters": {key: value or "" for key, value in filters.items()},
                "message": "No matching variables found.",
            }

        result_status = "success" if len(matches) == 1 else "ambiguous"
        return {
            "tool": "variable_lookup",
            "status": result_status,
            "match_type": "fuzzy",
            "query": query,
            "filters": {key: value or "" for key, value in filters.items()},
            "result_count": len(matches),
            "results": [_serialize_record(record) for record in matches],
            "message": "Found a single matching variable." if len(matches) == 1 else "Multiple candidate variables found.",
        }

    context.report_progress("Listing variables with filters.")
    matches = catalog.filter_records(model=model, domain=domain, table=table)[:limit]
    if not matches:
        return {
            "tool": "variable_lookup",
            "status": "not_found",
            "match_type": "filtered_list",
            "filters": {key: value or "" for key, value in filters.items()},
            "message": "No variables matched the requested filters.",
        }

    return {
        "tool": "variable_lookup",
        "status": "success",
        "match_type": "filtered_list",
        "filters": {key: value or "" for key, value in filters.items()},
        "result_count": len(matches),
        "results": [_serialize_record(record) for record in matches],
    }
