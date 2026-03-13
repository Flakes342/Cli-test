TOOL: compute_metrics
Use to compute overall and segment-level model metrics from scored data.

Expected argument object:
{{"score_ref":"bq://project.dataset.scored_table","label_col":"label","score_col":"score","metrics":["coverage","hitrate","accuracy","gini","ks"],"segments":["card_present","se_visited"],"segment_definitions_ref":"optional"}}

Rules:
- If score_ref is unavailable, prefer workflow: data_prep -> model_score -> compute_metrics.
- Ask concise follow-up if score_ref is missing and workflow should not be auto-run.
