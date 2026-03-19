from __future__ import annotations

import json
import logging
from typing import Any, Dict

from amex_ai_agent.pipelines.rnn_data_prep.runner import run_rnn_data_prep
from amex_ai_agent.tools.base import ToolExecutionContext


LOGGER = logging.getLogger(__name__)
DEFAULT_SAMPLE_RATE = 0.025
SUPPORTED_MODELS = {"rnn", "ensemble", "xgboost"}
REQUIRED_FIELDS = ("start_dt", "end_dt", "model")


def _safe_json(argument: str) -> Dict[str, Any]:
    text = (argument or "").strip()
    if not text:
        return {}

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}

    return payload if isinstance(payload, dict) else {}


def _normalize_payload(payload: Dict[str, Any], defaults: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
    resolved_defaults: Dict[str, Any] = {}

    def resolve(field: str, *aliases: str, fallback: Any = "") -> Any:
        for key in (field, *aliases):
            value = payload.get(key)
            if value not in (None, ""):
                return value

        default_value = defaults.get(field, fallback)
        if default_value not in (None, ""):
            resolved_defaults[field] = default_value
        return default_value

    sample_rate = resolve("sample_rate", fallback=DEFAULT_SAMPLE_RATE)
    if sample_rate in (None, ""):
        sample_rate = DEFAULT_SAMPLE_RATE
        resolved_defaults["sample_rate"] = DEFAULT_SAMPLE_RATE

    params = {
        "start_dt": str(resolve("start_dt", "start_date")).strip(),
        "end_dt": str(resolve("end_dt", "end_date")).strip(),
        "model": str(resolve("model", "model_type")).strip().lower(),
        "sample_rate": float(sample_rate),
        "project_id": str(resolve("project_id")).strip(),
        "dataset_id": str(resolve("dataset_id")).strip(),
        "folder_nm": str(resolve("folder_nm", "output_folder", fallback=defaults.get("folder_nm", "rnn_data_prep"))).strip(),
    }
    return params, resolved_defaults


def _missing_fields(params: Dict[str, Any], defaults: Dict[str, Any]) -> list[str]:
    missing = [field for field in REQUIRED_FIELDS if not str(params.get(field, "")).strip()]
    if not str(params.get("project_id", "")).strip() and not defaults.get("project_id"):
        missing.append("project_id")
    if not str(params.get("dataset_id", "")).strip() and not defaults.get("dataset_id"):
        missing.append("dataset_id")
    return missing


def _validate_dates(params: Dict[str, Any]) -> str | None:
    start_dt = params["start_dt"]
    end_dt = params["end_dt"]

    if len(start_dt) != 10 or len(end_dt) != 10:
        return "Dates must be in YYYY-MM-DD format."
    if start_dt > end_dt:
        return "start_dt must be less than or equal to end_dt."
    return None


def run(argument: str, context: ToolExecutionContext | None = None) -> Dict[str, Any]:
    context = context or ToolExecutionContext(logger=LOGGER)
    payload = _safe_json(argument)
    params, defaults_applied = _normalize_payload(payload, context.defaults)
    missing = _missing_fields(params, context.defaults)

    LOGGER.info("data_prep invoked with model=%s", params.get("model"))
    context.report_progress("Data prep tool starting...")

    if missing:
        return {
            "tool": "data_prep",
            "status": "needs_user_input",
            "missing_fields": missing,
            "message": "Provide the missing parameters to run data prep.",
            "required_parameters": list(REQUIRED_FIELDS) + ["project_id", "dataset_id"],
            "resolved_parameters": params,
            "defaults_applied": defaults_applied,
        }

    date_error = _validate_dates(params)
    if date_error:
        return {
            "tool": "data_prep",
            "status": "invalid_input",
            "message": date_error,
            "resolved_parameters": params,
            "defaults_applied": defaults_applied,
        }

    if params["model"] not in SUPPORTED_MODELS:
        return {
            "tool": "data_prep",
            "status": "invalid_input",
            "message": f"Unsupported model '{params['model']}'. Supported models: {sorted(SUPPORTED_MODELS)}",
            "resolved_parameters": params,
            "defaults_applied": defaults_applied,
        }

    if params["model"] != "rnn":
        return {
            "tool": "data_prep",
            "status": "not_ready",
            "message": f"{params['model']} data prep is planned but not wired yet.",
            "resolved_parameters": params,
            "defaults_applied": defaults_applied,
        }

    result = run_rnn_data_prep(params, context=context)
    return {
        "tool": "data_prep",
        "resolved_parameters": params,
        "defaults_applied": defaults_applied,
        **result,
    }
