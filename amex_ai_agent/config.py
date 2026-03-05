from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict


@dataclass
class AgentConfig:
    """Application-level configuration values."""

    agent_name: str = "AMEX-Agent"
    theme: str = "dark"
    memory_enabled: bool = True
    auto_execute_tools: bool = False


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

    def load(self) -> AgentConfig:
        if not self.config_path.exists():
            return AgentConfig()

        text = self.config_path.read_text(encoding="utf-8")
        data = self._parse_simple_yaml(text)

        return AgentConfig(
            agent_name=data.get("agent_name", "AMEX-Agent"),
            theme=data.get("theme", "dark"),
            memory_enabled=self._as_bool(data.get("memory_enabled", "true"), True),
            auto_execute_tools=self._as_bool(data.get("auto_execute_tools", "false"), False),
        )
