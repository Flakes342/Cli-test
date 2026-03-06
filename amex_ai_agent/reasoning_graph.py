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
    intent_analysis: str = "{}"
    routing_decision: str = "{}"
    route: str = "execute"
    iteration: int = 0
    tool_feedback: str = "No tool outputs yet."
    parsed: ParsedResponse | None = None
    final_answer: str = ""
    done: bool = False
    trace: List[str] = field(default_factory=list)


class FraudReasoningGraph:
    """LangGraph style node/edge orchestration with swappable LLM gateway."""

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
        node = "intent"

        while not state.done:
            state.trace.append(node)
            if node == "intent":
                node = self._intent_node(state)
            elif node == "route":
                node = self._route_node(state)
            elif node == "conversation":
                node = self._conversation_node(state)
            elif node == "evaluate":
                node = self._evaluate_node(state)
            elif node == "plan":
                node = self._plan_node(state)
            elif node == "tools":
                node = self._tools_node(state)
            elif node == "done":
                state.done = True
            else:
                state.final_answer = f"Unknown graph node: {node}"
                state.done = True

        return state

    def _intent_node(self, state: GraphState) -> str:
        prompt = self.planner.build_intent_prompt(
            task=state.task,
            memory_context=self.memory.context_text(max_items=20),
        )
        self.memory.add_chat("agent", prompt)
        response = self.llm.invoke(prompt, label="intent-discovery")
        self.memory.add_chat("assistant_raw", f"[intent-discovery]\n{response}")
        intent = self.parser.parse_intent(response)
        state.intent_analysis = self._json_compact({
            "intent_summary": intent.intent_summary,
            "success_criteria": intent.success_criteria,
            "constraints": intent.constraints,
        })
        return "route"

    def _route_node(self, state: GraphState) -> str:
        prompt = self.planner.build_routing_prompt(task=state.task, intent_analysis=state.intent_analysis)
        self.memory.add_chat("agent", prompt)
        response = self.llm.invoke(prompt, label="task-routing")
        self.memory.add_chat("assistant_raw", f"[task-routing]\n{response}")

        routing = self.parser.parse_routing(response)
        state.routing_decision = self._json_compact({
            "task_type": routing.task_type,
            "recommended_tools": routing.recommended_tools,
            "risks_or_gaps": routing.risks_or_gaps,
        })
        state.route = self._normalize_route(routing.task_type)
        if state.route == "conversation":
            return "conversation"
        if state.route == "evaluate":
            return "evaluate"
        return "plan"

    def _conversation_node(self, state: GraphState) -> str:
        prompt = self.planner.build_conversation_prompt(
            task=state.task,
            memory_context=self.memory.context_text(max_items=20),
            intent_analysis=state.intent_analysis,
            routing_decision=state.routing_decision,
        )
        self.memory.add_chat("agent", prompt)
        response = self.llm.invoke(prompt, label="conversation-response")
        self.memory.add_chat("assistant_raw", f"[conversation-response]\n{response}")
        convo = self.parser.parse_conversation(response)
        state.final_answer = convo.message.strip() or "No response generated."
        self.memory.add_chat("assistant", state.final_answer)
        self.ui.agent_message(f"\n{state.final_answer}")
        return "done"

    def _evaluate_node(self, state: GraphState) -> str:
        prompt = self.planner.build_evaluation_prompt(
            task=state.task,
            memory_context=self.memory.context_text(max_items=25),
            tool_summary=self._recent_tool_summary(),
            intent_analysis=state.intent_analysis,
            routing_decision=state.routing_decision,
        )
        self.memory.add_chat("agent", prompt)
        response = self.llm.invoke(prompt, label="evaluation-response")
        self.memory.add_chat("assistant_raw", f"[evaluation-response]\n{response}")
        eval_result = self.parser.parse_evaluation(response)
        state.final_answer = "\n".join(
            part for part in [
                eval_result.finding_summary,
                f"Limitations: {eval_result.confidence_and_limitations}" if eval_result.confidence_and_limitations else "",
                f"Next step: {eval_result.recommended_next_step}" if eval_result.recommended_next_step else "",
            ]
            if part
        ).strip() or "No evaluation generated."
        self.memory.add_chat("assistant", state.final_answer)
        self.ui.agent_message(f"\n{state.final_answer}")
        return "done"

    def _plan_node(self, state: GraphState) -> str:
        state.iteration += 1
        prompt = self.planner.build_reasoning_prompt(
            task=state.task,
            memory_context=self.memory.context_text(max_items=20),
            iteration=state.iteration,
            tool_feedback=state.tool_feedback,
            intent_analysis=state.intent_analysis,
            routing_decision=state.routing_decision,
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
            self.ui.agent_message(f"\n{state.final_answer}")
            return "done"

        if state.iteration >= max(1, self.config.max_reasoning_loops):
            state.final_answer = (
                f"Reached max reasoning iterations ({self.config.max_reasoning_loops}). "
                "Review /memory and run /reason again if needed."
            )
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

    @staticmethod
    def _normalize_route(task_type: str) -> str:
        value = (task_type or "execute").strip().lower().replace("-", "_")
        if value in {"conversation", "chat", "normal_conversation"}:
            return "conversation"
        if value in {"evaluate", "evaluation", "result_evaluation", "review_results"}:
            return "evaluate"
        return "execute"

    @staticmethod
    def _json_compact(payload: dict) -> str:
        import json

        return json.dumps(payload, separators=(",", ":"))

    def _recent_tool_summary(self, limit: int = 8) -> str:
        rows = self.memory.state.tool_runs[-limit:]
        if not rows:
            return "No prior tool runs found."
        return "\n".join(
            f"- {row.get('timestamp', '')} | {row.get('tool', '')} | {row.get('status', '')} | {str(row.get('output', ''))[:250]}"
            for row in rows
        )
