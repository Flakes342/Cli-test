# FraudForge (Human-in-the-loop CLI)

A local-first reasoning assistant for fraud data scientists in restricted AMEX-like environments.
No model API is required today: prompts are generated in CLI, pasted into ChatGPT Enterprise, and responses are pasted back for planning/tool execution.
All LLM stages are JSON-contract driven for reliable parsing.

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
import pyperclip
print("All required packages imported successfully.")
PY
```

## Graph-based reasoning architecture (simplified)

The `/reason` command runs a simplified node/edge loop in `amex_ai_agent/reasoning_graph.py` and uses the `reasoning_loop` prompt contract for iterative planning:

1. `plan` node — generate iterative plan + optional tool calls
2. `tools` node — execute parsed tool calls and capture outputs
3. loop `plan <-> tools` until `next_action = DONE` or max iterations

This reduces routing complexity and improves reliability for actionable prompts.

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

## Interaction behavior

- Typing a normal message runs the planning/tool loop by default (`/reason` behavior).
- Runtime no longer prints graph-trace panels in normal output.
- `/plan` remains available and uses the same planning contract.
- Memory context excludes stored prompt payloads to prevent recursive prompt growth.
- Startup preflight warns if packages/tools are missing.

## Commands

- `/plan` Generate one-shot plan prompt and parse model response
- `/reason` Run simplified planning/tool loop
- `/run` Execute tool calls from latest parsed response
- `/tools` Show available tools
- `/doctor` Validate package and tool-module readiness
- `/copy` Copy latest copyable agent output (shown in UI as `[📋 /copy]`)
- `/prompts` Show which prompt contracts are active vs reserved
- `/memory` Show recent memory context
- `/history` Show recent chat history
- `/clear` Reset memory
- `/exit` Quit

## Available fraud-focused tools

- `data_prep(dataset_path_or_instruction)`
- `model_score(model_scoring_instruction_or_json)`
- `compute_metrics(model_scoring_csv_path)`
- `rca_analysis(transcript_or_notes)`
- `case_review(case_json_or_notes)`
- `alert_rationalization(alert_csv_path_or_instruction)`
- `generate_ppt(summary_text)`

## Notes

- Designed for restricted enterprise environments where LLM API access is unavailable.
- UI is retro terminal-style for lightweight CLI usability.
- Data-prep and domain tool internals can be expanded independently without changing graph orchestration.

## JSON contract

The planning loop requests JSON-only output with:

- `plan`
- `tools`
- `next_action`
- `final_answer`

This keeps parsing deterministic in copy/paste mode and future API mode.

## Prompt files

Prompt contracts are stored in `.md` files under `amex_ai_agent/prompts/` and loaded via
`amex_ai_agent.prompts.registry.get_prompt_template(...)`.

Current runtime behavior:
- Normal chat + `/reason` use `reasoning_loop_prompt.md` (iterative planning/tool execution).
- `/plan` uses the same planning contract via planner aliasing.
- Non-runtime prompt variants are moved under `amex_ai_agent/prompts/experimental/` to keep the active tree clean.
