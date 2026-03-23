# Sally Developer Guide

This document is a code-oriented guide to the full repository. It is intended to help you:

- understand the runtime flow end-to-end
- know what every file is for
- know what every public function/class is doing
- trace how prompts, parsing, tool execution, logging, and memory fit together
- add new tools safely
- modify existing tools and pipelines without breaking the CLI loop

The guide is intentionally exhaustive rather than brief.

---

## 1. High-level mental model

Sally is a **local-first command-line orchestration layer** for fraud workflows.

It does **not** directly call a hosted LLM API by default.
Instead, it works like this:

1. You start the CLI with `./sally run`.
2. Startup/bootstrap collects or loads defaults like:
   - default BigQuery project
   - default BigQuery dataset
   - default output folder
   - Spark Python path
   - variable catalog CSV path
3. The chat app starts.
4. When you enter a request, Sally:
   - stores the request in memory
   - asks the LLM for a route (`conversation`, `evaluate`, `execute`)
   - asks the LLM for a structured JSON plan
   - parses the JSON
   - executes any tool calls
   - saves tool outputs to memory
   - loops until the model returns `DONE` or the max loop count is reached
5. Tool execution currently centers on `data_prep`, especially the RNN data-prep pipeline, plus `variable_lookup` for CSV-backed metadata lookups.
6. Results are shown in the terminal and also logged to disk.

You can think of the repo as six layers:

1. **Launcher / startup layer** — `sally`, `cli.py`, `startup.py`, `config.py`
2. **Chat/orchestration layer** — `chat.py`, `reasoning_graph.py`, `planner.py`, `parser.py`, `llm_gateway.py`, `memory.py`
3. **Tool execution layer** — `executor.py`, `tools/*`
4. **Catalog layer** — `variable_catalog.py`
5. **Pipeline layer** — `pipelines/rnn_data_prep/*`
6. **Embedded domain code** — `rnn_data_prep/src`, `rnn_data_prep/utils`, `rnn_data_prep/sqlQ`

---

## 2. Repository map

### Root files

- `agent.py`
  - Tiny compatibility entrypoint.
  - Imports `amex_ai_agent.agent.main` and runs it.

- `sally`
  - Shell launcher.
  - Changes into repo root and runs `python3 -m amex_ai_agent.cli "$@"`.

- `config.yaml`
  - Saved runtime config.
  - Holds agent name, execution mode, startup defaults, and `variable_catalog_path`.

- `environment.yml`
  - Conda/Mamba environment definition.

- `README.md`
  - User-facing quick start.

- `.gitignore`
  - Ignores logs, caches, memory files, and generated artifacts.

### Main package: `amex_ai_agent/`

- `agent.py` — top-level app startup
- `chat.py` — interactive CLI app, including direct `/var` and `/vars` shortcuts
- `cli.py` — subcommand CLI wrapper
- `config.py` — config dataclass + loader/saver
- `executor.py` — tool registry and dispatcher
- `llm_gateway.py` — manual-paste or future API model gateway
- `logging_utils.py` — root logging setup
- `memory.py` — persistent chat/tool/task memory
- `parser.py` — parses model JSON responses into structured objects
- `planner.py` — builds prompts from task + memory + routing
- `reasoning_graph.py` — bounded route → reason → tools loop
- `startup.py` — interactive bootstrap, config persistence, env var setup
- `variable_catalog.py` — CSV-backed variable metadata loader, normalizer, and search helper

### UI package: `amex_ai_agent/ui/`

- `chat_ui.py` — terminal rendering panels/status updates
- `spinner.py` — simple unused/minimally used status helper

### Tool package: `amex_ai_agent/tools/`

Currently active or core:

- `data_prep.py`
- `model_score.py`
- `metrics.py`
- `variable_lookup.py`
- `base.py`

Other existing but not currently wired into the active tool registry:

- `rca_analysis.py`
- `alerts.py`
- `case_review.py`
- `ppt_generator.py`
- `sql_query.py`
- `feature_rca.py`

### Pipeline package: `amex_ai_agent/pipelines/`

- `rnn_data_prep/config.py`
- `rnn_data_prep/runner.py`

### Embedded RNN code: `amex_ai_agent/rnn_data_prep/`

- `src/main.py`
- `utils/lumi_utils.py`
- `utils/prep_utils.py`
- `sqlQ/*.txt`

### Prompts: `amex_ai_agent/prompts/`

- `plan_prompt.md`
- `routing_prompt.md`
- `reasoning_loop_prompt.md`
- `registry.py`
- `templates.py`
- `tools/*.md`
- `experimental/*.md`

### Tests

- `tests/test_variable_catalog.py`
- `tests/test_variable_lookup_tool.py`

---

## 3. End-to-end runtime flow

### 3.1 Startup flow

Normal path:

```text
./sally run
  -> amex_ai_agent.cli.main()
  -> ConfigLoader.load()
  -> StartupManager.initialize(...)
  -> agent.run_app(config)
  -> configure_logging()
  -> AgentChatApp(config).start()
```

### 3.2 Task execution flow

For a normal user message:

```text
AgentChatApp.start()
  -> stores user message in memory
  -> FraudReasoningGraph.run(task)
       -> _route(task)
       -> loop:
            _reason(task, state)
            if tools requested:
                _run_tools(parsed)
                   -> ToolExecutor.execute(...)
                      -> tool_module.run(argument, context?)
                         -> maybe pipeline runner
            else finish
```

### 3.3 RNN data prep flow

When the model requests the `data_prep` tool with `model=rnn`:

```text
data_prep.run(...)
  -> validate/normalize input
  -> run_rnn_data_prep(params, context)
       -> try import mode:
            from src.main import run_pipeline
            run_pipeline(...)
       -> else fallback to subprocess mode:
            python main.py with env vars
       -> return structured result
```

Inside the embedded pipeline:

```text
run_pipeline(...)
  -> create/init sample table
  -> create exclusions table
  -> create rnn sequence table
  -> create vars pull table
  -> load Spark DataFrames from BigQuery
  -> bucket features
  -> build final sequence dataset
  -> write CSV to gs://.../data
  -> return structured metadata
```

---

## 3.4 Variable catalog flow

When the model or analyst needs variable definitions:

```text
variable_lookup.run(...)
  -> load configured CSV from variable_catalog_path
  -> normalize headers/values
  -> exact lookup by code OR
  -> filtered list by model/domain/table OR
  -> fuzzy search over code/full name/description
  -> return structured JSON result
```

The direct chat commands `/var <code>`, `/vars model <model>`, and `/vars domain <domain>` reuse the same catalog layer without invoking the LLM.

---

## 4. Root-level files

## 4.1 `agent.py`

Purpose:
- minimal compatibility shim
- useful if someone still runs `python agent.py`

Behavior:
- imports `main` from `amex_ai_agent.agent`
- executes it if run as a script

Notes:
- no logic lives here
- real startup logic is in `amex_ai_agent/agent.py`

## 4.2 `sally`

Purpose:
- ergonomic shell entrypoint

Behavior:
- runs as Bash
- finds its own directory
- `cd`s into repo root
- uses `${PYTHON_BIN:-python3}`
- executes `python -m amex_ai_agent.cli "$@"`

Why this exists:
- avoids import-path issues
- supports both `./sally run` and `bash ./sally run`

## 4.3 `config.yaml`

Purpose:
- user-editable persisted configuration

Fields currently used:
- `agent_name`
- `theme`
- `memory_enabled`
- `auto_execute_tools`
- `max_reasoning_loops`
- `llm_mode`
- `llm_model`
- `default_project_id`
- `default_dataset_id`
- `default_folder_nm`
- `spark_python`
- `variable_catalog_path`

Important behavior:
- `default_project_id` / `default_dataset_id` are especially important for data prep
- `spark_python` is reused to set all Spark-related Python env vars
- `variable_catalog_path` points to the CSV used by direct variable commands and the `variable_lookup` tool

## 4.4 `environment.yml`

Purpose:
- environment spec for Mamba/Conda

Usage:
- `mamba env create -f environment.yml`
- `mamba activate amex-ai-agent`

## 4.5 `README.md`

Purpose:
- concise user quick start
- not the full technical reference

## 4.6 `.gitignore`

Purpose:
- keep runtime outputs out of git

Notable ignored items:
- `logs/`
- memory JSON files
- caches (`__pycache__`, pytest, mypy, ruff)
- generated PPTX files

---

## 5. Core startup and configuration modules

## 5.1 `amex_ai_agent/agent.py`

Purpose:
- app-level startup after config is ready

### `run_app(config)`
Responsibilities:
- initializes centralized logging via `configure_logging()`
- logs the path being used
- constructs `AgentChatApp`
- starts the interactive chat loop

### `main()`
Responsibilities:
- loads config via `ConfigLoader`
- calls `run_app(config)`

Use this module when:
- you want the app running after config already exists
- you want logging initialized before chat starts

---

## 5.2 `amex_ai_agent/config.py`

Purpose:
- define config shape and persistence

### `AgentConfig`
Dataclass holding runtime configuration.

Fields:
- `agent_name`
- `theme`
- `memory_enabled`
- `auto_execute_tools`
- `max_reasoning_loops`
- `llm_mode`
- `llm_model`
- `default_project_id`
- `default_dataset_id`
- `default_folder_nm`
- `spark_python`
- `variable_catalog_path`

### `ConfigLoader`
Handles reading and writing `config.yaml`.

#### `__init__(config_path="config.yaml")`
Stores the config file path.

#### `_parse_simple_yaml(text)`
Very lightweight parser.
Important limitation:
- this is **not full YAML support**
- it only supports simple `key: value` lines

#### `_as_bool(value, default)`
Converts common truthy strings to `bool`.

#### `_as_int(value, default)`
Converts a string to `int` with fallback.

#### `load()`
Reads the file if it exists and returns an `AgentConfig`.
If not present, returns defaults.

#### `save(config)`
Writes a full config file from the `AgentConfig` object.

Extension advice:
- if you add new config fields, update both `AgentConfig`, `load()`, and `save()`
- because parsing is simple, avoid nested YAML structures

---

## 5.3 `amex_ai_agent/cli.py`

Purpose:
- parse top-level Sally commands

Subcommands:
- `init`
- `run`
- `doctor`

### `build_parser()`
Creates the `argparse` parser.

### `main()`
Behavior:
- loads config
- creates `StartupManager`
- for `init`:
  - prompts and saves startup defaults
- for `doctor`:
  - ensures defaults are collected
  - prints saved resolved config
- for `run` (or no explicit command):
  - initializes startup defaults
  - imports `run_app`
  - launches app

Why `run_app` is imported lazily:
- to avoid loading the full interactive chat stack during lighter commands unless needed

---

## 5.4 `amex_ai_agent/startup.py`

Purpose:
- interactive bootstrap for restricted environments

### `StartupManager`
Encapsulates startup prompting and environment setup.

#### `__init__(loader)`
Stores `ConfigLoader`.

#### `initialize(config, prompt_for_auth)`
Main bootstrap method.

Responsibilities:
- clone incoming config via `replace(...)`
- prompt for missing `default_project_id`
- prompt for missing `default_dataset_id`
- optionally prompt/confirm `default_folder_nm`
- optionally prompt/confirm `spark_python`
- apply Python env vars for Spark
- save resolved config back to disk
- optionally ask to run `gcloud auth login`

#### `_maybe_run_gcloud_auth()`
If `gcloud` exists in `PATH`, asks whether to run login.

#### `_apply_python_env(python_path)`
Sets:
- `RNN_SPARK_PYTHON`
- `PYSPARK_PYTHON`
- `PYSPARK_DRIVER_PYTHON`

This is one of the most important helpers for data prep.

#### `_prompt(label, default="", required=True)`
Simple loop around `input()` with defaults.

Extension advice:
- if you add new startup-level defaults, add prompt logic here
- anything needed by multiple tools should probably be configured here rather than hardcoded in the tool

---

## 6. Logging

## 6.1 `amex_ai_agent/logging_utils.py`

Purpose:
- configure one root logger for the whole runtime

### `LOG_PATH`
Default file target:
- `logs/sally.log`

### `configure_logging(level=logging.INFO)`
Responsibilities:
- create `logs/` directory
- create a rotating file handler
- create a stderr console handler
- clear any existing root handlers
- attach the new handlers
- capture Python warnings into logging
- return the log path

Current behavior:
- file logs get full info-level output
- console only gets warnings and errors

Extension advice:
- if console noise becomes too high, reduce console handler level
- if you want JSON logs, replace `logging.Formatter`

---

## 7. Interactive chat/orchestration layer

## 7.1 `amex_ai_agent/chat.py`

Purpose:
- this is the main interactive application shell

### `AgentChatApp`
Main runtime object.

#### Class constants

##### `COMMANDS`
Slash commands supported in the terminal:
- `/help`
- `/clear`
- `/history`
- `/tools`
- `/doctor`
- `/files`
- `/reason`
- `/memory`
- `/exit`

##### `REQUIRED_PACKAGES`
Modules checked at startup preflight:
- pandas
- numpy
- sklearn
- pptx

#### `__init__(config)`
Builds the runtime graph.

It creates:
- `MemoryStore`
- `PromptPlanner`
- `ResponseParser`
- `ToolExecutor`
- `ChatUI`
- `PromptSession`
- `LLM gateway` (manual or API placeholder)
- `FraudReasoningGraph`

#### `start()`
Main terminal loop.

Behavior:
- render header
- show initial help hint
- show environment/tool warnings if any
- loop forever reading input
- route slash commands to `_handle_command`
- otherwise treat text as a user task and call `_reasoning_graph()`

#### `_reasoning_graph()`
Thin wrapper around `self.graph.run(self.last_task)`.

#### `_preflight_checks()`
Returns a dict containing:
- package readiness
- tool import readiness

#### `_show_preflight_warnings()`
Renders missing dependency / broken tool warnings in UI.

#### `_handle_command(command)`
Implements all slash commands.

Behavior summary:
- `/help` — list commands
- `/clear` — clear memory
- `/history` — show recent chat history
- `/tools` — show available tools from registry
- `/doctor` — print package + tool checks
- `/files` — list top-level files in current directory
- `/reason` — rerun reasoning on current task
- `/memory` — show memory context text
- `/exit` — stop app

Extension advice:
- if you add commands, update both `COMMANDS` and `_handle_command`
- if you add required dependencies for new tools, add them to `REQUIRED_PACKAGES`

---

## 7.2 `amex_ai_agent/llm_gateway.py`

Purpose:
- abstract how Sally talks to an LLM

### `LLMGateway`
Protocol requiring:
- `invoke(prompt: str, label: str) -> str`

### `ManualPasteGateway`
Current active implementation.

#### `invoke(prompt, label)`
Behavior:
- prints instructions in the UI
- asks the human to paste the prompt into ChatGPT Enterprise
- collects pasted response lines until a line equal to `END`
- returns the collected text

This is the default/manual HITL mode.

### `ApiGateway`
Placeholder for future direct API use.

#### `invoke(prompt, label)`
Currently raises `NotImplementedError`.

Extension advice:
- if enterprise API access becomes available, implement this class first
- the rest of the orchestration code is already designed to call this abstraction

---

## 7.3 `amex_ai_agent/memory.py`

Purpose:
- persist lightweight session memory to disk

### `SessionMemory`
Dataclass containing:
- `chat_history`
- `tool_runs`
- `task_summaries`

### `MemoryStore`
Persistent memory manager.

#### `__init__(session_path, history_path)`
Creates directories and loads previous state if present.

#### `_load()`
Loads JSON from disk into `SessionMemory`.

#### `_sanitize_list_of_dicts(value)`
Ensures only lists of dicts are accepted.

#### `_sanitize_chat_history(value)`
Normalizes older or malformed history records.

#### `save()`
Writes current memory state to disk.

#### `add_chat(role, message)`
Appends a chat item with UTC timestamp.

#### `add_tool_run(tool_name, argument, output, status)`
Appends a tool-run record.

#### `add_task_summary(summary)`
Appends a summary record.

#### `clear()`
Resets all session memory.

#### `context_text(max_items=10, max_chars=500)`
Builds the compact memory string fed into prompts.
Notably excludes roles such as:
- `agent`
- `assistant_raw`
- `system_prompt`
- `prompt`

This prevents prompt recursion and runaway context growth.

---

## 7.4 `amex_ai_agent/parser.py`

Purpose:
- turn pasted LLM output into structured Python objects

### Dataclasses

#### `ToolCall`
Fields:
- `name`
- `argument`

#### `ParsedResponse`
Fields:
- `plan`
- `tools`
- `code`
- `explanation`
- `next_action`
- `final_answer`

#### `IntentResponse`
Used for intent analysis if needed.

#### `RoutingResponse`
Fields:
- `task_type`
- `recommended_tools`
- `risks_or_gaps`

#### `ConversationResponse`
Simple message wrapper.

#### `EvaluationResponse`
For evaluation summarization responses.

### `ResponseParser`
Main parser class.

#### `parse(text)`
Parses planning-stage JSON into `ParsedResponse`.
Handles:
- plan list
- tool list
- JSON arguments inside tool calls
- `next_action`
- `final_answer`

#### `parse_intent(text)`
Parses intent analysis JSON.

#### `parse_routing(text)`
Parses routing JSON.

#### `parse_conversation(text)`
Parses a conversational response.

#### `parse_evaluation(text)`
Parses evaluation response JSON.

#### `_extract_json_payload(text)`
Robust JSON extraction strategy:
1. try raw JSON
2. try repaired JSON
3. try fenced code block JSON
4. try first object/array chunk in the text

#### `_repair_argument_string_json(text)`
Escapes unescaped embedded JSON in `argument` fields.

Why this parser matters:
- it is the contract boundary between freeform pasted model output and deterministic tool execution

Extension advice:
- when adding new prompt schemas, add new parser methods rather than overloading `parse()`
- keep output schemas strict and simple

---

## 7.5 `amex_ai_agent/planner.py`

Purpose:
- compose prompts from task, memory, routing, and tool guidance

### `PromptPlanner`

#### `_extract_file_mentions(text)`
Looks for `@path/to/file` references inside a user task.

#### `_load_file_context(task)`
Reads file contents for each `@...` mention and injects up to 4000 chars per file.

#### `_build_full_context(task, memory_context)`
Combines memory context and file excerpts.

#### `_tool_prompt_path(tool_name)`
Finds tool-specific prompt guidance file.

#### `_tool_specific_guidance(routing)`
Loads `prompts/tools/<tool>.md` for recommended tools and appends their content to the plan prompt.

#### `build_plan_prompt(...)`
Builds the plan/execution prompt using:
- task
- memory
- route
- recommended tools
- risks/gaps
- iteration number
- latest tool feedback

#### `build_routing_prompt(task, intent_analysis)`
Builds the routing prompt.

Extension advice:
- if you add a new tool, create `prompts/tools/<tool>.md` and make sure routing can recommend it
- if you want a richer file-context system, this is where to add it

---

## 7.6 `amex_ai_agent/reasoning_graph.py`

Purpose:
- orchestrate the loop from route → plan → tools → plan

### `GraphState`
State carried through execution.

Fields:
- `task`
- `iteration`
- `tool_feedback`
- `parsed`
- `routing`
- `final_answer`
- `last_tool_signature`
- `repeated_tool_call_count`
- `trace`

### `FraudReasoningGraph`
Main orchestration loop.

#### `__init__(...)`
Stores dependencies:
- config
- planner
- parser
- executor
- memory
- llm
- ui

#### `_tool_signature(parsed)`
Creates a JSON signature for tool calls so repeated identical calls can be detected.

#### `run(task)`
Main loop.

Behavior:
1. route the task
2. iterate up to `max_reasoning_loops`
3. plan current iteration
4. if `DONE`, finish
5. if no tools, finish
6. detect repeated identical tool calls
7. run tools
8. feed tool output back into next iteration

#### `_route(task)`
Builds routing prompt, invokes LLM, parses routing output, stores it in memory/UI.

#### `_reason(task, state)`
Builds plan prompt, invokes LLM, parses result, saves summary to memory, prints plan.

#### `_run_tools(parsed)`
Runs all requested tools using `ToolExecutor.execute(...)`.
Also:
- shows a live status banner
- stores tool runs in memory
- renders success outputs or errors
- returns the combined tool output string for the next iteration

Important simplifications in the current design:
- bounded loop count
- no separate graph engine dependency
- repeated-call guardrail

Extension advice:
- if you add sophisticated branching, this is where complexity will grow
- if you want route-specific loops or tool result post-processing, add it here carefully

---

## 8. UI layer

## 8.1 `amex_ai_agent/ui/chat_ui.py`

Purpose:
- render terminal panels and live statuses using Rich

### `LOGO`
ASCII art header.

### `LiveStatus`
Small wrapper around Rich `Status`.

#### `update(message)`
Replaces current live status text in place.

### `ChatUI`
Main presentation layer.

#### `__init__(agent_name, tools)`
Stores console, agent name, tool list, last message.

#### `render_header()`
Prints branding, mode, enabled tools.

#### `user_message(message)`
Renders user panel.

#### `agent_message(message)`
Renders assistant panel and stores latest agent message.

#### `tool_log(message)`
Renders tool output panel.

#### `info(message)`
Renders info panel.

#### `live_status(initial_message)`
Context manager that returns a `LiveStatus` object.
Used for in-place progress updates during tool execution.

#### `error(message)`
Renders error panel.

---

## 8.2 `amex_ai_agent/ui/spinner.py`

Purpose:
- lightweight Rich status context helper

### `thinking(console, text="Agent is thinking...")`
Context manager returning a Rich `Status`.

Current status:
- exists but is not the main mechanism used for tool progress now
- `chat_ui.live_status` is more central in the current flow

---

## 9. Tool execution layer

## 9.1 `amex_ai_agent/tools/base.py`

Purpose:
- shared tool execution context object

### `ToolExecutionContext`
Fields:
- `logger`
- `defaults`
- `progress_callback`
- `events`

#### `report_progress(message)`
Responsibilities:
- append message to in-memory event list
- log the message
- forward it to the UI progress callback if present

This is the key mechanism that lets tools surface live updates without hard-coding UI dependencies.

---

## 9.2 `amex_ai_agent/executor.py`

Purpose:
- tool registry and dispatcher

### `ToolResult`
Fields:
- `tool`
- `status`
- `output`

### `ToolExecutor`
Registry-backed tool runner.

#### `REGISTRY`
Current active tools:
- `data_prep`
- `model_score`
- `compute_metrics`

Important note:
- more tool files exist, but these are the only ones currently registered for normal execution

#### `ALIASES`
Current aliases:
- `metrics` -> `compute_metrics`
- `score_model` -> `model_score`

#### `__init__(config)`
Stores runtime config.

#### `list_tools()`
Returns sorted active tool names.

#### `resolve_tool_name(name)`
Applies alias mapping.

#### `execute(calls, progress_callback=None)`
Main execution function.

Behavior per tool call:
1. resolve alias
2. build `defaults` from config
3. create `ToolExecutionContext`
4. import the tool module dynamically
5. inspect whether the module's `run()` accepts `context`
6. call tool
7. JSON-render the output
8. return a list of `ToolResult`

Defaults currently propagated to tools:
- `project_id`
- `dataset_id`
- `folder_nm`
- `spark_python`

#### `validate_registry()`
Imports every registered tool module and returns status per tool.
Used by `/doctor` and startup preflight.

Extension advice:
- to add a new real tool, add it to `REGISTRY`
- if you want an alias, add it to `ALIASES`
- if your tool needs UI progress, accept `context` and call `context.report_progress(...)`

---

## 10. Tools

## 10.1 `amex_ai_agent/tools/data_prep.py`

Purpose:
- validate and launch model-specific data prep
- currently only `rnn` is implemented

Constants:
- `DEFAULT_SAMPLE_RATE = 0.025`
- `SUPPORTED_MODELS = {"rnn", "ensemble", "xgboost"}`
- `REQUIRED_FIELDS = ("start_dt", "end_dt", "model")`

### `_safe_json(argument)`
Returns a dict parsed from JSON or `{}` on failure.

### `_normalize_payload(payload, defaults)`
Normalizes aliases and applies defaults.

Resolves fields:
- `start_dt` / `start_date`
- `end_dt` / `end_date`
- `model` / `model_type`
- `sample_rate`
- `project_id`
- `dataset_id`
- `folder_nm` / `output_folder`

Also records which values came from defaults.

### `_missing_fields(params, defaults)`
Determines missing required fields.
Special behavior:
- `project_id` and `dataset_id` are only considered missing if absent both from input and startup defaults

### `_validate_dates(params)`
Basic string/date ordering validation.

### `run(argument, context=None)`
Main tool entrypoint.

Possible outputs:
- `needs_user_input`
- `invalid_input`
- `not_ready` (for xgboost/ensemble placeholders)
- result from `run_rnn_data_prep(...)`

Important output keys:
- `tool`
- `resolved_parameters`
- `defaults_applied`

This is a good template for future tools because it separates:
- JSON parsing
- normalization
- validation
- execution

---

## 10.2 `amex_ai_agent/tools/model_score.py`

Purpose:
- currently a validation/handoff tool, not a full scoring implementation

### `_safe_json(argument)`
Parse JSON.

### `_missing_fields(payload)`
Checks for missing fields:
- `model`
- `input_ref`
- `score_output_ref`

### `run(argument)`
Returns:
- `needs_user_input` if required fields are missing
- otherwise `ready` with validated parameter echo

Current status:
- no scoring code is executed
- this is a placeholder contract for future real model scoring integration

---

## 10.3 `amex_ai_agent/tools/metrics.py`

Purpose:
- currently a validation/handoff tool for metrics computation

Constants:
- `DEFAULT_METRICS = ["coverage", "hitrate", "accuracy", "gini", "ks"]`
- `REQUIRED_FIELDS = ["score_ref"]`

### `_safe_json(argument)`
Parse JSON.

### `_missing_fields(payload)`
Check for missing `score_ref`.

### `run(argument)`
Returns:
- `needs_user_input` if score_ref missing
- `ready` with normalized metrics/segments otherwise

Current status:
- no actual metrics pipeline is executed
- this is a structured interface stub

---

## 10.4 Existing but currently unregistered tools

These files exist and can be studied or reused, but they are **not currently active in the tool registry** unless you register them.

### `rca_analysis.py`
- validates `analysis_ref` and `objective`
- returns `needs_user_input` or `ready`
- acts like a contract placeholder

### `alerts.py`
- currently returns fixed dummy values
- likely placeholder/stub

### `case_review.py`
- currently returns a static example summary
- not a real execution tool yet

### `ppt_generator.py`
- actually creates a PowerPoint file `fraud_summary.pptx`
- can be made active if needed

### `sql_query.py`
- reads a SQL file, creates a small in-memory sqlite sample DB, executes query, returns rows
- mainly a local/demo-style utility

### `feature_rca.py`
- loads a CSV with pandas
- compares a feature between current and baseline month
- returns shift statistics
- potentially useful as a concrete local-analysis tool if re-registered

Extension advice:
- before registering any of these, decide whether they are production-ready or just placeholders
- if you activate them, also update prompts and maybe README/docs

---

## 11. Pipeline layer for RNN data prep

## 11.1 `amex_ai_agent/pipelines/rnn_data_prep/config.py`

Purpose:
- small config object for runtime parameters passed into the RNN runner

### `RNNDataPrepConfig`
Fields:
- `start_dt`
- `end_dt`
- `sample_rate`
- `project_id`
- `dataset_id`
- `folder_nm`

### `to_dict()`
Returns the dataclass as a plain dict.

---

## 11.2 `amex_ai_agent/pipelines/rnn_data_prep/runner.py`

Purpose:
- bridge from Sally's `data_prep` tool into the embedded RNN pipeline code

Constants:
- `REPO_ROOT`
- `SPARK_PYTHON_FALLBACK`

### `_report(context, message)`
Logs and forwards progress to `context.report_progress(...)` if available.

### `_build_config(params)`
Constructs `RNNDataPrepConfig` from normalized tool params.

### `_spark_python()`
Resolves Spark Python path from environment:
1. `RNN_SPARK_PYTHON`
2. `PYSPARK_PYTHON`
3. fallback constant

### `_apply_spark_env(env, spark_python)`
Sets all three Spark Python env vars in the provided env mapping.

### `_try_import_execution(cfg, context)`
Import-mode execution path.

Behavior:
- ensure embedded RNN repo path exists
- prepend paths to `sys.path`
- apply Spark env vars to current process
- import `run_pipeline` from `src.main`
- call `run_pipeline(...)`
- return structured result

Best when:
- pyspark and dependencies are available in the current Python env

### `_try_subprocess_execution(cfg, context)`
Fallback execution path.

Behavior:
- build child-process env
- set `START_DT`, `END_DT`, `SAMPLE_RATE`, `PROJECT_ID`, `DATASET_ID`, `FOLDER_NM`
- set Spark Python env vars
- run `python main.py`
- stream combined stdout/stderr line by line back through `_report`
- capture final output tail
- return structured `completed` or `failed`

Best when:
- import mode fails
- you want the existing pipeline to run in a separate interpreter context

### `run_rnn_data_prep(params, context=None)`
Top-level entrypoint.

Behavior:
1. build config
2. try import mode
3. if import mode unavailable, log concise info and fallback to subprocess
4. if both fail, return structured failure metadata

Important design point:
- import failure is not treated as fatal by itself
- subprocess is an expected fallback mode

---

## 12. Embedded RNN code

This folder is where the existing data-prep logic lives.
Sally wraps it; it does not reimplement the fraud feature engineering logic.

## 12.1 `amex_ai_agent/rnn_data_prep/src/main.py`

Purpose:
- orchestrate the RNN data-prep pipeline steps
- usable via import (`run_pipeline`) or as a script

### `_emit(message, progress_callback=None)`
Logs message, prints it, and forwards to progress callback.

### `_load_sql(name)`
Reads SQL template text from `sqlQ/`.

### `_spark_python()`
Resolves Python to use for Spark.

### `_build_spark_session()`
Creates a Spark session and explicitly sets:
- `spark.pyspark.python`
- `spark.pyspark.driver.python`

Also updates process env vars for consistency.

### `run_pipeline(...)`
Main pipeline orchestration function.

Inputs:
- `start_dt`
- `end_dt`
- `sample_rate`
- `project_id`
- `dataset_id`
- `folder_nm`
- `progress_callback`

Steps:
1. build Spark session
2. configure materialization dataset if provided
3. compute date offsets (`start_dt_10`, `start_dt_20`)
4. create init sample table from `init_sample.txt`
5. create exclusions table from `exclusions.txt`
6. create RNN sequence table from `rnn_seq.txt`
7. create vars pull table from `vars_pull.txt`
8. create Spark DataFrames from BigQuery tables
9. bucket features with `dimension_bucketing`
10. generate final sequence dataset with `rnn_data_seq_final`
11. return a structured result dict with message, final output path, and table list

Important detail:
- `rnn_data_seq_final(...)` already writes the final CSV under `.../data`
- `run_pipeline(...)` returns metadata; it does not need to write again

Script mode:
- if run directly, reads env vars and executes `run_pipeline(...)`

---

## 12.2 `amex_ai_agent/rnn_data_prep/utils/lumi_utils.py`

Purpose:
- BigQuery table utilities for the RNN pipeline

Global state:
- module logger
- `google.cloud.bigquery.Client()`

### `_ts()`
Returns a local timestamp string.

### `format_duration(seconds)`
Human-readable duration helper.

### `non_empty_table_exists(table_id)`
Checks whether a table exists and has rows.

### `_get_row_count(table_id, where_clause=None)`
Counts rows in a table.

### `_get_col_count(table_id)`
Counts columns using `INFORMATION_SCHEMA`.

### `create_table(query, table_id)`
Main BigQuery query-to-table helper.

Behavior:
- skip work if destination table already exists and is non-empty
- otherwise execute query into destination with `WRITE_TRUNCATE`
- poll job status
- log row and column counts after completion

### `delete_table(table_id)`
Deletes a table if it exists.

### `fetch_data(table_id, filter_condition, max_row_count=100_000, sort_column="date_time")`
Fetches filtered data from BigQuery into pandas.
If row count is too large, only returns the latest `max_row_count` rows.

Extension advice:
- if you need more table lifecycle helpers for future tools, add them here or in a shared BQ utility module

---

## 12.3 `amex_ai_agent/rnn_data_prep/utils/prep_utils.py`

Purpose:
- PySpark feature engineering and final RNN sequence assembly

This file contains the largest amount of domain-specific transformation logic.
Some mapping logic is intentionally preserved as internal logic.

### `create_df(spark, project_id, dataset_id, folder_nm, table_nm)`
Loads a BigQuery-backed Spark DataFrame using a generated `SELECT *` query.

Returns:
- DataFrame on success
- `None` on error (after logging)

### `dimension_bucketing(data)`
Applies many bucket-mapping UDFs and returns a reduced DataFrame containing:
- `cas_pkey`
- bucketed features
- `age_in_days`

Important note:
- this function depends on many internal mapping functions such as `aav_map`, `disruption_map`, etc.
- those mappings are part of the preserved internal business logic

### `plus_one(v)`
Pads a sequence to length 10 and returns a comma-delimited string.

### `plus_one_ngt(v)`
Pads/adjusts age+time sequences and returns a comma-delimited string.

### `rnn_data_seq_final(base, data, df_sample_cas_pkeys, BASE_PATH, spark=None)`
Builds and writes the final RNN-ready dataset.

High-level steps:
1. create temp views
2. join mapping/feature/sample tables
3. collect historical sequences with window functions
4. keep only current rows (`seq_hist = seq`)
5. convert variable-length histories into fixed-length strings via UDFs
6. expand each sequence into 10 numeric columns
7. write final CSV to `f"{BASE_PATH}/data"`
8. return `None`

Important contract:
- this function performs the write as a side effect
- callers should **not** expect a DataFrame back

Extension advice:
- if you change the RNN sequence schema, most of that work happens here
- keep the final write path contract stable if external consumers depend on it

---

## 13. SQL template files

Located in `amex_ai_agent/rnn_data_prep/sqlQ/`:

- `init_sample.txt`
- `exclusions.txt`
- `rnn_seq.txt`
- `vars_pull.txt`

Purpose:
- parameterized SQL templates used by the RNN pipeline

Typical placeholders include:
- `start_dt`
- `end_dt`
- `start_dt_10`
- `start_dt_20`
- table IDs from prior stages
- `sample_rate`

Extension advice:
- if you introduce XGBoost/Ensemble prep with similar staged SQL, consider creating analogous subfolders or model-specific SQL template groups

---

## 14. Prompt system

## 14.1 `amex_ai_agent/prompts/registry.py`

Purpose:
- load prompt files with fallback to inline templates

### `PROMPT_FILES`
Maps prompt names to markdown files.

### `FALLBACKS`
Inline string templates from `templates.py`.

### `get_prompt_template(name)`
Loads prompt from file if present; otherwise fallback string.

Why this matters:
- prompt files are editable without changing Python code
- fallback templates preserve runtime behavior if files are missing

---

## 14.2 `amex_ai_agent/prompts/templates.py`

Purpose:
- inline fallback prompt templates

Contains:
- `PROMPT_TEMPLATE`
- `ROUTING_TEMPLATE`
- `INTENT_TEMPLATE`
- `CONVERSATION_TEMPLATE`
- `EVALUATION_TEMPLATE`
- `REASONING_LOOP_TEMPLATE`

Current note:
- some fallback text still references more tools than are actively registered
- prompt files are the more authoritative active runtime contracts when present

---

## 14.3 Prompt markdown files

### `plan_prompt.md`
Primary planning/execution schema used during reasoning iterations.

### `routing_prompt.md`
Used to classify the task into:
- conversation
- evaluate
- execute

### `reasoning_loop_prompt.md`
Additional planning/orchestration instructions.

### `prompts/tools/*.md`
Tool-specific call guidance.

Existing tool guidance files:
- `data_prep.md`
- `model_score.md`
- `compute_metrics.md`
- `rca_analysis.md`

Extension advice:
- if you add a new tool, add one of these files too
- keep these short, explicit, and schema-oriented

---

## 15. Current capabilities vs placeholders

## 15.1 What is actually wired today

Most reliable current execution path:
- `data_prep` with `model=rnn`

Also wired in registry but mostly parameter-validation stubs:
- `model_score`
- `compute_metrics`

## 15.2 What exists but is not actively registered

- `rca_analysis`
- `alerts`
- `case_review`
- `ppt_generator`
- `sql_query`
- `feature_rca`

## 15.3 What is explicitly planned but not implemented yet

Inside `data_prep`:
- `xgboost`
- `ensemble`

Current behavior for those model names:
- accepted as recognized values
- returns `status="not_ready"`

---

## 16. How to add a new tool

This is the most practical section if you want to extend Sally.

### Step 1: create the tool module

Create a file like:

```python
# amex_ai_agent/tools/my_new_tool.py
from __future__ import annotations

from typing import Any, Dict
from amex_ai_agent.tools.base import ToolExecutionContext


def run(argument: str, context: ToolExecutionContext | None = None) -> Dict[str, Any]:
    context = context or ToolExecutionContext(logger=...)
    context.report_progress("My tool starting...")
    return {
        "tool": "my_new_tool",
        "status": "completed",
        "result": "...",
    }
```

Recommended output keys:
- `tool`
- `status`
- `message` or `result`
- `parameters` if applicable
- `defaults_applied` if defaults matter

### Step 2: register the tool

Edit `amex_ai_agent/executor.py`:
- add tool name to `REGISTRY`
- optionally add aliases to `ALIASES`

### Step 3: document the tool prompt contract

Add:
- `amex_ai_agent/prompts/tools/my_new_tool.md`

Keep it clear about:
- when to use the tool
- required parameters
- expected argument JSON shape
- any workflow hints

### Step 4: update prompt lists if needed

Check:
- `plan_prompt.md`
- `reasoning_loop_prompt.md`
- fallback prompt text in `templates.py`

### Step 5: add startup config only if the tool needs shared defaults

Examples of things that belong in startup/config:
- global project IDs
- dataset IDs
- cluster settings
- region
- warehouse path

If a value is tool-specific and rarely reused, keep it as a tool parameter instead.

### Step 6: add validation and structured states

Good patterns to follow:
- `needs_user_input`
- `invalid_input`
- `ready`
- `completed`
- `not_ready`
- `failed`

### Step 7: wire progress reporting

If the tool is long-running:
- accept `context`
- call `context.report_progress(...)`

This will automatically update the terminal live status.

---

## 17. How to add a new pipeline-backed tool

If the new tool should wrap an existing codebase, follow the RNN pattern.

Recommended structure:

```text
amex_ai_agent/
  pipelines/
    xgboost_data_prep/
      config.py
      runner.py
  xgboost_data_prep/
    src/
    utils/
    sqlQ/
```

Suggested steps:
1. create `pipelines/<tool>/config.py`
2. create `pipelines/<tool>/runner.py`
3. expose an importable `run_pipeline(...)` in the embedded codebase
4. make subprocess fallback available if import mode is fragile
5. report progress via `context.report_progress(...)`

This keeps Sally-specific wrapper code separate from the embedded domain code.

---

## 18. How to add XGBoost or Ensemble to `data_prep`

Current branching is inside `amex_ai_agent/tools/data_prep.py`.

To implement one of these:

1. add a new runner module, e.g.
   - `amex_ai_agent/pipelines/xgboost_data_prep/runner.py`
2. add or embed the actual pipeline code
3. update `data_prep.run(...)`:
   - keep shared normalization/validation
   - branch by `params["model"]`
   - call the correct runner
4. return the same structured output shape as RNN so the UI and memory remain consistent

Goal:
- same tool name
- model-specific execution underneath
- consistent output contract on top

---

## 19. How to modify prompts safely

Prompt changes should preserve parser compatibility.

Rules:
- keep outputs STRICT JSON ONLY
- do not add required fields unless parser is updated too
- keep tool calls in the same list-of-dicts style
- keep `next_action` restricted to `CONTINUE` / `DONE`

If you change prompt schema, update:
- prompt markdown
- parser expectations
- any downstream code using those fields

---

## 20. Known limitations and gotchas

### 20.1 Config parser is intentionally simple
- nested YAML is not supported
- complex structures should go elsewhere or require a richer parser later

### 20.2 Prompt/tool lists are not perfectly synchronized everywhere
- some fallback prompt templates still mention tools not currently active in `executor.py`
- the file-based prompts are the main current runtime contract

### 20.3 Several tools are placeholders
- `model_score` and `compute_metrics` are validation/handoff tools only today
- some unregistered tools return static or demo data

### 20.4 Embedded RNN logic is partly black-box domain code
- especially mapping functions in `prep_utils.py`
- treat that internal logic carefully unless you are deliberately changing feature engineering behavior

### 20.5 Memory is simple and local
- saved as JSON files
- no vector DB or semantic retrieval
- prompt memory is truncation-based, not ranking-based

### 20.6 Manual paste flow is the default LLM mode
- this is by design for restricted enterprise environments
- moving to API mode requires implementing `ApiGateway`

---

## 21. Recommended next improvements

If you want to evolve this repo, these are good next steps.

### High value engineering improvements
1. add real automated tests
2. align prompt file tool lists with actual registry
3. promote placeholder tools only when backed by real execution code
4. replace simple config parsing with a real config library if structure grows
5. add structured tool output schemas/types
6. add richer health checks for Spark/BigQuery/GCloud
7. separate demo tools from production tools explicitly
8. add typed interfaces for pipeline runners
9. add retry/backoff around brittle subprocess or BigQuery operations
10. add a documentation index linking this guide from the README

### Good next tooling improvements
1. add a common `BaseValidatedTool` pattern
2. add model-specific pipeline registries under `data_prep`
3. add standardized result fields like:
   - `status`
   - `tool`
   - `message`
   - `parameters`
   - `artifacts`
   - `metrics`
4. add structured error categories
5. add unit tests for parser, planner, executor, and startup flow

---

## 22. Short practical cheat sheet

### Start Sally

```bash
./sally run
```

### Initialize defaults only

```bash
./sally init
```

### Inspect current saved startup config

```bash
./sally doctor
```

### Key files to edit for common tasks

- Add startup defaults: `amex_ai_agent/startup.py`, `amex_ai_agent/config.py`
- Add a tool: `amex_ai_agent/tools/`, `amex_ai_agent/executor.py`, `amex_ai_agent/prompts/tools/`
- Change plan/routing behavior: `amex_ai_agent/planner.py`, `amex_ai_agent/parser.py`, `amex_ai_agent/reasoning_graph.py`, `amex_ai_agent/prompts/*.md`
- Change UI behavior: `amex_ai_agent/ui/chat_ui.py`
- Change RNN pipeline wrapper: `amex_ai_agent/pipelines/rnn_data_prep/runner.py`
- Change actual RNN prep logic: `amex_ai_agent/rnn_data_prep/src/main.py`, `utils/`, `sqlQ/`

### Minimum steps to add a new real tool

1. create `tools/<name>.py`
2. add to `executor.py`
3. add `prompts/tools/<name>.md`
4. update prompt tool lists if needed
5. return structured JSON-compatible dicts
6. use `context.report_progress(...)` for long-running work

---

## 23. Final mental summary

If you remember only one thing, remember this:

- **`chat.py`** runs the interactive shell
- **`reasoning_graph.py`** decides the loop
- **`planner.py` + `parser.py`** are the prompt/JSON contract pair
- **`executor.py`** is the tool registry and dispatcher
- **`tools/data_prep.py`** is the active heavy-duty tool entrypoint
- **`pipelines/rnn_data_prep/runner.py`** is the Sally wrapper around the RNN code
- **`rnn_data_prep/src/main.py` + `utils/*`** are the actual embedded pipeline internals
- **`startup.py` + `config.py`** make the environment repeatable
- **`logging_utils.py` + `chat_ui.py`** make the system observable and usable

That is the core of the whole repo.
