from __future__ import annotations

import json
from typing import Any, Dict, List


DEFAULT_METRICS = ["coverage", "hitrate", "accuracy", "gini", "ks"]
REQUIRED_FIELDS = ["score_ref"]


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
            "tool": "compute_metrics",
            "status": "needs_user_input",
            "missing_fields": missing,
            "message": "Need scored data reference before metrics can run.",
            "required_parameters": REQUIRED_FIELDS,
            "example_argument": {
                "score_ref": "bq://project.dataset.scored_table",
                "label_col": "label",
                "score_col": "score",
                "metrics": DEFAULT_METRICS,
                "segments": ["card_present", "se_visited"],
            },
            "workflow_hint": "If score_ref is unavailable, run data_prep -> model_score first.",
        }

    requested_metrics = payload.get("metrics")
    metrics = requested_metrics if isinstance(requested_metrics, list) and requested_metrics else DEFAULT_METRICS

    requested_segments = payload.get("segments")
    segments = requested_segments if isinstance(requested_segments, list) and requested_segments else []

    return {
        "tool": "compute_metrics",
        "status": "ready",
        "parameters": {
            "score_ref": str(payload.get("score_ref", "")),
            "label_col": str(payload.get("label_col", "label")),
            "score_col": str(payload.get("score_col", "score")),
            "metrics": metrics,
            "segments": segments,
            "segment_definitions_ref": str(payload.get("segment_definitions_ref", "")),
        },
        "execution_mode": "pass_parameters_to_existing_pipeline",
        "notes": "Metrics are computed by pre-built code; this tool performs request validation only.",
        "workflow_hint": "Use segment columns available in scored dataset or pass segment_definitions_ref.",
    }
