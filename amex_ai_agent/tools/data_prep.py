from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class WorkflowStep:
    name: str

    def as_payload(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "sql": "",
            "python": "",
        }


def _safe_json(argument: str) -> Dict[str, Any]:
    text = (argument or "").strip()
    if not text:
        return {}

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {"instruction": text}

    if isinstance(payload, dict):
        return payload
    return {"instruction": text}


def _build_workflow(payload: Dict[str, Any]) -> List[WorkflowStep]:
    steps = [
        WorkflowStep("fetch_initial_population"),
        WorkflowStep("apply_exclusions"),
    ]

    transform_steps = payload.get("transform_steps")
    if isinstance(transform_steps, list) and transform_steps:
        steps.extend(WorkflowStep(str(step).strip() or "transform") for step in transform_steps)
    else:
        steps.append(WorkflowStep("transform"))

    steps.append(WorkflowStep("publish_outputs"))
    return steps


def run(argument: str) -> Dict[str, Any]:
    payload = _safe_json(argument)

    return {
        "tool": "data_prep",
        "source_table": payload.get("source_table", ""),
        "start_date": payload.get("start_date", ""),
        "end_date": payload.get("end_date", ""),
        "workflow_steps": [step.as_payload() for step in _build_workflow(payload)],
        "notes": "Fill sql/python fields per step with your internal code. Reasoning loop decides what tool runs next.",
    }
