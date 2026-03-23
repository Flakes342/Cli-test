from __future__ import annotations

import json
from pathlib import Path

from amex_ai_agent.config import AgentConfig
from amex_ai_agent.executor import ToolExecutor
from amex_ai_agent.parser import ToolCall
from amex_ai_agent.tools.base import ToolExecutionContext
from amex_ai_agent.tools.variable_lookup import run


CSV_TEXT = """Variable,Full Name,Description,Table,Domain,Model
var_auth_amt,Authorization Amount,Authorized amount in USD,feature_store,authorization,rnn
var_auth_rate,Authorization Rate,Rate of authorizations over time,feature_store,authorization,rnn
var_device_risk,Device Risk Score,Risk score for device fingerprint,model_features,risk,xgboost
"""


def _write_catalog(tmp_path: Path) -> Path:
    path = tmp_path / "variables.csv"
    path.write_text(CSV_TEXT, encoding="utf-8")
    return path


def test_variable_lookup_tool_returns_exact_match(tmp_path: Path) -> None:
    catalog_path = _write_catalog(tmp_path)
    context = ToolExecutionContext(logger=__import__("logging").getLogger("test"), defaults={"variable_catalog_path": str(catalog_path)})

    result = run(json.dumps({"code": "VAR_AUTH_AMT"}), context=context)

    assert result["status"] == "success"
    assert result["match_type"] == "exact"
    assert result["record"]["variable"] == "var_auth_amt"


def test_variable_lookup_tool_returns_ambiguous_fuzzy_results(tmp_path: Path) -> None:
    catalog_path = _write_catalog(tmp_path)
    context = ToolExecutionContext(logger=__import__("logging").getLogger("test"), defaults={"variable_catalog_path": str(catalog_path)})

    result = run(json.dumps({"query": "authorization", "model": "rnn", "limit": 5}), context=context)

    assert result["status"] == "ambiguous"
    assert result["match_type"] == "fuzzy"
    assert result["result_count"] == 2


def test_variable_lookup_tool_can_filter_without_search_text(tmp_path: Path) -> None:
    catalog_path = _write_catalog(tmp_path)
    context = ToolExecutionContext(logger=__import__("logging").getLogger("test"), defaults={"variable_catalog_path": str(catalog_path)})

    result = run(json.dumps({"domain": "risk"}), context=context)

    assert result["status"] == "success"
    assert result["match_type"] == "filtered_list"
    assert result["results"][0]["variable"] == "var_device_risk"


def test_executor_runs_variable_lookup_tool(tmp_path: Path) -> None:
    catalog_path = _write_catalog(tmp_path)
    config = AgentConfig(variable_catalog_path=str(catalog_path))
    executor = ToolExecutor(config)

    results = executor.execute([ToolCall(name="variable_lookup", argument=json.dumps({"code": "var_auth_amt"}))])

    assert len(results) == 1
    assert results[0].status == "success"
    payload = json.loads(results[0].output)
    assert payload["record"]["variable"] == "var_auth_amt"
