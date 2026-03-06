from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from amex_ai_agent.prompts import templates


PROMPT_FILES = {
    "plan": "plan_prompt.md",
    "intent": "intent_prompt.md",
    "routing": "routing_prompt.md",
    "conversation": "conversation_prompt.md",
    "evaluation": "evaluation_prompt.md",
    "reasoning_loop": "reasoning_loop_prompt.md",
}

FALLBACKS = {
    "plan": templates.PROMPT_TEMPLATE,
    "intent": templates.INTENT_DISCOVERY_TEMPLATE,
    "routing": templates.TASK_ROUTING_TEMPLATE,
    "conversation": templates.CONVERSATION_RESPONSE_TEMPLATE,
    "evaluation": templates.EVALUATION_RESPONSE_TEMPLATE,
    "reasoning_loop": templates.REASONING_LOOP_TEMPLATE,
}


@lru_cache(maxsize=None)
def get_prompt_template(name: str) -> str:
    rel = PROMPT_FILES.get(name)
    if not rel:
        raise KeyError(f"Unknown prompt template key: {name}")

    path = Path(__file__).with_name(rel)
    if path.exists() and path.is_file():
        return path.read_text(encoding="utf-8")

    return FALLBACKS[name]
