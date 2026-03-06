from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict


@dataclass
class AgentConfig:
    """Application-level configuration values."""

    agent_name: str = "FraudForge"
    theme: str = "dark"
    memory_enabled: bool = True
    auto_execute_tools: bool = False
    max_reasoning_loops: int = 5
    llm_mode: str = "manual"
    llm_model: str = ""


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
            agent_name=data.get("agent_name", "FraudForge"),
            theme=data.get("theme", "dark"),
            memory_enabled=self._as_bool(data.get("memory_enabled", "true"), True),
            auto_execute_tools=self._as_bool(data.get("auto_execute_tools", "false"), False),
            max_reasoning_loops=self._as_int(data.get("max_reasoning_loops", "5"), 5),
            llm_mode=data.get("llm_mode", "manual") or "manual",
            llm_model=data.get("llm_model", "") or "",
        )
