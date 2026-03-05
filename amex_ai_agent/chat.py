from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter

from amex_ai_agent.config import AgentConfig
from amex_ai_agent.executor import ToolExecutor
from amex_ai_agent.memory import MemoryStore
from amex_ai_agent.parser import ParsedResponse, ResponseParser
from amex_ai_agent.planner import PromptPlanner
from amex_ai_agent.ui.chat_ui import ChatUI
from amex_ai_agent.ui.spinner import thinking

LOGGER = logging.getLogger(__name__)


class AgentChatApp:
    COMMANDS = ["/help", "/clear", "/history", "/tools", "/files", "/run", "/plan", "/memory", "/exit"]

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.memory = MemoryStore()
        self.planner = PromptPlanner()
        self.parser = ResponseParser()
        self.executor = ToolExecutor()
        self.ui = ChatUI(config.agent_name, self.executor.list_tools())
        self.last_task: Optional[str] = None
        self.last_parsed: Optional[ParsedResponse] = None
        words = self.COMMANDS + self.executor.list_tools()
        self.session = PromptSession(completer=WordCompleter(words, ignore_case=True))

    def start(self) -> None:
        self.ui.render_header()
        self.ui.agent_message("Type /help to view commands.")

        while True:
            raw = self.session.prompt("\nYou > ").strip()
            if not raw:
                continue
            if raw.startswith("/"):
                if self._handle_command(raw):
                    break
                continue

            self.last_task = raw
            self.memory.add_chat("user", raw)
            self.ui.user_message(raw)
            self._generate_plan(raw)

    def _generate_plan(self, task: str) -> None:
        with thinking(self.ui.console):
            prompt = self.planner.build_prompt(task=task, memory_context=self.memory.context_text())
        self.memory.add_chat("agent", prompt)
        self.ui.agent_message("Prompt generated. Paste this into ChatGPT Enterprise:\n\n" + prompt)

    def _parse_response(self) -> None:
        self.ui.agent_message("Paste ChatGPT response. End with a single line containing END")
        lines = []
        while True:
            line = self.session.prompt("")
            if line.strip() == "END":
                break
            lines.append(line)
        response_text = "\n".join(lines)

        parsed = self.parser.parse(response_text)
        self.last_parsed = parsed
        self.memory.add_chat("assistant_raw", response_text)
        self.memory.add_task_summary("; ".join(parsed.plan[:3]) or "No plan")

        plan_text = "\n".join(f"{idx+1}. {step}" for idx, step in enumerate(parsed.plan)) or "No PLAN section parsed."
        self.ui.agent_message(f"Plan parsed:\n{plan_text}")

    def _run_tools(self) -> None:
        if not self.last_parsed:
            self.ui.error("No parsed response available. Use /plan then /run.")
            return
        if not self.last_parsed.tools:
            self.ui.error("No tool calls found in parsed response.")
            return

        with thinking(self.ui.console, "Executing tools..."):
            results = self.executor.execute(self.last_parsed.tools)

        for result in results:
            self.memory.add_tool_run(result.tool, "", result.output, result.status)
            if result.status == "success":
                self.ui.tool_log(f"[tool={result.tool}]\n{result.output}")
            else:
                self.ui.error(f"[tool={result.tool}] ERROR: {result.output}")

    def _handle_command(self, command: str) -> bool:
        if command == "/help":
            self.ui.agent_message(
                "Commands: /help, /clear, /history, /tools, /files, /run, /plan, /memory, /exit"
            )
            return False
        if command == "/clear":
            self.memory.clear()
            self.last_parsed = None
            self.last_task = None
            self.ui.agent_message("Memory cleared.")
            return False
        if command == "/history":
            for item in self.memory.state.chat_history[-20:]:
                self.ui.agent_message(f"{item['role']}: {item['message'][:300]}")
            return False
        if command == "/tools":
            self.ui.agent_message("Available tools: " + ", ".join(self.executor.list_tools()))
            return False
        if command == "/files":
            files = [str(path) for path in Path('.').iterdir() if path.is_file()]
            self.ui.agent_message("Files:\n" + "\n".join(files))
            return False
        if command == "/plan":
            if not self.last_task:
                self.ui.error("No task found. Enter a message first.")
            else:
                self._generate_plan(self.last_task)
                self._parse_response()
                if self.config.auto_execute_tools:
                    self._run_tools()
            return False
        if command == "/run":
            if not self.last_parsed:
                self._parse_response()
            self._run_tools()
            return False
        if command == "/memory":
            self.ui.agent_message(self.memory.context_text(max_items=20) or "Memory empty")
            return False
        if command == "/exit":
            self.ui.agent_message("Goodbye.")
            return True

        self.ui.error("Unknown command. Type /help.")
        return False
