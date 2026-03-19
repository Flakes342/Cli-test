from _future_ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(_file_).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import json
from typing import Any, Dict, List

from pipelines.rnn_data_prep.runner import run_rnn_data_prep

DEFAULT_SAMPLE_RATE = 0.025
SUPPORTED_MODELS = {"rnn"}
REQUIRED_FIELDS = ["start_dt", "end_dt", "model"]


def _safe_json(argument: str) -> Dict[str, Any]:
    text = (argument or "").strip()
    if not text:
        return {}

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}

    return payload if isinstance(payload, dict) else {}


def _normalize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    sample_rate = payload.get("sample_rate", DEFAULT_SAMPLE_RATE)
    if sample_rate in (None, ""):
        sample_rate = DEFAULT_SAMPLE_RATE

    folder_nm = payload.get("folder_nm") or payload.get("output_folder") or ""
    project_id = payload.get("project_id") or ""
    dataset_id = payload.get("dataset_id") or ""

    return {
        "start_dt": str(payload.get("start_dt") or payload.get("start_date") or "").strip(),
        "end_dt": str(payload.get("end_dt") or payload.get("end_date") or "").strip(),
        "model": str(payload.get("model") or payload.get("model_type") or "").strip().lower(),
        "sample_rate": float(sample_rate),
        "project_id": str(project_id).strip(),
        "dataset_id": str(dataset_id).strip(),
        "folder_nm": str(folder_nm).strip(),
    }


def _missing_fields(params: Dict[str, Any]) -> List[str]:
    return [name for name in REQUIRED_FIELDS if not str(params.get(name, "")).strip()]


def _validate_dates(params: Dict[str, Any]) -> str | None:
    start_dt = params["start_dt"]
    end_dt = params["end_dt"]

    if len(start_dt) != 10 or len(end_dt) != 10:
        return "Dates must be in YYYY-MM-DD format."

    if start_dt > end_dt:
        return "start_dt must be less than or equal to end_dt."

    return None


def run(argument: str) -> Dict[str, Any]:
    params = _normalize_payload(_safe_json(argument))
    missing = _missing_fields(params)

    if missing:
        return {
            "tool": "data_prep",
            "status": "needs_user_input",
            "missing_fields": missing,
            "message": "Please provide missing parameters so the existing SQL/Python pipeline can run.",
            "required_parameters": REQUIRED_FIELDS,
            "default_parameters": {"sample_rate": DEFAULT_SAMPLE_RATE},
            "notes": "sample_rate defaults to 0.025 unless specified.",
        }

    date_error = _validate_dates(params)
    if date_error:
        return {
            "tool": "data_prep",
            "status": "invalid_input",
            "message": date_error,
            "parameters": params,
        }

    if params["model"] not in SUPPORTED_MODELS:
        return {
            "tool": "data_prep",
            "status": "invalid_input",
            "message": f"Unsupported model '{params['model']}'. Supported models: {sorted(SUPPORTED_MODELS)}",
            "parameters": params,
        }

    if params["model"] == "rnn":
        result = run_rnn_data_prep(params)
        return {
            "tool": "data_prep",
            **result,
        }

    return {
        "tool": "data_prep",
        "status": "error",
        "message": "Unhandled model type.",
        "parameters": params,
    }