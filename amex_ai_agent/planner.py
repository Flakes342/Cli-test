from __future__ import annotations

from pathlib import Path
import re

from amex_ai_agent.prompts.templates import PROMPT_TEMPLATE, REASONING_LOOP_TEMPLATE


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

    def build_prompt(self, task: str, memory_context: str) -> str:
        file_context = self._load_file_context(task)
        full_context = memory_context
        if file_context:
            full_context = f"{memory_context}\n\nFILE CONTEXT:\n{file_context}"

        return PROMPT_TEMPLATE.format(task=task, memory=full_context.strip() or "No prior context")

    def build_reasoning_prompt(
        self,
        task: str,
        memory_context: str,
        iteration: int,
        tool_feedback: str,
    ) -> str:
        file_context = self._load_file_context(task)
        full_context = memory_context
        if file_context:
            full_context = f"{memory_context}\n\nFILE CONTEXT:\n{file_context}"

        return REASONING_LOOP_TEMPLATE.format(
            task=task,
            iteration=iteration,
            memory=full_context.strip() or "No prior context",
            tool_feedback=tool_feedback or "No tool outputs yet.",
        )
