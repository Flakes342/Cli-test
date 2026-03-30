from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from amex_ai_agent.tools.base import ToolExecutionContext
from amex_ai_agent.variable_catalog import VariableCatalog


DEFAULT_SEARCH_LIMIT = 1
DEFAULT_FILTER_LIMIT = 10


def _parse_argument(argument: str) -> tuple[dict[str, Any], str]:
    text = (argument or "").strip()
    if not text:
        return {}, ""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}, text
    return (payload if isinstance(payload, dict) else {}), text


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


def _limit_value(raw_limit: Any, *, default: int) -> int:
    try:
        return max(1, int(raw_limit))
    except (TypeError, ValueError):
        return default


def _fuzzy_response(
    catalog: VariableCatalog,
    *,
    query: str,
    model: str | None,
    domain: str | None,
    table: str | None,
    limit: int,
) -> dict[str, Any]:
    filters = {"model": model, "domain": domain, "table": table}
    all_matches = catalog.search(query, model=model, domain=domain, table=table, limit=None)
    if not all_matches:
        return {
            "tool": "variable_lookup",
            "status": "not_found",
            "match_type": "fuzzy",
            "query": query,
            "filters": {key: value or "" for key, value in filters.items()},
            "message": "No matching variables found.",
        }

    visible_matches = all_matches[:limit]
    status = "success" if len(all_matches) == 1 else "ambiguous"
    response: dict[str, Any] = {
        "tool": "variable_lookup",
        "status": status,
        "match_type": "fuzzy",
        "query": query,
        "filters": {key: value or "" for key, value in filters.items()},
        "result_count": len(visible_matches),
        "total_matches": len(all_matches),
        "results": [_serialize_record(record) for record in visible_matches],
    }
    if len(all_matches) > 1:
        response["message"] = "Multiple candidate variables found. Showing the top-ranked result(s)."
    else:
        response["message"] = "Found a single matching variable."
    return response


def run(argument: str, *, context: ToolExecutionContext) -> dict[str, Any]:
    context.report_progress("Loading variable catalog...")
    payload, raw_text = _parse_argument(argument)
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
                "limit": 3,
            },
        }

    code = str(payload.get("code", "") or "").strip()
    query = str(payload.get("query", "") or "").strip()
    model = str(payload.get("model", "") or "").strip() or None
    domain = str(payload.get("domain", "") or "").strip() or None
    table = str(payload.get("table", "") or "").strip() or None
    filters = {"model": model, "domain": domain, "table": table}

    if raw_text and not payload:
        query = raw_text
        if "limit" not in payload:
            search_limit = DEFAULT_SEARCH_LIMIT
        else:
            search_limit = _limit_value(payload.get("limit"), default=DEFAULT_SEARCH_LIMIT)
    else:
        search_limit = _limit_value(payload.get("limit"), default=DEFAULT_SEARCH_LIMIT)
    filter_limit = _limit_value(payload.get("limit"), default=DEFAULT_FILTER_LIMIT)

    if code:
        context.report_progress(f"Looking up exact variable code: {code}")
        record = catalog.exact_lookup(code)
        if record is not None:
            return {
                "tool": "variable_lookup",
                "status": "success",
                "match_type": "exact",
                "record": _serialize_record(record),
            }

        context.report_progress(f"No exact code match for {code}; trying fuzzy catalog search.")
        return _fuzzy_response(
            catalog,
            query=code,
            model=model,
            domain=domain,
            table=table,
            limit=search_limit,
        )

    if query:
        context.report_progress(f"Searching variable catalog for: {query}")
        return _fuzzy_response(
            catalog,
            query=query,
            model=model,
            domain=domain,
            table=table,
            limit=search_limit,
        )

    if any(filters.values()):
        context.report_progress("Listing variables with filters.")
        matches = catalog.filter_records(model=model, domain=domain, table=table)[:filter_limit]
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

    return {
        "tool": "variable_lookup",
        "status": "needs_user_input",
        "message": "Provide a variable code, free-text query, or at least one filter (model/domain/table).",
        "example_argument": {
            "code": "CMN5",
            "query": "common merchant mismatch",
            "model": "RNN Gen 4",
            "domain": "Authentication",
            "table": "axp-lumi.dw.wwcas_authorization",
            "limit": 3,
        },
    }
