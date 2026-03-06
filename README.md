# FraudForge (Human-in-the-loop CLI)

A local-first reasoning assistant for fraud data scientists in restricted AMEX-like environments.
No model API is required today: prompts are generated in CLI, pasted into ChatGPT Enterprise, and responses are pasted back for routing/planning/tool execution.

## Quick start with Mamba

```bash
mamba env create -f environment.yml
mamba activate amex-ai-agent
python agent.py
```

## If the env already exists

```bash
mamba env update -n amex-ai-agent -f environment.yml --prune
mamba activate amex-ai-agent
python agent.py
```

## Validate dependencies

```bash
python - <<'PY'
import rich
import prompt_toolkit
import pandas
import numpy
import sklearn
import pptx
print("All required packages imported successfully.")
PY
```

## Graph-based reasoning architecture (LangGraph-ready)

The `/reason` command now runs a node/edge orchestration layer in `amex_ai_agent/reasoning_graph.py`:

1. `intent` node — understand user intent and constraints
2. `route` node — classify request as `conversation`, `evaluate`, or `execute`
3. route-specific branch:
   - `conversation` -> direct response using memory
   - `evaluate` -> evaluate prior outputs/history
   - `execute` -> planning loop with tools (`plan <-> tools`) until DONE/max loops

This keeps flow fully structured even in copy/paste mode.

## Single swap point for API migration

All model calls pass through one interface in `amex_ai_agent/llm_gateway.py`:

- `ManualPasteGateway` (current)
- `ApiGateway` (future direct API)

When API access is available, replace/implement `ApiGateway.invoke(...)` and set:

```yaml
llm_mode: api
llm_model: <enterprise-model-name>
```

No orchestration-node logic needs to change.

## Commands

- `/plan` Generate one-shot plan prompt and parse model response
- `/reason` Run graph-based staged flow (intent, routing, route branch, tool loop)
- `/run` Execute tool calls from latest parsed response
- `/tools` Show available tools
- `/memory` Show recent memory context
- `/history` Show recent chat history
- `/clear` Reset memory
- `/exit` Quit

## Available fraud-focused tools

- `data_prep(dataset_path)`
- `compute_metrics(model_scoring_csv_path)`
- `feature_rca(csv_path|feature_name|current_month|baseline_month)`
- `rca_analysis(transcript_or_notes)`
- `case_review(case_json)`
- `alert_rationalization(alert_csv_path)`
- `sql_query(sql_file_path)`
- `generate_ppt(summary_text)`

## Notes

- Designed for restricted enterprise environments where LLM API access is unavailable.
- UI is retro terminal-style for lightweight CLI usability.
- Data-prep and domain tool internals can be expanded independently without changing graph orchestration.
