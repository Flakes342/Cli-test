Route the task to the right execution path.
Return JSON only.

USER TASK:
{task}

INTENT ANALYSIS:
{intent_analysis}

ROUTING OPTIONS:
- conversation (general chat/help/clarification, no tools)
- evaluate (evaluate or summarize previous results/history)
- execute (new actionable work requiring planning and optional tools)

Return JSON schema:
{{
  "task_type": "conversation|evaluate|execute",
  "recommended_tools": ["tool_name"],
  "risks_or_gaps": ["..."]
}}
