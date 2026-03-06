from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from prompt_toolkit import PromptSession

from amex_ai_agent.ui.chat_ui import ChatUI


class LLMGateway(Protocol):
    """Single swappable interface for all model calls.

    Swap implementation here to move from copy/paste mode to direct API mode.
    """

    def invoke(self, prompt: str, label: str) -> str:
        ...


@dataclass
class ManualPasteGateway:
    """Human-in-the-loop gateway using ChatGPT Enterprise copy/paste."""

    session: PromptSession
    ui: ChatUI

    def invoke(self, prompt: str, label: str) -> str:
        self.ui.agent_message(
            f"[{label}] Paste this prompt into ChatGPT Enterprise.\n"
            "Then paste model output here and finish with a single line: END\n"
            "Tip: multi-line paste is supported.\n"
            "(Use /exit to quit app if needed).\n\n"
            f"{prompt}"
        )
        lines: list[str] = []
        while True:
            chunk = self.session.prompt("")
            parts = chunk.splitlines() or [chunk]
            for part in parts:
                if part.strip() == "END":
                    return "\n".join(lines)
                lines.append(part)


@dataclass
class ApiGateway:
    """Placeholder for future direct API calls.

    Replace this class internals once enterprise API access is available.
    """

    model_name: str = ""

    def invoke(self, prompt: str, label: str) -> str:
        raise NotImplementedError(
            "API gateway is not configured yet. Use llm_mode: manual for copy/paste mode."
        )
