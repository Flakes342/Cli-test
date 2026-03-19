from _future_ import annotations

import time
from typing import Iterable

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text


LOGO = r"""
    ███████╗ █████╗ ██╗     ██╗     ██╗   ██╗
    ██╔════╝██╔══██╗██║     ██║     ╚██╗ ██╔╝
    ███████╗███████║██║     ██║      ╚████╔╝
    ╚════██║██╔══██║██║     ██║       ╚██╔╝
    ███████║██║  ██║███████╗███████╗   ██║
    ╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝   ╚═╝

            :@@@=            %@     +@:
           @#                %@@% -@@@:
         %@                  %@@@@@@@@:
         %@         @@@@@+   %@ .@* +@:
         %@       #@@@@@@+ *@@@@% -@@@@@
         %@@#     #@@@ :@@@-    .@*
            :@@@= #@@@@# +@@@@@@% -@=
                  #@@@@@@+ @@@@@@ +@:
"""

class ChatUI:
    """Presentation layer for terminal chat and status rendering."""

    def _init_(self, agent_name: str, tools: Iterable[str]) -> None:
        self.console = Console()
        self.agent_name = agent_name
        self.tools = list(tools)
        self.last_agent_message: str = ""

    def render_header(self) -> None:
        self.console.print(Rule("[bold #D97757]SALLY[/bold #D97757]", style="#2A2A2A"))
        self.console.print(Text(LOGO, style="bold #D97757"))

        details = (
            "[bold #5C87DB]AMEX FRAUD OPS ASSISTANT[/bold #5C87DB]\n"
            "[dim][/dim]\n\n"
            "[bold #5C87DB]Mode[/bold #5C87DB]: Interactive HITL\n"
            f"[bold #5C87DB]Tools[/bold #5C87DB]: {', '.join(self.tools)}"
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

    def loading_timer(self, seconds: int = 10, label: str = "Working on it") -> None:
        with self.console.status(f"[#D97757]{label} · {seconds}s remaining[/#D97757]") as status:
            for remaining in range(seconds, 0, -1):
                status.update(f"[#D97757]{label} · {remaining}s remaining[/#D97757]")
                time.sleep(1)


    def error(self, message: str) -> None:
        self.console.print(Panel(Text(message, style="#FCA5A5"), title="[bold red]error[/bold red]", border_style="red"))