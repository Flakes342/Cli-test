from __future__ import annotations

import json
from typing import Any, Dict, List


DEFAULT_SAMPLE_RATE = 0.025
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

    return {
        "start_dt": str(payload.get("start_dt") or payload.get("start_date") or ""),
        "end_dt": str(payload.get("end_dt") or payload.get("end_date") or ""),
        "model": str(payload.get("model") or payload.get("model_type") or ""),
        "sample_rate": sample_rate,
    }


def _missing_fields(params: Dict[str, Any]) -> List[str]:
    return [name for name in REQUIRED_FIELDS if not str(params.get(name, "")).strip()]


def run(argument: str) -> Dict[str, Any]:
    params = _normalize_payload(_safe_json(argument))
    missing = _missing_fields(params)

    if missing:
        return {
            "tool": "data_prep",
            "status": "needs_user_input",
            "missing_fields": missing,
            "message": "Please provide missing parameters so existing SQL/Python pipeline can run.",
            "required_parameters": REQUIRED_FIELDS,
            "default_parameters": {"sample_rate": DEFAULT_SAMPLE_RATE},
            "notes": "Sample rate defaults to 0.025 unless user specifies otherwise.",
        }

    return {
        "tool": "data_prep",
        "status": "ready",
        "parameters": params,
        "execution_mode": "pass_parameters_to_existing_pipeline",
        "notes": "Sample rate defaults to 0.025 unless user specifies otherwise.",
    }
