# Sally

Sally is a local-first CLI assistant for fraud workflows in restricted environments. The current implemented tool paths focus on the RNN data-prep pipeline, CSV-backed variable catalog lookup, and variable alert rationalization.

## Quick start

```bash
mamba env create -f environment.yml
mamba activate amex-ai-agent
./sally run
```

`./sally run` now handles runtime bootstrap:

- prompts once for default `project_id` and `dataset_id`
- stores those defaults in `config.yaml`
- sets `RNN_SPARK_PYTHON`, `PYSPARK_PYTHON`, and `PYSPARK_DRIVER_PYTHON` from config so you do not need separate export steps
- can optionally launch `gcloud auth login`
- can store a `variable_catalog_path` that points to a CSV with `Variable`, `Full Name`, `Description`, `Variable Type`, `Default Value`, `Table`, `Domain`, and `Model` columns

If your environment prefers shell-invoked scripts, `bash ./sally run` works too.

## Helpful commands

- `./sally init` — collect/update startup defaults without launching the chat UI
- `./sally doctor` — print saved startup configuration
- `python agent.py` — legacy entrypoint if you do not want the bootstrap wrapper
- `/var <code>` — show the exact variable definition from the configured catalog
- `/vars model <model>` — list variables for a model
- `/vars domain <domain>` — list variables for a domain

## Variable catalog format

Point `variable_catalog_path` at a CSV file with these headers:

- `Variable`
- `Full Name`
- `Description`
- `Variable Type`
- `Default Value`
- `Table`
- `Domain`
- `Model`

The variable catalog powers both the direct chat commands and the `variable_lookup` tool. The tool supports:

- exact code lookup
- filtered listings by `model`, `domain`, and `table`
- fuzzy text search over variable code, full name, and description

Example tool argument:

```json
{
  "query": "authorization amount",
  "model": "rnn",
  "domain": "authorization",
  "limit": 5
}
```


## Deeper documentation

For a code-level walkthrough of the full repository, see:

- `docs/DEVELOPER_GUIDE.md`

## Current tool scope

Enabled tools:

- `data_prep`
- `variable_lookup`
- `alert_rationalization`

### `alert_rationalization` output tables

When `execute_sql=true`, `alert_rationalization` persists each default query output
to BigQuery destination tables (similar to the RNN data-prep pattern), and returns
those table names in `sql_execution.destination_tables`.

To enable table persistence, provide:

- `project_id` + `dataset_id` in the tool payload, **or**
- `default_project_id` + `default_dataset_id` in `config.yaml`.

`data_prep` supports these model names:

- `rnn` — implemented
- `xgboost` — reserved, not wired yet
- `ensemble` — reserved, not wired yet

## Logging

All runtime logs now flow through a centralized logger and are written to:

```text
logs/sally.log
```

During tool execution the CLI shows live in-place status updates such as:

- `Data prep tool starting...`
- `Creating init sample table...`
- `Creating Spark dataframes...`
- `Writing dataset...`
- `Loading variable catalog...`

The final structured tool output still prints after the live status completes.
