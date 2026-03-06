from __future__ import annotations

import json
from typing import Any, Dict


def run(argument: str) -> Dict[str, Any]:
    summary = {
        "case_details": "Case ID: 12345, Date: 2024-06-01, Customer: John Doe, Amount: $500, Location: New York",
        "anomalies": ['Mexico','IP mismatch', 'Email mismatch'],
        "model_score": 0.03,
    }
    return summary
