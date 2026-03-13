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

## End-to-end workflow map (exhaustive)

```mermaid
flowchart TD
    U[User query in CLI] --> C{Command?}

    C -->|/help,/tools,/doctor,/memory,/history| SYS[Direct command handler in chat.py]
    C -->|normal text or /reason| RG[FraudReasoningGraph.run]

    RG --> R1[Route stage prompt]
    R1 --> LLM1[Human-pasted LLM routing JSON]
    LLM1 --> PR1[parse_routing in parser.py]
    PR1 --> D1{task_type}

    D1 -->|conversation| P1[Plan stage prompt]
    D1 -->|evaluate| P1
    D1 -->|execute| P1

    P1 --> LLM2[Human-pasted LLM planning JSON]
    LLM2 --> PR2[parse in parser.py]
    PR2 --> D2{next_action}

    D2 -->|DONE| OUT1[Final analyst-facing answer]
    D2 -->|CONTINUE + no tools| OUT2[Explain missing info and stop]
    D2 -->|CONTINUE + tools| TN[Tools node]

    TN --> UI1[UI info: running tools + loading timer]
    TN --> EX[ToolExecutor.execute]

    EX --> TDP[data_prep tool]
    EX --> TMS[model_score tool]
    EX --> TCM[compute_metrics tool]
    EX --> TRCA[rca_analysis tool]
    EX --> TCR[case_review tool]
    EX --> TAR[alert_rationalization tool]
    EX --> TPPT[generate_ppt tool]

    TDP --> STDP{status}
    TMS --> STMS{status}
    TCM --> STCM{status}
    TRCA --> STRCA{status}

    STDP -->|needs_user_input| FEED[tool_feedback back to planning loop]
    STDP -->|ready/success| FEED

    STMS -->|needs_user_input| FEED
    STMS -->|ready/success| FEED

    STCM -->|needs_user_input| FEED
    STCM -->|ready/success| FEED

    STRCA -->|needs_user_input| FEED
    STRCA -->|ready/success| FEED

    TCR --> FEED
    TAR --> FEED
    TPPT --> FEED

    FEED --> MEM[MemoryStore: save tool runs + summaries]
    MEM --> P2[Next plan iteration prompt]
    P2 --> LLM3[Human-pasted LLM planning JSON]
    LLM3 --> PR3[parse]
    PR3 --> D3{DONE?}
    D3 -->|No| TN
    D3 -->|Yes| OUT1

    subgraph Prompt composition
      ROUTING[routing_prompt.md]
      PLAN[plan_prompt.md]
      TOOLSPEC[tool-specific prompt snippets under prompts/tools/*.md]
    end

    PR1 --> PLAN
    P1 --> PLAN
    P1 --> TOOLSPEC

    subgraph Workflow examples (policy-level)
      W1[data_prep -> model_score -> compute_metrics]
      W2[data_prep -> model_score -> rca_analysis]
      W3[Direct compute_metrics when score_ref already exists]
      W4[Direct rca_analysis when analysis_ref already exists]
    end

    TN --> W1
    TN --> W2
    TN --> W3
    TN --> W4
```

### What happens for every user query

1. Query enters chat loop (`chat.py`) and triggers reasoning graph unless it is a slash command.
2. Routing stage classifies intent (`conversation`, `evaluate`, `execute`).
3. Planning stage requests strict JSON with plan, optional tool calls, and `next_action`.
4. Parser validates/repairs JSON and extracts tool calls.
5. Tools execute via registry dispatch in `executor.py`.
6. Tool outputs are written to memory and fed into the next planning iteration.
7. Loop continues until `next_action = DONE` or max iterations is reached.
8. Final answer is rendered to CLI.

### Tool-specific prompting behavior

- Base planning prompts remain concise and generic.
- If routing recommends specific tools, planner appends small tool-specific guidance snippets from `amex_ai_agent/prompts/tools/*.md`.
- This avoids overloading main plan prompts while still enforcing per-tool argument contracts.
