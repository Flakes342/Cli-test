from __future__ import annotations

from typing import Iterable

from rich.console import Console
from rich.panel import Panel
from rich.text import Text


LOGO = r"""
███████╗██████╗  █████╗ ██╗   ██╗██████╗
██╔════╝██╔══██╗██╔══██╗██║   ██║██╔══██╗
█████╗  ██████╔╝███████║██║   ██║██████╔╝
██╔══╝  ██╔══██╗██╔══██║██║   ██║██╔══██╗
██║     ██║  ██║██║  ██║╚██████╔╝██║  ██║
╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝

 ███████╗ ██████╗ ██████╗  ██████╗ ███████╗
 ██╔════╝██╔═══██╗██╔══██╗██╔════╝ ██╔════╝
 █████╗  ██║   ██║██████╔╝██║  ███╗█████╗
 ██╔══╝  ██║   ██║██╔══██╗██║   ██║██╔══╝
 ██║     ╚██████╔╝██║  ██║╚██████╔╝███████╗
 ╚═╝      ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝
"""


class ChatUI:
    """Presentation layer for terminal chat and status rendering."""

    def __init__(self, agent_name: str, tools: Iterable[str]) -> None:
        self.console = Console()
        self.agent_name = agent_name
        self.tools = list(tools)

    def render_header(self) -> None:
        self.console.print(Panel.fit("✶ Welcome to FraudForge CLI", border_style="bright_red"))
        self.console.print(Text(LOGO, style="bold #e07a5f"))

        details = (
            f"[bold white]{self.agent_name}[/bold white]\n"
            "[dim]Reasoning assistant for AMEX fraud data science workflows[/dim]\n\n"
            "[bold]Mode[/bold]: Interactive HITL (ChatGPT Enterprise copy/paste)\n"
            f"[bold]Tools[/bold]: {', '.join(self.tools)}"
        )
        self.console.print(Panel(details, border_style="cyan"))

    def user_message(self, message: str) -> None:
        self.console.print(Text(f"You > {message}", style="green"))

    def agent_message(self, message: str) -> None:
        self.console.print(Panel(message, title="Agent", border_style="bright_cyan"))

    def tool_log(self, message: str) -> None:
        self.console.print(Panel(message, title="Tool Output", border_style="yellow"))

    def error(self, message: str) -> None:
        self.console.print(Text(message, style="red"))
