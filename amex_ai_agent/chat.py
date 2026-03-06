from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Optional

try:
    import pyperclip
except Exception:  # noqa: BLE001
    pyperclip = None
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter

from amex_ai_agent.config import AgentConfig
from amex_ai_agent.executor import ToolExecutor
from amex_ai_agent.llm_gateway import ApiGateway, ManualPasteGateway
from amex_ai_agent.memory import MemoryStore
from amex_ai_agent.parser import ParsedResponse, ResponseParser
from amex_ai_agent.planner import PromptPlanner
from amex_ai_agent.reasoning_graph import FraudReasoningGraph
from amex_ai_agent.ui.chat_ui import ChatUI
from amex_ai_agent.ui.spinner import thinking

LOGGER = logging.getLogger(__name__)


class AgentChatApp:
    COMMANDS = [
        "/help",
        "/clear",
        "/history",
        "/tools",
        "/doctor",
        "/files",
        "/run",
        "/plan",
        "/reason",
        "/memory",
        "/copy",
        "/prompts",
        "/exit",
    ]

    REQUIRED_PACKAGES = {
        "pandas": "pandas",
        "numpy": "numpy",
        "scikit-learn": "sklearn",
        "python-pptx": "pptx",
    }

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

        if self.config.llm_mode.lower() == "api":
            self.llm = ApiGateway(model_name=self.config.llm_model)
        else:
            self.llm = ManualPasteGateway(session=self.session, ui=self.ui)

        self.graph = FraudReasoningGraph(
            config=self.config,
            planner=self.planner,
            parser=self.parser,
            executor=self.executor,
            memory=self.memory,
            llm=self.llm,
            ui=self.ui,
        )

    def start(self) -> None:
        self.ui.render_header()
        self.ui.agent_message("Type /help to view commands.")
        self._show_preflight_warnings()

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
            self._reasoning_graph()

    def _generate_plan(self, task: str) -> None:
        with thinking(self.ui.console):
            prompt = self.planner.build_prompt(task=task, memory_context=self.memory.context_text())
        self.memory.add_chat("agent", prompt)
        self.ui.set_copyable_message(prompt)
        self.ui.agent_message("Prompt generated. Paste this into ChatGPT Enterprise:\n\n" + prompt)

    def _collect_model_response(self) -> ParsedResponse:
        self.ui.agent_message("Paste ChatGPT response. End with a single line containing END")
        lines = []
        while True:
            chunk = self.session.prompt("")
            parts = chunk.splitlines() or [chunk]
            stop = False
            for part in parts:
                if part.strip() == "END":
                    stop = True
                    break
                lines.append(part)
            if stop:
                break
        response_text = "\n".join(lines)

        parsed = self.parser.parse(response_text)
        self.last_parsed = parsed
        self.memory.add_chat("assistant_raw", response_text)
        self.memory.add_task_summary("; ".join(parsed.plan[:3]) or "No plan")

        plan_text = "\n".join(f"{idx+1}. {step}" for idx, step in enumerate(parsed.plan)) or "No PLAN section parsed."
        summary = f"Plan parsed:\n{plan_text}\n\nNEXT_ACTION: {parsed.next_action}"
        self.ui.set_copyable_message(summary)
        self.ui.agent_message(summary)
        return parsed

    def _run_tools(self, parsed: Optional[ParsedResponse] = None) -> str:
        active = parsed or self.last_parsed
        if not active:
            self.ui.error("No parsed response available. Use /plan or /reason first.")
            return ""
        if not active.tools:
            self.ui.tool_log("No tool calls found in parsed response.")
            return ""

        with thinking(self.ui.console, "Executing tools..."):
            results = self.executor.execute(active.tools)

        rendered_results = []
        for result in results:
            self.memory.add_tool_run(result.tool, "", result.output, result.status)
            rendered_results.append(f"[{result.tool}] ({result.status})\n{result.output}")
            if result.status == "success":
                self.ui.tool_log(f"[tool={result.tool}]\n{result.output}")
            else:
                self.ui.error(f"[tool={result.tool}] ERROR: {result.output}")
        return "\n\n".join(rendered_results)

    def _reasoning_graph(self) -> None:
        if not self.last_task:
            self.ui.error("No task found. Enter a message first.")
            return

        self.ui.agent_message("Running reasoning flow...")
        self.graph.run(self.last_task)

    def _preflight_checks(self) -> dict[str, dict[str, str]]:
        packages: dict[str, str] = {}
        for label, module_name in self.REQUIRED_PACKAGES.items():
            try:
                importlib.import_module(module_name)
                packages[label] = "ok"
            except Exception as exc:  # noqa: BLE001
                packages[label] = f"missing: {exc}"

        tools = self.executor.validate_registry()
        return {"packages": packages, "tools": tools}

    def _show_preflight_warnings(self) -> None:
        checks = self._preflight_checks()
        missing = [f"{name} ({status})" for name, status in checks["packages"].items() if status != "ok"]
        broken_tools = [f"{name} ({status})" for name, status in checks["tools"].items() if status != "ok"]

        if not missing and not broken_tools:
            return

        if missing:
            self.ui.error("Environment warning: missing packages -> " + ", ".join(missing))
        if broken_tools:
            self.ui.error("Tool registry warning: " + ", ".join(broken_tools))

        self.ui.agent_message(
            "Setup hint:\n"
            "1) mamba env create -f environment.yml\n"
            "2) mamba activate amex-ai-agent\n"
            "3) python agent.py"
        )

    def _latest_copy_payload(self) -> str:
        if self.ui.last_copyable_message.strip():
            return self.ui.last_copyable_message

        # Prefer final assistant answers stored in memory over UI status panels like graph traces.
        for item in reversed(self.memory.state.chat_history):
            if item.get("role") == "assistant" and str(item.get("message", "")).strip():
                return str(item.get("message", ""))

        if self.last_parsed:
            if self.last_parsed.final_answer.strip():
                return self.last_parsed.final_answer
            if self.last_parsed.explanation.strip():
                return self.last_parsed.explanation

        return self.ui.last_agent_message

    def _copy_latest_output(self) -> None:
        payload = self._latest_copy_payload().strip()
        if not payload:
            self.ui.error("No agent output available to copy yet.")
            return
        if pyperclip is None:
            self.ui.error("Clipboard dependency not available. Install pyperclip in the conda env.")
            return
        try:
            pyperclip.copy(payload)
            self.ui.copied_notice()
        except Exception as exc:  # noqa: BLE001
            self.ui.error(
                "Clipboard copy failed. If running over SSH/remote shell, clipboard may be unavailable. "
                f"Details: {exc}"
            )

    def _handle_command(self, command: str) -> bool:
        if command == "/help":
            self.ui.agent_message(
                "Commands: /help, /clear, /history, /tools, /doctor, /files, /run, /plan, /reason, /memory, /copy, /prompts, /exit"
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
        if command == "/doctor":
            checks = self._preflight_checks()
            lines = ["Package checks:"]
            lines.extend(f"- {name}: {status}" for name, status in checks["packages"].items())
            lines.append("\nTool registry checks:")
            lines.extend(f"- {name}: {status}" for name, status in checks["tools"].items())
            self.ui.agent_message("\n".join(lines))
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
                parsed = self._collect_model_response()
                if self.config.auto_execute_tools:
                    self._run_tools(parsed)
            return False
        if command == "/reason":
            self._reasoning_graph()
            return False
        if command == "/run":
            if not self.last_parsed:
                parsed = self._collect_model_response()
                self._run_tools(parsed)
            else:
                self._run_tools(self.last_parsed)
            return False
        if command == "/memory":
            self.ui.agent_message(self.memory.context_text(max_items=20) or "Memory empty")
            return False
        if command == "/copy":
            self._copy_latest_output()
            return False
        if command == "/prompts":
            self.ui.agent_message(
                "Prompt usage:\n"
                "- Active runtime: reasoning_loop_prompt.md (normal chat + /reason)\n"
                "- /plan: uses same reasoning-loop contract via planner alias\n"
                "- Experimental (moved): prompts/experimental/{intent,routing,conversation,evaluation}_prompt.md"
            )
            return False
        if command == "/exit":
            self.ui.agent_message("Goodbye.")
            return True

        self.ui.error("Unknown command. Type /help.")
        return False
