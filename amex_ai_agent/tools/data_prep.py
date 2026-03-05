from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pandas as pd


def run(argument: str) -> Dict[str, Any]:
    path = Path(argument.strip().strip('"').strip("'"))
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    df = pd.read_csv(path)
    before_shape = df.shape

    missing = df.isna().sum().to_dict()
    df = df.drop_duplicates()
    categorical_cols = [col for col in df.columns if df[col].dtype == "object"]

    numeric_cols = df.select_dtypes(include=["number"]).columns
    for col in numeric_cols:
        df[f"{col}_zscore"] = (df[col] - df[col].mean()) / (df[col].std() + 1e-9)

    cleaned_path = path.with_name(f"{path.stem}_cleaned.csv")
    df.to_csv(cleaned_path, index=False)

    return {
        "input_shape": before_shape,
        "output_shape": df.shape,
        "missing_values": missing,
        "categorical_columns": categorical_cols,
        "saved_to": str(cleaned_path),
    }
