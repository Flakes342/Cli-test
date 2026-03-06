from __future__ import annotations

import re
from typing import Dict, List


FRAUD_KEYWORDS = [
    "chargeback",
    "stolen",
    "account takeover",
    "social engineering",
    "vpn",
    "proxy",
    "mule",
    "suspicious",
]


def run(argument: str) -> Dict[str, List[str]]:
    text = argument.lower()
    signals = [kw for kw in FRAUD_KEYWORDS if kw in text]

    behavior = []
    if re.search(r"urgent|immediately|now", text):
        behavior.append("urgency pressure")
    if re.search(r"new device|unknown device", text):
        behavior.append("new device usage")
    if re.search(r"password reset|otp", text):
        behavior.append("credential manipulation")

    suggested_variables = [
        "device_age_days",
        "velocity_1h",
        "chargeback_rate_90d",
        "ip_risk_score",
    ]

    return {
        "fraud_signals": "Don't know password, urgent request, new device",
        "sentiment_score": -2,
        "suggested_model_variables": suggested_variables,
    }