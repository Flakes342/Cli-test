# Sally

Sally is a local-first CLI assistant for fraud workflows in restricted environments. Right now the only wired execution path is the RNN data-prep pipeline; other tool scaffolding has been trimmed back so the agent behavior stays predictable.

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

If your environment prefers shell-invoked scripts, `bash ./sally run` works too.

## Helpful commands

- `./sally init` — collect/update startup defaults without launching the chat UI
- `./sally doctor` — print saved startup configuration
- `python agent.py` — legacy entrypoint if you do not want the bootstrap wrapper

## Deeper documentation

For a code-level walkthrough of the full repository, see:

- `docs/DEVELOPER_GUIDE.md`

## Current tool scope

Enabled tools:

- `data_prep`
- `model_score`
- `compute_metrics`

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

The final structured tool output still prints after the live status completes.
