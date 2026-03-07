from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from amex_ai_agent.prompts import templates


PROMPT_FILES = {
    "plan": "plan_prompt.md",
    "routing": "routing_prompt.md",
    "reasoning_loop": "reasoning_loop_prompt.md",
    "conversation": "experimental/conversation_prompt.md",
    "evaluation": "experimental/evaluation_prompt.md",
    "intent": "experimental/intent_prompt.md",
}

FALLBACKS = {
    "plan": templates.PROMPT_TEMPLATE,
    "routing": templates.ROUTING_TEMPLATE,
    "reasoning_loop": templates.REASONING_LOOP_TEMPLATE,
    "conversation": templates.CONVERSATION_TEMPLATE,
    "evaluation": templates.EVALUATION_TEMPLATE,
    "intent": templates.INTENT_TEMPLATE,
}


@lru_cache(maxsize=None)
def get_prompt_template(name: str) -> str:
    rel = PROMPT_FILES.get(name)
    if not rel:
        raise KeyError(f"Unknown prompt template key: {name}")

    path = Path(__file__).parent / rel
    if path.exists() and path.is_file():
        return path.read_text(encoding="utf-8")

    return FALLBACKS[name]
