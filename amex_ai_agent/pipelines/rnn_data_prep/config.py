from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class RNNDataPrepConfig:
    start_dt: str
    end_dt: str
    sample_rate: float = 0.025
    project_id: str = ""
    dataset_id: str = ""
    folder_nm: str = "rnn_data_prep"

    def to_dict(self) -> dict[str, str | float]:
        return asdict(self)
