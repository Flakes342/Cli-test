from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import Any, List


@dataclass
class ToolCall:
    name: str
    argument: str


@dataclass
class ParsedResponse:
    plan: List[str] = field(default_factory=list)
    tools: List[ToolCall] = field(default_factory=list)
    code: str = ""
    explanation: str = ""
    next_action: str = "CONTINUE"
    final_answer: str = ""


@dataclass
class IntentResponse:
    intent_summary: str = ""
    success_criteria: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)


@dataclass
class RoutingResponse:
    task_type: str = "execute"
    recommended_tools: List[str] = field(default_factory=list)
    risks_or_gaps: List[str] = field(default_factory=list)


@dataclass
class ConversationResponse:
    message: str = ""


@dataclass
class EvaluationResponse:
    finding_summary: str = ""
    confidence_and_limitations: str = ""
    recommended_next_step: str = ""


class ResponseParser:
    """Parses JSON-first responses from human-pasted LLM output."""

    def parse(self, text: str) -> ParsedResponse:
        payload = self._extract_json_payload(text)
        parsed = ParsedResponse()
        if not isinstance(payload, dict):
            return parsed

        plan = payload.get("plan", [])
        if isinstance(plan, list):
            parsed.plan = [str(item).strip() for item in plan if str(item).strip()]

        tools = payload.get("tools", [])
        if isinstance(tools, list):
            for item in tools:
                if isinstance(item, dict):
                    name = str(item.get("name", "")).strip()
                    raw_argument = item.get("argument", "")
                    if isinstance(raw_argument, (dict, list)):
                        argument = json.dumps(raw_argument)
                    else:
                        argument = str(raw_argument).strip()
                    if name:
                        parsed.tools.append(ToolCall(name=name, argument=argument))

        parsed.code = str(payload.get("code", "") or "").strip()
        parsed.explanation = str(payload.get("explanation", "") or "").strip()

        next_action = str(payload.get("next_action", "CONTINUE") or "CONTINUE").upper().strip()
        parsed.next_action = next_action if next_action in {"CONTINUE", "DONE"} else "CONTINUE"

        parsed.final_answer = str(payload.get("final_answer", "") or "").strip()
        return parsed

    def parse_intent(self, text: str) -> IntentResponse:
        payload = self._extract_json_payload(text)
        if not isinstance(payload, dict):
            return IntentResponse(intent_summary=text.strip())

        criteria = payload.get("success_criteria", [])
        constraints = payload.get("constraints", [])
        return IntentResponse(
            intent_summary=str(payload.get("intent_summary", "") or "").strip(),
            success_criteria=[str(item).strip() for item in criteria] if isinstance(criteria, list) else [],
            constraints=[str(item).strip() for item in constraints] if isinstance(constraints, list) else [],
        )

    def parse_routing(self, text: str) -> RoutingResponse:
        payload = self._extract_json_payload(text)
        if not isinstance(payload, dict):
            return RoutingResponse(task_type="execute")

        tools = payload.get("recommended_tools", [])
        gaps = payload.get("risks_or_gaps", [])
        return RoutingResponse(
            task_type=str(payload.get("task_type", "execute") or "execute").strip().lower(),
            recommended_tools=[str(item).strip() for item in tools] if isinstance(tools, list) else [],
            risks_or_gaps=[str(item).strip() for item in gaps] if isinstance(gaps, list) else [],
        )

    def parse_conversation(self, text: str) -> ConversationResponse:
        payload = self._extract_json_payload(text)
        if isinstance(payload, dict) and payload.get("message"):
            return ConversationResponse(message=str(payload.get("message", "")).strip())
        return ConversationResponse(message=text.strip())

    def parse_evaluation(self, text: str) -> EvaluationResponse:
        payload = self._extract_json_payload(text)
        if not isinstance(payload, dict):
            return EvaluationResponse(finding_summary=text.strip())
        return EvaluationResponse(
            finding_summary=str(payload.get("finding_summary", "") or "").strip(),
            confidence_and_limitations=str(payload.get("confidence_and_limitations", "") or "").strip(),
            recommended_next_step=str(payload.get("recommended_next_step", "") or "").strip(),
        )

    def _extract_json_payload(self, text: str) -> Any:
        stripped = text.strip()
        if not stripped:
            return None

        # direct JSON
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

        repaired = self._repair_argument_string_json(stripped)
        if repaired != stripped:
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                pass

        # fenced code block
        fence_match = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", stripped, re.DOTALL | re.IGNORECASE)
        if fence_match:
            candidate = fence_match.group(1)
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

        # first top-level object/array chunk
        for opener, closer in (("{", "}"), ("[", "]")):
            start = stripped.find(opener)
            end = stripped.rfind(closer)
            if start != -1 and end > start:
                candidate = stripped[start : end + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    repaired_candidate = self._repair_argument_string_json(candidate)
                    try:
                        return json.loads(repaired_candidate)
                    except json.JSONDecodeError:
                        pass
                    continue
        return None

    def _repair_argument_string_json(self, text: str) -> str:
        pattern = re.compile(r'("argument"\s*:\s*)"(\{.*?\})"', re.DOTALL)

        def _escape_match(match: re.Match[str]) -> str:
            prefix = match.group(1)
            inner = match.group(2)
            escaped = inner.replace('\\', '\\\\').replace('"', '\\"')
            return f'{prefix}"{escaped}"'

        return pattern.sub(_escape_match, text)
