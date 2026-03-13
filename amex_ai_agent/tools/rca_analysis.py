from __future__ import annotations

import json
from typing import Any, Dict, List


REQUIRED_FIELDS = ["analysis_ref", "objective"]


def _safe_json(argument: str) -> Dict[str, Any]:
    text = (argument or "").strip()
    if not text:
        return {}

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _missing_fields(payload: Dict[str, Any]) -> List[str]:
    return [field for field in REQUIRED_FIELDS if not str(payload.get(field, "")).strip()]


def run(argument: str) -> Dict[str, Any]:
    payload = _safe_json(argument)
    missing = _missing_fields(payload)

    if missing:
        return {
            "tool": "rca_analysis",
            "status": "needs_user_input",
            "missing_fields": missing,
            "message": "Provide RCA objective and dataset/reference to run existing RCA pipeline.",
            "required_parameters": REQUIRED_FIELDS,
            "example_argument": {
                "analysis_ref": "bq://project.dataset.analysis_table",
                "objective": "Explain hit-rate drop in Mar-2025",
                "segments": ["card_present", "se_visited"],
                "time_window": {"start_dt": "YYYY-MM-DD", "end_dt": "YYYY-MM-DD"},
            },
            "workflow_hint": "If analysis_ref is unavailable, run data_prep (and model_score if needed) first.",
        }

    segments = payload.get("segments") if isinstance(payload.get("segments"), list) else []

    return {
        "tool": "rca_analysis",
        "status": "ready",
        "parameters": {
            "analysis_ref": str(payload.get("analysis_ref", "")),
            "objective": str(payload.get("objective", "")),
            "segments": segments,
            "time_window": payload.get("time_window", {}),
        },
        "execution_mode": "pass_parameters_to_existing_pipeline",
        "notes": "RCA logic is expected in existing code; tool validates runtime inputs and workflow readiness.",
    }
