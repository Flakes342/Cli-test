TOOL: alert_rationalization
Use for alert-level triage and quick rationalization.

Recommended workflow for variable alerts:
1) Run `variable_lookup` first if the variable code/name is uncertain.
2) Then run `alert_rationalization` with the exact `variable_id`.

Input examples:
- {"user_query": "RDMC3048 lower limit alert on 2026-03-22", "execute_sql": true}
- {"variable_id": "RDMC3048", "alert_date": "2026-03-22", "alert_table": "project.dataset.table", "execute_sql": true}

Behavior:
- Resolves variable metadata from the configured catalog when available.
- Selects and runs a default multi-query pack based on variable type:
  - categorical: `00_cat_var_dist`, `01_cat_var_stats`, `02_cat_top_cm`, `02_cat_top_se`
  - numerical: `00_num_var_dist`, `01_num_var_stats_(w|wo)_default`, `02_num_top_cm`, `02_num_top_se`
- Query templates are loaded from `amex_ai_agent/cdit_alert_rationalization/`.
- Executes queries sequentially when `execute_sql=true`, summarizes outputs, and returns an `llm_followup_prompt` when deeper analysis SQL is needed.


Important:
- Always resolve variable metadata first (`variable_lookup` if needed).
- Pass `alerted_value` for categorical alerts whenever available.
- Use the returned `llm_followup_prompt` to request additional LLM-authored SQL when `needs_llm_followup=true`.
