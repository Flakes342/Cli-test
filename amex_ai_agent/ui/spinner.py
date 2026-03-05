from __future__ import annotations

from contextlib import contextmanager

from rich.console import Console
from rich.status import Status


@contextmanager
def thinking(console: Console, text: str = "Agent is thinking..."):
    status: Status
    with console.status(f"[cyan]{text}[/cyan]") as status:
        yield status
