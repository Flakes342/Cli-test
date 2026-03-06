from __future__ import annotations

from pathlib import Path
import re

from amex_ai_agent.prompts.registry import get_prompt_template


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

    def build_prompt(self, task: str, memory_context: str) -> str:
        return get_prompt_template("plan").format(
            task=task,
            memory=self._build_full_context(task, memory_context),
        )

    def build_intent_prompt(self, task: str, memory_context: str) -> str:
        return get_prompt_template("intent").format(
            task=task,
            memory=self._build_full_context(task, memory_context),
        )

    def build_routing_prompt(self, task: str, intent_analysis: str) -> str:
        return get_prompt_template("routing").format(
            task=task,
            intent_analysis=intent_analysis.strip() or "Not available",
        )

    def build_conversation_prompt(
        self,
        task: str,
        memory_context: str,
        intent_analysis: str,
        routing_decision: str,
    ) -> str:
        return get_prompt_template("conversation").format(
            task=task,
            intent_analysis=intent_analysis.strip() or "Not available",
            routing_decision=routing_decision.strip() or "Not available",
            memory=self._build_full_context(task, memory_context),
        )

    def build_evaluation_prompt(
        self,
        task: str,
        memory_context: str,
        tool_summary: str,
        intent_analysis: str,
        routing_decision: str,
    ) -> str:
        return get_prompt_template("evaluation").format(
            task=task,
            intent_analysis=intent_analysis.strip() or "Not available",
            routing_decision=routing_decision.strip() or "Not available",
            memory=self._build_full_context(task, memory_context),
            tool_summary=tool_summary.strip() or "No prior tool runs found.",
        )

    def build_reasoning_prompt(
        self,
        task: str,
        memory_context: str,
        iteration: int,
        tool_feedback: str,
        intent_analysis: str,
        routing_decision: str,
    ) -> str:
        return get_prompt_template("reasoning_loop").format(
            task=task,
            intent_analysis=intent_analysis.strip() or "Not available",
            routing_decision=routing_decision.strip() or "Not available",
            iteration=iteration,
            memory=self._build_full_context(task, memory_context),
            tool_feedback=tool_feedback or "No tool outputs yet.",
        )
