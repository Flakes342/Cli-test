from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict


ProgressCallback = Callable[[str], None]


@dataclass
class ToolExecutionContext:
    logger: logging.Logger
    defaults: Dict[str, Any] = field(default_factory=dict)
    progress_callback: ProgressCallback | None = None
    events: list[str] = field(default_factory=list)

    def report_progress(self, message: str) -> None:
        self.events.append(message)
        self.logger.info(message)
        if self.progress_callback is not None:
            self.progress_callback(message)
