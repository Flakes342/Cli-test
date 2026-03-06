from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pandas as pd


def run(argument: str) -> Dict[str, Any]:
    parts = [part.strip().strip('"').strip("'") for part in argument.split("|")]
    if len(parts) != 4:
        raise ValueError(
            "Expected argument format: csv_path|feature_name|current_month|baseline_month"
        )

    csv_path, feature, current_month, baseline_month = parts
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    df = pd.read_csv(path)
    if "month" not in df.columns:
        raise ValueError("Dataset must include a 'month' column")
    if feature not in df.columns:
        raise ValueError(f"Feature '{feature}' not found in dataset")

    current = df[df["month"].astype(str) == str(current_month)][feature].dropna()
    baseline = df[df["month"].astype(str) == str(baseline_month)][feature].dropna()

    if current.empty or baseline.empty:
        raise ValueError("Current or baseline month has no data for selected feature")

    current_mean = float(current.mean())
    baseline_mean = float(baseline.mean())
    shift_pct = float(((current_mean - baseline_mean) / (abs(baseline_mean) + 1e-9)) * 100)

    return {
        "feature": feature,
        "current_month": str(current_month),
        "baseline_month": str(baseline_month),
        "current_mean": current_mean,
        "baseline_mean": baseline_mean,
        "mean_shift_pct": shift_pct,
        "current_p95": float(current.quantile(0.95)),
        "baseline_p95": float(baseline.quantile(0.95)),
        "sample_size": {"current": int(current.shape[0]), "baseline": int(baseline.shape[0])},
    }
