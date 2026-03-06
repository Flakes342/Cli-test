from __future__ import annotations

import importlib
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List

from amex_ai_agent.parser import ToolCall

LOGGER = logging.getLogger(__name__)


@dataclass
class ToolResult:
    tool: str
    status: str
    output: str


class ToolExecutor:
    """Executes tool calls against a modular registry."""

    REGISTRY = {
        "data_prep": "amex_ai_agent.tools.data_prep",
        "rca_analysis": "amex_ai_agent.tools.rca_analysis",
        "case_review": "amex_ai_agent.tools.case_review",
        "alert_rationalization": "amex_ai_agent.tools.alerts",
        "compute_metrics": "amex_ai_agent.tools.metrics",
        "generate_ppt": "amex_ai_agent.tools.ppt_generator",
    }

    ALIASES = {
        "metrics": "compute_metrics",
    }

    def list_tools(self) -> List[str]:
        return sorted(self.REGISTRY.keys())

    def resolve_tool_name(self, name: str) -> str:
        candidate = (name or "").strip()
        return self.ALIASES.get(candidate, candidate)

    def execute(self, calls: List[ToolCall]) -> List[ToolResult]:
        results: List[ToolResult] = []
        for call in calls:
            canonical_name = self.resolve_tool_name(call.name)
            if canonical_name not in self.REGISTRY:
                results.append(ToolResult(call.name, "error", "Tool not registered"))
                continue

            try:
                module = importlib.import_module(self.REGISTRY[canonical_name])
                output: Dict[str, Any] = module.run(call.argument)
                rendered = json.dumps(output, indent=2, default=str)
                display_name = call.name if call.name == canonical_name else f"{call.name}->{canonical_name}"
                results.append(ToolResult(display_name, "success", rendered))
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("Tool execution failed: %s", canonical_name)
                results.append(ToolResult(canonical_name, "error", str(exc)))
        return results

    def validate_registry(self) -> Dict[str, str]:
        """Return registry validation results keyed by tool name."""
        status: Dict[str, str] = {}
        for tool, module_path in self.REGISTRY.items():
            try:
                importlib.import_module(module_path)
                status[tool] = "ok"
            except Exception as exc:  # noqa: BLE001
                status[tool] = f"error: {exc}"
        return status
