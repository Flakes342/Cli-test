from __future__ import annotations

import json
from dataclasses import dataclass, field

from amex_ai_agent.config import AgentConfig
from amex_ai_agent.executor import ToolExecutor
from amex_ai_agent.llm_gateway import LLMGateway
from amex_ai_agent.memory import MemoryStore
from amex_ai_agent.parser import ParsedResponse, ResponseParser, RoutingResponse
from amex_ai_agent.planner import PromptPlanner
from amex_ai_agent.ui.chat_ui import ChatUI


@dataclass
class GraphState:
    task: str
    iteration: int = 0
    tool_feedback: str = "No tool outputs yet."
    parsed: ParsedResponse | None = None
    routing: RoutingResponse | None = None
    final_answer: str = ""
    last_tool_signature: str = ""
    repeated_tool_call_count: int = 0
    trace: list[str] = field(default_factory=list)


class FraudReasoningGraph:
    """Lean route -> reason -> tools loop for the CLI agent."""

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

    def _tool_signature(self, parsed: ParsedResponse | None) -> str:
        if not parsed or not parsed.tools:
            return ""
        payload = [{"name": tool.name, "argument": tool.argument} for tool in parsed.tools]
        return json.dumps(payload, sort_keys=True)

    def run(self, task: str) -> GraphState:
        state = GraphState(task=task)
        state.routing = self._route(task)

        for iteration in range(1, max(1, self.config.max_reasoning_loops) + 1):
            state.iteration = iteration
            state.trace.append(f"reason:{iteration}")
            parsed = self._reason(task, state)
            state.parsed = parsed

            if parsed.next_action == "DONE":
                state.final_answer = parsed.final_answer or parsed.explanation or "Task completed."
                self.memory.add_chat("assistant", state.final_answer)
                self.ui.agent_message(state.final_answer)
                return state

            if not parsed.tools:
                state.final_answer = parsed.final_answer or parsed.explanation or "No tools requested."
                self.memory.add_chat("assistant", state.final_answer)
                self.ui.agent_message(state.final_answer)
                return state

            signature = self._tool_signature(parsed)
            if signature and signature == state.last_tool_signature:
                state.repeated_tool_call_count += 1
            else:
                state.last_tool_signature = signature
                state.repeated_tool_call_count = 0

            if state.repeated_tool_call_count >= 1:
                state.final_answer = "Detected repeated identical tool call. Stop or change the request."
                self.memory.add_chat("assistant", state.final_answer)
                self.ui.error(state.final_answer)
                return state

            state.tool_feedback = self._run_tools(parsed)

        state.final_answer = (
            f"Reached max planning iterations ({self.config.max_reasoning_loops}). "
            "Review /memory and run /reason again if needed."
        )
        self.ui.error(state.final_answer)
        return state

    def _route(self, task: str) -> RoutingResponse:
        prompt = self.planner.build_routing_prompt(task=task, intent_analysis="Initial request")
        self.memory.add_chat("agent", prompt)
        response = self.llm.invoke(prompt, label="routing-stage")
        self.memory.add_chat("assistant_raw", f"[routing]\n{response}")
        routing = self.parser.parse_routing(response)
        route = routing.task_type if routing.task_type in {"conversation", "evaluate", "execute"} else "execute"
        self.ui.agent_message(f"Route selected: {route}")
        return routing

    def _reason(self, task: str, state: GraphState) -> ParsedResponse:
        prompt = self.planner.build_plan_prompt(
            task=task,
            memory_context=self.memory.context_text(max_items=20),
            routing=state.routing,
            iteration=state.iteration,
            tool_feedback=state.tool_feedback,
        )
        self.memory.add_chat("agent", prompt)
        response = self.llm.invoke(prompt, label=f"plan-iteration-{state.iteration}")
        self.memory.add_chat("assistant_raw", f"[plan-{state.iteration}]\n{response}")

        parsed = self.parser.parse(response)
        plan_summary = "; ".join(parsed.plan[:3]) or parsed.explanation or "No plan"
        self.memory.add_task_summary(plan_summary)

        plan_text = "\n".join(f"{idx + 1}. {step}" for idx, step in enumerate(parsed.plan)) or "No PLAN section parsed."
        self.ui.agent_message(f"Plan parsed:\n{plan_text}\n\nNEXT_ACTION: {parsed.next_action}")
        return parsed

    def _run_tools(self, parsed: ParsedResponse) -> str:
        tool_names = ", ".join(call.name for call in parsed.tools)
        self.ui.info(f"Running tool(s): {tool_names}")

        with self.ui.live_status("Tool run starting...") as status:
            results = self.executor.execute(parsed.tools, progress_callback=status.update)

        rendered_results: list[str] = []
        for result in results:
            self.memory.add_tool_run(result.tool, "", result.output, result.status)
            rendered_results.append(f"[{result.tool}] ({result.status})\n{result.output}")
            if result.status in {"completed", "ready", "success", "not_ready", "needs_user_input"}:
                self.ui.tool_log(f"[tool={result.tool}]\n{result.output}")
            else:
                self.ui.error(f"[tool={result.tool}] ERROR: {result.output}")

        return "\n\n".join(rendered_results) if rendered_results else "No tool results."
