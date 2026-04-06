from __future__ import annotations

import importlib
import logging
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter

from amex_ai_agent.config import AgentConfig
from amex_ai_agent.executor import ToolExecutor
from amex_ai_agent.llm_gateway import ApiGateway, ManualPasteGateway
from amex_ai_agent.memory import MemoryStore
from amex_ai_agent.parser import ResponseParser
from amex_ai_agent.planner import PromptPlanner
from amex_ai_agent.reasoning_graph import FraudReasoningGraph
from amex_ai_agent.ui.chat_ui import ChatUI
from amex_ai_agent.variable_catalog import VariableCatalog, VariableRecord

LOGGER = logging.getLogger(__name__)


class AgentChatApp:
    COMMANDS = [
        "/help",
        "/clear",
        "/history",
        "/tools",
        "/doctor",
        "/files",
        "/reason",
        "/memory",
        "/var",
        "/vars",
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
        self.executor = ToolExecutor(config)
        self.ui = ChatUI(config.agent_name, self.executor.list_tools())
        self.last_task: str = ""
        self._variable_catalog: VariableCatalog | None = None

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

    def _reasoning_graph(self) -> None:
        if not self.last_task:
            self.ui.error("No task found. Enter a message first.")
            return

        self.ui.agent_message("Building execution graph...")
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
            "3) ./sally run"
        )

    def _handle_command(self, command: str) -> bool:
        command = command.strip()
        if command == "/help":
            self.ui.agent_message(
                "Commands: /help, /clear, /history, /tools, /doctor, /files, /reason, /memory, "
                "/var <code>, /vars model <model>, /vars domain <domain>, /exit"
            )
            return False
        if command == "/clear":
            self.memory.clear()
            self.last_task = ""
            self.ui.agent_message("Memory cleared.")
            return False
        if command == "/history":
            for item in self.memory.state.chat_history[-20:]:
                role = str(item.get("role", "unknown"))
                message = str(item.get("message", ""))
                self.ui.agent_message(f"{role}: {message[:300]}")
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
            lines.append(f"\nVariable catalog path: {self.config.variable_catalog_path or '<not configured>'}")
            self.ui.agent_message("\n".join(lines))
            return False
        if command == "/files":
            files = [str(path) for path in Path(".").iterdir() if path.is_file()]
            self.ui.agent_message("Files:\n" + "\n".join(files))
            return False
        if command == "/reason":
            self._reasoning_graph()
            return False
        if command == "/memory":
            self.ui.agent_message(self.memory.context_text(max_items=20) or "Memory empty")
            return False
        if command.startswith("/var "):
            return self._handle_var_command(command)
        if command.startswith("/vars "):
            return self._handle_vars_command(command)
        if command == "/var" or command == "/vars":
            self.ui.error("Usage: /var <code> | /vars model <model> | /vars domain <domain>")
            return False
        if command == "/exit":
            self.ui.agent_message("Goodbye.")
            return True

        self.ui.error("Unknown command. Type /help.")
        return False

    def _handle_var_command(self, command: str) -> bool:
        code = command[len("/var ") :].strip()
        if not code:
            self.ui.error("Usage: /var <code>")
            return False

        catalog = self._load_variable_catalog()
        if catalog is None:
            return False

        record = catalog.exact_lookup(code)
        if record is None:
            self.ui.error(f"No variable found for code '{code}'.")
            return False

        self.ui.agent_message(self._format_record(record))
        return False

    def _handle_vars_command(self, command: str) -> bool:
        parts = command.split(maxsplit=2)
        if len(parts) < 3 or parts[1] not in {"model", "domain"}:
            self.ui.error("Usage: /vars model <model> | /vars domain <domain>")
            return False

        scope = parts[1]
        value = parts[2].strip()
        if not value:
            self.ui.error(f"Usage: /vars {scope} <value>")
            return False

        catalog = self._load_variable_catalog()
        if catalog is None:
            return False

        if scope == "model":
            records = catalog.filter_records(model=value)
            label = f"model={value}"
        else:
            records = catalog.filter_records(domain=value)
            label = f"domain={value}"

        if not records:
            self.ui.error(f"No variables found for {label}.")
            return False

        self.ui.agent_message(self._format_record_list(records, header=f"Variables for {label}"))
        return False

    def _load_variable_catalog(self) -> VariableCatalog | None:
        if self._variable_catalog is not None:
            return self._variable_catalog

        path = Path(self.config.variable_catalog_path)
        if not self.config.variable_catalog_path:
            self.ui.error("Variable catalog path is not configured. Update config.yaml or run ./sally init.")
            return None
        if not path.exists() or not path.is_file():
            self.ui.error(f"Variable catalog file not found: {path}")
            return None

        try:
            self._variable_catalog = VariableCatalog.from_csv(path)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Failed to load variable catalog from %s", path)
            self.ui.error(f"Failed to load variable catalog: {exc}")
            return None
        return self._variable_catalog

    @staticmethod
    def _format_record(record: VariableRecord) -> str:
        return (
            f"Variable: {record.variable}\n"
            f"Full Name: {record.full_name or '-'}\n"
            f"Description: {record.description or '-'}\n"
            f"Table: {record.table or '-'}\n"
            f"Domain: {record.domain or '-'}\n"
            f"Model: {record.model or '-'}"
        )

    def _format_record_list(self, records: list[VariableRecord], *, header: str) -> str:
        lines = [header]
        for record in records[:20]:
            lines.append(
                f"- {record.variable}: {record.full_name or '-'} "
                f"[domain={record.domain or '-'}, model={record.model or '-'}, table={record.table or '-'}]"
            )
        if len(records) > 20:
            lines.append(f"... and {len(records) - 20} more")
        return "\n".join(lines)
