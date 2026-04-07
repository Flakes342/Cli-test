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
- Builds default SQL from variable metadata + window.
- Can run SQL via `bq query` when `execute_sql=true`.


Important:
- The planner/LLM should write a concrete `sql_query` (or `query`) whenever possible, following alert template logic and variable metadata.
- `alert_rationalization` only uses generated fallback SQL when no SQL query is supplied.
