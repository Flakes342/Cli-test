from __future__ import annotations

from typing import Iterable

from rich.console import Console
from rich.panel import Panel
from rich.text import Text


class ChatUI:
    """Presentation layer for terminal chat and status rendering."""

    def __init__(self, agent_name: str, tools: Iterable[str]) -> None:
        self.console = Console()
        self.agent_name = agent_name
        self.tools = list(tools)

    def render_header(self) -> None:
        content = (
            f"Mode: Interactive Chat\n"
            f"Tools: {', '.join(self.tools)}"
        )
        self.console.print(Panel.fit(content, title=self.agent_name, border_style="cyan"))

    def user_message(self, message: str) -> None:
        self.console.print(Text(f"You > {message}", style="green"))

    def agent_message(self, message: str) -> None:
        self.console.print(Text(f"Agent >\n{message}", style="cyan"))

    def tool_log(self, message: str) -> None:
        self.console.print(Text(message, style="yellow"))

    def error(self, message: str) -> None:
        self.console.print(Text(message, style="red"))
