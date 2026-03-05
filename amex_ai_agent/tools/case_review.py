from __future__ import annotations

import json
from typing import Any, Dict


def run(argument: str) -> Dict[str, Any]:
    try:
        data = json.loads(argument)
    except json.JSONDecodeError:
        data = {"raw": argument}

    anomalies = []
    if isinstance(data, dict):
        amount = float(data.get("amount", 0)) if str(data.get("amount", "0")).replace('.', '', 1).isdigit() else 0
        if amount > 5000:
            anomalies.append("High transaction amount")
        if data.get("new_device", False):
            anomalies.append("Transaction from new device")

    summary = {
        "case_details": data,
        "anomalies": anomalies,
        "model_behavior": "Model likely elevated score due to velocity, device novelty, and amount patterns.",
    }
    return summary
