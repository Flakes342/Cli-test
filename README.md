# AMEX AI Agent (Human-in-the-loop CLI)

A local-first reasoning assistant for fraud data scientists in restricted AMEX-like environments.
No model API is required: prompts are generated in CLI, pasted into ChatGPT Enterprise, and the response is pasted back for tool execution + iterative reasoning.

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

## Key workflow

1. Enter a task in plain language (example: "RCA for spike in October fraud score for feature velocity_1h").
2. CLI generates a strict prompt.
3. Paste prompt into ChatGPT Enterprise.
4. Paste model response back (finish input with a single `END` line).
5. Agent parses plan/tool calls, executes local tools, and can continue iterative reasoning via `/reason`.

## Commands

- `/plan` Generate one-shot plan prompt and parse model response
- `/reason` Run multi-step reasoning loop (CONTINUE/DONE protocol)
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
- The CLI includes a polished retro terminal-style interface for a friendlier analyst experience.
- Later migration to API-based LLM calls can reuse the same parser + tool execution architecture.
