from _future_ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RNNDataPrepConfig:
    start_dt: str
    end_dt: str
    sample_rate: float = 0.025
    project_id: str = "prj-p-ai-fraud"
    dataset_id: str = "atanw9"
    folder_nm: str = ""