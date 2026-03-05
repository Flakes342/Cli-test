# AMEX AI Agent (Human-in-the-loop CLI)

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

## Notes
- This project is designed for restricted enterprise environments where LLM API access is unavailable.
- Use `/plan` to generate a structured prompt for ChatGPT Enterprise, then paste the model response back for parsing and local tool execution.
