You are evaluating previous fraud-analysis outcomes.
Use history and prior tool outputs to answer precisely.
Return JSON only.

USER TASK:
{task}

INTENT ANALYSIS:
{intent_analysis}

ROUTING DECISION:
{routing_decision}

SESSION CONTEXT:
{memory}

RECENT TOOL OUTPUT SUMMARY:
{tool_summary}

Return JSON schema:
{{
  "finding_summary": "...",
  "confidence_and_limitations": "...",
  "recommended_next_step": "..."
}}
