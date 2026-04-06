TOOL: rca_analysis
Use this tool for CDIT/control-chart variable alert investigation.

Input modes:
1) Natural-language query mode:
{"user_query":"RDMC3048 got a lower-limit alert on 2026-03-22. Please do initial RCA."}

2) Structured mode:
{"variable_id":"RDMC3048","alert_date":"2026-03-22","alert_type":"lower_limit_breach"}

Optional fields:
- start_date / end_date
- baseline_start_date / baseline_end_date
- segmentation_filters
- market_filters
- sample_rate_override
- analyst_notes
- observations (precomputed metric/stage/driver stats)
- execute_sql / execute_generated_sql
- query or queries[] for ad-hoc SQL execution
- response_mode: `compact` (default) or `full`
- include_sql_templates: include raw SQL strings in response

Behavior:
- Parses variable/date/alert type from natural language.
- Resolves variable metadata from the configured variable catalog file.
- Returns an initial RCA package: alert context, metadata, windows, alert summary, decomposition, funnel diagnostics, top drivers, DQ checks, hypotheses, analyst summary, and executable SQL templates.

If variable matching is ambiguous, ask the analyst to provide explicit `variable_id`.

When `execute_sql=true`, the tool runs ad-hoc BigQuery SQL via the `bq query --nouse_legacy_sql --format=json` pattern and returns gathered rows in `sql_execution.query_results`.
