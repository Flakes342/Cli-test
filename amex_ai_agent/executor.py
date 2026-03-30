from __future__ import annotations

import importlib
import inspect
import json
import logging
from dataclasses import dataclass
from typing import Any

from amex_ai_agent.config import AgentConfig
from amex_ai_agent.parser import ToolCall
from amex_ai_agent.tools.base import ToolExecutionContext


LOGGER = logging.getLogger(__name__)


@dataclass
class ToolResult:
    tool: str
    status: str
    output: str


class ToolExecutor:
    """Executes enabled tool calls against a modular registry."""

    REGISTRY = {
        "data_prep": "amex_ai_agent.tools.data_prep",
        "model_score": "amex_ai_agent.tools.model_score",
        "compute_metrics": "amex_ai_agent.tools.metrics",
        "rca_analysis": "amex_ai_agent.tools.rca_analysis",
        "variable_lookup": "amex_ai_agent.tools.variable_lookup",
    }

    ALIASES = {
        "metrics": "compute_metrics",
        "score_model": "model_score",
        "var_lookup": "variable_lookup",
    }

    def __init__(self, config: AgentConfig) -> None:
        self.config = config

    def list_tools(self) -> list[str]:
        return sorted(self.REGISTRY.keys())

    def resolve_tool_name(self, name: str) -> str:
        candidate = (name or "").strip()
        return self.ALIASES.get(candidate, candidate)

    def execute(
        self,
        calls: list[ToolCall],
        progress_callback: Any = None,
    ) -> list[ToolResult]:
        results: list[ToolResult] = []
        defaults = {
            "project_id": self.config.default_project_id,
            "dataset_id": self.config.default_dataset_id,
            "folder_nm": self.config.default_folder_nm,
            "spark_python": self.config.spark_python,
            "variable_catalog_path": self.config.variable_catalog_path,
        }

        for call in calls:
            canonical_name = self.resolve_tool_name(call.name)
            if canonical_name not in self.REGISTRY:
                results.append(ToolResult(call.name, "error", "Tool not registered"))
                continue

            display_name = call.name if call.name == canonical_name else f"{call.name}->{canonical_name}"
            tool_logger = logging.getLogger(f"amex_ai_agent.tools.{canonical_name}")
            context = ToolExecutionContext(
                logger=tool_logger,
                defaults=defaults,
                progress_callback=progress_callback,
            )

            try:
                module = importlib.import_module(self.REGISTRY[canonical_name])
                run_signature = inspect.signature(module.run)
                if "context" in run_signature.parameters:
                    output: dict[str, Any] = module.run(call.argument, context=context)
                else:
                    output = module.run(call.argument)

                rendered = json.dumps(output, indent=2, default=str)
                status = str(output.get("status", "success"))
                results.append(ToolResult(display_name, status, rendered))
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("Tool execution failed: %s", canonical_name)
                results.append(ToolResult(display_name, "error", str(exc)))
        return results

    def validate_registry(self) -> dict[str, str]:
        status: dict[str, str] = {}
        for tool, module_path in self.REGISTRY.items():
            try:
                importlib.import_module(module_path)
                status[tool] = "ok"
            except Exception as exc:  # noqa: BLE001
                status[tool] = f"error: {exc}"
        return status
