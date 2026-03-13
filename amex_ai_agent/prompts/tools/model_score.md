TOOL: model_score
Use when prepared data must be scored offline.

Expected argument object:
{{"model":"rnn|xgboost|ensemble","input_ref":"bq://project.dataset.prepared_table","score_output_ref":"bq://project.dataset.scored_table","score_version":"optional"}}

Rules:
- Call after data_prep unless user already provides a prepared dataset reference.
- Ask concise follow-up if model/input_ref/score_output_ref are missing.
