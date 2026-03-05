from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import List


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


class ResponseParser:
    """Parses strict response format from human-pasted LLM output."""

    PLAN_RE = re.compile(r"PLAN:\s*(.*?)\s*TOOLS:", re.DOTALL | re.IGNORECASE)
    TOOLS_RE = re.compile(r"TOOLS:\s*(.*?)\s*CODE:", re.DOTALL | re.IGNORECASE)
    CODE_RE = re.compile(r"CODE:\s*(.*?)\s*EXPLANATION:", re.DOTALL | re.IGNORECASE)
    EXPL_RE = re.compile(r"EXPLANATION:\s*(.*)$", re.DOTALL | re.IGNORECASE)

    def parse(self, text: str) -> ParsedResponse:
        parsed = ParsedResponse()

        plan_section = self._extract(self.PLAN_RE, text)
        if plan_section:
            parsed.plan = [
                line.strip("- ").strip()
                for line in plan_section.splitlines()
                if line.strip()
            ]

        tools_section = self._extract(self.TOOLS_RE, text)
        for line in tools_section.splitlines():
            match = re.search(r"-?\s*([a-zA-Z_]+)\((.*)\)", line.strip())
            if match:
                parsed.tools.append(
                    ToolCall(name=match.group(1).strip(), argument=match.group(2).strip())
                )

        parsed.code = self._extract(self.CODE_RE, text).strip()
        parsed.explanation = self._extract(self.EXPL_RE, text).strip()
        return parsed

    @staticmethod
    def _extract(pattern: re.Pattern[str], text: str) -> str:
        match = pattern.search(text)
        return match.group(1).strip() if match else ""
