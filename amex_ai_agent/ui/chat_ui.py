from __future__ import annotations

import time
from typing import Iterable

from rich.console import Console
from rich.panel import Panel
from rich.text import Text


LOGO = r"""
            :@@@=            %@     +@:
           @#                %@@% -@@@:
         %@                  %@@@@@@@@:
         %@         @@@@@+   %@ .@* +@:
         %@       #@@@@@@+ *@@@@% -@@@@@
         %@@#     #@@@ :@@@-    .@*
            :@@@= #@@@@# +@@@@@@% -@=
                  #@@@@@@+ *@@@@@@* +@:
"""


class ChatUI:
    """Presentation layer for terminal chat and status rendering."""

    def __init__(self, agent_name: str, tools: Iterable[str]) -> None:
        self.console = Console()
        self.agent_name = agent_name
        self.tools = list(tools)
        self.last_agent_message: str = ""

    def render_header(self) -> None:
        self.console.print(Panel.fit("✶ Welcome to Sally's CLI", border_style="bright_red"))
        self.console.print(Text(LOGO, style="bold #E07A5F"))

        details = (
            f"[bold white]{self.agent_name}[/bold white]\n"
            "[dim]Reasoning assistant for AMEX fraud data science workflows[/dim]\n\n"
            "[bold]Mode[/bold]: Interactive HITL (ChatGPT Enterprise copy/paste)\n"
            f"[bold]Tools[/bold]: {', '.join(self.tools)}"
        )
        self.console.print(Panel(Text.from_markup(details), border_style="cyan"))

    def user_message(self, message: str) -> None:
        self.console.print(Text(f"You > {message}", style="green"))

    def agent_message(self, message: str) -> None:
        self.last_agent_message = message
        self.console.print(Panel(Text(message), title=self.agent_name, border_style="bright_cyan"))

    def tool_log(self, message: str) -> None:
        self.console.print(Panel(Text(message), title="Tool Output", border_style="yellow"))

    def info(self, message: str) -> None:
        self.console.print(Panel(Text(message), title="Info", border_style="blue"))

    def loading_timer(self, seconds: int = 10, label: str = "Working on it") -> None:
        with self.console.status(f"[cyan]{label}... {seconds}s remaining[/cyan]") as status:
            for remaining in range(seconds, 0, -1):
                status.update(f"[cyan]{label}... {remaining}s remaining[/cyan]")
                time.sleep(1)


    def error(self, message: str) -> None:
        self.console.print(Text(message, style="red"))
