TOOL: rca_analysis
Use for root-cause analysis on model/alert performance shifts.

Expected argument object:
{{"analysis_ref":"bq://project.dataset.analysis_table","objective":"Explain metric drift","segments":["card_present"],"time_window":{{"start_dt":"YYYY-MM-DD","end_dt":"YYYY-MM-DD"}}}}

Rules:
- If analysis_ref is unavailable, prefer workflow: data_prep -> model_score (if needed) -> rca_analysis.
- Ask concise follow-up if objective is missing.
