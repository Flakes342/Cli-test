from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pandas as pd


def run(argument: str) -> Dict[str, Any]:
    path = Path(argument.strip().strip('"').strip("'"))
    if not path.exists():
        raise FileNotFoundError(f"Alert dataset not found: {path}")

    df = pd.read_csv(path)
    volume_distribution = df["alert_type"].value_counts().to_dict() if "alert_type" in df.columns else {}

    feature_importance = {}
    for col in ["risk_score", "velocity", "amount"]:
        if col in df.columns:
            feature_importance[col] = float(df[col].corr(df.get("label", pd.Series([0] * len(df)))).fillna(0))

    candidates = [k for k, v in volume_distribution.items() if v < 5]

    return {
        "alert_volume_distribution": volume_distribution,
        "feature_importance_indicators": feature_importance,
        "potential_rule_removal_candidates": candidates,
    }
