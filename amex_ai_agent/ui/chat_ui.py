from __future__ import annotations

from contextlib import contextmanager
from typing import Iterable, Iterator

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.status import Status
from rich.text import Text


LOGO = r"""
    ███████╗ █████╗ ██╗     ██╗     ██╗   ██╗
    ██╔════╝██╔══██╗██║     ██║     ╚██╗ ██╔╝
    ███████╗███████║██║     ██║      ╚████╔╝
    ╚════██║██╔══██║██║     ██║       ╚██╔╝
    ███████║██║  ██║███████╗███████╗   ██║
    ╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝   ╚═╝
"""


class LiveStatus:
    def __init__(self, status: Status) -> None:
        self._status = status

    def update(self, message: str) -> None:
        self._status.update(f"[#D97757]{message}[/#D97757]")


class ChatUI:
    """Presentation layer for terminal chat and status rendering."""

    def __init__(self, agent_name: str, tools: Iterable[str]) -> None:
        self.console = Console()
        self.agent_name = agent_name
        self.tools = list(tools)
        self.last_agent_message = ""

    def render_header(self) -> None:
        self.console.print(Rule("[bold #D97757]SALLY[/bold #D97757]", style="#2A2A2A"))
        self.console.print(Text(LOGO, style="bold #D97757"))

        details = (
            "[bold #5C87DB]Fraud workflow orchestration CLI[/bold #5C87DB]\n"
            "[bold #5C87DB]Mode[/bold #5C87DB]: Interactive HITL\n"
            f"[bold #5C87DB]Enabled tools[/bold #5C87DB]: {', '.join(self.tools)}"
        )
        self.console.print(
            Panel(
                Text.from_markup(details),
                border_style="#3A3A3A",
                title="[bold #D97757]System[/bold #D97757]",
                title_align="left",
            )
        )

    def user_message(self, message: str) -> None:
        self.console.print(
            Panel(
                Text(message, style="#0A0A0A"),
                title="[bold #9CA3AF]you[/bold #9CA3AF]",
                title_align="left",
                border_style="#4B5563",
            )
        )

    def agent_message(self, message: str) -> None:
        self.last_agent_message = message
        self.console.print(
            Panel(
                Text(message, style="#0A0A0A"),
                title=f"[bold #D97757]{self.agent_name.lower()}[/bold #D97757]",
                title_align="left",
                border_style="#D97757",
            )
        )

    def tool_log(self, message: str) -> None:
        self.console.print(
            Panel(
                Text(message, style="#FCD34D"),
                title="[bold #F59E0B]tool output[/bold #F59E0B]",
                title_align="left",
                border_style="#B45309",
            )
        )

    def info(self, message: str) -> None:
        self.console.print(
            Panel(
                Text(message, style="#BFDBFE"),
                title="[bold #60A5FA]info[/bold #60A5FA]",
                title_align="left",
                border_style="#1D4ED8",
            )
        )

    @contextmanager
    def live_status(self, initial_message: str) -> Iterator[LiveStatus]:
        with self.console.status(f"[#D97757]{initial_message}[/#D97757]") as status:
            yield LiveStatus(status)

    def error(self, message: str) -> None:
        self.console.print(
            Panel(
                Text(message, style="#FCA5A5"),
                title="[bold red]error[/bold red]",
                border_style="red",
            )
        )
