from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class SessionMemory:
    """In-memory representation of session data."""

    chat_history: List[Dict[str, Any]] = field(default_factory=list)
    tool_runs: List[Dict[str, Any]] = field(default_factory=list)
    task_summaries: List[Dict[str, Any]] = field(default_factory=list)


class MemoryStore:
    """Persistent JSON-based memory storage."""

    def __init__(
        self,
        session_path: str | Path = "memory/session.json",
        history_path: str | Path = "memory/task_history.json",
    ) -> None:
        self.session_path = Path(session_path)
        self.history_path = Path(history_path)
        self.session_path.parent.mkdir(parents=True, exist_ok=True)
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        self.state = SessionMemory()
        self._load()

    def _load(self) -> None:
        if self.session_path.exists():
            with self.session_path.open("r", encoding="utf-8") as file:
                data = json.load(file)
            self.state.chat_history = data.get("chat_history", [])
            self.state.tool_runs = data.get("tool_runs", [])
            self.state.task_summaries = data.get("task_summaries", [])

    def save(self) -> None:
        payload = {
            "chat_history": self.state.chat_history,
            "tool_runs": self.state.tool_runs,
            "task_summaries": self.state.task_summaries,
        }
        with self.session_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2)

        with self.history_path.open("w", encoding="utf-8") as file:
            json.dump(self.state.task_summaries, file, indent=2)

    def add_chat(self, role: str, message: str) -> None:
        self.state.chat_history.append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "role": role,
                "message": message,
            }
        )
        self.save()

    def add_tool_run(self, tool_name: str, argument: str, output: str, status: str) -> None:
        self.state.tool_runs.append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "tool": tool_name,
                "argument": argument,
                "output": output,
                "status": status,
            }
        )
        self.save()

    def add_task_summary(self, summary: str) -> None:
        self.state.task_summaries.append(
            {"timestamp": datetime.utcnow().isoformat(), "summary": summary}
        )
        self.save()

    def clear(self) -> None:
        self.state = SessionMemory()
        self.save()

    def context_text(self, max_items: int = 10) -> str:
        recent = self.state.chat_history[-max_items:]
        return "\n".join(
            f"{item['role'].upper()}: {item['message'][:500]}" for item in recent
        )
