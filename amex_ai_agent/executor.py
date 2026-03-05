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
        "sql_query": "amex_ai_agent.tools.sql_query",
    }

    def list_tools(self) -> List[str]:
        return sorted(self.REGISTRY.keys())

    def execute(self, calls: List[ToolCall]) -> List[ToolResult]:
        results: List[ToolResult] = []
        for call in calls:
            if call.name not in self.REGISTRY:
                results.append(ToolResult(call.name, "error", "Tool not registered"))
                continue

            try:
                module = importlib.import_module(self.REGISTRY[call.name])
                output: Dict[str, Any] = module.run(call.argument)
                rendered = json.dumps(output, indent=2, default=str)
                results.append(ToolResult(call.name, "success", rendered))
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("Tool execution failed: %s", call.name)
                results.append(ToolResult(call.name, "error", str(exc)))
        return results
