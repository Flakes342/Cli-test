from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pandas as pd


def run(argument: str) -> Dict[str, Any]:

    return {
        "start_dt": '2024-01-01',
        "end_dt": '2024-06-01',
        "sample_rate": 0.025,
        "algorithm": 'rnn',
    }
