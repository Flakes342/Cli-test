from __future__ import annotations

from pathlib import Path
import re

from amex_ai_agent.prompts.registry import get_prompt_template
from amex_ai_agent.parser import RoutingResponse


class PromptPlanner:
    """Builds structured prompts and enriches with file context."""

    def _extract_file_mentions(self, text: str) -> list[str]:
        return re.findall(r"@([^\s]+)", text)

    def _load_file_context(self, task: str) -> str:
        contexts: list[str] = []
        for file_ref in self._extract_file_mentions(task):
            path = Path(file_ref)
            if not path.exists() or not path.is_file():
                contexts.append(f"File not found: {file_ref}")
                continue

            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                contexts.append(
                    f"\n--- BEGIN FILE {file_ref} ---\n{content[:4000]}\n--- END FILE {file_ref} ---"
                )
            except Exception as exc:
                contexts.append(f"Failed to read {file_ref}: {exc}")
        return "\n".join(contexts)

    def _build_full_context(self, task: str, memory_context: str) -> str:
        file_context = self._load_file_context(task)
        full_context = memory_context
        if file_context:
            full_context = f"{memory_context}\n\nFILE CONTEXT:\n{file_context}"
        return full_context.strip() or "No prior context"

    def build_plan_prompt(
        self,
        task: str,
        memory_context: str,
        routing: RoutingResponse | None,
        iteration: int,
        tool_feedback: str,
    ) -> str:
        route = routing.task_type if routing else "execute"
        recommended = ", ".join(routing.recommended_tools) if routing and routing.recommended_tools else "none"
        gaps = "; ".join(routing.risks_or_gaps) if routing and routing.risks_or_gaps else "none"
        return get_prompt_template("plan").format(
            task=task,
            memory=self._build_full_context(task, memory_context),
            route=route,
            recommended_tools=recommended,
            risks_or_gaps=gaps,
            iteration=iteration,
            tool_feedback=tool_feedback or "No tool outputs yet.",
        )

    def build_routing_prompt(self, task: str, intent_analysis: str) -> str:
        return get_prompt_template("routing").format(
            task=task,
            intent_analysis=intent_analysis or "No intent analysis available.",
        )
