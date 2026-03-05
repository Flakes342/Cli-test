from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.feature_selection import mutual_info_classif


def run(argument: str) -> Dict[str, Any]:
    path = Path(argument.strip().strip('"').strip("'"))
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    df = pd.read_csv(path)
    if not {"label", "score"}.issubset(set(df.columns)):
        raise ValueError("Dataset must include 'label' and 'score' columns")

    y_true = df["label"].astype(int).values
    y_score = df["score"].astype(float).values

    auc = float(roc_auc_score(y_true, y_score))
    gini = 2 * auc - 1

    pos = np.sort(y_score[y_true == 1])
    neg = np.sort(y_score[y_true == 0])
    ks = float(max(abs((pos <= t).mean() - (neg <= t).mean()) for t in np.unique(y_score)))

    feature_cols = [c for c in df.columns if c not in {"label"} and np.issubdtype(df[c].dtype, np.number)]
    X = df[feature_cols].fillna(0)
    mi_values = mutual_info_classif(X, y_true, discrete_features=False)
    mutual_info = {col: float(val) for col, val in zip(feature_cols, mi_values)}

    return {"gini": float(gini), "ks": ks, "roc_auc": auc, "mutual_information": mutual_info}
