from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict


@dataclass
class AgentConfig:
    """Application-level configuration values."""

    agent_name: str = "Sally"
    theme: str = "dark"
    memory_enabled: bool = True
    auto_execute_tools: bool = False
    max_reasoning_loops: int = 5
    llm_mode: str = "manual"
    llm_model: str = ""
    default_project_id: str = ""
    default_dataset_id: str = ""
    default_folder_nm: str = "rnn_data_prep"
    spark_python: str = "/opt/conda/miniconda3/bin/python"


class ConfigLoader:
    """Loads a simple key:value YAML config into typed objects."""

    def __init__(self, config_path: str | Path = "config.yaml") -> None:
        self.config_path = Path(config_path)

    def _parse_simple_yaml(self, text: str) -> Dict[str, str]:
        parsed: Dict[str, str] = {}
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or ":" not in stripped:
                continue
            key, value = stripped.split(":", 1)
            parsed[key.strip()] = value.strip()
        return parsed

    @staticmethod
    def _as_bool(value: str, default: bool) -> bool:
        if value == "":
            return default
        return value.lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _as_int(value: str, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def load(self) -> AgentConfig:
        if not self.config_path.exists():
            return AgentConfig()

        text = self.config_path.read_text(encoding="utf-8")
        data = self._parse_simple_yaml(text)

        return AgentConfig(
            agent_name=data.get("agent_name", "Sally"),
            theme=data.get("theme", "dark"),
            memory_enabled=self._as_bool(data.get("memory_enabled", "true"), True),
            auto_execute_tools=self._as_bool(data.get("auto_execute_tools", "false"), False),
            max_reasoning_loops=self._as_int(data.get("max_reasoning_loops", "5"), 5),
            llm_mode=data.get("llm_mode", "manual") or "manual",
            llm_model=data.get("llm_model", "") or "",
            default_project_id=data.get("default_project_id", "") or "",
            default_dataset_id=data.get("default_dataset_id", "") or "",
            default_folder_nm=data.get("default_folder_nm", "rnn_data_prep") or "rnn_data_prep",
            spark_python=data.get("spark_python", "/opt/conda/miniconda3/bin/python")
            or "/opt/conda/miniconda3/bin/python",
        )

    def save(self, config: AgentConfig) -> None:
        content = "\n".join(
            [
                f"agent_name: {config.agent_name}",
                f"theme: {config.theme}",
                f"memory_enabled: {'true' if config.memory_enabled else 'false'}",
                f"auto_execute_tools: {'true' if config.auto_execute_tools else 'false'}",
                f"max_reasoning_loops: {config.max_reasoning_loops}",
                f"llm_mode: {config.llm_mode}",
                f"llm_model: {config.llm_model}",
                f"default_project_id: {config.default_project_id}",
                f"default_dataset_id: {config.default_dataset_id}",
                f"default_folder_nm: {config.default_folder_nm}",
                f"spark_python: {config.spark_python}",
            ]
        )
        self.config_path.write_text(content + "\n", encoding="utf-8")
