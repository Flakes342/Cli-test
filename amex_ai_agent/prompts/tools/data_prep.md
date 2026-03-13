TOOL: data_prep
Use when data must be prepared before scoring/analysis.

Expected argument object:
{{"start_dt":"YYYY-MM-DD","end_dt":"YYYY-MM-DD","model":"rnn|xgboost|ensemble","sample_rate":0.025}}

Rules:
- Extract parameters from user request before calling.
- Ask concise follow-up if start_dt/end_dt/model are missing.
- sample_rate defaults to 0.025 when omitted.
