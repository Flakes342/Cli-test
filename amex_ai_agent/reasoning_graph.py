from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from amex_ai_agent.config import AgentConfig
from amex_ai_agent.executor import ToolExecutor
from amex_ai_agent.llm_gateway import LLMGateway
from amex_ai_agent.memory import MemoryStore
from amex_ai_agent.parser import (
    ParsedResponse,
    ResponseParser,
)
from amex_ai_agent.planner import PromptPlanner
from amex_ai_agent.ui.chat_ui import ChatUI


@dataclass
class GraphState:
    task: str
    iteration: int = 0
    tool_feedback: str = "No tool outputs yet."
    parsed: ParsedResponse | None = None
    final_answer: str = ""
    done: bool = False
    trace: List[str] = field(default_factory=list)


class FraudReasoningGraph:
    """Simplified LangGraph-style planning loop for tool-oriented workflows."""

    def __init__(
        self,
        config: AgentConfig,
        planner: PromptPlanner,
        parser: ResponseParser,
        executor: ToolExecutor,
        memory: MemoryStore,
        llm: LLMGateway,
        ui: ChatUI,
    ) -> None:
        self.config = config
        self.planner = planner
        self.parser = parser
        self.executor = executor
        self.memory = memory
        self.llm = llm
        self.ui = ui

    def run(self, task: str) -> GraphState:
        state = GraphState(task=task)
        node = "plan"

        while not state.done:
            state.trace.append(node)
            if node == "plan":
                node = self._plan_node(state)
            elif node == "tools":
                node = self._tools_node(state)
            elif node == "done":
                state.done = True
            else:
                state.final_answer = f"Unknown graph node: {node}"
                state.done = True

        return state

    def _plan_node(self, state: GraphState) -> str:
        state.iteration += 1
        prompt = self.planner.build_reasoning_prompt(
            task=state.task,
            memory_context=self.memory.context_text(max_items=20),
            iteration=state.iteration,
            tool_feedback=state.tool_feedback,
        )
        self.memory.add_chat("agent", prompt)
        response = self.llm.invoke(prompt, label=f"reasoning-iteration-{state.iteration}")
        self.memory.add_chat("assistant_raw", f"[reasoning-{state.iteration}]\n{response}")

        parsed = self.parser.parse(response)
        state.parsed = parsed
        self.memory.add_task_summary("; ".join(parsed.plan[:3]) or "No plan")

        plan_text = "\n".join(f"{idx+1}. {step}" for idx, step in enumerate(parsed.plan)) or "No PLAN section parsed."
        self.ui.agent_message(f"Plan parsed:\n{plan_text}\n\nNEXT_ACTION: {parsed.next_action}")

        if parsed.next_action == "DONE":
            state.final_answer = parsed.final_answer or parsed.explanation or "Task completed."
            self.memory.add_chat("assistant", state.final_answer)
            self._set_copyable_message(state.final_answer)
            self.ui.agent_message(f"\n{state.final_answer}")
            return "done"

        if state.iteration >= max(1, self.config.max_reasoning_loops):
            state.final_answer = (
                f"Reached max reasoning iterations ({self.config.max_reasoning_loops}). "
                "Review /memory and run /reason again if needed."
            )
            self._set_copyable_message(state.final_answer)
            self.ui.error(state.final_answer)
            return "done"

        return "tools"

    def _tools_node(self, state: GraphState) -> str:
        if not state.parsed or not state.parsed.tools:
            self.ui.tool_log("No tool calls found in parsed response.")
            state.tool_feedback = "No tool calls found in parsed response."
            return "plan"

        results = self.executor.execute(state.parsed.tools)
        rendered_results: List[str] = []
        for result in results:
            self.memory.add_tool_run(result.tool, "", result.output, result.status)
            rendered_results.append(f"[{result.tool}] ({result.status})\n{result.output}")
            if result.status == "success":
                self.ui.tool_log(f"[tool={result.tool}]\n{result.output}")
            else:
                self.ui.error(f"[tool={result.tool}] ERROR: {result.output}")

        state.tool_feedback = "\n\n".join(rendered_results) if rendered_results else "No tool results."
        return "plan"

    def _set_copyable_message(self, message: str) -> None:
        setter = getattr(self.ui, "set_copyable_message", None)
        if callable(setter):
            setter(message)
