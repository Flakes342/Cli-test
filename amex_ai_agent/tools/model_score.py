from __future__ import annotations

import json
from typing import Any, Dict, List


REQUIRED_FIELDS = ["model", "input_ref", "score_output_ref"]


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
            "tool": "model_score",
            "status": "needs_user_input",
            "missing_fields": missing,
            "message": "Provide required parameters to run the existing model-scoring pipeline.",
            "required_parameters": REQUIRED_FIELDS,
            "example_argument": {
                "model": "rnn|xgboost|ensemble",
                "input_ref": "bq://project.dataset.prepared_table",
                "score_output_ref": "bq://project.dataset.scored_table",
                "score_version": "optional",
            },
            "notes": "This tool is a parameter handoff to pre-built scoring code.",
        }

    return {
        "tool": "model_score",
        "status": "ready",
        "parameters": {
            "model": str(payload.get("model", "")),
            "input_ref": str(payload.get("input_ref", "")),
            "score_output_ref": str(payload.get("score_output_ref", "")),
            "score_version": str(payload.get("score_version", "")),
        },
        "execution_mode": "pass_parameters_to_existing_pipeline",
        "notes": "Scoring pipeline is assumed pre-implemented; this tool validates and forwards runtime parameters.",
    }
