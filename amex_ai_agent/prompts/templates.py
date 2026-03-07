from __future__ import annotations

PROMPT_TEMPLATE = """You are an enterprise AI assistant helping a fraud analyst in a restricted environment.
You cannot call tools directly. A local CLI agent will execute tools for you.
Return JSON only (no markdown, no prose outside JSON).

TASK:
{task}

CONTEXT:
{memory}

LATEST TOOL OUTPUTS:
No tool outputs yet.

AVAILABLE TOOLS:
data_prep(dataset_path_or_instruction)
rca_analysis(transcript_or_notes)
case_review(case_json_or_notes)
alert_rationalization(alert_csv_path_or_instruction)
compute_metrics(model_scoring_csv_path)
generate_ppt(summary_text)

Return JSON with this schema:
{{
  "plan": ["step 1", "step 2"],
  "tools": [{{"name": "tool_name", "argument": "raw argument string"}}],
  "code": "optional code or empty string",
  "explanation": "concise analyst explanation",
  "next_action": "CONTINUE or DONE",
  "final_answer": "required only when next_action is DONE"
}}
"""


ROUTING_TEMPLATE = """You are a task routing agent in a fraud analytics system.
Choose one path only and do not request tool execution in this stage.

USER TASK:
{task}

INTENT ANALYSIS:
{intent_analysis}

Return strict JSON:
{{
  "task_type": "conversation | evaluate | execute",
  "recommended_tools": ["tool_name"],
  "risks_or_gaps": ["potential issue or missing information"]
}}
"""


INTENT_TEMPLATE = """You are an intent analysis stage for a fraud analytics workflow.
Summarize what success looks like and key constraints.

TASK:
{task}

CONTEXT:
{memory}

Return strict JSON:
{{
  "intent_summary": "short summary",
  "success_criteria": ["criterion"],
  "constraints": ["constraint"]
}}
"""


CONVERSATION_TEMPLATE = """You are a fraud analytics assistant.
Provide a direct conversational response without tools.

TASK:
{task}

CONTEXT:
{memory}

Return strict JSON:
{{
  "message": "assistant response"
}}
"""


EVALUATION_TEMPLATE = """You are evaluating prior workflow/tool outputs.
Summarize findings, caveats, and next step.

TASK:
{task}

CONTEXT:
{memory}

LATEST TOOL OUTPUTS:
{tool_feedback}

Return strict JSON:
{{
  "finding_summary": "summary",
  "confidence_and_limitations": "confidence and caveats",
  "recommended_next_step": "next step"
}}
"""


REASONING_LOOP_TEMPLATE = """You are orchestrating a multi-step fraud analytics workflow with tool feedback.
This is the only stage that may emit executable tool calls.
Return JSON only.

ORIGINAL TASK:
{task}

ITERATION:
{iteration}

SESSION MEMORY:
{memory}

LATEST TOOL OUTPUTS:
{tool_feedback}

Available tool names:
- data_prep
- rca_analysis
- case_review
- alert_rationalization
- compute_metrics
- generate_ppt

Instructions:
- Think stepwise and choose only necessary tools.
- If more evidence is required, set next_action to CONTINUE.
- If the task is complete, set next_action to DONE and provide final_answer.

Return JSON schema:
{{
  "plan": ["step 1", "step 2"],
  "tools": [{{"name": "tool_name", "argument": "raw argument string"}}],
  "code": "optional code or empty string",
  "explanation": "what was learned this iteration",
  "next_action": "CONTINUE or DONE",
  "final_answer": "required when next_action is DONE"
}}
"""
