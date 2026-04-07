# Developer Guide

## Scope

This repository intentionally keeps a small tool surface area.

Implemented and registered tools:
- `data_prep`
- `variable_lookup`
- `alert_rationalization`

Anything outside that list should be considered out of scope unless explicitly added back with tests and planner/executor wiring.

## Core Architecture

- `amex_ai_agent/executor.py`
  - Canonical tool registry and aliases.
  - Enforces what the planner can execute.
- `amex_ai_agent/planner.py`
  - Builds prompts and parses JSON tool requests.
- `amex_ai_agent/reasoning_graph.py`
  - Routing/evaluation/execution loop.

## Implemented Tools

### `data_prep`
File: `amex_ai_agent/tools/data_prep.py`

Runs the existing RNN data-preparation pipeline and reports run artifacts/status.

### `variable_lookup`
File: `amex_ai_agent/tools/variable_lookup.py`

CSV-backed variable discovery utility:
- exact lookup by variable code
- fuzzy query search
- filters by model/domain/table

Primary backing module: `amex_ai_agent/variable_catalog.py`.

### `alert_rationalization`
File: `amex_ai_agent/tools/alerts.py`

Variable-level alert triage helper:
- resolves variable metadata via configured CSV catalog
- prefers planner/LLM SQL (`sql_query` or `query`)
- falls back to generated SQL when no query is supplied
- executes SQL only when `execute_sql=true`

Supporting modules:
- `amex_ai_agent/rca/alert_query_parser.py`
- `amex_ai_agent/rca/variable_metadata_resolver.py`
- `amex_ai_agent/rca/bq_executor.py`

## Prompt Files

Planner-visible tool lists must stay aligned with executor registry:
- `amex_ai_agent/prompts/plan_prompt.md`
- `amex_ai_agent/prompts/reasoning_loop_prompt.md`
- `amex_ai_agent/prompts/templates.py`
- `amex_ai_agent/prompts/tools/*.md`

## Config

`variable_catalog_path` is persisted in config and shared across chat/tools.

Relevant files:
- `amex_ai_agent/config.py`
- `amex_ai_agent/startup.py`
- `config.yaml`

## Testing

Run:

```bash
pytest -q
python -m compileall amex_ai_agent tests
```

Primary tests:
- `tests/test_variable_catalog.py`
- `tests/test_variable_lookup_tool.py`
- `tests/test_alert_query_parser.py`
- `tests/test_variable_metadata_resolver.py`
- `tests/test_bq_executor.py`
- `tests/test_alert_rationalization_tool.py`
